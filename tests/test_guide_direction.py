"""Guide 4.3/4.4 direction gate inside Strategy V1 [U-RANGE-GUIDE-002].

The scenario is the shipped 1H/15m price action under a 4H dealing range of
120 .. 200. Its equilibrium is 160, so the sweep to 112 is a discount
deviation that lands on the 4H Valid Low. The superseded gate would refuse it:
the 4H structure is bearish there and `long_permission` is False.
"""
from decimal import Decimal as D
import unittest

from guide_fixtures import (ACCEPTANCE_AXIS, RANGE_AXIS, guide_acceptance_candles,
                            guide_acceptance_profile, guide_bias_candles, guide_profile,
                            long_candles, low_frame_bias_candles, run_guide,
                            short_acceptance_candles, short_candles)
from strategy_v1_fixtures import entry_candles, first_event, range_candles


class GuideLongTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strategy = run_guide()

    def test_the_htf_verdict_is_recorded_with_the_manipulation(self):
        event = first_event(self.strategy, 'HTF_CONTEXT')
        self.assertIsNotNone(event)
        verdict = event.payload
        self.assertEqual((verdict.direction, verdict.allowed, verdict.region),
                         ('LONG', True, 'DISCOUNT'))
        self.assertEqual((verdict.frame_low, verdict.frame_high, verdict.eq),
                         (D('120'), D('200'), D('160')))
        self.assertEqual([zone.kind for zone in verdict.zones], ['HTF_VALID_LOW'])
        self.assertEqual(event.observed_at,
                         first_event(self.strategy, 'MANIPULATION_CONFIRMED').observed_at)

    def test_a_discount_long_no_longer_needs_the_bias_permission(self):
        self.assertFalse(self.strategy.bias.long_permission)
        self.assertEqual(len(self.strategy.broker.trades), 1)
        self.assertEqual(self.strategy.broker.trades[0].direction, 'LONG')

    def test_the_trade_keeps_the_shipped_geometry(self):
        plan = first_event(self.strategy, 'ENTRY_PLAN').payload
        self.assertEqual(plan.entry_price, D('128'))
        self.assertEqual(plan.target, D('140'))

    def test_a_premium_long_is_refused(self):
        strategy = run_guide(candles=low_frame_bias_candles() + range_candles()
                             + entry_candles())
        verdict = first_event(strategy, 'HTF_CONTEXT').payload
        self.assertFalse(verdict.allowed)
        self.assertEqual((verdict.reason, verdict.region), ('PREMIUM_BLOCKS_LONG', 'PREMIUM'))
        self.assertEqual(strategy.broker.trades, ())
        self.assertIsNone(first_event(strategy, 'TRADE_CANDIDATE'))

    def test_a_deviation_that_touches_no_htf_zone_is_refused(self):
        strategy = run_guide(profile=guide_profile(htf_zone_tolerance=D('0.5')))
        verdict = first_event(strategy, 'HTF_CONTEXT').payload
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.reason, 'NO_HTF_ZONE')
        self.assertEqual(strategy.broker.trades, ())

    def test_the_confluence_requirement_can_be_switched_off(self):
        strategy = run_guide(profile=guide_profile(htf_zone_tolerance=D('0.5'),
                                                   htf_confluence_required=False))
        self.assertTrue(first_event(strategy, 'HTF_CONTEXT').payload.allowed)
        self.assertEqual(len(strategy.broker.trades), 1)

    def test_the_superseded_gate_refuses_the_same_scenario(self):
        strategy = run_guide(profile=guide_profile(direction='LONG_ONLY',
                                                   direction_gate='BIAS_LONG_PERMISSION'))
        self.assertIsNone(first_event(strategy, 'HTF_CONTEXT'))
        self.assertEqual(strategy.broker.trades, ())

    def test_a_long_only_profile_still_takes_the_discount_long(self):
        strategy = run_guide(profile=guide_profile(direction='LONG_ONLY'))
        self.assertEqual(len(strategy.broker.trades), 1)

    def test_a_short_only_profile_takes_nothing_here(self):
        strategy = run_guide(profile=guide_profile(direction='SHORT_ONLY'))
        self.assertEqual(strategy.broker.trades, ())
        self.assertIsNone(first_event(strategy, 'HTF_CONTEXT'))


class GuideBiasContextTests(unittest.TestCase):
    def test_the_context_follows_the_bias_timeframe(self):
        strategy = run_guide(candles=guide_bias_candles())
        self.assertEqual(strategy.context.frame, (D('120'), D('200'), D('160')))
        self.assertEqual(strategy.context.timeframe, strategy.roles.bias)

    def test_the_superseded_gate_builds_no_context(self):
        strategy = run_guide(candles=guide_bias_candles(),
                             profile=guide_profile(direction='LONG_ONLY',
                                                   direction_gate='BIAS_LONG_PERMISSION'))
        self.assertIsNone(strategy.context)


# ------------------------------------------------------------------- SHORT
class GuideShortTests(unittest.TestCase):
    """The same range, swept upwards: the premium mirror of the long setup.

    The 15m stream is the long scenario reflected about the range axis, so
    every price the short run touches is `RANGE_AXIS` minus its long twin.
    """

    @classmethod
    def setUpClass(cls):
        cls.strategy = run_guide(candles=short_candles())
        cls.long = run_guide()

    def test_the_range_is_the_shipped_one(self):
        state = first_event(self.strategy, 'RANGE_CONFIRMED').payload
        self.assertEqual((state.range_low, state.range_high, state.eq),
                         (D('118'), D('140'), D('129')))

    def test_the_manipulation_sweeps_above_the_range_high(self):
        change = first_event(self.strategy, 'MANIPULATION_CONFIRMED').payload
        self.assertEqual((change.direction, change.extreme), ('SHORT', D('146')))

    def test_the_htf_context_allows_a_premium_short(self):
        verdict = first_event(self.strategy, 'HTF_CONTEXT').payload
        self.assertEqual((verdict.direction, verdict.allowed, verdict.region),
                         ('SHORT', True, 'PREMIUM'))
        self.assertEqual((verdict.frame_low, verdict.frame_high, verdict.eq),
                         (D('84'), D('140'), D('112')))
        self.assertEqual([zone.kind for zone in verdict.zones], ['HTF_VALID_HIGH'])

    def test_the_short_plan_mirrors_the_long_plan(self):
        plan = first_event(self.strategy, 'ENTRY_PLAN').payload
        reference = first_event(self.long, 'ENTRY_PLAN').payload
        self.assertEqual(plan.entry_price, RANGE_AXIS - reference.entry_price)
        self.assertEqual(plan.target, RANGE_AXIS - reference.target)
        self.assertEqual(plan.entry_level, reference.entry_level)
        self.assertEqual(plan.stop_source, reference.stop_source)

    def test_the_short_trade_mirrors_the_long_trade(self):
        trade, reference = self.strategy.broker.trades[0], self.long.broker.trades[0]
        self.assertEqual(trade.direction, 'SHORT')
        self.assertEqual(trade.entry, RANGE_AXIS - reference.entry)
        self.assertEqual(trade.stop, RANGE_AXIS - reference.stop)
        self.assertEqual(trade.tp, RANGE_AXIS - reference.tp)
        self.assertGreater(trade.approved_plan.stop, trade.entry)
        self.assertLess(trade.tp, trade.entry)
        self.assertEqual(trade.quantity, reference.quantity)

    def test_the_short_target_is_the_frozen_range_low(self):
        state = first_event(self.strategy, 'RANGE_CONFIRMED').payload
        self.assertEqual(self.strategy.broker.trades[0].tp, state.range_low)

    def test_the_short_run_ends_with_the_same_equity(self):
        self.assertEqual(self.strategy.broker.equity, self.long.broker.equity)
        self.assertEqual(self.strategy.counts['PAPER_ORDER_OPENED'],
                         self.long.counts['PAPER_ORDER_OPENED'])

    def test_a_long_only_profile_refuses_the_premium_short(self):
        strategy = run_guide(candles=short_candles(),
                             profile=guide_profile(direction='LONG_ONLY'))
        self.assertEqual(strategy.broker.trades, ())
        self.assertIsNone(first_event(strategy, 'HTF_CONTEXT'))

    def test_the_superseded_gate_can_never_take_this_setup(self):
        strategy = run_guide(candles=short_candles(),
                             profile=guide_profile(direction='LONG_ONLY',
                                                   direction_gate='BIAS_LONG_PERMISSION'))
        self.assertEqual(strategy.broker.trades, ())


class GuideShortExitTests(unittest.TestCase):
    """Partials, break-even, trailing, boundary exit and runner, mirrored."""

    @classmethod
    def setUpClass(cls):
        cls.long = run_guide(candles=guide_acceptance_candles(),
                             profile=guide_acceptance_profile())
        cls.strategy = run_guide(candles=short_acceptance_candles(),
                                 profile=guide_acceptance_profile())

    def test_the_long_reference_run_still_works_on_the_guide_gate(self):
        self.assertEqual(len(self.long.broker.trades), 1)
        self.assertEqual(self.long.broker.trades[0].direction, 'LONG')

    def test_every_realised_slice_mirrors_its_long_counterpart(self):
        ledger = self.strategy.broker.trades[0].ledger
        reference = self.long.broker.trades[0].ledger
        self.assertEqual(len(ledger.exits), len(reference.exits))
        for slice_, other in zip(ledger.exits, reference.exits):
            with self.subTest(kind=other.kind):
                self.assertEqual(slice_.quantity, other.quantity)
                self.assertEqual(slice_.exit_price, ACCEPTANCE_AXIS - other.exit_price)
                self.assertEqual(slice_.realized_pnl, other.realized_pnl)
        self.assertEqual(ledger.total_realized_pnl, reference.total_realized_pnl)

    def test_the_boundary_exit_is_the_range_low_for_a_short(self):
        kinds = [slice_.kind for slice_ in self.strategy.broker.trades[0].ledger.exits]
        self.assertIn('RANGE_LOW', kinds)
        self.assertNotIn('RANGE_HIGH', kinds)
        self.assertIn('RANGE_HIGH',
                      [s.kind for s in self.long.broker.trades[0].ledger.exits])

    def test_the_short_stop_only_ever_tightens_downward(self):
        trade = self.strategy.broker.trades[0]
        self.assertTrue(trade.stop_updates)
        for update in trade.stop_updates:
            self.assertLess(update.new_stop, update.previous_stop)

    def test_the_trailing_records_name_the_mirrored_structure(self):
        records = self.strategy.broker.trailing_updates
        self.assertTrue(records)
        for record in records:
            self.assertEqual(record.structural_reference, 'CONFIRMED_LOWER_HIGH')
        for record in self.long.broker.trailing_updates:
            self.assertEqual(record.structural_reference, 'CONFIRMED_HIGHER_LOW')

    def test_both_runs_end_with_the_same_equity(self):
        self.assertEqual(self.strategy.broker.equity, self.long.broker.equity)


if __name__ == '__main__':
    unittest.main()
