"""[U-DD-DEVIATION-001] DD trade management on the broker alone.

30% of the original position closes at the range EQ and the stop moves to entry;
the opposite boundary closes 50%; the last 20% is trailed. A short is the long
reflected about its 128 entry, so every check runs both ways.
"""
import unittest
from decimal import Decimal as D

from agent_trading.market import bar_duration
from agent_trading.trading_brain.models import FVG, TradeCandidate
from agent_trading.trading_brain.risk import RiskEngine
from agent_trading.strategy_v1 import PendingLimitPaperBroker
from agent_trading.strategy_v1.models import EntryPlan, TrackedFvg

from strategy_v1_fixtures import SYMBOL, bias_candles, candle, scenario_profile

STEP = bar_duration('15m')
AXIS = D('256')
SIDES = ('LONG', 'SHORT')
DD = dict(direction='BOTH', eq_scale_out_fraction=D('0.30'), break_even_trigger='RANGE_EQ',
          runner_fraction=D('0.20'), secondary_fvg_support_enabled=False)


def price(side, value):
    value = D(str(value))
    return value if side == 'LONG' else AXIS - value


def bar(side, moment, open_, high, low, close):
    """A long-shaped bar; for a short it is reflected, so high and low swap."""
    if side == 'LONG':
        return candle('15m', moment, open_, high, low, close)
    return candle('15m', moment, price(side, open_), price(side, low),
                  price(side, high), price(side, close))


def boundary_kind(side):
    return 'RANGE_HIGH' if side == 'LONG' else 'RANGE_LOW'


def open_trade(side='LONG', eq=140, **overrides):
    """Fill a RiskEngine-approved DD plan at 128.

    Long: sweep 119, stop 118, boundary 160, range EQ 140. R is 10, quantity 10.
    Short: the same prices reflected about 256 (stop 138, boundary 96, EQ 116).
    """
    settings = dict(DD)
    settings.update(overrides)
    profile = scenario_profile(**settings)
    risk = RiskEngine(profile.risk_config())
    broker = PendingLimitPaperBroker(risk, D('10000'), profile)
    start = bias_candles()[0].close_time
    gap = FVG(side, D('126'), D('130'), (start, start, start), start)
    candidate = TradeCandidate(side, D('128'), price(side, 119), price(side, 160), start, (),
                               sweep_extreme=price(side, 119))
    decision = risk.evaluate(candidate, D('10000'), (), symbol=SYMBOL, timeframe='15m')
    assert decision.plan is not None, 'DD management fixture must be approvable'
    plan = EntryPlan(TrackedFvg('p1', gap), 'FVG_EQ', D('128'), price(side, 160),
                     'MANIPULATION_SWEEP_LOW' if side == 'LONG' else 'MANIPULATION_SWEEP_HIGH',
                     None, None, None, start,
                     range_eq=None if eq is None else price(side, eq), entry_model='CHOCH_FVG')
    broker.submit(decision.plan, plan)
    broker.process(bar(side, start + STEP, 129, 129.5, 128, 128.5))
    assert broker.trades[-1].status == 'OPEN'
    return broker, start + STEP


def kinds(events):
    return [event.kind for event in events]


class EqScaleOutTests(unittest.TestCase):
    def test_thirty_percent_closes_at_the_range_eq(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                events = broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                record = next(e.payload for e in events if e.kind == 'RANGE_EQ_PARTIAL_EXIT')
                self.assertEqual(record.kind, 'RANGE_EQ')
                self.assertEqual((record.exit_price, record.target_price),
                                 (price(side, 140), price(side, 140)))
                self.assertEqual((record.quantity, record.remaining_quantity), (D('3'), D('7')))
                self.assertEqual(record.realized_pnl, D('36'))

    def test_eq_moves_the_stop_to_entry_and_announces_break_even(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                events = broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                trade = broker.trades[-1]
                self.assertEqual(trade.stop, D('128'))
                self.assertEqual(trade.stop_updates[-1].reason, 'RANGE_EQ_BREAK_EVEN')
                protected = next(e.payload for e in events if e.kind == 'BREAK_EVEN_PROTECTED')
                self.assertEqual(protected.structural_reference, 'RANGE_EQ_BREAK_EVEN')

    def test_one_r_alone_no_longer_moves_the_stop(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                events = broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                self.assertEqual(broker.trades[-1].stop, price(side, 118))
                self.assertNotIn('BREAK_EVEN_PROTECTED', kinds(events))

    def test_the_boundary_closes_half_and_leaves_a_twenty_percent_runner(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                events = broker.process(bar(side, moment + 2 * STEP, 140.5, 161, 140, 160.5))
                ledger = broker.trades[-1].ledger
                self.assertEqual([(x.kind, x.quantity) for x in ledger.exits],
                                 [('RANGE_EQ', D('3')), (boundary_kind(side), D('5'))])
                self.assertEqual(ledger.remaining_quantity, D('2'))
                self.assertIn('RUNNER_OPEN', kinds(events))

    def test_one_bar_through_eq_and_the_boundary_books_eq_first(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                broker.process(bar(side, moment + STEP, 130, 161, 129, 160))
                trade = broker.trades[-1]
                self.assertEqual([(x.kind, x.quantity) for x in trade.ledger.exits],
                                 [('RANGE_EQ', D('3')), (boundary_kind(side), D('5'))])
                self.assertEqual(trade.stop, D('128'))

    def test_an_eq_outside_the_trade_is_skipped_and_break_even_waits_for_the_boundary(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side, eq=125)        # behind the entry
                events = broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                self.assertNotIn('RANGE_EQ_PARTIAL_EXIT', kinds(events))
                self.assertEqual(broker.trades[-1].stop, price(side, 118))
                broker.process(bar(side, moment + 2 * STEP, 140.5, 161, 140, 160.5))
                trade = broker.trades[-1]
                self.assertEqual([(x.kind, x.quantity) for x in trade.ledger.exits],
                                 [(boundary_kind(side), D('8'))])
                self.assertEqual(trade.stop, D('128'))
                self.assertEqual(trade.stop_updates[-1].reason, 'RANGE_EQ_BREAK_EVEN')

    def test_without_an_eq_slice_eq_still_protects_the_entry(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side, eq_scale_out_fraction=None)
                events = broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                self.assertNotIn('RANGE_EQ_PARTIAL_EXIT', kinds(events))
                self.assertIn('BREAK_EVEN_PROTECTED', kinds(events))
                self.assertEqual(broker.trades[-1].stop, D('128'))

    def test_the_legacy_trigger_keeps_the_one_r_break_even(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side, break_even_trigger='R_MULTIPLE',
                                            eq_scale_out_fraction=None,
                                            runner_fraction=D('0.10'))
                broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                trade = broker.trades[-1]
                self.assertEqual((trade.stop, trade.stop_updates[-1].reason),
                                 (D('128'), 'BREAK_EVEN'))


if __name__ == '__main__':
    unittest.main()
