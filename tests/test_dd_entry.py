"""[U-DD-DEVIATION-001] DD model 1 (CHoCH) and model 2 (HTF FVG), end to end."""
import unittest

from dd_fixtures import (DD, both_ready_long_candles, model_one_long_candles,
                         model_one_short_candles, model_two_long_candles, run_dd)
from strategy_v1_fixtures import (D, acceptance_candles, events_of, first_event,
                                  run_scenario, scenario_profile)


class ModelOneLongTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strategy = run_dd(model_one_long_candles())
        cls.trade = cls.strategy.broker.trades[0]

    def test_the_choch_breaks_the_last_swing_high_before_the_sweep(self):
        choch = first_event(self.strategy, 'CHOCH_CONFIRMED').payload
        self.assertEqual((choch.direction, choch.level, choch.extreme),
                         ('LONG', D('129'), D('112')))
        self.assertEqual((choch.extreme_at.strftime('%H:%M'),
                          choch.confirmed_at.strftime('%H:%M')), ('13:00', '15:30'))

    def test_one_model_one_trade_enters_at_the_gap_the_break_left(self):
        self.assertEqual(len(self.strategy.broker.trades), 1)
        pending = first_event(self.strategy, 'PENDING_ENTRY')
        self.assertEqual(pending.observed_at.strftime('%H:%M'), '15:45')
        plan = pending.payload
        self.assertEqual(plan.entry_model, 'CHOCH_FVG')
        self.assertEqual((plan.primary.lower, plan.primary.upper, plan.range_eq),
                         (D('126'), D('130'), D('144')))
        self.assertEqual(self.trade.entry, D('128'))

    def test_the_stop_sits_behind_the_deviation_wick(self):
        self.assertEqual(self.trade.approved_plan.stop, D('111'))
        self.assertEqual(first_event(self.strategy, 'ENTRY_PLAN').payload.stop_source,
                         'MANIPULATION_SWEEP_LOW')

    def test_thirty_percent_at_eq_fifty_at_the_boundary_and_the_runner_trails_out(self):
        self.assertEqual([(x.kind, x.exit_price, x.quantity) for x in self.trade.ledger.exits],
                         [('RANGE_EQ', D('144'), D('1.76470588')),
                          ('RANGE_HIGH', D('170'), D('2.94117648')),
                          ('RUNNER', D('160'), D('1.17647058'))])

    def test_break_even_comes_from_eq_then_the_stop_trails_the_trades_own_lows(self):
        self.assertEqual([(u.reason, u.new_stop) for u in self.trade.stop_updates],
                         [('RANGE_EQ_BREAK_EVEN', D('128')), ('STRUCTURAL_TRAIL', D('130.5')),
                          ('STRUCTURAL_TRAIL', D('140')), ('STRUCTURAL_TRAIL', D('160'))])

    def test_the_trade_closes_in_profit(self):
        self.assertEqual(self.trade.status, 'CLOSED')
        self.assertEqual(self.strategy.broker.equity, D('10189.4117648'))


class ModelOneShortTests(unittest.TestCase):
    def test_a_model_one_short_mirrors_the_long(self):
        strategy = run_dd(model_one_short_candles())
        trade = strategy.broker.trades[0]
        self.assertEqual(first_event(strategy, 'PENDING_ENTRY').payload.entry_model, 'CHOCH_FVG')
        self.assertEqual((trade.direction, trade.entry, trade.approved_plan.stop),
                         ('SHORT', D('160'), D('177')))
        self.assertEqual([(x.kind, x.exit_price, x.quantity) for x in trade.ledger.exits],
                         [('RANGE_EQ', D('144'), D('1.76470588')),
                          ('RANGE_LOW', D('118'), D('2.94117648')),
                          ('RUNNER', D('128'), D('1.17647058'))])
        self.assertEqual(strategy.broker.equity, D('10189.4117648'))


class ModelTwoTests(unittest.TestCase):
    def test_without_an_htf_fvg_model_two_takes_nothing(self):
        strategy = run_dd(model_one_long_candles(), entry_models=('HTF_FVG_REVERSAL',))
        verdict = first_event(strategy, 'HTF_CONTEXT').payload
        self.assertTrue(verdict.allowed)
        self.assertNotIn('HTF_FVG', [zone.kind for zone in verdict.zones])
        self.assertEqual(events_of(strategy, 'PENDING_ENTRY'), ())

    def test_a_sweep_into_an_htf_fvg_trades_the_first_reversal_gap(self):
        strategy = run_dd(model_two_long_candles())
        verdict = first_event(strategy, 'HTF_CONTEXT').payload
        self.assertIn('HTF_FVG', [zone.kind for zone in verdict.zones])
        pending = first_event(strategy, 'PENDING_ENTRY')
        self.assertEqual((pending.payload.entry_model, pending.observed_at.strftime('%H:%M')),
                         ('HTF_FVG_REVERSAL', '15:45'))
        self.assertGreater(first_event(strategy, 'CHOCH_CONFIRMED').observed_at,
                           pending.observed_at)
        trade = strategy.broker.trades[0]
        self.assertEqual((trade.entry, trade.approved_plan.stop), (D('128'), D('111')))

    def test_when_both_are_ready_on_one_bar_model_one_is_tried_first(self):
        strategy = run_dd(both_ready_long_candles())
        self.assertEqual([e.payload.entry_model for e in events_of(strategy, 'PENDING_ENTRY')],
                         ['CHOCH_FVG'])

    def test_the_old_gate_keeps_the_pre_dd_entry(self):
        profile = scenario_profile(**dict(DD, entry_models=('HTF_FVG_REVERSAL',)))
        strategy = run_scenario(profile=profile, candles=acceptance_candles())
        self.assertFalse(profile.effective_model2_requires_htf_fvg)
        self.assertEqual(first_event(strategy, 'PENDING_ENTRY').payload.entry_model,
                         'HTF_FVG_REVERSAL')

    def test_model_one_alone_ignores_the_reversal_gap(self):
        strategy = run_dd(model_two_long_candles(), entry_models=('CHOCH_FVG',))
        pending = first_event(strategy, 'PENDING_ENTRY')
        self.assertEqual((pending.payload.entry_model, pending.observed_at.strftime('%H:%M')),
                         ('CHOCH_FVG', '16:45'))


if __name__ == '__main__':
    unittest.main()
