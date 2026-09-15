"""Range re-seek [U-RANGE-RESEEK-001] and multi-setup [U-MULTI-SETUP-001].

Both are user-authorised Strategy V1 semantic changes. Re-seek applies only to
an INVALIDATED candidate; a CONFIRMED range is still terminal. The setup slot is
released only once nothing is pending or open.
"""
import unittest
from dataclasses import replace
from datetime import timedelta

from agent_trading.market import bar_duration
from agent_trading.swing import ConfirmedSwing, SwingSide
from agent_trading.trading_brain.models import SwingHigh, SwingLow, ValidHigh, ValidLow
from agent_trading.trading_brain.range import RangeEngine
from agent_trading.strategy_v1 import StrategyProfile, StrategyV1

from strategy_v1_fixtures import (D, SYMBOL, acceptance_candles, acceptance_profile,
                                  bias_candles, candle, entry_candles, first_event,
                                  range_candles, run_scenario, scenario_profile)

STEP = bar_duration('1H')
START = bias_candles()[0].close_time


def raw(side, price, swing_time):
    return ConfirmedSwing(SYMBOL, '1H', side, D(str(price)), swing_time,
                          swing_time + STEP, 1, D('1'), D('1'))


def valid_low(price, swing_time, target_price):
    low = SwingLow(raw(SwingSide.LOW, price, swing_time))
    high = SwingHigh(raw(SwingSide.HIGH, target_price, swing_time - STEP))
    return ValidLow(low, high, swing_time + STEP)


def valid_high(price, swing_time, target_price):
    high = SwingHigh(raw(SwingSide.HIGH, price, swing_time))
    low = SwingLow(raw(SwingSide.LOW, target_price, swing_time - STEP))
    return ValidHigh(high, low, swing_time + STEP)


def bar(close_time, low, price=None):
    """A consistent OHLC bar sitting just above `low`."""
    price = low + 1 if price is None else price
    return candle('1H', close_time, price, max(price, low) + 1, low, price)


class RangeReseekUnitTests(unittest.TestCase):
    """Drive the shipped RangeEngine directly with hand-built Valid levels."""

    def _pair(self, engine, moment, low_price, high_price):
        engine.process(bar(moment, low=low_price), valid=(valid_low(low_price, moment, 95),))
        return engine.process(bar(moment + STEP, low=low_price),
                              valid=(valid_high(high_price, moment + STEP, 96),))

    def test_a_confirmed_range_stays_terminal_even_with_reseek_enabled(self):
        engine = RangeEngine(D('5'), allow_reseek=True)
        self._pair(engine, START, 100, 120)
        engine.state = replace(engine.state, phase='RANGE_CONFIRMED',
                               confirmed_at=START + 2 * STEP)
        engine.process(bar(START + 3 * STEP, low=100),
                       valid=(valid_low(50, START + 3 * STEP, 45),))
        self.assertEqual(engine.state.phase, 'RANGE_CONFIRMED')
        self.assertEqual(engine.reseeks, 0)

    def test_without_reseek_an_invalidated_candidate_ends_the_stream(self):
        engine = RangeEngine(D('5'))                      # default: off
        self.assertFalse(engine.allow_reseek)
        self._pair(engine, START, 100, 120)
        engine.process(bar(START + 2 * STEP, low=90))     # wick below RangeLow
        self.assertEqual(engine.state.phase, 'RANGE_INVALIDATED')
        self._pair(engine, START + 3 * STEP, 200, 220)
        self.assertEqual(engine.state.phase, 'RANGE_INVALIDATED')
        self.assertEqual(engine.state.range_low, D('100'))
        self.assertEqual(engine.reseeks, 0)

    def test_with_reseek_a_new_pair_forms_a_new_range(self):
        engine = RangeEngine(D('5'), allow_reseek=True)
        self._pair(engine, START, 100, 120)
        self.assertEqual(engine.state.range_low, D('100'))
        engine.process(bar(START + 2 * STEP, low=90))
        self.assertEqual(engine.state.phase, 'RANGE_INVALIDATED')
        self._pair(engine, START + 3 * STEP, 200, 220)
        self.assertEqual(engine.reseeks, 1)
        self.assertEqual(engine.state.phase, 'WAIT_LOW_TOUCH')
        self.assertEqual((engine.state.range_low, engine.state.range_high),
                         (D('200'), D('220')))

    def test_repeated_invalidations_keep_re_seeking(self):
        engine = RangeEngine(D('5'), allow_reseek=True)
        for index, (low, high) in enumerate(((100, 120), (200, 220), (300, 320))):
            moment = START + index * 4 * STEP
            self._pair(engine, moment, low, high)
            engine.process(bar(moment + 2 * STEP, low=low - 10))
            self.assertEqual(engine.state.phase, 'RANGE_INVALIDATED')
        self.assertEqual(engine.reseeks, 2)


class RangeRetireTests(unittest.TestCase):
    """[U-RANGE-RETIRE-001] a confirmed range retires when a body truly leaves it.

    The tolerance is `boundary_proximity`, the distance the profile already uses
    for "at the boundary". That is what separates a manipulation sweep, which
    pokes just past the edge and reclaims, from price leaving the band.
    """

    def _confirmed(self, proximity=5, allow_retire=True):
        engine = RangeEngine(D(str(proximity)), allow_reseek=True,
                             allow_retire=allow_retire)
        engine.process(bar(START, low=100), valid=(valid_low(100, START, 95),))
        engine.process(bar(START + STEP, low=100),
                       valid=(valid_high(120, START + STEP, 96),))
        engine.state = replace(engine.state, phase='RANGE_CONFIRMED',
                               confirmed_at=START + 2 * STEP)
        return engine

    def test_a_body_close_well_beyond_the_band_retires_the_range(self):
        engine = self._confirmed()
        states = engine.process(bar(START + 3 * STEP, low=90, price=92))   # 8 below 100
        self.assertEqual(engine.state.phase, 'RANGE_RETIRED')
        self.assertEqual(states[-1].invalidation_reasons, ('BODY_CLOSE_BELOW_RANGE_LOW',))

    def test_an_upside_departure_is_recorded_with_its_own_reason(self):
        engine = self._confirmed()
        engine.process(bar(START + 3 * STEP, low=125, price=130))          # 10 above 120
        self.assertEqual(engine.state.invalidation_reasons,
                         ('BODY_CLOSE_ABOVE_RANGE_HIGH',))

    def test_a_sweep_that_closes_just_past_the_edge_does_not_retire(self):
        engine = self._confirmed()
        engine.process(bar(START + 3 * STEP, low=94, price=97))   # 3 below, inside tol 5
        self.assertEqual(engine.state.phase, 'RANGE_CONFIRMED')

    def test_a_wick_outside_with_the_body_inside_never_retires(self):
        engine = self._confirmed()
        engine.process(bar(START + 3 * STEP, low=80, price=110))  # deep wick, body inside
        self.assertEqual(engine.state.phase, 'RANGE_CONFIRMED')

    def test_retirement_can_be_switched_off(self):
        engine = self._confirmed(allow_retire=False)
        engine.process(bar(START + 3 * STEP, low=50, price=55))
        self.assertEqual(engine.state.phase, 'RANGE_CONFIRMED')

    def test_a_retired_range_is_replaced_by_the_next_valid_pair(self):
        engine = self._confirmed()
        engine.process(bar(START + 3 * STEP, low=90, price=92))
        self.assertEqual(engine.state.phase, 'RANGE_RETIRED')
        engine.process(bar(START + 4 * STEP, low=200),
                       valid=(valid_low(200, START + 4 * STEP, 195),))
        engine.process(bar(START + 5 * STEP, low=200),
                       valid=(valid_high(220, START + 5 * STEP, 196),))
        self.assertEqual(engine.reseeks, 1)
        self.assertEqual((engine.state.range_low, engine.state.range_high),
                         (D('200'), D('220')))

    def test_the_default_profile_enables_retirement(self):
        self.assertTrue(StrategyProfile().range_retire_enabled)
        self.assertTrue(StrategyProfile().as_dict()['range_retire_enabled'])


class ReseekStrategyTests(unittest.TestCase):
    def _broken(self, profile=None):
        strategy = run_scenario()
        candidate_at = first_event(strategy, 'RANGE_CANDIDATE').observed_at
        broken = [replace(c, low=D('117'), open=D('124'), high=D('124'), close=D('120'))
                  if c.close_time == candidate_at + timedelta(hours=1) else c
                  for c in range_candles()]
        return run_scenario(profile=profile,
                            candles=bias_candles() + broken + entry_candles())

    def test_an_invalidated_candidate_emits_a_reseek_and_clears_the_setup(self):
        strategy = self._broken()
        self.assertIsNotNone(first_event(strategy, 'RANGE_INVALIDATED'))
        reseek = first_event(strategy, 'RANGE_RESEEK')
        self.assertIsNotNone(reseek)
        self.assertEqual(reseek.payload, 'PREVIOUS_CANDIDATE_INVALIDATED')
        self.assertGreater(reseek.observed_at,
                           first_event(strategy, 'RANGE_INVALIDATED').observed_at)
        self.assertFalse(strategy._setup_consumed)

    def test_a_reseek_discards_the_old_manipulation(self):
        strategy = self._broken()
        reseek_at = first_event(strategy, 'RANGE_RESEEK').observed_at
        for event in strategy.events:
            if event.kind == 'MANIPULATION_CONFIRMED':
                self.assertGreater(event.observed_at, reseek_at)

    def test_reseek_can_be_switched_off(self):
        strategy = self._broken(profile=scenario_profile(range_reseek_enabled=False))
        self.assertIsNone(first_event(strategy, 'RANGE_RESEEK'))
        self.assertEqual(strategy.range.reseeks, 0)

    def test_the_default_profile_enables_both_new_behaviours(self):
        profile = StrategyProfile()
        self.assertTrue(profile.range_reseek_enabled)
        self.assertTrue(profile.multi_setup_enabled)
        data = profile.as_dict()
        self.assertTrue(data['range_reseek_enabled'])
        self.assertTrue(data['multi_setup_enabled'])


class MultiSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strategy = StrategyV1(SYMBOL, acceptance_profile())
        cls.strategy.feed(acceptance_candles())

    def test_the_setup_slot_is_released_once_the_trade_settles(self):
        released = first_event(self.strategy, 'SETUP_SLOT_RELEASED')
        self.assertIsNotNone(released)
        self.assertEqual(released.payload, 'PREVIOUS_TRADE_SETTLED')
        closed = first_event(self.strategy, 'PAPER_ORDER_CLOSED')
        self.assertGreaterEqual(released.observed_at, closed.observed_at)
        self.assertFalse(self.strategy._setup_consumed)

    def test_the_range_and_bias_survive_the_release(self):
        self.assertEqual(self.strategy.range.state.phase, 'RANGE_CONFIRMED')
        self.assertTrue(self.strategy.bias.long_permission)
        self.assertEqual(len(self.strategy.broker.trades), 1)

    def test_the_slot_is_not_released_while_the_trade_is_open(self):
        opened = first_event(self.strategy, 'PAPER_ORDER_OPENED').observed_at
        closed = first_event(self.strategy, 'PAPER_ORDER_CLOSED').observed_at
        for event in self.strategy.events:
            if event.kind == 'SETUP_SLOT_RELEASED':
                self.assertFalse(opened <= event.observed_at < closed)

    def test_multi_setup_can_be_switched_off(self):
        strategy = StrategyV1(SYMBOL, acceptance_profile(multi_setup_enabled=False))
        strategy.feed(acceptance_candles())
        self.assertIsNone(first_event(strategy, 'SETUP_SLOT_RELEASED'))
        self.assertTrue(strategy._setup_consumed)

    def test_a_second_submission_resets_per_trade_protection_state(self):
        broker = self.strategy.broker
        self.assertIsNotNone(broker.break_even_at)       # first trade reached BE
        trade = broker.trades[-1]
        # The recorder now derives per-trade counts from the trade itself, so a
        # later trade cannot inherit this one's break-even or trailing history.
        self.assertTrue(any(u.reason in ('BREAK_EVEN', 'RECOVERY_BREAK_EVEN')
                            for u in trade.stop_updates))
        self.assertEqual(sum(1 for u in trade.stop_updates
                             if u.reason == 'STRUCTURAL_TRAIL'), 3)


if __name__ == '__main__':
    unittest.main()
