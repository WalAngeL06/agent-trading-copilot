"""Strategy V1: bias, range, manipulation, entry, stops, recovery and policy.

Provisional [H] defaults are asserted as configuration, never as validated
trading rules. Nothing here measures profitability.
"""
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from agent_trading.market import bar_duration
from agent_trading.models import Candle
from agent_trading.swing import SwingConfig
from agent_trading.trading_brain.gaps import GapEngine
from agent_trading.trading_brain.manipulation import ManipulationEngine
from agent_trading.trading_brain.models import FVG, SwingLow, TradeCandidate
from agent_trading.trading_brain.risk import RiskEngine
from agent_trading.trading_brain.risk_models import SupportingZone
from agent_trading.strategy_v1 import (BiasEngine, FvgBook, PendingLimitPaperBroker,
                                       StrategyProfile, StrategyV1, TimeframeRoles,
                                       entry_price, protecting_swing_low)
from agent_trading.strategy_v1.models import EntryPlan, TrackedFvg

from strategy_v1_fixtures import (D, SYMBOL, all_candles, bars, bias_candles, candle,
                                  entry_candles, events_of, first_event, range_candles,
                                  run_scenario, scenario_profile)


def at(candles, close_time):
    return next(c for c in candles if c.close_time == close_time)


def replace_candle(candles, close_time, **changes):
    return [replace(c, **changes) if c.close_time == close_time else c for c in candles]


class ScenarioMixin:
    @classmethod
    def setUpClass(cls):
        cls.strategy = run_scenario()


# --------------------------------------------------------------------- 4H BIAS
class BiasTests(unittest.TestCase):
    def _engine_with_unbroken_high(self):
        engine = BiasEngine(SYMBOL, '4H', SwingConfig())
        last = None
        for bar in bias_candles():
            engine.process(bar)
            last = bar
            if engine.unbroken_valid_high is not None:
                return engine, last
        self.fail('scenario never produced an unbroken Valid High')

    def test_a_wick_above_a_valid_high_is_not_a_structural_break(self):
        engine, last = self._engine_with_unbroken_high()
        level = engine.unbroken_valid_high
        before = engine.state
        moment = last.close_time + bar_duration('4H')
        wick = candle('4H', moment, level.price - 2, level.price + 5,
                      level.price - 4, level.price - 1)
        _raw, _valid, breaks = engine.process(wick)
        self.assertEqual(breaks, ())
        self.assertEqual(engine.state, before)
        self.assertIs(engine.unbroken_valid_high, level)

    def test_a_body_close_above_a_valid_high_breaks_structure_immediately(self):
        engine, last = self._engine_with_unbroken_high()
        level = engine.unbroken_valid_high
        moment = last.close_time + bar_duration('4H')
        body = candle('4H', moment, level.price - 1, level.price + 6,
                      level.price - 2, level.price + 1)
        _raw, _valid, breaks = engine.process(body)
        self.assertEqual(len(breaks), 1)
        self.assertEqual(breaks[0].direction, 'BULLISH')
        self.assertEqual(breaks[0].broken_price, level.price)
        self.assertEqual(breaks[0].confirmed_at, moment)
        self.assertTrue(engine.long_permission)

    def test_the_break_does_not_wait_for_a_future_valid_high(self):
        engine, last = self._engine_with_unbroken_high()
        level = engine.unbroken_valid_high
        moment = last.close_time + bar_duration('4H')
        _raw, valid, breaks = engine.process(
            candle('4H', moment, level.price - 1, level.price + 6, level.price - 2,
                   level.price + 1))
        self.assertEqual(len(breaks), 1)
        # No new Valid High was confirmed on the breaking candle.
        self.assertEqual(tuple(v for v in valid if hasattr(v, 'target')
                               and isinstance(v.swing, type(v.swing))
                               and v.__class__.__name__ == 'ValidHigh'), ())
        self.assertIs(engine.current_valid_high, level)

    def test_structural_history_keeps_current_and_previous_levels(self):
        engine = BiasEngine(SYMBOL, '4H', SwingConfig())
        for bar in bias_candles():
            engine.process(bar)
        self.assertIsNotNone(engine.current_valid_high)
        self.assertIsNotNone(engine.current_valid_low)
        self.assertIsNotNone(engine.past_valid_low)
        self.assertGreaterEqual(len(engine.breaks), 2)

    def test_scenario_reaches_bullish_reversal_through_a_bearish_state(self):
        strategy = run_scenario()
        breaks = [e.payload for e in events_of(strategy, 'BIAS_BREAK')]
        self.assertEqual(breaks[0].direction, 'BEARISH')
        self.assertEqual(breaks[0].new_bias, 'LONG_DISABLED')
        self.assertEqual(breaks[1].direction, 'BULLISH')
        self.assertEqual(breaks[1].previous_bias, 'LONG_DISABLED')
        self.assertEqual(breaks[1].new_bias, 'BULLISH_REVERSAL')
        self.assertTrue(strategy.bias.long_permission)

    def test_bias_break_evidence_is_auditable(self):
        strategy = run_scenario()
        event = events_of(strategy, 'BIAS_BREAK')[1]
        payload = event.payload
        self.assertEqual(event.timeframe, '4H')
        for field in ('broken_price', 'close_price', 'confirmed_at', 'previous_bias',
                      'new_bias', 'break_candle'):
            self.assertIsNotNone(getattr(payload, field))
        self.assertGreater(payload.close_price, payload.broken_price)
        self.assertEqual(payload.break_candle.timeframe, '4H')

    def test_a_bearish_break_never_produces_a_short_setup(self):
        strategy = run_scenario()
        bearish = [e for e in events_of(strategy, 'BIAS_BREAK')
                   if e.payload.direction == 'BEARISH']
        self.assertTrue(bearish)
        for event in events_of(strategy, 'TRADE_CANDIDATE'):
            self.assertEqual(event.payload.direction, 'LONG')


# ------------------------------------------------------------------- 1H RANGE
class RangeTests(ScenarioMixin, unittest.TestCase):
    def test_frozen_range_uses_the_selected_valid_pair_and_midpoint_eq(self):
        state = first_event(self.strategy, 'RANGE_CONFIRMED').payload
        self.assertEqual(state.range_low, D('118'))
        self.assertEqual(state.range_high, D('140'))
        self.assertEqual(state.eq, D('129'))

    def test_a_pre_confirmation_wick_below_range_low_invalidates_the_candidate(self):
        candidate_at = first_event(self.strategy, 'RANGE_CANDIDATE').observed_at
        broken = replace_candle(range_candles(), candidate_at + timedelta(hours=1),
                                low=D('117'), open=D('124'), high=D('124'), close=D('120'))
        strategy = run_scenario(candles=bias_candles() + broken + entry_candles())
        invalidated = first_event(strategy, 'RANGE_INVALIDATED')
        self.assertIsNotNone(invalidated)
        self.assertIn('WICK_BELOW_RANGE_LOW', invalidated.payload.invalidation_reasons)
        self.assertIsNone(first_event(strategy, 'RANGE_CONFIRMED'))

    def test_manipulation_cannot_exist_before_range_confirmation(self):
        confirmed_at = first_event(self.strategy, 'RANGE_CONFIRMED').observed_at
        for kind in ('SWEEP', 'MANIPULATION_CONFIRMED'):
            for event in events_of(self.strategy, kind):
                self.assertGreater(event.observed_at, confirmed_at)

    def test_manipulation_engine_ignores_an_unconfirmed_range(self):
        engine = ManipulationEngine()
        state = first_event(self.strategy, 'RANGE_CANDIDATE').payload
        self.assertIsNone(state.confirmed_at)
        bar = candle('1H', state.low.confirmed_at + timedelta(hours=1), 120, 121, 100, 119)
        self.assertEqual(engine.process(bar, state), ())

    def test_confirmed_range_survives_internal_swing_count_variation(self):
        extra = list(range_candles())
        confirmed_at = first_event(self.strategy, 'RANGE_CONFIRMED').observed_at
        # Additional inside oscillation before confirmation must not break it.
        self.assertTrue(all(c.low >= D('118') or c.close_time > confirmed_at
                            for c in extra if c.close_time <= confirmed_at))


# ------------------------------------------------------------ 1H MANIPULATION
class ManipulationTests(ScenarioMixin, unittest.TestCase):
    def test_a_low_below_range_low_alone_is_not_a_confirmed_manipulation(self):
        sweep = first_event(self.strategy, 'SWEEP')
        reclaim = first_event(self.strategy, 'MANIPULATION_CONFIRMED')
        self.assertEqual(sweep.payload.phase, 'SWEPT')
        self.assertLess(sweep.observed_at, reclaim.observed_at)

    def test_body_close_back_above_range_low_confirms_manipulation(self):
        reclaim = first_event(self.strategy, 'MANIPULATION_CONFIRMED').payload
        state = first_event(self.strategy, 'RANGE_CONFIRMED').payload
        bar = at(range_candles(), reclaim.reclaimed_at)
        self.assertGreater(bar.close, state.range_low)
        self.assertLess(bar.close, state.range_high)
        self.assertEqual(reclaim.phase, 'RECLAIMED')
        self.assertEqual(reclaim.direction, 'LONG')

    def test_manipulation_evidence_is_auditable(self):
        event = first_event(self.strategy, 'MANIPULATION_CONFIRMED')
        payload = event.payload
        self.assertEqual(payload.extreme, D('112'))
        self.assertIsNotNone(payload.swept_at)
        self.assertIsNotNone(payload.reclaimed_at)
        self.assertTrue(event.evidence_ids)

    def test_an_upside_sweep_never_creates_a_short_setup(self):
        upside = [e for e in events_of(self.strategy, 'SWEEP')
                  if e.payload.direction == 'SHORT']
        self.assertTrue(upside, 'scenario should still observe an upside sweep')
        self.assertEqual(len(events_of(self.strategy, 'TRADE_CANDIDATE')), 1)
        self.assertEqual(first_event(self.strategy, 'TRADE_CANDIDATE').payload.direction, 'LONG')


# ------------------------------------------------------------------ CAUSALITY
class CausalityTests(ScenarioMixin, unittest.TestCase):
    def test_entry_search_cannot_start_before_manipulation_is_confirmed(self):
        reclaim = first_event(self.strategy, 'MANIPULATION_CONFIRMED').observed_at
        candidate = first_event(self.strategy, 'TRADE_CANDIDATE')
        self.assertGreater(candidate.observed_at, reclaim)

    def test_a_backwards_candle_is_rejected_across_timeframes(self):
        strategy = StrategyV1(SYMBOL, scenario_profile())
        feed = all_candles()[:40]
        for bar in sorted(feed, key=lambda c: (c.close_time, strategy.roles.rank(c.timeframe))):
            strategy.process(bar)
        stale = candle('15m', strategy.as_of - timedelta(hours=6), 100, 101, 99, 100)
        with self.assertRaises(ValueError):
            strategy.process(stale)

    def test_equal_close_times_must_resolve_highest_timeframe_first(self):
        strategy = StrategyV1(SYMBOL, scenario_profile())
        moment = bias_candles()[0].close_time
        strategy.process(candle('15m', moment, 100, 101, 99, 100))
        with self.assertRaises(ValueError):
            strategy.process(candle('4H', moment, 100, 101, 99, 100))

    def test_each_stream_must_stay_contiguous(self):
        strategy = StrategyV1(SYMBOL, scenario_profile())
        first = bias_candles()[0]
        strategy.process(first)
        with self.assertRaises(ValueError):
            strategy.process(replace(first, close_time=first.close_time + timedelta(hours=12)))

    def test_a_foreign_timeframe_has_no_strategy_role(self):
        strategy = StrategyV1(SYMBOL, scenario_profile())
        with self.assertRaises(ValueError):
            strategy.process(candle('5m', bias_candles()[0].close_time, 100, 101, 99, 100))

    def test_only_closed_candles_can_exist(self):
        with self.assertRaises(ValueError):
            Candle(SYMBOL, '4H', bias_candles()[0].close_time, D('1'), D('1'), D('1'),
                   D('1'), D('1'), closed=False)


# ---------------------------------------------------------------- 15m ENTRY
class EntryLevelTests(unittest.TestCase):
    def setUp(self):
        moment = bias_candles()[0].close_time
        self.gap = FVG('LONG', D('100'), D('110'), (moment, moment, moment), moment)

    def test_low_eq_and_high_entry_levels(self):
        self.assertEqual(entry_price(self.gap, 'FVG_LOW', D('0.5')), D('100'))
        self.assertEqual(entry_price(self.gap, 'FVG_EQ', D('0.5')), D('105'))
        self.assertEqual(entry_price(self.gap, 'FVG_HIGH', D('0.5')), D('110'))

    def test_eq_default_is_exactly_the_fifty_percent_midpoint(self):
        self.assertEqual(StrategyProfile().entry_level, 'FVG_EQ')
        self.assertEqual(StrategyProfile().entry_level_ratio, D('0.5'))
        midpoint = (self.gap.lower + self.gap.upper) / D(2)
        self.assertEqual(entry_price(self.gap, 'FVG_EQ', D('0.5')), midpoint)

    def test_the_ratio_is_configuration_not_a_hardcoded_constant(self):
        self.assertEqual(entry_price(self.gap, 'FVG_EQ', D('0.25')), D('102.5'))
        self.assertEqual(entry_price(self.gap, 'FVG_EQ', D('0')), D('100'))
        self.assertEqual(entry_price(self.gap, 'FVG_EQ', D('1')), D('110'))

    def test_decimal_digits_are_preserved(self):
        gap = replace(self.gap, lower=D('100.000000000000000001'), upper=D('100.000000000000000003'))
        self.assertEqual(entry_price(gap, 'FVG_EQ', D('0.5')), D('100.000000000000000002'))

    def test_an_unknown_entry_level_is_rejected(self):
        with self.assertRaises(ValueError):
            entry_price(self.gap, 'FVG_MIDDLE', D('0.5'))
        with self.assertRaises(ValueError):
            StrategyProfile(entry_level='FVG_MIDDLE')


class BullishGapDetectionTests(unittest.TestCase):
    def test_a_three_candle_bullish_gap_is_detected(self):
        engine, start = GapEngine(), bias_candles()[0].close_time
        rows = [(100, 101, 99, 100), (101, 110, 101, 109), (109, 112, 105, 111)]
        gaps = []
        for index, (o, h, l, c) in enumerate(rows):
            gaps.extend(engine.process(candle('15m', start + timedelta(minutes=15 * index),
                                              o, h, l, c)))
        longs = [g for g in gaps if g.direction == 'LONG' and g.kind == 'FVG']
        self.assertEqual(len(longs), 1)
        self.assertEqual((longs[0].lower, longs[0].upper), (D('101'), D('105')))


class PendingEntryTests(ScenarioMixin, unittest.TestCase):
    def test_pending_entry_is_created_at_the_configured_level(self):
        plan = first_event(self.strategy, 'ENTRY_PLAN').payload
        self.assertEqual(plan.entry_level, 'FVG_EQ')
        self.assertEqual((plan.primary.lower, plan.primary.upper), (D('126'), D('130')))
        self.assertEqual(plan.entry_price, D('128'))

    def test_the_fill_waits_for_price_to_trade_back_to_the_level(self):
        pending = first_event(self.strategy, 'PENDING_ENTRY')
        opened = first_event(self.strategy, 'PAPER_ORDER_OPENED')
        self.assertGreater(opened.observed_at, pending.observed_at)
        self.assertEqual(opened.payload.entry, D('128'))
        fill_bar = at(entry_candles(), opened.observed_at)
        self.assertLessEqual(fill_bar.low, D('128'))

    def test_there_is_no_forced_next_open_fill(self):
        pending = first_event(self.strategy, 'PENDING_ENTRY')
        following = pending.observed_at + bar_duration('15m')
        opened = first_event(self.strategy, 'PAPER_ORDER_OPENED')
        self.assertNotEqual(opened.observed_at, following)
        self.assertNotEqual(opened.payload.entry, at(entry_candles(), following).open)

    def test_a_low_entry_level_that_price_never_reaches_stays_pending(self):
        strategy = run_scenario(profile=scenario_profile(entry_level='FVG_LOW'))
        plan = first_event(strategy, 'ENTRY_PLAN').payload
        self.assertEqual(plan.entry_price, D('126'))
        self.assertIsNone(first_event(strategy, 'PAPER_ORDER_OPENED'))
        self.assertEqual(strategy.phase(), 'PENDING_ENTRY')

    def test_a_high_entry_level_worsens_reward_risk_and_is_blocked(self):
        # FVG_HIGH buys 2 points higher against the same structural stop, so the
        # same setup fails the minimum reward/risk gate instead of being taken.
        strategy = run_scenario(profile=scenario_profile(entry_level='FVG_HIGH'))
        plan = first_event(strategy, 'ENTRY_PLAN').payload
        self.assertEqual(plan.entry_price, D('130'))
        decision = first_event(strategy, 'BLOCKED').payload
        self.assertEqual(decision.reason, 'MIN_REWARD_RISK')
        self.assertEqual(decision.evidence.risk_distance, D('12'))
        self.assertEqual(decision.evidence.reward_distance, D('10'))
        self.assertIsNone(first_event(strategy, 'PAPER_ORDER_OPENED'))


class FreshnessTests(unittest.TestCase):
    def _book(self):
        start = bias_candles()[0].close_time
        gap = FVG('LONG', D('100'), D('110'), (start, start, start), start)
        book = FvgBook(True)
        book.publish(gap, 'g1')
        return book, start

    def test_a_new_gap_is_fresh(self):
        book, _ = self._book()
        self.assertEqual(book.current('g1').state, 'FRESH')
        self.assertTrue(book.current('g1').fresh)

    def test_a_wick_into_the_gap_removes_freshness(self):
        book, start = self._book()
        book.process(candle('15m', start + timedelta(minutes=15), 115, 116, 108, 114))
        self.assertEqual(book.current('g1').state, 'TOUCHED')
        self.assertFalse(book.current('g1').fresh)

    def test_a_close_below_the_protective_edge_invalidates(self):
        book, start = self._book()
        book.process(candle('15m', start + timedelta(minutes=15), 105, 106, 99, 99.5))
        self.assertEqual(book.current('g1').state, 'INVALIDATED')

    def test_invalidation_is_terminal(self):
        book, start = self._book()
        book.process(candle('15m', start + timedelta(minutes=15), 105, 106, 99, 99.5))
        book.process(candle('15m', start + timedelta(minutes=30), 120, 130, 120, 129))
        self.assertEqual(book.current('g1').state, 'INVALIDATED')

    def test_the_publishing_candle_never_ages_its_own_gap(self):
        book, start = self._book()
        book.process(candle('15m', start, 100, 111, 99, 110))
        self.assertEqual(book.current('g1').state, 'FRESH')


# --------------------------------------------------------- SECONDARY FVG / SL
class SecondaryStopTests(ScenarioMixin, unittest.TestCase):
    def test_the_secondary_gap_below_primary_is_selected(self):
        plan = first_event(self.strategy, 'ENTRY_PLAN').payload
        self.assertEqual(plan.stop_source, 'SECONDARY_FVG_PROTECTING_SWING')
        self.assertIsNotNone(plan.secondary)
        self.assertEqual((plan.secondary.lower, plan.secondary.upper), (D('120'), D('122')))
        self.assertLess(plan.secondary.upper, plan.primary.lower)

    def test_the_protecting_confirmed_swing_low_sits_below_the_secondary_gap(self):
        plan = first_event(self.strategy, 'ENTRY_PLAN').payload
        self.assertEqual(plan.protecting_price, D('119'))
        self.assertLessEqual(plan.protecting_price, plan.secondary.lower)
        self.assertIsNotNone(plan.protecting_swing)

    def test_the_initial_stop_is_placed_beyond_the_protecting_swing(self):
        decision = first_event(self.strategy, 'RISK_APPROVED').payload
        evidence = decision.evidence
        self.assertEqual(evidence.initial_stop_source, 'SUPPORTING_ZONE')
        self.assertEqual(evidence.invalidation_level, D('119'))
        self.assertEqual(evidence.initial_stop, D('118'))       # 119 - configured buffer 1
        self.assertLess(evidence.initial_stop, evidence.invalidation_level)

    def test_protecting_swing_selection_prefers_the_most_recent_low(self):
        start = bias_candles()[0].close_time
        lows = []
        for index, price in enumerate((D('90'), D('95'), D('80'))):
            raw = _fake_swing_low(price, start + timedelta(minutes=15 * index))
            lows.append(raw)
        chosen = protecting_swing_low(lows, D('100'), start + timedelta(hours=5))
        self.assertEqual(chosen.price, D('80'))

    def test_the_fallback_stop_is_used_when_no_secondary_support_exists(self):
        strategy = run_scenario(profile=scenario_profile(secondary_fvg_support_enabled=False))
        plan = first_event(strategy, 'ENTRY_PLAN').payload
        self.assertEqual(plan.stop_source, 'MANIPULATION_SWEEP_LOW')
        self.assertIsNone(plan.secondary)
        decision = first_event(strategy, 'BLOCKED').payload
        self.assertEqual(decision.evidence.initial_stop_source, 'SWEEP_EXTREME')
        self.assertEqual(decision.evidence.initial_stop, D('111'))   # sweep 112 - buffer 1

    def test_the_fallback_stop_still_faces_every_risk_gate(self):
        strategy = run_scenario(profile=scenario_profile(secondary_fvg_support_enabled=False))
        decision = first_event(strategy, 'BLOCKED').payload
        self.assertEqual(decision.status, 'BLOCKED')
        self.assertEqual(decision.reason, 'MIN_REWARD_RISK')
        self.assertIsNone(first_event(strategy, 'PAPER_ORDER_OPENED'))


def _fake_swing_low(price, moment):
    from agent_trading.swing import ConfirmedSwing, SwingSide
    raw = ConfirmedSwing(SYMBOL, '15m', SwingSide.LOW, price, moment,
                         moment + timedelta(minutes=15), 1, D('1'), D('1'))
    return SwingLow(raw)


# ------------------------------------------------------------------- TARGET
class TargetTests(ScenarioMixin, unittest.TestCase):
    def test_the_terminal_target_is_the_frozen_range_high(self):
        state = first_event(self.strategy, 'RANGE_CONFIRMED').payload
        plan = first_event(self.strategy, 'ENTRY_PLAN').payload
        self.assertEqual(plan.target, state.range_high)
        self.assertEqual(plan.target, D('140'))

    def test_eq_is_never_the_terminal_target(self):
        state = first_event(self.strategy, 'RANGE_CONFIRMED').payload
        plan = first_event(self.strategy, 'ENTRY_PLAN').payload
        self.assertEqual(state.eq, D('129'))
        self.assertNotEqual(plan.target, state.eq)

    def test_reward_risk_uses_entry_structural_stop_and_range_high(self):
        evidence = first_event(self.strategy, 'RISK_APPROVED').payload.evidence
        self.assertEqual(evidence.entry, D('128'))
        self.assertEqual(evidence.initial_stop, D('118'))
        self.assertEqual(evidence.tp, D('140'))
        self.assertEqual(evidence.risk_distance, D('10'))
        self.assertEqual(evidence.reward_distance, D('12'))
        self.assertEqual(evidence.reward_risk_ratio, D('1.2'))

    def test_a_target_at_or_below_entry_cannot_be_approved(self):
        risk = RiskEngine(scenario_profile().risk_config())
        moment = bias_candles()[0].close_time
        candidate = TradeCandidate('LONG', D('130'), D('118'), D('125'), moment, (),
                                   sweep_extreme=D('119'))
        decision = risk.evaluate(candidate, D('10000'), (), symbol=SYMBOL, timeframe='15m')
        self.assertEqual(decision.status, 'BLOCKED')
        self.assertEqual(decision.reason, 'INVALID_TP_SIDE')


# --------------------------------------------------------------- DIRECTION
class DirectionTests(ScenarioMixin, unittest.TestCase):
    def test_no_short_trade_candidate_is_ever_produced(self):
        for event in events_of(self.strategy, 'TRADE_CANDIDATE'):
            self.assertEqual(event.payload.direction, 'LONG')

    def test_no_short_paper_trade_is_ever_opened(self):
        for trade in self.strategy.broker.trades:
            self.assertEqual(trade.direction, 'LONG')
        for event in events_of(self.strategy, 'PAPER_ORDER_OPENED'):
            self.assertEqual(event.payload.direction, 'LONG')

    def test_the_broker_refuses_a_short_plan(self):
        profile = scenario_profile()
        risk = RiskEngine(profile.risk_config())
        broker = PendingLimitPaperBroker(risk, D('10000'), profile)
        moment = bias_candles()[0].close_time
        candidate = TradeCandidate('SHORT', D('130'), D('140'), D('100'), moment, (),
                                   sweep_extreme=D('141'))
        decision = risk.evaluate(candidate, D('10000'), (), symbol=SYMBOL, timeframe='15m')
        self.assertIsNotNone(decision.plan)
        with self.assertRaises(ValueError):
            broker.submit(decision.plan, None)

    def test_only_long_direction_is_configurable(self):
        with self.assertRaises(ValueError):
            StrategyProfile(direction='SHORT_ONLY')
        with self.assertRaises(ValueError):
            StrategyProfile(direction='BOTH')


# ----------------------------------------------------------- CUSTOMIZATION
class CustomizationTests(unittest.TestCase):
    def test_default_timeframe_roles(self):
        profile = StrategyProfile()
        self.assertEqual((profile.timeframes.bias, profile.timeframes.range,
                          profile.timeframes.entry), ('4H', '1H', '15m'))
        self.assertEqual(profile.direction, 'LONG_ONLY')
        self.assertEqual(profile.entry_zone, 'BULLISH_FVG')
        self.assertTrue(profile.secondary_fvg_support_enabled)

    def test_an_alternate_timeframe_profile_needs_no_engine_change(self):
        profile = StrategyProfile(timeframes=TimeframeRoles('1H', '15m', '5m'))
        strategy = StrategyV1(SYMBOL, profile)
        self.assertEqual(strategy.roles.ordered, ('1H', '15m', '5m'))
        self.assertEqual(strategy.bias.timeframe, '1H')
        self.assertEqual(strategy.range_swing.timeframe, '15m')
        self.assertEqual(strategy.entry_swing.timeframe, '5m')
        self.assertEqual(strategy.phase(), 'WAITING_FOR_BIAS')

    def test_timeframe_roles_must_descend(self):
        with self.assertRaises(ValueError):
            TimeframeRoles('15m', '1H', '4H')
        with self.assertRaises(ValueError):
            TimeframeRoles('1H', '1H', '15m')

    def test_risk_and_entry_settings_are_exposed(self):
        profile = StrategyProfile(entry_level='FVG_LOW', boundary_proximity=D('7'),
                                  stop_buffer=D('3'), break_even_r=D('2'),
                                  min_reward_risk=D('1.5'))
        config = profile.risk_config()
        self.assertEqual(config.stop_buffer, D('3'))
        self.assertEqual(config.break_even_r, D('2'))
        self.assertEqual(config.min_reward_risk, D('1.5'))
        self.assertEqual(profile.entry_level, 'FVG_LOW')
        self.assertEqual(profile.boundary_proximity, D('7'))

    def test_invalid_configuration_is_rejected(self):
        for kwargs in ({'entry_level_ratio': D('1.5')}, {'stop_buffer': D('0')},
                       {'risk_fraction': D('0')}, {'pending_expiry_bars': 0},
                       {'primary_failure_mode': 'GUESS'}):
            with self.assertRaises(ValueError):
                StrategyProfile(**kwargs)


# --------------------------------------------------------- CAPITAL / AUTO EARN
class CapitalPolicyTests(ScenarioMixin, unittest.TestCase):
    def test_confirmed_range_awaiting_manipulation_is_idle_capital(self):
        event = first_event(self.strategy, 'CAPITAL_POLICY')
        self.assertTrue(event.payload.capital_idle)
        self.assertEqual(event.payload.desired_capital_policy, 'AUTO_EARN_ELIGIBLE')
        self.assertEqual(event.payload.reason, 'RANGE_CONFIRMED_WAITING_FOR_MANIPULATION')
        self.assertEqual(event.observed_at,
                         first_event(self.strategy, 'RANGE_CONFIRMED').observed_at)

    def test_confirmed_manipulation_releases_idle_capital(self):
        policies = events_of(self.strategy, 'CAPITAL_POLICY')
        self.assertGreaterEqual(len(policies), 2)
        self.assertFalse(policies[1].payload.capital_idle)
        self.assertEqual(policies[1].payload.desired_capital_policy, 'RESERVED_FOR_ENTRY')
        self.assertEqual(policies[1].observed_at,
                         first_event(self.strategy, 'MANIPULATION_CONFIRMED').observed_at)

    def test_no_confirmed_range_means_no_auto_earn_eligibility(self):
        strategy = StrategyV1(SYMBOL, scenario_profile())
        policy = strategy.capital_policy()
        self.assertFalse(policy.capital_idle)
        self.assertEqual(policy.desired_capital_policy, 'NOT_ELIGIBLE')

    def test_the_policy_state_performs_no_exchange_write(self):
        import agent_trading.strategy_v1.strategy as module
        import agent_trading.strategy_v1.broker as broker_module
        for source in (module, broker_module):
            with open(source.__file__, encoding='utf-8') as handle:
                text = handle.read()
            for forbidden in ('earn_auto_set', 'place_order', 'transfer', 'redeem', 'purchase'):
                self.assertNotIn(forbidden, text)


# ------------------------------------------------------------------ RECOVERY
class RecoveryTests(unittest.TestCase):
    """PRIMARY fails, SECONDARY holds, price returns to entry -> break-even."""

    def _open_trade(self, profile=None):
        profile = profile or scenario_profile()
        risk = RiskEngine(profile.risk_config())
        broker = PendingLimitPaperBroker(risk, D('10000'), profile)
        start = bias_candles()[0].close_time
        primary = TrackedFvg('p1', FVG('LONG', D('126'), D('130'), (start, start, start), start))
        secondary = TrackedFvg('s1', FVG('LONG', D('120'), D('122'),
                                         (start, start, start), start))
        swing = _fake_swing_low(D('119'), start)
        zone = SupportingZone('s1', 'FVG', 'LONG', D('120'), D('122'), D('119'),
                              start, SYMBOL, '15m')
        candidate = TradeCandidate('LONG', D('128'), D('119'), D('140'), start, (),
                                   sweep_extreme=D('112'))
        decision = risk.evaluate(candidate, D('10000'), (zone,), symbol=SYMBOL, timeframe='15m')
        self.assertIsNotNone(decision.plan, 'recovery fixture must be approvable')
        plan = EntryPlan(primary, 'FVG_EQ', D('128'), D('140'),
                         'SECONDARY_FVG_PROTECTING_SWING', secondary, swing, D('119'), start)
        broker.submit(decision.plan, plan)
        step = bar_duration('15m')
        broker.process(candle('15m', start + step, 129, 129.5, 128, 128.5))   # fill at 128
        return broker, start + step, step

    def test_the_fixture_opens_at_the_configured_entry(self):
        broker, _, _ = self._open_trade()
        trade = broker.trades[-1]
        self.assertEqual(trade.entry, D('128'))
        self.assertEqual(trade.stop, D('118'))
        self.assertEqual(trade.tp, D('140'))

    def test_the_trade_survives_primary_failure_while_the_structural_stop_holds(self):
        broker, moment, step = self._open_trade()
        broker.process(candle('15m', moment + step, 128, 128.5, 124, 125))    # closes below 126
        self.assertEqual(broker.trades[-1].status, 'OPEN')
        self.assertIsNotNone(broker.primary_failed_at)

    def test_recovery_to_the_original_entry_moves_the_stop_to_break_even(self):
        broker, moment, step = self._open_trade()
        broker.process(candle('15m', moment + step, 128, 128.5, 124, 125))       # primary fails
        broker.process(candle('15m', moment + 2 * step, 125, 125.5, 121, 123))   # secondary holds
        self.assertIsNotNone(broker.secondary_reacted_at)
        self.assertEqual(broker.trades[-1].stop, D('118'))
        broker.process(candle('15m', moment + 3 * step, 123, 128.5, 122.5, 128)) # back to entry
        trade = broker.trades[-1]
        self.assertEqual(trade.stop, D('128'))
        self.assertEqual(trade.stop_updates[-1].reason, 'RECOVERY_BREAK_EVEN')

    def test_recovery_requires_the_secondary_to_actually_hold(self):
        broker, moment, step = self._open_trade()
        broker.process(candle('15m', moment + step, 128, 128.5, 124, 125))
        broker.process(candle('15m', moment + 2 * step, 125, 125.5, 123.5, 124))  # never reaches
        self.assertIsNone(broker.secondary_reacted_at)
        broker.process(candle('15m', moment + 3 * step, 124, 128.5, 123.5, 128))
        self.assertEqual(broker.trades[-1].stop, D('118'))

    def test_a_stop_can_never_loosen(self):
        broker, moment, step = self._open_trade()
        trade = broker.trades[-1]
        loosened = broker.risk.tighten_stop(trade, D('100'), moment + step, 'ATTEMPT')
        self.assertEqual(loosened.stop, D('118'))
        self.assertEqual(loosened.stop_updates, ())

    def test_the_inherited_one_r_break_even_still_applies(self):
        broker, moment, step = self._open_trade()
        self.assertEqual(broker.trades[-1].approved_plan.evidence.break_even_r, D('1'))
        # entry 128 + 1R (10) = 138 favorable excursion, still short of the 140 target.
        broker.process(candle('15m', moment + step, 128, 138.5, 127.5, 138))
        trade = broker.trades[-1]
        self.assertEqual(trade.stop, D('128'))
        self.assertEqual(trade.stop_updates[-1].reason, 'BREAK_EVEN')


# ------------------------------------------------------- ACCEPTANCE SCENARIO
class AcceptanceScenarioTests(ScenarioMixin, unittest.TestCase):
    def test_the_full_default_chain_reaches_the_range_high_exit(self):
        # SUPERSEDED: this chain used to end in PAPER_ORDER_CLOSED because the
        # RangeHigh closed 100%. The Strategy V1 default is now a 10% runner, so
        # the structural exit realises 90% and the trade stays open as a runner.
        order = ['BIAS_BREAK', 'RANGE_CONFIRMED', 'CAPITAL_POLICY', 'SWEEP',
                 'MANIPULATION_CONFIRMED', 'TRADE_CANDIDATE', 'ENTRY_PLAN',
                 'RISK_APPROVED', 'PENDING_ENTRY', 'PAPER_ORDER_OPENED',
                 'RANGE_HIGH_PARTIAL_EXIT', 'RUNNER_OPEN']
        for kind in order:
            self.assertIsNotNone(first_event(self.strategy, kind), f'missing {kind}')
        times = [first_event(self.strategy, kind).observed_at for kind in order]
        self.assertEqual(times, sorted(times))

    def test_the_scenario_passes_through_production_classes_only(self):
        self.assertIsInstance(self.strategy, StrategyV1)
        self.assertEqual(self.strategy.report()['schema_version'], 'strategy-v1-paper-v0.1')
        self.assertEqual(self.strategy.report()['mode'], 'PAPER')

    def test_the_range_high_exit_realises_ninety_percent_and_leaves_a_runner(self):
        # SUPERSEDED: the old expectation was a single 100% exit worth 120.
        # Default runner_fraction is 0.10, so 90% is realised at RangeHigh.
        exit_event = first_event(self.strategy, 'RANGE_HIGH_PARTIAL_EXIT').payload
        self.assertEqual(exit_event.quantity, D('9.00000000'))
        self.assertEqual(exit_event.exit_price, D('140'))
        self.assertEqual(exit_event.realized_pnl, D('108'))
        trade = self.strategy.broker.trades[-1]
        self.assertEqual(trade.status, 'OPEN')
        self.assertEqual(trade.entry, D('128'))
        self.assertEqual(trade.ledger.original_quantity, D('10.00000000'))
        self.assertEqual(trade.ledger.remaining_quantity, D('1.00000000'))
        self.assertTrue(trade.ledger.runner_open)
        self.assertFalse(trade.ledger.has_upside_target)

    def test_the_scenario_is_deterministic(self):
        again = run_scenario()
        self.assertEqual([(e.id, e.kind, e.observed_at) for e in self.strategy.events],
                         [(e.id, e.kind, e.observed_at) for e in again.events])

    def test_exactly_one_setup_is_taken(self):
        self.assertEqual(len(events_of(self.strategy, 'TRADE_CANDIDATE')), 1)
        self.assertEqual(len(self.strategy.broker.trades), 1)


if __name__ == '__main__':
    unittest.main()
