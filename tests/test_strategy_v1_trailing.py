"""Strategy V1 structural trailing and pending-entry cancellation.

Trailing uses confirmed structure the trade itself made, only after that trade's
own break-even, never puts the stop beyond the close it is set on, and can never
loosen a stop. Every default here is provisional [H]-SV1-TRAIL-001.
"""
import unittest
from dataclasses import replace
from decimal import Decimal

from agent_trading.market import bar_duration
from agent_trading.swing import ConfirmedSwing, SwingSide
from agent_trading.trading_brain.models import FVG, SwingHigh, SwingLow, TradeCandidate
from agent_trading.trading_brain.risk import RiskEngine
from agent_trading.trading_brain.risk_models import SupportingZone
from agent_trading.strategy_v1 import PendingLimitPaperBroker, StrategyProfile, StrategyV1
from agent_trading.strategy_v1.models import EntryPlan, TrackedFvg

from strategy_v1_fixtures import (D, SYMBOL, all_candles, bias_candles, candle,
                                  recovery_candles, scenario_profile)

STEP = bar_duration('15m')


def swing_low(price, swing_time, delay=STEP):
    raw = ConfirmedSwing(SYMBOL, '15m', SwingSide.LOW, D(str(price)), swing_time,
                         swing_time + delay, 1, D('1'), D('1'))
    return SwingLow(raw)


def swing_high(price, swing_time, delay=STEP):
    raw = ConfirmedSwing(SYMBOL, '15m', SwingSide.HIGH, D(str(price)), swing_time,
                         swing_time + delay, 1, D('1'), D('1'))
    return SwingHigh(raw)


def confirmed_low(price, now, bars_ago=2):
    """A swing low whose confirmation is already in the past at `now`."""
    return swing_low(price, now - bars_ago * STEP)


def _submit(profile, secondary=True, *, broker=None, at=None):
    """Submit a real RiskEngine-approved LONG plan and leave it resting.

    With `broker` and `at` the plan goes to an existing broker, the way the
    next trade of the same run does [U-MULTI-SETUP-001].
    """
    if broker is None:
        broker = PendingLimitPaperBroker(RiskEngine(profile.risk_config()), D('10000'),
                                         profile)
    risk = broker.risk
    start = at if at is not None else bias_candles()[0].close_time
    primary = TrackedFvg('p1', FVG('LONG', D('126'), D('130'), (start, start, start), start))
    second = TrackedFvg('s1', FVG('LONG', D('120'), D('122'), (start, start, start), start))
    zone = SupportingZone('s1', 'FVG', 'LONG', D('120'), D('122'), D('119'),
                          start, SYMBOL, '15m')
    candidate = TradeCandidate('LONG', D('128'), D('119'), D('140'), start, (),
                               sweep_extreme=D('112'))
    decision = risk.evaluate(candidate, D('10000'), (zone,), symbol=SYMBOL, timeframe='15m')
    assert decision.plan is not None, 'trailing fixture must be approvable'
    plan = EntryPlan(primary, 'FVG_EQ', D('128'), D('140'),
                     'SECONDARY_FVG_PROTECTING_SWING', second if secondary else None,
                     swing_low(119, start), D('119'), start)
    broker.submit(decision.plan, plan)
    return broker, start


def open_long(profile=None):
    """Submit and fill at the configured EQ entry of 128."""
    broker, start = _submit(profile or scenario_profile())
    broker.process(candle('15m', start + STEP, 129, 129.5, 128, 128.5))
    return broker, start + STEP


def open_short():
    """The long fixture reflected about 128: entry 128, stop 138, target 116."""
    profile = scenario_profile(direction='BOTH')
    risk = RiskEngine(profile.risk_config())
    broker = PendingLimitPaperBroker(risk, D('10000'), profile)
    start = bias_candles()[0].close_time
    primary = TrackedFvg('p1', FVG('SHORT', D('126'), D('130'), (start, start, start), start))
    candidate = TradeCandidate('SHORT', D('128'), D('137'), D('116'), start, (),
                               sweep_extreme=D('137'))
    decision = risk.evaluate(candidate, D('10000'), (), symbol=SYMBOL, timeframe='15m')
    assert decision.plan is not None, 'short trailing fixture must be approvable'
    plan = EntryPlan(primary, 'FVG_EQ', D('128'), D('116'), 'MANIPULATION_SWEEP_HIGH',
                     None, None, None, start)
    broker.submit(decision.plan, plan)
    broker.process(candle('15m', start + STEP, 127, 128, 126.5, 127.5))
    return broker, start + STEP


def protect(broker, moment):
    """One bar reaching 1R: the inherited break-even moves the stop to 128."""
    moment = moment + STEP
    return broker.process(candle('15m', moment, 128, 138.5, 127.5, 138)), moment


class TrailingTests(unittest.TestCase):
    def _protected(self, profile=None):
        broker, moment = open_long(profile)
        events, moment = protect(broker, moment)
        self.assertIn('BREAK_EVEN_PROTECTED', [e.kind for e in events])
        self.assertEqual(broker.trades[-1].stop, D('128'))
        return broker, moment

    def test_break_even_protection_is_announced_with_old_and_new_stop(self):
        broker, moment = open_long()
        events = broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        record = next(e.payload for e in events if e.kind == 'BREAK_EVEN_PROTECTED')
        self.assertEqual(record.old_stop, D('118'))
        self.assertEqual(record.new_stop, D('128'))
        self.assertEqual(record.structural_reference, 'BREAK_EVEN')
        self.assertEqual(record.confirmed_at, moment + STEP)
        self.assertIsNotNone(broker.break_even_at)

    def test_trailing_cannot_begin_before_break_even(self):
        broker, moment = open_long()
        events = broker.process(candle('15m', moment + STEP, 128.5, 129, 127, 128.5),
                                (confirmed_low(125, moment + STEP),))
        self.assertIsNone(broker.break_even_at)
        self.assertEqual([e.kind for e in events], [])
        self.assertEqual(broker.trades[-1].stop, D('118'))

    def test_trailing_cannot_use_an_unconfirmed_swing(self):
        broker, moment = self._protected()
        pending = swing_low(135, moment + STEP)          # confirms on a later bar
        self.assertGreater(pending.confirmed_at, moment + STEP)
        events = broker.process(candle('15m', moment + STEP, 138, 139, 136, 137), (pending,))
        self.assertEqual([e.kind for e in events], [])
        self.assertEqual(broker.trades[-1].stop, D('128'))

    def test_a_confirmed_higher_low_tightens_the_stop_after_break_even(self):
        broker, moment = self._protected()
        low = confirmed_low(131, moment + STEP)
        events = broker.process(candle('15m', moment + STEP, 138, 139, 136, 137), (low,))
        record = next(e.payload for e in events if e.kind == 'TRAILING_STOP_UPDATED')
        self.assertEqual(record.old_stop, D('128'))
        self.assertEqual(record.new_stop, D('130'))       # 131 - trailing buffer 1
        self.assertEqual(record.structural_reference, 'CONFIRMED_HIGHER_LOW')
        self.assertEqual(record.reference_price, D('131'))
        self.assertEqual(record.confirmed_at, low.confirmed_at)
        self.assertEqual(broker.trades[-1].stop, D('130'))
        self.assertEqual(broker.trades[-1].stop_updates[-1].reason, 'STRUCTURAL_TRAIL')

    def test_a_lower_or_equal_structure_never_changes_the_stop(self):
        broker, moment = self._protected()
        for price in (126, 128, 129):          # 129 - 1 equals the current stop
            moment = moment + STEP
            events = broker.process(candle('15m', moment, 138, 139, 136, 137),
                                    (confirmed_low(price, moment),))
            self.assertEqual([e.kind for e in events], [])
            self.assertEqual(broker.trades[-1].stop, D('128'))

    def test_the_stop_never_drops_below_entry_after_break_even(self):
        broker, moment = self._protected()
        trade = broker.trades[-1]
        self.assertEqual(trade.stop, trade.entry)
        loosened = broker.risk.tighten_stop(trade, D('120'), moment + STEP, 'ATTEMPT')
        self.assertEqual(loosened.stop, D('128'))
        self.assertEqual(loosened.stop_updates, trade.stop_updates)
        broker.process(candle('15m', moment + STEP, 138, 139, 136, 137),
                       (confirmed_low(121, moment + STEP),))
        self.assertGreaterEqual(broker.trades[-1].stop, broker.trades[-1].entry)

    def test_multiple_higher_lows_progressively_tighten_the_stop(self):
        broker, moment = self._protected()
        progression, lows = [broker.trades[-1].stop], []
        for price, bar in ((131, 1), (134, 2), (136, 3)):
            lows.append(confirmed_low(price, moment + bar * STEP))
            broker.process(candle('15m', moment + bar * STEP, 138, 139, 137, 138.5),
                           tuple(lows))
            progression.append(broker.trades[-1].stop)
        self.assertEqual(progression, [D('128'), D('130'), D('133'), D('135')])
        self.assertEqual(progression, sorted(progression))
        self.assertEqual(len(broker.trailing_updates), 3)

    def test_the_range_high_target_never_moves_while_trailing(self):
        broker, moment = self._protected()
        targets = [broker.trades[-1].tp]
        for price, bar in ((131, 1), (134, 2)):
            broker.process(candle('15m', moment + bar * STEP, 138, 139, 137, 138.5),
                           (confirmed_low(price, moment + bar * STEP),))
            targets.append(broker.trades[-1].tp)
        self.assertEqual(targets, [D('140'), D('140'), D('140')])
        self.assertEqual(broker.trades[-1].approved_plan.tp, D('140'))

    def test_the_trailing_sequence_is_deterministic(self):
        def run():
            broker, moment = self._protected()
            stops, lows = [], []
            for price, bar in ((131, 1), (134, 2), (136, 3)):
                lows.append(confirmed_low(price, moment + bar * STEP))
                broker.process(candle('15m', moment + bar * STEP, 138, 139, 137, 138.5),
                               tuple(lows))
                stops.append(broker.trades[-1].stop)
            return stops, [(r.old_stop, r.new_stop, r.reference_price)
                           for r in broker.trailing_updates]
        self.assertEqual(run(), run())

    def test_trailing_can_be_disabled_by_configuration(self):
        broker, moment = self._protected(scenario_profile(trailing_enabled=False))
        broker.process(candle('15m', moment + STEP, 138, 139, 136, 137),
                       (confirmed_low(131, moment + STEP),))
        self.assertEqual(broker.trades[-1].stop, D('128'))
        self.assertEqual(broker.trailing_updates, ())

    def test_the_trailing_buffer_is_configurable_and_defaults_to_the_stop_buffer(self):
        self.assertIsNone(scenario_profile().trailing_buffer)
        self.assertEqual(scenario_profile().effective_trailing_buffer, D('1'))
        profile = scenario_profile(trailing_buffer=D('3'))
        self.assertEqual(profile.effective_trailing_buffer, D('3'))
        broker, moment = self._protected(profile)
        broker.process(candle('15m', moment + STEP, 138, 139, 136, 137),
                       (confirmed_low(134, moment + STEP),))
        self.assertEqual(broker.trades[-1].stop, D('131'))        # 134 - 3

    def test_trailing_moves_a_long_stop_only_upward(self):
        broker, moment = self._protected()
        broker.process(candle('15m', moment + STEP, 138, 139, 137, 138.5),
                       (confirmed_low(131, moment + STEP),))
        self.assertEqual(broker.trades[-1].direction, 'LONG')
        for record in broker.trailing_updates:
            self.assertGreater(record.new_stop, record.old_stop)
        self.assertEqual(StrategyProfile().trailing_mode, 'CONFIRMED_HIGHER_LOW')

    def test_an_unknown_trailing_mode_or_buffer_is_rejected(self):
        with self.assertRaises(ValueError):
            StrategyProfile(trailing_mode='ATR')
        with self.assertRaises(ValueError):
            StrategyProfile(trailing_buffer=D('0'))

    def test_a_trailed_stop_can_close_the_trade(self):
        broker, moment = self._protected()
        broker.process(candle('15m', moment + STEP, 138, 139, 136, 137),
                       (confirmed_low(131, moment + STEP),))
        self.assertEqual(broker.trades[-1].stop, D('130'))
        broker.process(candle('15m', moment + 2 * STEP, 137, 137, 129, 129.5))
        closed = broker.trades[-1]
        self.assertEqual(closed.status, 'CLOSED')
        self.assertEqual(closed.exit_price, D('130'))
        self.assertGreater(closed.pnl, 0)                 # exited above entry


class PerTradeStateTests(unittest.TestCase):
    """[U-MULTI-SETUP-001] The next trade on the same broker starts clean.

    Break-even and the recovery chain belong to one trade; a later trade that
    inherited them would trail from its first bar.
    """

    def _second_trade(self):
        """Trade 1 reaches break-even and is stopped there; trade 2 fills at 128."""
        broker, moment = open_long()
        _events, moment = protect(broker, moment)
        self.assertIsNotNone(broker.break_even_at)
        moment = moment + STEP
        broker.process(candle('15m', moment, 137, 137, 127, 127.5))     # stopped at 128
        self.assertEqual(broker.trades[-1].status, 'CLOSED')
        _submit(scenario_profile(), broker=broker, at=moment)
        moment = moment + STEP
        broker.process(candle('15m', moment, 129, 129.5, 128, 128.5))
        self.assertEqual(len(broker.trades), 2)
        self.assertEqual(broker.trades[-1].status, 'OPEN')
        return broker, moment

    def test_a_second_trade_does_not_inherit_break_even(self):
        broker, moment = self._second_trade()
        self.assertIsNone(broker.break_even_at)
        # Trade 2's own higher low, confirmed on the next bar; it may only be
        # trailed to once trade 2 itself reaches break-even.
        broker.process(candle('15m', moment + STEP, 131.2, 132, 131, 131.5))
        low = swing_low(131, moment + STEP)
        events = broker.process(candle('15m', moment + 2 * STEP, 131.5, 133, 131.2, 132.5),
                                (low,))
        self.assertEqual([e.kind for e in events], [])
        self.assertEqual(broker.trades[-1].stop, D('118'))

    def test_the_second_trade_announces_its_own_break_even(self):
        broker, moment = self._second_trade()
        events, _moment = protect(broker, moment)
        record = next((e.payload for e in events if e.kind == 'BREAK_EVEN_PROTECTED'), None)
        self.assertIsNotNone(record)
        self.assertEqual((record.old_stop, record.new_stop), (D('118'), D('128')))
        self.assertIsNotNone(broker.break_even_at)

    def test_a_new_submission_clears_the_recovery_chain(self):
        broker, moment = open_long()
        moment = moment + STEP
        broker.process(candle('15m', moment, 128, 128.5, 124, 125))   # closes below PRIMARY
        self.assertIsNotNone(broker.primary_failed_at)
        moment = moment + STEP
        broker.process(candle('15m', moment, 125, 125, 117, 117.5))   # stopped at 118
        self.assertEqual(broker.trades[-1].status, 'CLOSED')
        _submit(scenario_profile(), broker=broker, at=moment)
        self.assertEqual((broker.primary_failed_at, broker.secondary_reacted_at,
                          broker.recovery_at), (None, None, None))


class TrailingStructureTests(unittest.TestCase):
    """Trailing follows the trade's own structure and stays on the market side.

    Found in the 30-pair sweep: every trailing update referenced a swing
    confirmed before the fill, often far beyond price, so the next bar's open
    closed the trade (AVAX-USDT: a long at 9.17 had its stop moved to 34.98).
    """

    def _protected_long(self):
        broker, moment = open_long()
        _events, moment = protect(broker, moment)
        self.assertEqual(broker.trades[-1].stop, D('128'))
        return broker, moment

    def _protected_short(self):
        broker, moment = open_short()
        self.assertEqual(broker.trades[-1].stop, D('138'))
        moment = moment + STEP
        broker.process(candle('15m', moment, 128, 128.5, 117.5, 118))      # 1R: break-even
        self.assertEqual(broker.trades[-1].stop, D('128'))
        return broker, moment

    def test_a_long_never_trails_to_structure_formed_before_the_fill(self):
        broker, moment = self._protected_long()
        older = swing_low(131, broker.trades[-1].filled_at - 3 * STEP)   # below the close
        events = broker.process(candle('15m', moment + STEP, 138, 139, 136, 137), (older,))
        self.assertEqual([e.kind for e in events], [])
        self.assertEqual(broker.trades[-1].stop, D('128'))

    def test_a_short_never_trails_to_structure_formed_before_the_fill(self):
        broker, moment = self._protected_short()
        older = swing_high(125, broker.trades[-1].filled_at - 3 * STEP)  # above the close
        events = broker.process(candle('15m', moment + STEP, 118, 120, 117, 119), (), (older,))
        self.assertEqual([e.kind for e in events], [])
        self.assertEqual(broker.trades[-1].stop, D('128'))

    def test_the_reported_case_a_swing_far_beyond_price_is_ignored(self):
        broker, moment = self._protected_long()
        ancient = swing_low(400, broker.trades[-1].filled_at - 40 * STEP)
        events = broker.process(candle('15m', moment + STEP, 138, 139, 136, 137), (ancient,))
        self.assertEqual([e.kind for e in events], [])
        self.assertEqual(broker.trades[-1].stop, D('128'))

    def test_a_long_stop_is_never_placed_above_the_close(self):
        broker, moment = self._protected_long()
        own = swing_low(137, moment)                  # 137 - 1 = 136, above the 135 close
        events = broker.process(candle('15m', moment + STEP, 138, 138.5, 134.5, 135), (own,))
        self.assertEqual([e.kind for e in events], [])
        self.assertEqual(broker.trades[-1].stop, D('128'))

    def test_a_short_stop_is_never_placed_below_the_close(self):
        broker, moment = self._protected_short()
        own = swing_high(119, moment)                 # 119 + 1 = 120, below the 121 close
        events = broker.process(candle('15m', moment + STEP, 118, 121.5, 117.5, 121), (), (own,))
        self.assertEqual([e.kind for e in events], [])
        self.assertEqual(broker.trades[-1].stop, D('128'))

    def test_a_stop_beyond_the_close_gives_way_to_the_next_valid_structure(self):
        broker, moment = self._protected_long()
        lows = (swing_low(131, moment - STEP), swing_low(137, moment))
        broker.process(candle('15m', moment + STEP, 138, 138.5, 134.5, 135), lows)
        self.assertEqual(broker.trades[-1].stop, D('130'))


class PendingCancellationTests(unittest.TestCase):
    def test_a_pending_entry_expires_with_an_auditable_reason(self):
        broker, start = _submit(scenario_profile(pending_expiry_bars=1))
        self.assertIsNotNone(broker.pending_plan)
        first = broker.process(candle('15m', start + STEP, 135, 136, 131, 134))
        self.assertEqual([e.kind for e in first], [])
        self.assertIsNotNone(broker.pending_plan)
        second = broker.process(candle('15m', start + 2 * STEP, 134, 136, 131, 135))
        self.assertEqual([e.kind for e in second], ['PAPER_ORDER_CANCELLED'])
        self.assertEqual(second[0].payload, 'PENDING_ENTRY_EXPIRED')
        self.assertIsNone(broker.pending_plan)

    def test_no_trade_opens_from_an_expired_pending_order(self):
        broker, start = _submit(scenario_profile(pending_expiry_bars=1))
        broker.process(candle('15m', start + STEP, 135, 136, 131, 134))
        broker.process(candle('15m', start + 2 * STEP, 134, 136, 131, 135))
        self.assertIsNone(broker.pending_plan)
        # Price now trades straight back through the old entry level.
        broker.process(candle('15m', start + 3 * STEP, 135, 135, 126, 127))
        broker.process(candle('15m', start + 4 * STEP, 127, 133, 127, 132))
        self.assertEqual(broker.trades, ())

    def test_losing_long_permission_cancels_a_resting_order(self):
        strategy, cancelled = _pending_then_bias_break()
        self.assertEqual(cancelled.payload, 'LONG_PERMISSION_LOST_BEFORE_FILL')
        self.assertIsNone(strategy.broker.pending_plan)
        self.assertEqual(strategy.broker.trades, ())
        self.assertFalse(strategy.bias.long_permission)

    def test_no_trade_opens_after_a_thesis_cancellation(self):
        # The tail drives price straight through the cancelled 126 entry level.
        strategy, cancelled = _pending_then_bias_break(revisit_entry=True)
        self.assertEqual(cancelled.payload, 'LONG_PERMISSION_LOST_BEFORE_FILL')
        self.assertEqual(strategy.broker.trades, ())
        self.assertIsNone(strategy.broker.pending_plan)
        self.assertGreater(strategy.as_of, cancelled.observed_at)
        self.assertEqual([e.kind for e in strategy.events
                          if e.kind == 'PAPER_ORDER_OPENED'], [])

    def test_cancel_pending_drops_the_order_and_is_idempotent(self):
        broker, start = _submit(scenario_profile())
        event = broker.cancel_pending('RANGE_INVALIDATED_BEFORE_FILL', start)
        self.assertEqual(event.kind, 'PAPER_ORDER_CANCELLED')
        self.assertEqual(event.payload, 'RANGE_INVALIDATED_BEFORE_FILL')
        self.assertIsNone(broker.pending_plan)
        self.assertIsNone(broker.cancel_pending('AGAIN', start))
        broker.process(candle('15m', start + STEP, 129, 129.5, 126, 127))
        self.assertEqual(broker.trades, ())

    def test_a_confirmed_range_is_terminal_so_its_cancel_path_cannot_fire(self):
        # Documents a reachability boundary rather than asserting dead behaviour:
        # entry needs RANGE_CONFIRMED, and the shipped RangeEngine never
        # re-evaluates a confirmed range, so RANGE_INVALIDATED_BEFORE_FILL is
        # wired defensively but cannot currently occur in production.
        strategy = StrategyV1(SYMBOL, scenario_profile(entry_level='FVG_LOW'))
        strategy.feed(all_candles())
        self.assertIsNotNone(strategy.broker.pending_plan)
        self.assertEqual(strategy.range.state.phase, 'RANGE_CONFIRMED')
        moment = strategy._stream_as_of['1H'] + bar_duration('1H')
        low = strategy.range.state.range_low
        emitted = strategy.process(candle('1H', moment, low + 1, low + 2, low - 50, low + 1))
        self.assertNotIn('RANGE_INVALIDATED', [e.kind for e in emitted])
        self.assertIsNotNone(strategy.broker.pending_plan)

    def test_a_stop_breaching_candle_fills_and_stops_instead_of_cancelling(self):
        """A LONG stop sits below the entry, so a candle reaching the stop must
        have traded the limit first. Cancelling would assume intrabar ordering in
        the trade's favour, so the fill wins and the bar stops the position."""
        broker, start = _submit(scenario_profile())
        events = broker.process(candle('15m', start + STEP, 129, 129.5, 117, 118.5))
        self.assertEqual([e.kind for e in events],
                         ['RISK_APPROVED', 'PAPER_ORDER_OPENED', 'PAPER_ORDER_CLOSED'])
        self.assertEqual(broker.trades[-1].status, 'CLOSED')
        self.assertEqual(broker.trades[-1].exit_price, D('118'))
        self.assertIsNone(broker.pending_plan)


def _pending_then_bias_break(revisit_entry=False):
    """Drive the real strategy to a resting order, then lose long permission.

    The bias stream lags the entry stream, so the extra bias bars go into the
    same feed and are interleaved by close time rather than back-filled. With
    `revisit_entry` the entry stream continues past the break and trades back
    through the cancelled level, proving the stale order cannot fill.
    """
    bias_step = bar_duration('4H')
    candles = list(all_candles())
    last_bias = max(c.close_time for c in candles if c.timeframe == '4H')
    entry_end = max(c.close_time for c in candles if c.timeframe == '15m')
    moment, extra = last_bias + bias_step, []
    while moment <= entry_end:
        # Neutral bars: they advance the stream without breaking any structure.
        extra.append(candle('4H', moment, 132, 133, 131, 132))
        moment = moment + bias_step
    kill_at = moment
    # Far below any Valid Low on this synthetic grid, so the break is unambiguous.
    extra.append(candle('4H', kill_at, 131, 131, 45, 50))
    if revisit_entry:
        entry_at = entry_end + STEP
        while entry_at <= kill_at:            # stay above the 126 entry until then
            extra.append(candle('15m', entry_at, 131, 131.5, 130.5, 131))
            entry_at = entry_at + STEP
        extra.append(candle('15m', entry_at, 131, 131, 120, 121))
        extra.append(candle('15m', entry_at + STEP, 121, 131, 121, 130))
    strategy = StrategyV1(SYMBOL, scenario_profile(entry_level='FVG_LOW'))
    strategy.feed(candles + extra)
    cancelled = next(e for e in strategy.events if e.kind == 'PAPER_ORDER_CANCELLED')
    return strategy, cancelled


class RecoveryFullChainTests(unittest.TestCase):
    """The recovery chain through the production classes, not the broker alone.

    PRIMARY fails -> SECONDARY holds -> price recovers to entry -> break-even ->
    a later confirmed higher low trails the stop.
    """

    @classmethod
    def setUpClass(cls):
        cls.strategy = StrategyV1(SYMBOL, scenario_profile())
        cls.strategy.feed(recovery_candles())

    def _first(self, kind):
        return next((e for e in self.strategy.events if e.kind == kind), None)

    def test_the_trade_opens_at_the_configured_entry(self):
        opened = self._first('PAPER_ORDER_OPENED')
        self.assertIsNotNone(opened)
        self.assertEqual(opened.payload.entry, D('128'))
        self.assertEqual(opened.payload.stop, D('118'))
        self.assertEqual(opened.payload.tp, D('140'))

    def test_primary_failure_and_secondary_hold_are_recorded_in_order(self):
        broker = self.strategy.broker
        self.assertIsNotNone(broker.primary_failed_at)
        self.assertIsNotNone(broker.secondary_reacted_at)
        self.assertLess(broker.primary_failed_at, broker.secondary_reacted_at)
        self.assertEqual(broker.trades[-1].status, 'OPEN')

    def test_recovery_to_entry_produces_break_even_protection(self):
        broker = self.strategy.broker
        protected = self._first('BREAK_EVEN_PROTECTED')
        self.assertIsNotNone(protected)
        self.assertEqual(protected.payload.new_stop, D('128'))
        self.assertEqual(protected.payload.structural_reference, 'RECOVERY_BREAK_EVEN')
        self.assertEqual(broker.recovery_at, broker.break_even_at)
        self.assertGreater(broker.recovery_at, broker.secondary_reacted_at)

    def test_a_later_confirmed_higher_low_trails_the_stop(self):
        trailed = self._first('TRAILING_STOP_UPDATED')
        self.assertIsNotNone(trailed)
        self.assertEqual(trailed.payload.old_stop, D('128'))
        self.assertEqual(trailed.payload.new_stop, D('128.5'))
        self.assertEqual(trailed.payload.reference_price, D('129.5'))
        self.assertEqual(trailed.payload.structural_reference, 'CONFIRMED_HIGHER_LOW')
        self.assertGreater(trailed.observed_at, self._first('BREAK_EVEN_PROTECTED').observed_at)

    def test_the_stop_sequence_only_tightens_and_the_target_never_moves(self):
        trade = self.strategy.broker.trades[-1]
        stops = [D('118')] + [u.new_stop for u in trade.stop_updates]
        self.assertEqual(stops, sorted(stops))
        self.assertEqual(stops, [D('118'), D('128'), D('128.5')])
        self.assertEqual(trade.tp, D('140'))
        self.assertEqual(trade.approved_plan.tp, D('140'))

    def test_the_recovery_chain_stays_long_only_and_deterministic(self):
        again = StrategyV1(SYMBOL, scenario_profile())
        again.feed(recovery_candles())
        self.assertEqual([(e.id, e.kind, e.observed_at) for e in self.strategy.events],
                         [(e.id, e.kind, e.observed_at) for e in again.events])
        for trade in self.strategy.broker.trades:
            self.assertEqual(trade.direction, 'LONG')


if __name__ == '__main__':
    unittest.main()
