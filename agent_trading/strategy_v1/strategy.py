"""Strategy V1: configurable bias / range / entry timeframe chain, LONG only.

Causality is structural: every engine consumes one closed candle at a time and
no stream can observe a bar that has not closed. Replay and incremental live
processing are the same code path.
"""
from collections import Counter

from ..market import bar_duration
from ..models import Candle
from ..swing import SwingEngine, SwingEventType, SwingSide, ConfirmedSwing
from ..trading_brain.gaps import GapEngine
from ..trading_brain.manipulation import ManipulationEngine
from ..trading_brain.models import SwingLow, TradeCandidate, ValidLow
from ..trading_brain.range import RangeEngine
from ..trading_brain.risk import RiskEngine
from ..trading_brain.risk_models import SupportingZone
from ..trading_brain.structure import StructureEngine
from .bias import BiasEngine
from .broker import PendingLimitPaperBroker
from .config import StrategyProfile
from .entry import FvgBook, entry_price, protecting_swing_low
from .models import CapitalPolicy, EntryPlan, StrategyEvent

PHASES = ('WAITING_FOR_BIAS', 'WAITING_FOR_RANGE', 'WAITING_FOR_MANIPULATION',
          'WAITING_FOR_FVG', 'PENDING_ENTRY', 'IN_POSITION', 'CLOSED')

RANGE_KINDS = {'WAIT_LOW_TOUCH': 'RANGE_CANDIDATE', 'WAIT_HIGH_TOUCH': 'RANGE_LOW_TOUCH',
               'RANGE_CONFIRMED': 'RANGE_CONFIRMED', 'RANGE_INVALIDATED': 'RANGE_INVALIDATED',
               'RANGE_RETIRED': 'RANGE_RETIRED'}


class StrategyV1:
    def __init__(self, symbol, profile=None):
        self.profile = profile if profile is not None else StrategyProfile()
        if not isinstance(self.profile, StrategyProfile):
            raise ValueError('profile must be StrategyProfile')
        roles = self.profile.timeframes
        self.symbol, self.roles = symbol, roles
        self.bias = BiasEngine(symbol, roles.bias, self.profile.swing)
        self.range_swing = SwingEngine(symbol, roles.range, self.profile.swing)
        self.range_structure = StructureEngine(symbol, roles.range)
        self.range = RangeEngine(self.profile.boundary_proximity,
                                 allow_reseek=self.profile.range_reseek_enabled,
                                 allow_retire=self.profile.range_retire_enabled)
        self.manipulation = ManipulationEngine()
        self.entry_swing = SwingEngine(symbol, roles.entry, self.profile.swing)
        self.gaps = GapEngine()
        self.book = FvgBook(self.profile.fvg_freshness_enabled)
        self.risk = RiskEngine(self.profile.risk_config())
        self.broker = PendingLimitPaperBroker(self.risk, self.profile.equity, self.profile)
        self.entry_swing_lows = ()
        self.entry_plan = None
        self.events = ()
        self.as_of = None
        self._last_rank = None
        self._stream_as_of = {}
        self._ids = {}
        self._range_id = self._sweep_id = self._reclaim_id = None
        self._setup_consumed = False
        self.counts = Counter()

    # ----------------------------------------------------------------- events
    def _emit(self, kind, timeframe, payload, refs=(), sources=None):
        refs = tuple(dict.fromkeys(r for r in refs if r is not None))
        event = StrategyEvent(f's{len(self.events)+1:06d}', kind, timeframe, self.as_of,
                              payload, refs,
                              tuple(sources if sources is not None
                                    else getattr(payload, 'source_ids', ())))
        self.events += (event,)
        self.counts[kind] += 1
        try:
            self._ids[payload] = event.id
        except TypeError:
            pass
        return event.id

    # -------------------------------------------------------------- causality
    def process(self, candle):
        if not isinstance(candle, Candle) or candle.closed is not True:
            raise ValueError('Strategy V1 requires closed candles')
        if candle.symbol != self.symbol:
            raise ValueError('candle does not belong to this strategy symbol')
        if candle.timeframe not in self.roles.ordered:
            raise ValueError('candle timeframe has no Strategy V1 role')
        rank = self.roles.rank(candle.timeframe)
        if self.as_of is not None:
            if candle.close_time < self.as_of:
                raise ValueError('strategy candles must be chronological across timeframes')
            if candle.close_time == self.as_of and rank < self._last_rank:
                raise ValueError('equal close times must resolve highest timeframe first')
        previous = self._stream_as_of.get(candle.timeframe)
        if previous is not None and candle.close_time != previous + bar_duration(candle.timeframe):
            raise ValueError('each timeframe stream must be contiguous')
        self._stream_as_of[candle.timeframe] = candle.close_time
        self.as_of, self._last_rank = candle.close_time, rank
        start = len(self.events)
        if candle.timeframe == self.roles.bias:
            self._bias(candle)
        elif candle.timeframe == self.roles.range:
            self._range(candle)
        else:
            self._entry(candle)
        return self.events[start:]

    def feed(self, candles):
        """Deterministic multi-stream replay order: time, then highest timeframe."""
        ordered = sorted(candles, key=lambda c: (c.close_time, self.roles.rank(c.timeframe)))
        for candle in ordered:
            self.process(candle)
        return self.events

    # ----------------------------------------------------------------- streams
    def _bias(self, candle):
        _raw, valid, breaks = self.bias.process(candle)
        for level in valid:
            kind = 'BIAS_VALID_LOW' if isinstance(level, ValidLow) else 'BIAS_VALID_HIGH'
            self.bias.register_level_id(level, self._emit(kind, candle.timeframe, level))
        for event in breaks:
            self._emit('BIAS_BREAK', candle.timeframe, event, (event.broken_level_id,))
            self._emit('BIAS_STATE', candle.timeframe, self.bias.snapshot())
            if event.new_bias == 'LONG_DISABLED':
                self._cancel_pending('LONG_PERMISSION_LOST_BEFORE_FILL', candle.timeframe)

    def _reset_setup(self, reason):
        """Free the setup slot so the next opportunity can be taken."""
        self._setup_consumed = False
        self.entry_plan = None
        if reason == 'RANGE_RESEEK':
            # The old range is gone, so its sweep and reclaim can no longer arm
            # a setup against whatever range replaces it.
            self.manipulation = ManipulationEngine()
            self._sweep_id = self._reclaim_id = None

    def _range(self, candle):
        before_reseeks = self.range.reseeks
        raw = []
        for event in self.range_swing.process(candle):
            if event.event_type is SwingEventType.SWING_CONFIRMED:
                raw.append(ConfirmedSwing.from_event(event))
        valid = self.range_structure.process(candle, raw)
        states = self.range.process(candle, valid, raw)
        if self.range.reseeks != before_reseeks:
            self._reset_setup('RANGE_RESEEK')
            self._emit('RANGE_RESEEK', candle.timeframe, 'PREVIOUS_CANDIDATE_INVALIDATED',
                       sources=('[U-RANGE-RESEEK-001]',))
        for state in states:
            self._range_id = self._emit(RANGE_KINDS[state.phase], candle.timeframe, state,
                                        (self._range_id,))
            if state.phase == 'RANGE_CONFIRMED':
                self._emit('CAPITAL_POLICY', candle.timeframe, self.capital_policy())
            if state.phase in ('RANGE_INVALIDATED', 'RANGE_RETIRED'):
                self._reset_setup('RANGE_RESEEK')
                self._cancel_pending(f'{state.phase}_BEFORE_FILL', candle.timeframe)
        for change in self.manipulation.process(candle, self.range.state):
            if change.phase == 'AMBIGUOUS':
                self._emit('MANIPULATION_AMBIGUOUS', candle.timeframe, change, (self._range_id,))
                self._sweep_id = self._reclaim_id = None
            elif change.phase == 'SWEPT':
                self._sweep_id = self._emit('SWEEP', candle.timeframe, change, (self._range_id,))
                self._reclaim_id = None
            else:
                self._reclaim_id = self._emit('MANIPULATION_CONFIRMED', candle.timeframe, change,
                                              (self._range_id, self._sweep_id))
                # Upside manipulation stays observable but never becomes a setup.
                if change.direction == 'LONG':
                    self._emit('CAPITAL_POLICY', candle.timeframe, self.capital_policy())

    def _entry(self, candle):
        for change in self.broker.process(candle, self.entry_swing_lows):
            self._emit(change.kind, candle.timeframe, change.payload)
        # [U-MULTI-SETUP-001] Once nothing is pending or open the setup slot is
        # free again. Bias, range and manipulation state are left untouched.
        if (self.profile.multi_setup_enabled and self._setup_consumed
                and self.broker.pending_plan is None
                and not any(t.status == 'OPEN' for t in self.broker.trades)):
            self._reset_setup('TRADE_SETTLED')
            self._emit('SETUP_SLOT_RELEASED', candle.timeframe, 'PREVIOUS_TRADE_SETTLED',
                       sources=('[U-MULTI-SETUP-001]',))
        self.book.process(candle)
        for event in self.entry_swing.process(candle):
            if event.event_type is SwingEventType.SWING_CONFIRMED:
                raw = ConfirmedSwing.from_event(event)
                if raw.side is SwingSide.LOW:
                    low = SwingLow(raw)
                    self.entry_swing_lows += (low,)
                    self._emit('ENTRY_SWING_LOW', candle.timeframe, low)
        for gap in self.gaps.process(candle):
            gap_id = self._emit(gap.kind, candle.timeframe, gap)
            self.book.publish(gap, gap_id)
            self._consider(candle, gap_id)

    def _cancel_pending(self, reason, timeframe):
        change = self.broker.cancel_pending(reason, self.as_of)
        if change is not None:
            self._emit(change.kind, timeframe, change.payload,
                       sources=('[U-STRATEGY-V1-001]', '[H]-SV1-ENTRY-001'))

    # ------------------------------------------------------------------- setup
    def long_setup_ready(self):
        state, manipulation = self.range.state, self.manipulation.active
        return (self.bias.long_permission and state is not None
                and state.phase == 'RANGE_CONFIRMED' and manipulation is not None
                and manipulation.direction == 'LONG' and manipulation.phase == 'RECLAIMED')

    def _consider(self, candle, gap_id):
        if self._setup_consumed or not self.long_setup_ready():
            return
        if (self.broker.pending_plan is not None
                or any(t.status == 'OPEN' for t in self.broker.trades)):
            return
        manipulation, state = self.manipulation.active, self.range.state
        eligible = self.book.eligible_long(self.profile, manipulation, candle.close_time)
        primary = next((g for g in eligible if g.gap_id == gap_id), None)
        if primary is None:
            return
        price = entry_price(primary.gap, self.profile.entry_level, self.profile.entry_level_ratio)
        target = state.range_high                 # terminal target is RangeHigh, never EQ
        secondary = self.book.secondary_below(self.profile, primary, manipulation,
                                              candle.close_time)
        protecting = zones = None
        stop_source = 'MANIPULATION_SWEEP_LOW'
        if secondary is not None:
            protecting = protecting_swing_low(self.entry_swing_lows, secondary.lower,
                                              candle.close_time)
            if protecting is not None:
                stop_source = 'SECONDARY_FVG_PROTECTING_SWING'
                zones = (SupportingZone(secondary.gap_id, secondary.gap.kind, 'LONG',
                                        secondary.lower, secondary.upper, protecting.price,
                                        secondary.observed_at, self.symbol, self.roles.entry,
                                        source_ids=secondary.gap.source_ids
                                        + ('[H]-SV1-STOP-001',)),)
        plan = EntryPlan(primary, self.profile.entry_level, price, target, stop_source,
                         secondary if stop_source != 'MANIPULATION_SWEEP_LOW' else None,
                         protecting, protecting.price if protecting is not None else None,
                         candle.close_time)
        structural = protecting.price if protecting is not None else manipulation.extreme
        refs = (self._range_id, self._reclaim_id, gap_id)
        candidate = TradeCandidate('LONG', price, structural, target, candle.close_time, refs,
                                   sweep_extreme=manipulation.extreme)
        candidate_id = self._emit('TRADE_CANDIDATE', candle.timeframe, candidate, refs)
        self._emit('ENTRY_PLAN', candle.timeframe, plan, (candidate_id, gap_id))
        decision = self.risk.evaluate(candidate, self.broker.equity, zones or (),
                                      symbol=self.symbol, timeframe=self.roles.entry)
        self._emit('RISK_APPROVED' if decision.plan is not None else 'BLOCKED',
                   candle.timeframe, decision, (candidate_id,))
        if decision.plan is None:
            return
        self.entry_plan = plan
        self.broker.submit(decision.plan, plan)
        self._setup_consumed = True
        self._emit('PENDING_ENTRY', candle.timeframe, plan, (candidate_id,))

    # ------------------------------------------------------------------ policy
    def capital_policy(self):
        """Idle while a confirmed range waits for manipulation. Performs no write."""
        state, manipulation = self.range.state, self.manipulation.active
        confirmed = state is not None and state.phase == 'RANGE_CONFIRMED'
        reclaimed = (manipulation is not None and manipulation.direction == 'LONG'
                     and manipulation.phase == 'RECLAIMED')
        if confirmed and not reclaimed:
            return CapitalPolicy(True, 'AUTO_EARN_ELIGIBLE',
                                 'RANGE_CONFIRMED_WAITING_FOR_MANIPULATION', self.as_of)
        if confirmed and reclaimed:
            return CapitalPolicy(False, 'RESERVED_FOR_ENTRY',
                                 'MANIPULATION_CONFIRMED_PREPARING_ENTRY', self.as_of)
        return CapitalPolicy(False, 'NOT_ELIGIBLE', 'NO_CONFIRMED_RANGE', self.as_of)

    def phase(self):
        if any(t.status == 'OPEN' for t in self.broker.trades):
            return 'IN_POSITION'
        if self.broker.pending_plan is not None:
            return 'PENDING_ENTRY'
        if not self.bias.long_permission:
            return 'WAITING_FOR_BIAS'
        state = self.range.state
        if state is None or state.phase != 'RANGE_CONFIRMED':
            return 'WAITING_FOR_RANGE'
        if not self.long_setup_ready():
            return 'WAITING_FOR_MANIPULATION'
        return 'CLOSED' if self.broker.trades else 'WAITING_FOR_FVG'

    def snapshot(self):
        state = self.range.state
        return {'as_of': self.as_of, 'phase': self.phase(), 'symbol': self.symbol,
                'timeframes': self.roles, 'direction': self.profile.direction,
                'bias': self.bias.snapshot(), 'range': state,
                'range_levels': None if state is None else
                    {'low': state.range_low, 'high': state.range_high, 'eq': state.eq},
                'manipulation': self.manipulation.active,
                'capital_policy': self.capital_policy(), 'entry_plan': self.entry_plan,
                'tracked_fvgs': self.book.tracked, 'pending_plan': self.broker.pending_plan,
                'trades': self.broker.trades, 'equity': self.broker.equity}

    def report(self):
        snapshot = self.snapshot()
        snapshot.update({'schema_version': 'strategy-v1-paper-v0.1', 'mode': 'PAPER',
                         'profile': self.profile,
                         'counts': dict(sorted(self.counts.items())), 'events': self.events,
                         'limitations': ('PROVISIONAL_H_RULES', 'NOT_BACKTESTED', 'LONG_ONLY',
                                         'SINGLE_RANGE_SINGLE_SETUP',
                                         'NO_COSTS_OR_PRODUCTION_RISK')})
        return snapshot
