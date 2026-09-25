"""[U-RR-TRAIL-001] Trailing modes: internal pivots and ATR tiers."""
from decimal import Decimal as D
import unittest

from agent_trading.backtest.metrics import SETUP_EVENTS
from agent_trading.backtest.recorder import EXIT_REASONS
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


ATR = D('2')                                   # tiers at peak - 1.5, - 2.5, - 3


class AtrTierTests(unittest.TestCase):
    """Legacy long: entry 128, stop 118, 10 units, break-even at 1R (138)."""

    def _protected(self, **overrides):
        broker, moment = open_long(scenario_profile(trailing_mode='ATR_TIERS', **overrides))
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138), atr=ATR)  # BE
        return broker, moment + STEP

    def test_the_tiers_are_validated(self):
        self.assertEqual(StrategyProfile().trailing_atr_tiers,
                         ((D('0.75'), D('0.25')), (D('1.25'), D('0.5')), (D('1.5'), D('1'))))
        for bad in ((), ((D('1'), D('0')),), ((D('1'), D('0.5')), (D('0.5'), D('1'))),
                    ((D('1'), D('1.5')),), (('x', '1'),)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                StrategyProfile(trailing_atr_tiers=bad)

    def test_each_tier_closes_its_share_of_the_open_position(self):
        broker, moment = self._protected()                     # peak 138.5 after this bar
        broker.process(candle('15m', moment + STEP, 138, 138.2, 137, 137.5), atr=ATR)
        broker.process(candle('15m', moment + 2 * STEP, 137.5, 137.6, 136, 136.5), atr=ATR)
        events = broker.process(candle('15m', moment + 3 * STEP, 136.5, 136.6, 135.4, 135.5),
                                atr=ATR)
        ledger = broker.trades[-1].ledger
        self.assertEqual([(x.kind, x.quantity, x.exit_price) for x in ledger.exits],
                         [('ATR_TIER', D('2.5'), D('137')), ('ATR_TIER', D('3.75'), D('136')),
                          ('ATR_TIER', D('3.75'), D('135.5'))])
        self.assertEqual(broker.trades[-1].status, 'CLOSED')
        self.assertIn('PAPER_ORDER_CLOSED', [e.kind for e in events])
        self.assertIn('ATR_TIER_EXIT', [e.kind for e in events])

    def test_no_tier_fires_before_break_even_or_without_atr(self):
        broker, moment = open_long(scenario_profile(trailing_mode='ATR_TIERS'))
        broker.process(candle('15m', moment + STEP, 128.5, 133, 128.2, 132), atr=ATR)
        broker.process(candle('15m', moment + 2 * STEP, 132, 132, 129, 129.5), atr=ATR)
        self.assertEqual(broker.trades[-1].ledger.exits, ())
        broker, moment = self._protected()
        broker.process(candle('15m', moment + STEP, 138, 138.2, 135, 135.5), atr=None)
        self.assertEqual(broker.trades[-1].ledger.exits, ())

    def test_one_bar_through_several_tiers_fills_them_in_order_at_the_open_when_gapped(self):
        broker, moment = self._protected()
        broker.process(candle('15m', moment + STEP, 136.8, 136.9, 135, 135.2), atr=ATR)
        ledger = broker.trades[-1].ledger
        self.assertEqual([(x.quantity, x.exit_price) for x in ledger.exits],
                         [(D('2.5'), D('136.8')), (D('3.75'), D('136')), (D('3.75'), D('135.5'))])

    def test_the_tiers_never_move_the_protective_stop(self):
        broker, moment = self._protected()
        broker.process(candle('15m', moment + STEP, 138, 138.2, 137, 137.5), atr=ATR,
                       swing_lows=())
        self.assertEqual(broker.trades[-1].stop, D('128'))
        self.assertEqual(broker.trailing_updates, ())

    def test_a_new_trade_starts_with_fresh_tiers(self):
        broker, moment = self._protected()
        broker.process(candle('15m', moment + STEP, 138, 138.2, 137, 137.5), atr=ATR)
        self.assertEqual(broker.tiers_done, 1)
        from test_strategy_v1_trailing import _submit
        broker.process(candle('15m', moment + 2 * STEP, 137.5, 137.5, 127, 127.5), atr=ATR)
        self.assertEqual(broker.trades[-1].status, 'CLOSED')
        _submit(scenario_profile(trailing_mode='ATR_TIERS'), broker=broker, at=moment + 2 * STEP)
        self.assertEqual((broker.tiers_done, broker.peak), (0, None))

    def test_the_strategy_passes_the_previous_bars_atr(self):
        from agent_trading.strategy_v1 import StrategyV1
        from dd_fixtures import dd_profile
        from strategy_v1_fixtures import SYMBOL
        strategy = StrategyV1(SYMBOL, dd_profile(trailing_mode='ATR_TIERS'))
        seen, original = [], strategy.broker.process
        def spy(candle, lows=(), highs=(), atr=None):
            seen.append((atr, strategy.entry_swing.state.atr))
            return original(candle, lows, highs, atr=atr)
        strategy.broker.process = spy
        strategy.feed(model_one_long_candles())
        self.assertTrue(any(a is not None for a, _b in seen))
        self.assertTrue(all(a == b for a, b in seen))

    def test_the_command_line_and_the_reports_know_the_tiers(self):
        import argparse
        from agent_trading.backtest.cli import add_profile_arguments, profile_from_args
        parser = argparse.ArgumentParser()
        add_profile_arguments(parser)
        profile = profile_from_args(parser.parse_args(
            ['--trailing-mode', 'ATR_TIERS', '--atr-tiers', '1:0.5,2:1']))
        self.assertEqual(profile.trailing_atr_tiers, ((D('1'), D('0.5')), (D('2'), D('1'))))
        self.assertEqual(EXIT_REASONS['ATR_TIER'], 'ATR_TIER')
        self.assertEqual(SETUP_EVENTS['atr_tier_exits'], 'ATR_TIER_EXIT')


if __name__ == '__main__':
    unittest.main()
