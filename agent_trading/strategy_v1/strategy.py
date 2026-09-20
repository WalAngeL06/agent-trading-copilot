"""Strategy V1: configurable bias / range / entry timeframe chain, both ways.

Causality is structural: every engine consumes one closed candle at a time and
no stream can observe a bar that has not closed. Replay and incremental live
processing are the same code path.

[U-RANGE-GUIDE-002] The direction of a setup follows the guide's high
timeframe context (4.3 confluence, 4.4 premium/discount) in `context.py`. The
superseded bias-permission gate stays selectable as BIAS_LONG_PERMISSION, and
is the only mode that is long-only by construction.
"""
from collections import Counter

from ..market import bar_duration
from ..models import Candle
from ..swing import SwingEngine, SwingEventType, SwingSide, ConfirmedSwing
from ..trading_brain.gaps import GapEngine
from ..trading_brain.manipulation import ManipulationEngine
from ..trading_brain.models import SwingHigh, SwingLow, TradeCandidate, ValidLow
from ..trading_brain.range import RangeEngine
from ..trading_brain.risk import RiskEngine
from ..trading_brain.risk_models import SupportingZone
from ..trading_brain.structure import StructureEngine
from .bias import BiasEngine
from .broker import PendingLimitPaperBroker
from .config import StrategyProfile
from .context import HtfContext
from .entry import FvgBook, entry_price, protecting_swing
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
        # [U-RANGE-GUIDE-002] None means the superseded permission gate.
        self.context = (HtfContext(roles.bias, self.profile.effective_htf_zone_tolerance,
                                   self.profile.htf_confluence_required)
                        if self.profile.direction_gate == 'GUIDE_HTF_CONTEXT' else None)
        self.range_swing = SwingEngine(symbol, roles.range, self.profile.swing)
        self.range_structure = StructureEngine(symbol, roles.range)
        self.range = RangeEngine(self.profile.boundary_proximity,
                                 allow_reseek=self.profile.range_reseek_enabled,
                                 allow_retire=self.profile.range_retire_enabled,
                                 deviation_ratio=self.profile.range_deviation_ratio,
                                 require_eq_visit=self.profile.range_require_eq_visit)
        self.manipulation = ManipulationEngine()
        self.entry_swing = SwingEngine(symbol, roles.entry, self.profile.swing)
        self.gaps = GapEngine()
        self.book = FvgBook(self.profile.fvg_freshness_enabled)
        self.risk = RiskEngine(self.profile.risk_config())
        self.broker = PendingLimitPaperBroker(self.risk, self.profile.equity, self.profile)
        self.entry_swing_lows = self.entry_swing_highs = ()
        self.entry_plan = None
        self.events = ()
        self.as_of = None
        self._last_rank = None
        self._stream_as_of = {}
        self._ids = {}
        self._range_id = self._sweep_id = self._reclaim_id = None
        self.htf_verdict = None
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
        if self.context is not None:
            self.context.process(candle, valid)
        for level in valid:
            kind = 'BIAS_VALID_LOW' if isinstance(level, ValidLow) else 'BIAS_VALID_HIGH'
            self.bias.register_level_id(level, self._emit(kind, candle.timeframe, level))
        for event in breaks:
            self._emit('BIAS_BREAK', candle.timeframe, event, (event.broken_level_id,))
            self._emit('BIAS_STATE', candle.timeframe, self.bias.snapshot())
            # Only the superseded gate trades on that permission, so only it
            # has to drop a resting order when the permission disappears.
            if event.new_bias == 'LONG_DISABLED' and self.context is None:
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
            self.htf_verdict = None

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
                self.htf_verdict = None
            elif change.phase == 'SWEPT':
                self._sweep_id = self._emit('SWEEP', candle.timeframe, change, (self._range_id,))
                self._reclaim_id = None
                self.htf_verdict = None
            else:
                self._reclaim_id = self._emit('MANIPULATION_CONFIRMED', candle.timeframe, change,
                                              (self._range_id, self._sweep_id))
                # Guide 4.3/4.4 decide here whether this deviation is tradable.
                self.htf_verdict = self._htf_context(change)
                if self.htf_verdict is not None:
                    self._emit('HTF_CONTEXT', candle.timeframe, self.htf_verdict,
                               (self._range_id, self._reclaim_id))
                if self.setup_ready(change.direction):
                    self._emit('CAPITAL_POLICY', candle.timeframe, self.capital_policy())

    def _entry(self, candle):
        for change in self.broker.process(candle, self.entry_swing_lows,
                                          self.entry_swing_highs):
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
                else:
                    high = SwingHigh(raw)
                    self.entry_swing_highs += (high,)
                    self._emit('ENTRY_SWING_HIGH', candle.timeframe, high)
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
    def _htf_context(self, manipulation):
        """Guide 4.3/4.4 verdict for a confirmed manipulation, or None.

        The deviation is judged where it happened: the swept leg runs from the
        range boundary to the sweep extreme, and the extreme is the price the
        premium/discount rule reads.
        """
        if self.context is None or not self.profile.allows(manipulation.direction):
            return None
        state = self.range.state
        boundary = (state.range_low if manipulation.direction == 'LONG'
                    else state.range_high)
        extreme = manipulation.extreme
        return self.context.evaluate(
            manipulation.direction, extreme,
            span=(min(boundary, extreme), max(boundary, extreme)),
            structure_bearish=self.bias.state == 'LONG_DISABLED')

    def setup_ready(self, direction=None):
        """Is a setup armed in `direction`, or in any direction the profile allows?"""
        if direction is None:
            return any(self.setup_ready(side) for side in self.profile.directions)
        if not self.profile.allows(direction):
            return False
        state, manipulation = self.range.state, self.manipulation.active
        if (state is None or state.phase != 'RANGE_CONFIRMED' or manipulation is None
                or manipulation.direction != direction
                or manipulation.phase != 'RECLAIMED'):
            return False
        if self.context is None:
            # Superseded gate: only a bullish bias break ever opens a setup.
            return direction == 'LONG' and self.bias.long_permission
        return (self.htf_verdict is not None and self.htf_verdict.allowed
                and self.htf_verdict.direction == direction)

    def long_setup_ready(self):
        return self.setup_ready('LONG')

    def active_setup(self):
        """The direction of the armed setup, or None."""
        for direction in self.profile.directions:
            if self.setup_ready(direction):
                return direction
        return None

    def _consider(self, candle, gap_id):
        direction = self.active_setup()
        if self._setup_consumed or direction is None:
            return
        if (self.broker.pending_plan is not None
                or any(t.status == 'OPEN' for t in self.broker.trades)):
            return
        long_ = direction == 'LONG'
        manipulation, state = self.manipulation.active, self.range.state
        eligible = self.book.eligible(direction, self.profile, manipulation, candle.close_time)
        primary = next((g for g in eligible if g.gap_id == gap_id), None)
        if primary is None:
            return
        price = entry_price(primary.gap, self.profile.entry_level, self.profile.entry_level_ratio)
        # The terminal target is the opposite boundary, never EQ.
        target = state.range_high if long_ else state.range_low
        secondary = self.book.secondary_beyond(direction, self.profile, primary, manipulation,
                                               candle.close_time)
        protecting = zones = None
        sweep_source = 'MANIPULATION_SWEEP_LOW' if long_ else 'MANIPULATION_SWEEP_HIGH'
        stop_source = sweep_source
        if secondary is not None:
            protecting = protecting_swing(direction,
                                          self.entry_swing_lows if long_
                                          else self.entry_swing_highs,
                                          secondary.lower if long_ else secondary.upper,
                                          candle.close_time)
            if protecting is not None:
                stop_source = 'SECONDARY_FVG_PROTECTING_SWING'
                zones = (SupportingZone(secondary.gap_id, secondary.gap.kind, direction,
                                        secondary.lower, secondary.upper, protecting.price,
                                        secondary.observed_at, self.symbol, self.roles.entry,
                                        source_ids=secondary.gap.source_ids
                                        + ('[H]-SV1-STOP-001',)),)
        plan = EntryPlan(primary, self.profile.entry_level, price, target, stop_source,
                         secondary if stop_source != sweep_source else None,
                         protecting, protecting.price if protecting is not None else None,
                         candle.close_time)
        structural = protecting.price if protecting is not None else manipulation.extreme
        refs = (self._range_id, self._reclaim_id, gap_id)
        candidate = TradeCandidate(direction, price, structural, target, candle.close_time,
                                   refs, sweep_extreme=manipulation.extreme)
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
        state = self.range.state
        confirmed = state is not None and state.phase == 'RANGE_CONFIRMED'
        armed = self.active_setup() is not None
        if confirmed and not armed:
            return CapitalPolicy(True, 'AUTO_EARN_ELIGIBLE',
                                 'RANGE_CONFIRMED_WAITING_FOR_MANIPULATION', self.as_of)
        if confirmed and armed:
            return CapitalPolicy(False, 'RESERVED_FOR_ENTRY',
                                 'MANIPULATION_CONFIRMED_PREPARING_ENTRY', self.as_of)
        return CapitalPolicy(False, 'NOT_ELIGIBLE', 'NO_CONFIRMED_RANGE', self.as_of)

    def phase(self):
        if any(t.status == 'OPEN' for t in self.broker.trades):
            return 'IN_POSITION'
        if self.broker.pending_plan is not None:
            return 'PENDING_ENTRY'
        # Both gates start from the bias timeframe: the superseded one needs its
        # permission, the guide needs a dealing range to measure premium against.
        if (self.context.frame is None if self.context is not None
                else not self.bias.long_permission):
            return 'WAITING_FOR_BIAS'
        state = self.range.state
        if state is None or state.phase != 'RANGE_CONFIRMED':
            return 'WAITING_FOR_RANGE'
        if self.active_setup() is None:
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
                'direction_gate': self.profile.direction_gate,
                'htf_frame': None if self.context is None else self.context.frame,
                'htf_verdict': self.htf_verdict, 'setup_direction': self.active_setup(),
                'capital_policy': self.capital_policy(), 'entry_plan': self.entry_plan,
                'tracked_fvgs': self.book.tracked, 'pending_plan': self.broker.pending_plan,
                'trades': self.broker.trades, 'equity': self.broker.equity}

    def report(self):
        snapshot = self.snapshot()
        snapshot.update({'schema_version': 'strategy-v1-paper-v0.1', 'mode': 'PAPER',
                         'profile': self.profile,
                         'counts': dict(sorted(self.counts.items())), 'events': self.events,
                         'limitations': (('PROVISIONAL_H_RULES', 'NOT_BACKTESTED')
                                         + ((self.profile.direction,)
                                            if self.profile.direction != 'BOTH' else ())
                                         + ('SINGLE_RANGE_SINGLE_SETUP',
                                            'NO_COSTS_OR_PRODUCTION_RISK'))})
        return snapshot
