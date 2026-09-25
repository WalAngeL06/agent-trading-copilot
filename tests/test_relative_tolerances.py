"""[U-RR-TRAIL-001] Tolerances as a share of the price being tested [H]-REL-TOL-001."""
from decimal import Decimal as D
import unittest

import test_htf_context as htf
from test_range_guide_rules import candidate
from test_trading_brain import bar, raw
from agent_trading.swing import SwingSide
from agent_trading.trading_brain.models import TradeCandidate
from agent_trading.trading_brain.risk import RiskEngine
from agent_trading.trading_brain.risk_models import RiskConfig
from agent_trading.strategy_v1 import StrategyProfile

from strategy_v1_fixtures import bias_candles, candle, scenario_profile
from test_strategy_v1_trailing import STEP, confirmed_low, open_long, protect

START = bias_candles()[0].close_time


class RangeTouchTests(unittest.TestCase):
    """Candidate 80 .. 120, EQ 100; a 1% ratio is 0.8 at RL and 1.2 at RH."""

    def test_a_low_touch_is_measured_on_the_range_low(self):
        engine = candidate(proximity_ratio=D('0.01'))
        engine.process(bar(9, '85', '90', '81', '86'), (), (raw(SwingSide.LOW, '81', 8, 9),))
        engine.process(bar(10, '95', '101', '94', '100'))
        self.assertEqual(engine.state.phase, 'WAIT_LOW_TOUCH')         # 1.0 above RL > 0.8
        engine.process(bar(11, '85', '90', '80.5', '86'), (),
                       (raw(SwingSide.LOW, '80.5', 10, 11),))
        state, = engine.process(bar(12, '95', '101', '94', '100'))
        self.assertEqual((state.phase, state.low_touch.price), ('WAIT_HIGH_TOUCH', D('80.5')))

    def test_a_high_touch_is_measured_on_the_range_high(self):
        engine = candidate(proximity_ratio=D('0.01'))
        engine.process(bar(9, '85', '90', '80.5', '86'), (), (raw(SwingSide.LOW, '80.5', 8, 9),))
        engine.process(bar(10, '95', '101', '94', '100'))
        engine.process(bar(11, '110', '118.5', '109', '118'), (),
                       (raw(SwingSide.HIGH, '118.5', 10, 11),))
        engine.process(bar(12, '105', '106', '99', '100'))
        self.assertEqual(engine.state.phase, 'WAIT_HIGH_TOUCH')        # 1.5 below RH > 1.2
        engine.process(bar(13, '110', '119', '109', '118'), (),
                       (raw(SwingSide.HIGH, '119', 12, 13),))
        state, = engine.process(bar(14, '105', '106', '99', '100'))
        self.assertEqual((state.phase, state.high_touch.price), ('RANGE_CONFIRMED', D('119')))

    def test_a_bad_ratio_is_rejected(self):
        for bad in (D('0'), D('1'), D('NaN'), 0.01):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                candidate(proximity_ratio=bad)


class HtfBandTests(unittest.TestCase):
    """Frame 100 .. 200; a 2% ratio is a band of 2 at 100 and 4 at 200."""

    def framed(self):
        engine = htf.context(require_zone=True, tolerance_ratio=D('0.02'))
        low, high = htf.frame_levels()
        engine.process(htf.bar(3), (low,))
        engine.process(htf.bar(5), (high,))
        return engine

    def test_the_band_scales_with_each_level(self):
        engine = self.framed()
        self.assertEqual([z.kind for z in engine.zones_touching(D('97.5'), D('98'))],
                         ['HTF_VALID_LOW'])
        self.assertEqual(engine.zones_touching(D('97'), D('97.9')), ())
        self.assertEqual([z.kind for z in engine.zones_touching(D('196'), D('196.5'))],
                         ['HTF_VALID_HIGH'])
        self.assertEqual(engine.zones_touching(D('195'), D('195.9')), ())

    def test_a_bad_ratio_is_rejected(self):
        with self.assertRaises(ValueError):
            htf.context(tolerance_ratio=D('-0.1'))


class StopBufferTests(unittest.TestCase):
    def test_the_buffer_is_measured_on_the_invalidation_price(self):
        risk = RiskEngine(RiskConfig(stop_buffer=D('100'), stop_buffer_ratio=D('0.001')))
        long_ = TradeCandidate('LONG', D('128'), D('120'), D('140'), START, (),
                               sweep_extreme=D('120'))
        short = TradeCandidate('SHORT', D('128'), D('136'), D('116'), START, (),
                               sweep_extreme=D('136'))
        self.assertEqual(risk.evaluate(long_, D('10000')).plan.stop, D('119.88'))
        self.assertEqual(risk.evaluate(short, D('10000')).plan.stop, D('136.136'))

    def test_without_a_ratio_the_absolute_buffer_is_unchanged(self):
        risk = RiskEngine(RiskConfig(stop_buffer=D('1')))
        long_ = TradeCandidate('LONG', D('128'), D('120'), D('140'), START, (),
                               sweep_extreme=D('120'))
        self.assertEqual(risk.evaluate(long_, D('10000')).plan.stop, D('119'))

    def test_a_bad_ratio_is_rejected(self):
        for bad in (D('0'), D('1'), D('-0.001')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                RiskConfig(stop_buffer_ratio=bad)


class ProfileRatioTests(unittest.TestCase):
    def test_the_ratios_are_optional_and_validated(self):
        self.assertIsNone(StrategyProfile().boundary_proximity_ratio)
        self.assertIsNone(StrategyProfile().stop_buffer_ratio)
        for name in ('boundary_proximity_ratio', 'stop_buffer_ratio'):
            for bad in (D('0'), D('1'), D('NaN')):
                with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                    StrategyProfile(**{name: bad})

    def test_the_htf_band_and_the_trail_follow_the_ratios(self):
        profile = StrategyProfile(boundary_proximity_ratio=D('0.005'), stop_buffer_ratio=D('0.001'))
        self.assertEqual(profile.effective_htf_zone_tolerance_ratio, D('0.005'))
        self.assertEqual(profile.trailing_buffer_at(D('127')), D('0.127'))
        self.assertEqual(profile.risk_config().stop_buffer_ratio, D('0.001'))
        explicit = StrategyProfile(boundary_proximity_ratio=D('0.005'), htf_zone_tolerance=D('3'),
                                   stop_buffer_ratio=D('0.001'), trailing_buffer=D('2'))
        self.assertIsNone(explicit.effective_htf_zone_tolerance_ratio)
        self.assertEqual(explicit.trailing_buffer_at(D('127')), D('2'))
        data = profile.as_dict()
        self.assertEqual((data['boundary_proximity_ratio'], data['stop_buffer_ratio']),
                         ('0.005', '0.001'))

    def test_the_view_names_the_htf_band_that_is_used(self):
        relative = StrategyProfile(boundary_proximity_ratio=D('0.005')).as_dict()
        self.assertEqual((relative['htf_zone_tolerance'], relative['htf_zone_tolerance_ratio']),
                         (None, '0.005'))
        absolute = StrategyProfile().as_dict()
        self.assertEqual((absolute['htf_zone_tolerance'], absolute['htf_zone_tolerance_ratio']),
                         ('500', None))
        explicit = StrategyProfile(boundary_proximity_ratio=D('0.005'),
                                   htf_zone_tolerance=D('3')).as_dict()
        self.assertEqual((explicit['htf_zone_tolerance'], explicit['htf_zone_tolerance_ratio']),
                         ('3', None))

    def test_the_trail_buffer_is_a_share_of_the_swing(self):
        broker, moment = open_long(scenario_profile(stop_buffer_ratio=D('0.01')))
        protect(broker, moment)
        broker.process(candle('15m', moment + 2 * STEP, 138, 139, 136, 137),
                       (confirmed_low(131, moment + 2 * STEP),))
        self.assertEqual(broker.trades[-1].stop, D('129.69'))           # 131 - 1.31

    def test_the_strategy_hands_the_ratios_to_its_engines(self):
        from agent_trading.strategy_v1 import StrategyV1
        from guide_fixtures import guide_profile
        strategy = StrategyV1('BTC-USDT', guide_profile(boundary_proximity_ratio=D('0.005'),
                                                        stop_buffer_ratio=D('0.001')))
        self.assertEqual(strategy.range.proximity_ratio, D('0.005'))
        self.assertEqual(strategy.context.tolerance_ratio, D('0.005'))
        self.assertEqual(strategy.risk.config.stop_buffer_ratio, D('0.001'))


if __name__ == '__main__':
    unittest.main()
