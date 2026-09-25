"""[U-RR-TRAIL-001] The R ladder: break-even at 1R (or EQ), 30% at 2R.

It works independently of EQ and the boundary, which keep closing their own
parts. Long: entry 128, stop 118, R 10, quantity 10; a short is the long
reflected about 256, so every check runs both ways.
"""
import unittest
from decimal import Decimal as D

from agent_trading.market import bar_duration
from agent_trading.trading_brain.models import FVG, TradeCandidate
from agent_trading.trading_brain.risk import RiskEngine
from agent_trading.strategy_v1 import PendingLimitPaperBroker, StrategyProfile
from agent_trading.strategy_v1.config import BREAK_EVEN_TRIGGERS, PartialTakeProfit
from agent_trading.strategy_v1.models import EntryPlan, TrackedFvg

from strategy_v1_fixtures import SYMBOL, bias_candles, scenario_profile
from test_dd_management import SIDES, bar, price

STEP = bar_duration('15m')
LADDER = dict(direction='BOTH', eq_scale_out_fraction=D('0.30'),
              break_even_trigger='EQ_OR_R_MULTIPLE', runner_fraction=D('0.20'),
              secondary_fvg_support_enabled=False,
              partial_take_profits=({'r_multiple': '2', 'close_fraction': '0.30'},))


def open_ladder(side='LONG', eq=150, target=160, **overrides):
    """Fill a RiskEngine-approved plan at 128 with the given EQ and boundary."""
    settings = dict(LADDER)
    settings.update(overrides)
    profile = scenario_profile(**settings)
    risk = RiskEngine(profile.risk_config())
    broker = PendingLimitPaperBroker(risk, D('10000'), profile)
    start = bias_candles()[0].close_time
    gap = FVG(side, D('126'), D('130'), (start, start, start), start)
    cand = TradeCandidate(side, D('128'), price(side, 119), price(side, target), start, (),
                          sweep_extreme=price(side, 119))
    decision = risk.evaluate(cand, D('10000'), (), symbol=SYMBOL, timeframe='15m')
    assert decision.plan is not None, 'ladder fixture must be approvable'
    plan = EntryPlan(TrackedFvg('p1', gap), 'FVG_EQ', D('128'), price(side, target),
                     'MANIPULATION_SWEEP_LOW' if side == 'LONG' else 'MANIPULATION_SWEEP_HIGH',
                     None, None, None, start, range_eq=price(side, eq), entry_model='CHOCH_FVG')
    broker.submit(decision.plan, plan)
    broker.process(bar(side, start + STEP, 129, 129.5, 128, 128.5))
    assert broker.trades[-1].status == 'OPEN'
    return broker, start + STEP


def exits(broker):
    return [(x.kind, x.quantity, x.exit_price) for x in broker.trades[-1].ledger.exits]


def boundary_kind(side):
    return 'RANGE_HIGH' if side == 'LONG' else 'RANGE_LOW'


class LadderTests(unittest.TestCase):
    def test_one_r_moves_the_stop_to_entry_before_eq(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side)
                events = broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                trade = broker.trades[-1]
                self.assertEqual((trade.stop, trade.stop_updates[-1].reason),
                                 (D('128'), 'BREAK_EVEN'))
                self.assertIn('BREAK_EVEN_PROTECTED', [e.kind for e in events])
                self.assertEqual(exits(broker), [])

    def test_two_r_closes_thirty_percent_of_the_original(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side)
                broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                events = broker.process(bar(side, moment + 2 * STEP, 138, 148.5, 137, 148))
                self.assertEqual(exits(broker), [('PARTIAL_TP', D('3'), price(side, 148))])
                self.assertIn('PARTIAL_TP_FILLED', [e.kind for e in events])

    def test_a_trade_that_reached_two_r_and_fell_back_ends_in_profit(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side)
                broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                broker.process(bar(side, moment + 2 * STEP, 138, 148.5, 137, 148))
                broker.process(bar(side, moment + 3 * STEP, 140, 141, 127, 127.5))
                trade = broker.trades[-1]
                self.assertEqual(exits(broker), [('PARTIAL_TP', D('3'), price(side, 148)),
                                                 ('STOP', D('7'), D('128'))])
                self.assertEqual((trade.status, trade.ledger.total_realized_pnl),
                                 ('CLOSED', D('60')))

    def test_eq_and_the_boundary_still_close_their_parts(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side)
                broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                broker.process(bar(side, moment + 2 * STEP, 138, 148.5, 137, 148))
                broker.process(bar(side, moment + 3 * STEP, 148, 150.5, 147, 150))
                events = broker.process(bar(side, moment + 4 * STEP, 150, 160.5, 149, 160))
                self.assertEqual(exits(broker), [('PARTIAL_TP', D('3'), price(side, 148)),
                                                 ('RANGE_EQ', D('3'), price(side, 150)),
                                                 (boundary_kind(side), D('2'), price(side, 160))])
                self.assertEqual(broker.trades[-1].ledger.remaining_quantity, D('2'))
                self.assertIn('RUNNER_OPEN', [e.kind for e in events])

    def test_eq_before_one_r_protects_the_entry_at_eq(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side, eq=133)
                broker.process(bar(side, moment + STEP, 130, 133.5, 129, 133))
                trade = broker.trades[-1]
                self.assertEqual(exits(broker), [('RANGE_EQ', D('3'), price(side, 133))])
                self.assertEqual((trade.stop, trade.stop_updates[-1].reason),
                                 (D('128'), 'RANGE_EQ_BREAK_EVEN'))

    def test_a_two_r_level_beyond_the_boundary_is_left_to_the_boundary_exit(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side, eq=136, target=145)
                broker.process(bar(side, moment + STEP, 130, 145.5, 129, 145))
                self.assertEqual([kind for kind, _q, _p in exits(broker)],
                                 ['RANGE_EQ', boundary_kind(side)])


class LadderDefaultTests(unittest.TestCase):
    def test_the_ladder_is_the_default(self):
        profile = StrategyProfile()
        self.assertIn('EQ_OR_R_MULTIPLE', BREAK_EVEN_TRIGGERS)
        self.assertEqual(profile.break_even_trigger, 'EQ_OR_R_MULTIPLE')
        self.assertEqual(profile.break_even_r, D('1'))
        self.assertEqual(profile.partial_take_profits, (PartialTakeProfit(D('2'), D('0.30')),))


if __name__ == '__main__':
    unittest.main()
