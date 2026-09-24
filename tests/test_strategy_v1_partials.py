"""Configurable R-multiple partial take profits, RangeHigh exit and runner.

Every close fraction is a fraction of the ORIGINAL filled quantity. Initial R is
frozen at the fill. Nothing here measures profitability.
"""
import unittest
from decimal import Decimal

from agent_trading.market import bar_duration
from agent_trading.swing import ConfirmedSwing, SwingSide
from agent_trading.trading_brain.models import FVG, SwingLow, TradeCandidate
from agent_trading.trading_brain.risk import RiskEngine
from agent_trading.trading_brain.risk_models import SupportingZone
from agent_trading.strategy_v1 import PendingLimitPaperBroker, StrategyProfile, StrategyV1
from agent_trading.strategy_v1.broker import floor_to_step
from agent_trading.strategy_v1.config import PartialTakeProfit
from agent_trading.strategy_v1.models import EntryPlan, TrackedFvg

from strategy_v1_fixtures import (D, SYMBOL, acceptance_candles, acceptance_profile,
                                  bias_candles, candle, run_scenario, scenario_profile)

STEP = bar_duration('15m')
ENTRY = D('128')
STOP = D('118')
INITIAL_R = D('10')
TARGET = D('140')
QUANTITY = D('10.00000000')


def swing_low(price, swing_time):
    raw = ConfirmedSwing(SYMBOL, '15m', SwingSide.LOW, D(str(price)), swing_time,
                         swing_time + STEP, 1, D('1'), D('1'))
    return SwingLow(raw)


def confirmed_low(price, now, bars_ago=2):
    return swing_low(price, now - bars_ago * STEP)


def open_long(profile=None):
    """Fill the canonical LONG: entry 128, stop 118, R 10, target 140, qty 10."""
    profile = profile or scenario_profile()
    risk = RiskEngine(profile.risk_config())
    broker = PendingLimitPaperBroker(risk, D('10000'), profile)
    start = bias_candles()[0].close_time
    primary = TrackedFvg('p1', FVG('LONG', D('126'), D('130'), (start, start, start), start))
    second = TrackedFvg('s1', FVG('LONG', D('120'), D('122'), (start, start, start), start))
    zone = SupportingZone('s1', 'FVG', 'LONG', D('120'), D('122'), D('119'),
                          start, SYMBOL, '15m')
    candidate = TradeCandidate('LONG', ENTRY, D('119'), TARGET, start, (),
                               sweep_extreme=D('112'))
    decision = risk.evaluate(candidate, D('10000'), (zone,), symbol=SYMBOL, timeframe='15m')
    assert decision.plan is not None
    plan = EntryPlan(primary, 'FVG_EQ', ENTRY, TARGET, 'SECONDARY_FVG_PROTECTING_SWING',
                     second, swing_low(119, start), D('119'), start)
    broker.submit(decision.plan, plan)
    broker.process(candle('15m', start + STEP, 129, 129.5, 128, 128.5))
    return broker, start + STEP


def partials(*pairs):
    return tuple({'r_multiple': str(r), 'close_fraction': str(f)} for r, f in pairs)


# ------------------------------------------------------------------- CONFIG
# [U-DD-DEVIATION-001] The DD range-EQ slice also draws on the non-runner
# allocation (tested in test_dd_config); the R-partial rules below are measured
# with it switched off.
NO_EQ = dict(eq_scale_out_fraction=None)


class PartialConfigTests(unittest.TestCase):
    def test_an_empty_partial_list_is_the_default_and_is_valid(self):
        profile = StrategyProfile()
        self.assertEqual(profile.partial_take_profits, ())
        # [U-DD-DEVIATION-001] 30% at EQ, 50% at the boundary, a 20% runner.
        self.assertEqual(profile.runner_fraction, D('0.20'))

    def test_one_and_many_partials_are_accepted(self):
        self.assertEqual(len(StrategyProfile(
            partial_take_profits=partials((1, '0.25')), **NO_EQ).partial_take_profits), 1)
        self.assertEqual(len(StrategyProfile(
            partial_take_profits=partials((1, '0.2'), (2, '0.2'),
                                          (3, '0.2')), **NO_EQ).partial_take_profits), 3)

    def test_unsorted_input_is_normalised_to_ascending_r(self):
        profile = StrategyProfile(partial_take_profits=partials((3, '0.2'), (1, '0.2'),
                                                                (2, '0.2')), **NO_EQ)
        self.assertEqual([level.r_multiple for level in profile.partial_take_profits],
                         [D('1'), D('2'), D('3')])

    def test_duplicate_r_levels_are_rejected(self):
        with self.assertRaises(ValueError):
            StrategyProfile(partial_take_profits=partials((1, '0.2'), (1, '0.3')))

    def test_zero_and_negative_r_are_rejected(self):
        for value in ('0', '-1'):
            with self.assertRaises(ValueError):
                StrategyProfile(partial_take_profits=partials((value, '0.2')))

    def test_invalid_close_fractions_are_rejected(self):
        for value in ('0', '-0.1', '1.5'):
            with self.assertRaises(ValueError):
                StrategyProfile(partial_take_profits=partials((1, value)))

    def test_fractions_exceeding_the_non_runner_allocation_are_rejected(self):
        with self.assertRaises(ValueError):
            StrategyProfile(partial_take_profits=partials((1, '0.5'), (2, '0.45')),
                            runner_fraction=D('0.10'), **NO_EQ)
        # Exactly 1 - runner is allowed.
        StrategyProfile(partial_take_profits=partials((1, '0.5'), (2, '0.4')),
                        runner_fraction=D('0.10'), **NO_EQ)

    def test_runner_fraction_bounds_are_enforced(self):
        for value in (D('-0.1'), D('1.1')):
            with self.assertRaises(ValueError):
                StrategyProfile(runner_fraction=value, **NO_EQ)
        StrategyProfile(runner_fraction=D('0'), **NO_EQ)
        StrategyProfile(runner_fraction=D('1'), **NO_EQ)

    def test_a_full_runner_forbids_any_partial(self):
        with self.assertRaises(ValueError):
            StrategyProfile(runner_fraction=D('1'),
                            partial_take_profits=partials((1, '0.1')))

    def test_bad_configuration_is_never_silently_repaired(self):
        with self.assertRaises(ValueError):
            PartialTakeProfit(D('1'), D('0'))
        with self.assertRaises(ValueError):
            PartialTakeProfit.from_mapping({'r_multiple': '1'})

    def test_the_exit_plan_is_bot_and_api_ready(self):
        profile = StrategyProfile(partial_take_profits=partials((1, '0.2'), (2, '0.3')),
                                  runner_fraction=D('0.10'))
        data = profile.as_dict()
        self.assertEqual(data['partial_take_profits'],
                         [{'r_multiple': '1', 'close_fraction': '0.2'},
                          {'r_multiple': '2', 'close_fraction': '0.3'}])
        self.assertEqual(data['runner_fraction'], '0.10')
        import json
        json.dumps(data)                       # must be serialisable as-is
        rebuilt = StrategyProfile(
            partial_take_profits=tuple(data['partial_take_profits']),
            runner_fraction=D(data['runner_fraction']))
        self.assertEqual(rebuilt.partial_take_profits, profile.partial_take_profits)


# --------------------------------------------------------------- R CALCULATION
class InitialRTests(unittest.TestCase):
    def test_initial_r_is_frozen_at_the_fill(self):
        broker, _ = open_long()
        ledger = broker.trades[-1].ledger
        self.assertEqual(ledger.initial_r, INITIAL_R)
        self.assertEqual(ledger.original_quantity, QUANTITY)
        self.assertEqual(ledger.remaining_quantity, QUANTITY)

    def test_partial_targets_follow_entry_plus_r_multiple_times_initial_r(self):
        broker, _ = open_long()
        trade = broker.trades[-1]
        for multiple, expected in ((D('1'), D('138')), (D('2'), D('148')),
                                   (D('0.5'), D('133'))):
            self.assertEqual(broker.partial_target(trade, multiple), expected)

    def test_break_even_does_not_move_partial_targets(self):
        broker, moment = open_long()
        before = broker.partial_target(broker.trades[-1], D('2'))
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        trade = broker.trades[-1]
        self.assertEqual(trade.stop, ENTRY)                  # break-even reached
        self.assertEqual(trade.ledger.initial_r, INITIAL_R)
        self.assertEqual(broker.partial_target(trade, D('2')), before)

    def test_trailing_does_not_move_partial_targets(self):
        broker, moment = open_long()
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        broker.process(candle('15m', moment + 2 * STEP, 138, 139, 136, 137),
                       (confirmed_low(131, moment + 2 * STEP),))
        trade = broker.trades[-1]
        self.assertEqual(trade.stop, D('130'))
        self.assertEqual(trade.ledger.initial_r, INITIAL_R)
        self.assertEqual(broker.partial_target(trade, D('2')), D('148'))

    def test_a_realised_partial_does_not_change_initial_r(self):
        broker, moment = open_long(scenario_profile(partial_take_profits=partials((1, '0.25'))))
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        trade = broker.trades[-1]
        self.assertTrue(trade.ledger.partial_exits)
        self.assertEqual(trade.ledger.initial_r, INITIAL_R)
        self.assertEqual(broker.partial_target(trade, D('1')), D('138'))


# -------------------------------------------------------------------- EXECUTION
class PartialExecutionTests(unittest.TestCase):
    def _profile(self, **kwargs):
        return scenario_profile(partial_take_profits=partials((1, '0.25')), **kwargs)

    def test_a_one_r_partial_fills_at_its_target(self):
        broker, moment = open_long(self._profile())
        events = broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        record = next(e.payload for e in events if e.kind == 'PARTIAL_TP_FILLED')
        self.assertEqual(record.trigger_r, D('1'))
        self.assertEqual(record.target_price, D('138'))
        self.assertEqual(record.exit_price, D('138'))
        self.assertEqual(record.quantity, D('2.50000000'))       # 25% of the ORIGINAL
        self.assertEqual(record.remaining_quantity, D('7.50000000'))
        self.assertEqual(record.realized_pnl, D('25'))           # 2.5 * (138 - 128)

    def test_a_level_the_candle_never_reaches_does_not_fill(self):
        broker, moment = open_long(self._profile())
        events = broker.process(candle('15m', moment + STEP, 128, 137.9, 127.5, 137))
        self.assertEqual([e.kind for e in events], [])
        self.assertEqual(broker.trades[-1].ledger.remaining_quantity, QUANTITY)

    def test_each_fraction_is_of_the_original_not_the_remainder(self):
        profile = scenario_profile(partial_take_profits=partials(('0.5', '0.25'),
                                                                 (1, '0.25')))
        broker, moment = open_long(profile)
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        exits = broker.trades[-1].ledger.partial_exits
        self.assertEqual([e.quantity for e in exits],
                         [D('2.50000000'), D('2.50000000')])     # not 2.5 then 1.875
        self.assertEqual(broker.trades[-1].ledger.remaining_quantity, D('5.00000000'))

    def test_ascending_levels_fill_in_order_on_one_candle(self):
        profile = scenario_profile(partial_take_profits=partials(('0.5', '0.2'),
                                                                 ('0.8', '0.2')))
        broker, moment = open_long(profile)
        events = broker.process(candle('15m', moment + STEP, 128, 137, 127.5, 136))
        triggers = [e.payload.trigger_r for e in events if e.kind == 'PARTIAL_TP_FILLED']
        self.assertEqual(triggers, [D('0.5'), D('0.8')])

    def test_a_level_only_ever_fills_once(self):
        broker, moment = open_long(self._profile())
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        events = broker.process(candle('15m', moment + 2 * STEP, 138, 139, 137, 138.5))
        self.assertEqual([e.kind for e in events if e.kind == 'PARTIAL_TP_FILLED'], [])
        self.assertEqual(len(broker.trades[-1].ledger.partial_exits), 1)

    def test_a_gap_above_the_level_fills_at_the_open(self):
        broker, moment = open_long(self._profile())
        events = broker.process(candle('15m', moment + STEP, 139, 140, 138.5, 139.5))
        record = next(e.payload for e in events if e.kind == 'PARTIAL_TP_FILLED')
        self.assertEqual(record.exit_price, D('139'))
        self.assertEqual(record.target_price, D('138'))

    def test_quantity_is_floored_onto_the_configured_step(self):
        self.assertEqual(floor_to_step(D('2.555555555'), D('.00000001')), D('2.55555555'))
        self.assertEqual(floor_to_step(D('0.000000009'), D('.00000001')), D('0'))


# -------------------------------------------------------------------- RANGEHIGH
class RangeHighTests(unittest.TestCase):
    def test_the_default_leaves_exactly_ten_percent_as_runner(self):
        strategy = run_scenario()
        self.assertEqual(strategy.profile.partial_take_profits, ())
        self.assertEqual(strategy.profile.runner_fraction, D('0.10'))
        record = next(e.payload for e in strategy.events
                      if e.kind == 'RANGE_HIGH_PARTIAL_EXIT')
        ledger = strategy.broker.trades[-1].ledger
        self.assertEqual(record.quantity, D('9.00000000'))       # 90% of the original
        self.assertEqual(record.exit_price, D('140'))
        self.assertEqual(record.realized_pnl, D('108'))
        self.assertEqual(ledger.remaining_quantity, D('1.00000000'))
        self.assertEqual(ledger.runner_target_quantity, D('1.00000000'))

    def test_prior_partials_reduce_the_range_high_quantity(self):
        profile = scenario_profile(partial_take_profits=partials((1, '0.25')))
        broker, moment = open_long(profile)
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        events = broker.process(candle('15m', moment + 2 * STEP, 138, 141, 137, 140.5))
        record = next(e.payload for e in events if e.kind == 'RANGE_HIGH_PARTIAL_EXIT')
        # remaining 7.5 minus the 1.0 runner target
        self.assertEqual(record.quantity, D('6.50000000'))
        self.assertEqual(broker.trades[-1].ledger.remaining_quantity, D('1.00000000'))

    def test_the_runner_fraction_is_preserved_whatever_filled_before(self):
        for spec in ((), partials((1, '0.25')), partials(('0.5', '0.2'), (1, '0.2'))):
            with self.subTest(spec=spec):
                broker, moment = open_long(scenario_profile(partial_take_profits=spec))
                broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
                broker.process(candle('15m', moment + 2 * STEP, 138, 141, 137, 140.5))
                self.assertEqual(broker.trades[-1].ledger.remaining_quantity,
                                 D('1.00000000'))

    def test_unfilled_future_r_levels_are_cancelled_at_range_high(self):
        # 2R is 148, above the 140 RangeHigh, so it can never fill afterwards.
        profile = scenario_profile(partial_take_profits=partials((1, '0.2'), (2, '0.2')))
        broker, moment = open_long(profile)
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        broker.process(candle('15m', moment + 2 * STEP, 138, 141, 137, 140.5))
        ledger = broker.trades[-1].ledger
        self.assertIsNotNone(ledger.partials_cancelled_at)
        self.assertEqual(len(ledger.partial_exits), 1)
        # Price now trades far above 2R: the runner must not be touched.
        broker.process(candle('15m', moment + 3 * STEP, 141, 160, 140, 159))
        self.assertEqual(broker.trades[-1].ledger.remaining_quantity, D('1.00000000'))
        self.assertEqual(len(broker.trades[-1].ledger.partial_exits), 1)

    def test_a_zero_runner_closes_everything_at_range_high(self):
        broker, moment = open_long(scenario_profile(runner_fraction=D('0')))
        events = broker.process(candle('15m', moment + STEP, 128, 141, 127.5, 140.5))
        kinds = [e.kind for e in events]
        self.assertIn('RANGE_HIGH_PARTIAL_EXIT', kinds)
        self.assertIn('PAPER_ORDER_CLOSED', kinds)
        trade = broker.trades[-1]
        self.assertEqual(trade.status, 'CLOSED')
        self.assertEqual(trade.ledger.remaining_quantity, D('0'))

    def test_a_full_runner_closes_nothing_at_range_high(self):
        broker, moment = open_long(scenario_profile(runner_fraction=D('1')))
        events = broker.process(candle('15m', moment + STEP, 128, 141, 127.5, 140.5))
        kinds = [e.kind for e in events]
        self.assertNotIn('RANGE_HIGH_PARTIAL_EXIT', kinds)
        self.assertIn('RUNNER_OPEN', kinds)
        ledger = broker.trades[-1].ledger
        self.assertEqual(ledger.remaining_quantity, QUANTITY)
        self.assertTrue(ledger.runner_open)

    def test_partials_totalling_the_non_runner_share_leave_nothing_to_close(self):
        profile = scenario_profile(
            partial_take_profits=partials(('0.5', '0.3'), ('0.8', '0.3'), (1, '0.3')),
            runner_fraction=D('0.10'))
        broker, moment = open_long(profile)
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138))
        self.assertEqual(broker.trades[-1].ledger.remaining_quantity, D('1.00000000'))
        events = broker.process(candle('15m', moment + 2 * STEP, 138, 141, 137, 140.5))
        kinds = [e.kind for e in events]
        self.assertNotIn('RANGE_HIGH_PARTIAL_EXIT', kinds)      # valid: nothing left
        self.assertIn('RUNNER_OPEN', kinds)
        self.assertEqual(broker.trades[-1].ledger.remaining_quantity, D('1.00000000'))


# ----------------------------------------------------------------------- RUNNER
class RunnerTests(unittest.TestCase):
    def _runner(self, profile=None):
        broker, moment = open_long(profile or scenario_profile())
        broker.process(candle('15m', moment + STEP, 128, 141, 127.5, 140.5))
        self.assertTrue(broker.trades[-1].ledger.runner_open)
        return broker, moment + STEP

    def test_the_runner_keeps_the_trade_open(self):
        broker, _ = self._runner()
        trade = broker.trades[-1]
        self.assertEqual(trade.status, 'OPEN')
        self.assertEqual(trade.ledger.remaining_quantity, D('1.00000000'))

    def test_the_runner_has_no_fixed_upside_target(self):
        broker, moment = self._runner()
        self.assertFalse(broker.trades[-1].ledger.has_upside_target)
        events = broker.process(candle('15m', moment + STEP, 141, 200, 140, 199))
        self.assertEqual([e.kind for e in events if 'RANGE_HIGH' in e.kind], [])
        self.assertEqual(broker.trades[-1].status, 'OPEN')
        self.assertEqual(broker.trades[-1].ledger.remaining_quantity, D('1.00000000'))

    def test_the_runner_still_receives_trailing_updates(self):
        broker, moment = self._runner()
        events = broker.process(candle('15m', moment + STEP, 141, 145, 140, 144),
                                (confirmed_low(139, moment + STEP),))
        record = next(e.payload for e in events if e.kind == 'TRAILING_STOP_UPDATED')
        self.assertEqual(record.new_stop, D('138'))
        self.assertEqual(broker.trades[-1].stop, D('138'))

    def test_the_runner_stop_closes_the_final_quantity(self):
        broker, moment = self._runner()
        broker.process(candle('15m', moment + STEP, 141, 145, 140, 144),
                       (confirmed_low(139, moment + STEP),))
        events = broker.process(candle('15m', moment + 2 * STEP, 144, 144, 137, 137.5))
        kinds = [e.kind for e in events]
        self.assertIn('RUNNER_STOPPED', kinds)
        self.assertIn('PAPER_ORDER_CLOSED', kinds)
        trade = broker.trades[-1]
        self.assertEqual(trade.status, 'CLOSED')
        self.assertEqual(trade.ledger.remaining_quantity, D('0'))
        self.assertEqual(trade.ledger.runner_exit.exit_price, D('138'))


# ------------------------------------------------------------------- CAUSALITY
class ConservativeExecutionTests(unittest.TestCase):
    def test_a_candle_touching_both_stop_and_a_partial_awards_no_partial(self):
        profile = scenario_profile(partial_take_profits=partials((1, '0.25')))
        broker, moment = open_long(profile)
        events = broker.process(candle('15m', moment + STEP, 128, 138.5, 117, 130))
        kinds = [e.kind for e in events]
        self.assertNotIn('PARTIAL_TP_FILLED', kinds)
        self.assertIn('PAPER_ORDER_CLOSED', kinds)
        trade = broker.trades[-1]
        self.assertEqual(trade.status, 'CLOSED')
        self.assertEqual(trade.ledger.partial_exits, ())
        self.assertEqual(trade.ledger.runner_exit.exit_price, STOP)

    def test_a_candle_touching_both_stop_and_range_high_awards_no_exit(self):
        broker, moment = open_long()
        events = broker.process(candle('15m', moment + STEP, 128, 141, 117, 130))
        kinds = [e.kind for e in events]
        self.assertNotIn('RANGE_HIGH_PARTIAL_EXIT', kinds)
        self.assertEqual(broker.trades[-1].ledger.runner_exit.exit_price, STOP)

    def test_the_acceptance_chain_is_deterministic(self):
        def run():
            strategy = StrategyV1(SYMBOL, acceptance_profile())
            strategy.feed(acceptance_candles())
            ledger = strategy.broker.trades[-1].ledger
            return ([(e.id, e.kind, e.observed_at) for e in strategy.events],
                    [(x.kind, x.quantity, x.exit_price, x.realized_pnl) for x in ledger.exits])
        self.assertEqual(run(), run())


# --------------------------------------------------------- FULL ACCEPTANCE CHAIN
class FullChainAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strategy = StrategyV1(SYMBOL, acceptance_profile())
        cls.strategy.feed(acceptance_candles())
        cls.trade = cls.strategy.broker.trades[-1]
        cls.ledger = cls.trade.ledger

    def _kinds(self):
        return [e.kind for e in self.strategy.events]

    def test_the_whole_chain_occurs_in_order(self):
        order = ['BIAS_BREAK', 'RANGE_CONFIRMED', 'MANIPULATION_CONFIRMED',
                 'TRADE_CANDIDATE', 'ENTRY_PLAN', 'PENDING_ENTRY', 'PAPER_ORDER_OPENED',
                 'PARTIAL_TP_FILLED', 'BREAK_EVEN_PROTECTED', 'TRAILING_STOP_UPDATED',
                 'RANGE_HIGH_PARTIAL_EXIT', 'RUNNER_OPEN', 'RUNNER_STOPPED',
                 'PAPER_ORDER_CLOSED']
        times = []
        for kind in order:
            event = next((e for e in self.strategy.events if e.kind == kind), None)
            self.assertIsNotNone(event, f'missing {kind}')
            times.append(event.observed_at)
        self.assertEqual(times, sorted(times))

    def test_both_partials_filled_before_the_range_high_exit(self):
        exits = self.ledger.partial_exits
        self.assertEqual([e.trigger_r for e in exits], [D('1.0'), D('2.0')])
        self.assertEqual([e.target_price for e in exits], [D('138'), D('148')])
        self.assertEqual([e.quantity for e in exits],
                         [D('2.00000000'), D('2.00000000')])
        self.assertEqual([e.realized_pnl for e in exits], [D('20'), D('40')])

    def test_the_range_high_exit_leaves_exactly_the_runner(self):
        record = self.ledger.range_high_exit
        self.assertEqual(record.quantity, D('5.00000000'))
        self.assertEqual(record.exit_price, D('170'))
        self.assertEqual(record.realized_pnl, D('210'))
        self.assertEqual(record.remaining_quantity, D('1.00000000'))

    def test_the_runner_exits_on_its_trailed_stop(self):
        record = self.ledger.runner_exit
        self.assertEqual(record.kind, 'RUNNER')
        self.assertEqual(record.quantity, D('1.00000000'))
        self.assertEqual(record.exit_price, D('160'))
        self.assertEqual(record.realized_pnl, D('32'))

    def test_the_stop_only_ever_tightened(self):
        stops = [self.trade.approved_plan.stop] + [u.new_stop for u in self.trade.stop_updates]
        self.assertEqual(stops, [D('118'), D('128'), D('130.5'), D('140'), D('160')])
        self.assertEqual(stops, sorted(stops))
        for stop in stops[1:]:
            self.assertGreaterEqual(stop, self.trade.entry)

    def test_the_ledger_conserves_the_original_quantity(self):
        self.assertEqual(self.ledger.original_quantity, D('10.00000000'))
        self.assertEqual(self.ledger.realized_quantity, self.ledger.original_quantity)
        self.assertEqual(self.ledger.remaining_quantity, D('0'))
        self.assertEqual(len(self.ledger.exits), 4)

    def test_total_realised_pnl_is_the_sum_of_every_slice(self):
        self.assertEqual(self.ledger.total_realized_pnl, D('302'))
        self.assertEqual(sum(x.realized_pnl for x in self.ledger.exits), D('302'))
        self.assertEqual(self.strategy.broker.equity, D('10302'))
        self.assertEqual(self.trade.pnl, D('302'))

    def test_it_remains_one_logical_trade(self):
        self.assertEqual(len(self.strategy.broker.trades), 1)
        self.assertEqual(self.trade.status, 'CLOSED')
        self.assertEqual(self.trade.direction, 'LONG')

    def test_the_chain_stays_long_only(self):
        for event in self.strategy.events:
            if event.kind == 'TRADE_CANDIDATE':
                self.assertEqual(event.payload.direction, 'LONG')


if __name__ == '__main__':
    unittest.main()
