"""Guide 4.3/4.4 HTF context [U-RANGE-GUIDE-002]: premium/discount and confluence.

Source: docs/specs/range-trade-learning-guide.md sections 4.3 and 4.4. A lower
timeframe deviation is tradable only where it coincides with a high timeframe
zone, and only on the correct side of the high timeframe equilibrium.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest

from agent_trading.models import Candle
from agent_trading.strategy_v1.context import HtfContext
from agent_trading.swing import ConfirmedSwing, SwingSide
from agent_trading.trading_brain.models import SwingHigh, SwingLow, ValidHigh, ValidLow

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SYMBOL, TF = 'BTC-USDT', '4H'


def bar(i, o='150', h='155', l='145', c='150'):
    return Candle(SYMBOL, TF, START + timedelta(hours=4 * i), D(o), D(h), D(l), D(c), D('1'))


def raw(side, price, i, known):
    return ConfirmedSwing(SYMBOL, TF, side, D(price), bar(i).close_time,
                          bar(known).close_time, known - i, D('2'), D('2'))


def frame_levels(low='100', high='200'):
    """Valid pair 100 .. 200, so the HTF equilibrium sits at 150."""
    valid_low = ValidLow(SwingLow(raw(SwingSide.LOW, low, 2, 3)),
                         SwingHigh(raw(SwingSide.HIGH, '150', 0, 1)), bar(3).close_time)
    valid_high = ValidHigh(SwingHigh(raw(SwingSide.HIGH, high, 4, 5)),
                           valid_low.swing, bar(5).close_time)
    return valid_low, valid_high


def context(**kwargs):
    settings = dict(tolerance=D('5'), require_zone=False)
    settings.update(kwargs)
    return HtfContext(TF, **settings)


def framed(**kwargs):
    engine = context(**kwargs)
    low, high = frame_levels()
    engine.process(bar(3), (low,))
    engine.process(bar(5), (high,))
    return engine


class FrameTests(unittest.TestCase):
    def test_without_a_valid_pair_no_direction_is_allowed(self):
        engine = context()
        for direction in ('LONG', 'SHORT'):
            with self.subTest(direction=direction):
                verdict = engine.evaluate(direction, D('150'))
                self.assertFalse(verdict.allowed)
                self.assertEqual(verdict.reason, 'NO_HTF_FRAME')
                self.assertIsNone(verdict.region)

    def test_the_frame_is_the_current_valid_pair_and_its_midpoint(self):
        engine = framed()
        self.assertEqual(engine.frame, (D('100'), D('200'), D('150')))

    def test_the_region_splits_the_frame_at_equilibrium(self):
        engine = framed()
        self.assertEqual(engine.region(D('149')), 'DISCOUNT')
        self.assertEqual(engine.region(D('150')), 'EQUILIBRIUM')
        self.assertEqual(engine.region(D('151')), 'PREMIUM')
        # Guide 4.4 reads the price against equilibrium, not against the edges.
        self.assertEqual(engine.region(D('99')), 'DISCOUNT')
        self.assertEqual(engine.region(D('201')), 'PREMIUM')


class PremiumDiscountTests(unittest.TestCase):
    def test_a_long_in_premium_is_refused(self):
        verdict = framed().evaluate('LONG', D('151'))
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.reason, 'PREMIUM_BLOCKS_LONG')
        self.assertEqual((verdict.region, verdict.eq), ('PREMIUM', D('150')))

    def test_a_long_at_or_below_equilibrium_is_allowed(self):
        for price in ('150', '120'):
            with self.subTest(price=price):
                verdict = framed().evaluate('LONG', D(price))
                self.assertTrue(verdict.allowed)
                self.assertEqual(verdict.reason, 'HTF_CONTEXT_OK')

    def test_a_short_in_premium_is_allowed(self):
        verdict = framed().evaluate('SHORT', D('180'))
        self.assertTrue(verdict.allowed)

    def test_a_short_in_discount_needs_broken_market_structure(self):
        engine = framed()
        verdict = engine.evaluate('SHORT', D('120'))
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.reason, 'DISCOUNT_BLOCKS_SHORT')
        allowed = engine.evaluate('SHORT', D('120'), structure_bearish=True)
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.reason, 'HTF_CONTEXT_OK')

    def test_an_unknown_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            framed().evaluate('BOTH', D('120'))


class ZoneTests(unittest.TestCase):
    def _with_gap(self, **kwargs):
        """Quiet 4H bars, then a displacement leaving an unfilled gap 127 .. 135."""
        engine = context(require_zone=True, **kwargs)
        low, high = frame_levels()
        engine.process(bar(3, '125', '127', '123', '125'), (low,))
        engine.process(bar(5, '125', '127', '123', '125'), (high,))
        engine.process(bar(6, '125', '127', '123', '125'))
        engine.process(bar(7, '125', '127', '123', '126'))
        engine.process(bar(8, '126', '140', '126', '139'))
        engine.process(bar(9, '139', '145', '135', '144'))
        return engine

    def test_a_span_that_touches_nothing_is_refused(self):
        engine = self._with_gap()
        verdict = engine.evaluate('LONG', D('150'), span=(D('150'), D('152')))
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.reason, 'NO_HTF_ZONE')
        self.assertEqual(verdict.zones, ())

    def test_an_unfilled_htf_gap_is_a_zone(self):
        engine = self._with_gap()
        verdict = engine.evaluate('LONG', D('130'), span=(D('130'), D('131')))
        self.assertTrue(verdict.allowed)
        self.assertEqual([z.kind for z in verdict.zones], ['HTF_FVG'])
        self.assertEqual((verdict.zones[0].lower, verdict.zones[0].upper), (D('127'), D('135')))

    def test_a_gap_traded_through_stops_being_a_zone(self):
        engine = self._with_gap()
        engine.process(bar(10, '144', '145', '125', '126'))      # trades through 127
        verdict = engine.evaluate('LONG', D('130'), span=(D('130'), D('131')))
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.reason, 'NO_HTF_ZONE')

    def test_a_frame_boundary_within_tolerance_is_a_zone(self):
        engine = self._with_gap()
        verdict = engine.evaluate('LONG', D('96'), span=(D('96'), D('98')))
        self.assertTrue(verdict.allowed)
        self.assertEqual([z.kind for z in verdict.zones], ['HTF_VALID_LOW'])

    def test_the_zone_requirement_can_be_switched_off(self):
        engine = self._with_gap()
        self.assertFalse(engine.evaluate('LONG', D('150'), span=(D('150'), D('152'))).allowed)
        engine.require_zone = False
        self.assertTrue(engine.evaluate('LONG', D('150'), span=(D('150'), D('152'))).allowed)


if __name__ == '__main__':
    unittest.main()
