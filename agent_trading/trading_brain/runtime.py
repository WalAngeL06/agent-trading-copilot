"""Opt-in one-stream causal PAPER composition; replay and prefixes share process."""
from collections import Counter
from dataclasses import replace
from .models import (BrainConfig, BrainEvent, SwingHigh, SwingLow, ValidLow,
                     TradeCandidate)
from .structure import StructureEngine
from .range import RangeEngine
from .manipulation import ManipulationEngine
from .gaps import GapEngine
from .paper import RiskPolicy, PaperBroker
from ..market import bar_duration
from ..models import Candle
from ..swing import SwingEngine, SwingEventType, SwingSide, ConfirmedSwing

class TradingBrain:
    def __init__(self, symbol, timeframe, config=None):
        self.config = config if config is not None else BrainConfig()
        if not isinstance(self.config, BrainConfig):
            raise ValueError('config must be BrainConfig')
        self.swing = SwingEngine(symbol, timeframe, self.config.swing)
        self.symbol, self.timeframe = symbol, timeframe
        self.duration = bar_duration(timeframe)
        self.structure = StructureEngine(symbol, timeframe)
        self.range = RangeEngine(self.config.boundary_proximity)
        self.manipulation = ManipulationEngine()
        self.gaps = GapEngine()
        self.risk = RiskPolicy(self.config)
        self.broker = PaperBroker(self.risk, self.config.equity)
        self.as_of = None
        self.events = ()
        self._ids = {}
        self._range_id = self._sweep_id = self._reclaim_id = self._open_id = None
        self._candidate_emitted = False
        self._risk_id = None
        self.candle_count = 0

    def _emit(self, kind, payload, refs=(), sources=None):
        refs = tuple(dict.fromkeys(ref for ref in refs if ref is not None))
        event = BrainEvent(f'e{len(self.events)+1:06d}', kind, self.as_of, payload,
                           refs, tuple(sources if sources is not None else
                                       getattr(payload, 'source_ids', ())))
        self.events += (event,)
        self._ids[payload] = event.id
        return event.id

    def process(self, candle):
        # Fail closed BEFORE SwingEngine, broker or any other state mutation.
        if (not isinstance(candle, Candle) or candle.closed is not True
                or candle.symbol != self.symbol or candle.timeframe != self.timeframe):
            raise ValueError('expected closed Candle for this symbol/timeframe')
        if self.as_of is not None and candle.close_time != self.as_of + self.duration:
            raise ValueError('candles must be contiguous and strictly chronological')
        start = len(self.events)
        self.as_of = candle.close_time
        self.candle_count += 1
        # The pending signal is from a PRIOR closed candle; process its next open
        # and current-bar exits before publishing any current-bar signals.
        for change in self.broker.process(candle):
            candidate = getattr(change.payload, 'candidate', change.payload)
            refs = (self._ids[candidate], self._risk_id)
            if change.kind == 'PAPER_ORDER_CLOSED':
                refs += (self._open_id,)
            event_id = self._emit(change.kind, change.payload, refs,
                                  ('[H]-RISK-001', '[H]-PAPER-001'))
            if change.kind == 'PAPER_ORDER_OPENED':
                self._open_id = event_id
        swings = []
        for event in self.swing.process(candle):
            if event.event_type is SwingEventType.SWING_CONFIRMED:
                raw = ConfirmedSwing.from_event(event)
                swings.append(raw)
                level = SwingHigh(raw) if raw.side is SwingSide.HIGH else SwingLow(raw)
                raw_id = self._emit('SWING_HIGH' if raw.side is SwingSide.HIGH else 'SWING_LOW',
                                    level, sources=event.source_ids + ('[D-DD-MSB-001]',))
                self._ids[raw] = raw_id
        valid = self.structure.process(candle, swings)
        for level in valid:
            self._emit('VALID_LOW' if isinstance(level, ValidLow) else 'VALID_HIGH', level,
                       (self._ids[level.swing.raw], self._ids[level.target.raw]))
        for state in self.range.process(candle, valid, swings):
            kind = {'WAIT_LOW_TOUCH':'RANGE_CANDIDATE', 'WAIT_HIGH_TOUCH':'RANGE_LOW_TOUCH',
                    'RANGE_CONFIRMED':'RANGE_CONFIRMED',
                    'RANGE_INVALIDATED':'RANGE_INVALIDATED'}[state.phase]
            refs = [self._ids[state.low], self._ids[state.high], self._range_id]
            if state.low_touch is not None: refs.append(self._ids[state.low_touch.raw])
            if state.high_touch is not None: refs.append(self._ids[state.high_touch.raw])
            self._range_id = self._emit(kind, state, refs)
        for change in self.manipulation.process(candle, self.range.state):
            if change.phase == 'AMBIGUOUS':
                self._emit('MANIPULATION_AMBIGUOUS', change, (self._range_id,))
                self._sweep_id = self._reclaim_id = None
            elif change.phase == 'SWEPT':
                self._sweep_id = self._emit('SWEEP', change, (self._range_id,))
                self._reclaim_id = None
            else:
                self._reclaim_id = self._emit('RECLAIM', change, (self._range_id, self._sweep_id))
        for gap in self.gaps.process(candle):
            refs = ()
            if gap.kind == 'iFVG':
                origin = replace(gap, kind='FVG', origin_at=None,
                                 direction='SHORT' if gap.direction == 'LONG' else 'LONG',
                                 observed_at=gap.origin_at)
                refs = (self._ids[origin],)
            gap_id = self._emit(gap.kind, gap, refs)
            self._consider(candle, gap, gap_id)
        return self.events[start:]

    def _consider(self, candle, gap, gap_id):
        manipulation = self.manipulation.active
        state = self.range.state
        if (self._candidate_emitted or manipulation is None or state is None
                or manipulation.phase != 'RECLAIMED' or gap.direction != manipulation.direction
                or gap.observed_at <= manipulation.reclaimed_at):
            return
        if gap.kind == 'FVG' and gap.formed_from[0] < manipulation.swept_at:
            return
        if not state.range_low < candle.close < state.range_high:
            return
        stop = (manipulation.extreme - self.config.stop_buffer if gap.direction == 'LONG'
                else manipulation.extreme + self.config.stop_buffer)
        tp = (state.eq if self.config.target == 'EQ' else
              state.range_high if gap.direction == 'LONG' else state.range_low)
        refs = (self._range_id, self._reclaim_id, gap_id)
        candidate = TradeCandidate(gap.direction, candle.close, stop, tp, candle.close_time, refs)
        if not self.risk.geometry(candidate.direction, candidate.entry, candidate.stop, candidate.tp):
            self._emit('TRADE_REJECTED', candidate, refs, ('[H]-PLAN-001',))
            return
        quantity = self.risk.size(candidate.entry, candidate.stop, self.broker.equity)
        if quantity is None:
            self._emit('TRADE_REJECTED', candidate, refs, ('[H]-RISK-001',))
            return
        candidate = replace(candidate, planned_quantity=quantity,
                            risk_budget=self.broker.equity*self.config.risk_fraction)
        candidate_id = self._emit('TRADE_CANDIDATE', candidate, refs)
        self._risk_id = self._emit('RISK_APPROVED', candidate, (candidate_id,), ('[H]-RISK-001',))
        # Keep candidate identity mapped to its signal, not its risk observation.
        self._ids[candidate] = candidate_id
        self.broker.submit(candidate)
        self._candidate_emitted = True

    def bootstrap(self, candles):
        if self.as_of is not None:
            raise ValueError('bootstrap requires a fresh brain')
        for candle in candles:
            self.process(candle)
        return self.events

    def snapshot(self):
        return {'as_of': self.as_of, 'candle_count': self.candle_count,
                'raw_swings': self.swing.confirmed, 'valid_levels': self.structure.valid,
                'range': self.range.state, 'manipulation': self.manipulation.active,
                'pending_candidate': self.broker.pending, 'trades': self.broker.trades,
                'equity': self.broker.equity, 'events': self.events}

    def report(self):
        return {'schema_version':'trading-brain-paper-v0.1', 'mode':'PAPER',
                'symbol':self.symbol, 'timeframe':self.timeframe, 'as_of':self.as_of,
                'config':self.config, 'candle_count':self.candle_count,
                'counts':dict(sorted(Counter(e.kind for e in self.events).items())),
                'range':self.range.state,
                'range_levels': None if self.range.state is None else
                    {'low':self.range.state.range_low,'high':self.range.state.range_high,
                     'eq':self.range.state.eq},
                'trades':self.broker.trades,
                'pending_candidate':self.broker.pending, 'equity':self.broker.equity,
                'events':self.events,
                'limitations': ('PROVISIONAL_H_RULES', 'NOT_EMPIRICALLY_VALIDATED',
                                'SINGLE_STREAM_SINGLE_RANGE', 'NO_COSTS_OR_PRODUCTION_RISK')}


def replay(candles, config=None):
    iterator = iter(candles)
    first = next(iterator, None)
    if not isinstance(first, Candle):
        raise ValueError('replay requires at least one Candle')
    brain = TradingBrain(first.symbol, first.timeframe, config)
    brain.process(first)
    for candle in iterator: brain.process(candle)
    return brain
