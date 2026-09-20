"""Guide rules [U-RANGE-GUIDE-001]: deviation limit, body-close invalidation, EQ visits.

Source: docs/specs/range-trade-learning-guide.md sections 3.2, 4.1 and 4.2.
The frozen candidate is 80 .. 120, so EQ is 100 and the default deviation limit
is 50% of (RH - EQ) = 10, i.e. bodies may close down to 70 or up to 130.
"""
from decimal import Decimal as D
import unittest

from test_trading_brain import bar, pair, raw
from agent_trading.swing import SwingSide
from agent_trading.trading_brain import RangeEngine


def candidate(**kwargs):
    engine = RangeEngine(D('2'), **kwargs)
    low, high = pair()
    engine.process(bar(4), (low,), ())
    engine.process(bar(7), (high,), ())
    return engine


def confirmed(**kwargs):
    engine = candidate(**kwargs)
    engine.process(bar(9, '85', '90', '81', '86'), (), (raw(SwingSide.LOW, '81', 8, 9),))
    engine.process(bar(10, '95', '101', '94', '100'))
    engine.process(bar(11, '110', '119', '109', '118'), (), (raw(SwingSide.HIGH, '119', 10, 11),))
    engine.process(bar(12, '105', '106', '99', '100'))
    return engine


class DeviationLimitTests(unittest.TestCase):
    def test_a_wick_through_a_boundary_is_a_sweep_not_an_invalidation(self):
        for label, candle in (('below', bar(10, '100', '105', '70.1', '100')),
                              ('above', bar(10, '100', '129.9', '95', '100'))):
            with self.subTest(side=label):
                engine = candidate()
                self.assertEqual(engine.process(candle), ())
                self.assertEqual(engine.state.phase, 'WAIT_LOW_TOUCH')

    def test_a_body_closing_inside_the_deviation_band_keeps_the_candidate(self):
        for label, candle in (('below', bar(10, '100', '105', '69', '70.1')),
                              ('above', bar(10, '100', '131', '95', '129.9'))):
            with self.subTest(side=label):
                engine = candidate()
                self.assertEqual(engine.process(candle), ())
                self.assertEqual(engine.state.phase, 'WAIT_LOW_TOUCH')

    def test_a_body_beyond_the_deviation_limit_invalidates_the_candidate(self):
        cases = ((bar(10, '100', '105', '69', '69.9'), ('BODY_CLOSE_BELOW_DEVIATION_LIMIT',)),
                 (bar(10, '100', '131', '95', '130.1'), ('BODY_CLOSE_ABOVE_DEVIATION_LIMIT',)))
        for candle, reasons in cases:
            with self.subTest(reasons=reasons):
                engine = candidate()
                invalidated, = engine.process(candle)
                self.assertEqual(invalidated.phase, 'RANGE_INVALIDATED')
                self.assertEqual(invalidated.invalidation_reasons, reasons)
                self.assertEqual(invalidated.invalidation_candle, candle)
                self.assertEqual((invalidated.range_low, invalidated.range_high), (D('80'), D('120')))
                self.assertIsNone(invalidated.confirmed_at)

    def test_the_deviation_ratio_is_configurable(self):
        engine = candidate(deviation_ratio=D('0'))
        invalidated, = engine.process(bar(10, '100', '105', '79', '79.9'))
        self.assertEqual(invalidated.phase, 'RANGE_INVALIDATED')
        engine = candidate(deviation_ratio=D('1'))
        self.assertEqual(engine.process(bar(10, '100', '105', '61', '61')), ())


class TouchAndEqVisitTests(unittest.TestCase):
    def test_a_touch_counts_only_after_price_returns_to_eq(self):
        engine = candidate()
        self.assertEqual(engine.process(bar(9, '85', '90', '81', '86'), (),
                                        (raw(SwingSide.LOW, '81', 8, 9),)), ())
        self.assertEqual(engine.state.phase, 'WAIT_LOW_TOUCH')
        self.assertEqual(engine.process(bar(10, '90', '95', '85', '92')), ())
        state, = engine.process(bar(11, '95', '101', '94', '100'))
        self.assertEqual(state.phase, 'WAIT_HIGH_TOUCH')
        self.assertEqual(state.low_touch.price, D('81'))

    def test_confirmation_needs_the_high_touch_and_its_own_eq_visit(self):
        engine = candidate()
        engine.process(bar(9, '85', '90', '81', '86'), (), (raw(SwingSide.LOW, '81', 8, 9),))
        engine.process(bar(10, '95', '101', '94', '100'))
        self.assertEqual(engine.process(bar(11, '110', '119', '109', '118'), (),
                                        (raw(SwingSide.HIGH, '119', 10, 11),)), ())
        self.assertEqual(engine.state.phase, 'WAIT_HIGH_TOUCH')
        state, = engine.process(bar(12, '105', '106', '99', '100'))
        self.assertEqual(state.phase, 'RANGE_CONFIRMED')
        self.assertEqual(state.confirmed_at, bar(12).close_time)
        self.assertEqual(state.high_touch.price, D('119'))

    def test_the_eq_visit_requirement_can_be_switched_off(self):
        engine = candidate(require_eq_visit=False)
        state, = engine.process(bar(9, '85', '90', '81', '86'), (), (raw(SwingSide.LOW, '81', 8, 9),))
        self.assertEqual(state.phase, 'WAIT_HIGH_TOUCH')


class ConfirmedRangeTests(unittest.TestCase):
    def test_a_confirmed_range_survives_sweeps_and_retires_on_a_breakout_body(self):
        engine = confirmed(allow_retire=True)
        self.assertEqual(engine.state.phase, 'RANGE_CONFIRMED')
        self.assertEqual(engine.process(bar(13, '100', '105', '70.5', '100')), ())
        self.assertEqual(engine.state.phase, 'RANGE_CONFIRMED')
        retired, = engine.process(bar(14, '100', '105', '69', '69.5'))
        self.assertEqual(retired.phase, 'RANGE_RETIRED')
        self.assertEqual(retired.invalidation_reasons, ('BODY_CLOSE_BELOW_DEVIATION_LIMIT',))


if __name__ == '__main__':
    unittest.main()
