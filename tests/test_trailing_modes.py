"""[U-RR-TRAIL-001] Trailing modes: internal pivots and ATR tiers."""
from decimal import Decimal as D
import unittest

from agent_trading.strategy_v1 import StrategyProfile
from agent_trading.strategy_v1.pivots import Pivot
from dd_fixtures import model_one_long_candles, run_dd
from strategy_v1_fixtures import candle, scenario_profile
from test_strategy_v1_trailing import STEP, open_long, protect


class PivotTrailTests(unittest.TestCase):
    def test_the_mode_and_n_are_validated(self):
        self.assertEqual(StrategyProfile().trailing_pivot_bars, 3)
        for bad in (0, 11, 2.5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                StrategyProfile(trailing_pivot_bars=bad)
        self.assertEqual(StrategyProfile(trailing_mode='INTERNAL_PIVOT').trailing_mode,
                         'INTERNAL_PIVOT')

    def test_a_pivot_low_trails_the_stop_with_its_own_label(self):
        broker, moment = open_long(scenario_profile(trailing_mode='INTERNAL_PIVOT'))
        _events, moment = protect(broker, moment)
        pivot = Pivot('LOW', D('131'), moment - STEP, moment, 1)
        events = broker.process(candle('15m', moment + STEP, 138, 139, 136, 137), (pivot,))
        record = next(e.payload for e in events if e.kind == 'TRAILING_STOP_UPDATED')
        self.assertEqual((record.new_stop, record.structural_reference),
                         (D('130'), 'INTERNAL_PIVOT_LOW'))

    def test_the_strategy_trails_on_pivots_formed_after_the_fill(self):
        strategy = run_dd(model_one_long_candles(), trailing_mode='INTERNAL_PIVOT',
                          trailing_pivot_bars=1)
        trade = strategy.broker.trades[0]
        pivots = {(e.payload.price, e.payload.confirmed_at): e.payload
                  for e in strategy.events if e.kind == 'ENTRY_PIVOT_LOW'}
        updates = [e.payload for e in strategy.events if e.kind == 'TRAILING_STOP_UPDATED']
        self.assertTrue(updates)
        for record in updates:
            self.assertEqual(record.structural_reference, 'INTERNAL_PIVOT_LOW')
            pivot = pivots[(record.reference_price, record.confirmed_at)]
            self.assertGreaterEqual(pivot.swing_time, trade.filled_at)

    def test_other_modes_track_no_pivots(self):
        strategy = run_dd(model_one_long_candles())
        self.assertIsNone(strategy.entry_pivots)
        self.assertFalse(any(e.kind.startswith('ENTRY_PIVOT') for e in strategy.events))

    def test_the_command_line_selects_the_mode(self):
        import argparse
        from agent_trading.backtest.cli import add_profile_arguments, profile_from_args
        parser = argparse.ArgumentParser()
        add_profile_arguments(parser)
        profile = profile_from_args(parser.parse_args(
            ['--trailing-mode', 'INTERNAL_PIVOT', '--pivot-bars', '2']))
        self.assertEqual((profile.trailing_mode, profile.trailing_pivot_bars), ('INTERNAL_PIVOT', 2))


if __name__ == '__main__':
    unittest.main()
