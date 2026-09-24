"""[U-DD-DEVIATION-001] The entry model and the DD exits reach every report."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from agent_trading.backtest import report, sweep
from agent_trading.backtest.config import BacktestConfig
from agent_trading.backtest.engine import run
from agent_trading.bot_service import BotService
from agent_trading.config import Config
from agent_trading.strategy_v1 import StrategyV1

from dd_fixtures import dd_profile, model_one_long_candles, model_one_short_candles
from strategy_v1_fixtures import D, SYMBOL, events_of
from test_backtest import dump
from test_sweep import GRID, relabel

DD_FLAGS = ('--entry-models', 'CHOCH_FVG,HTF_FVG_REVERSAL', '--model2-htf-fvg', 'auto',
            '--eq-scale-out', '0.30', '--break-even-trigger', 'RANGE_EQ',
            '--runner-fraction', '0.20', '--no-secondary-fvg')


class DdRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.result = run(BacktestConfig(SYMBOL, dump(model_one_long_candles(), root / 'data'),
                                        D('10000'), profile=dd_profile()))
        cls.record = cls.result.trades[0]
        cls.out = root / 'out'
        report.write(cls.result, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_trade_record_names_its_entry_model(self):
        self.assertEqual(self.record.entry_model, 'CHOCH_FVG')
        self.assertEqual(self.record.as_dict()['entry_model'], 'CHOCH_FVG')

    def test_the_eq_slice_and_eq_break_even_are_counted(self):
        self.assertTrue(self.record.break_even_reached)
        self.assertEqual(self.record.partial_count, 1)
        self.assertEqual([s.kind for s in self.record.slices], ['RANGE_EQ', 'RANGE_HIGH', 'RUNNER'])
        self.assertEqual(self.record.exit_reason, 'RUNNER_STOP')

    def test_the_funnel_counts_chochs_and_eq_exits(self):
        funnel = self.result.summary_document()['funnel']
        self.assertEqual(funnel['choch_confirmations'],
                         len(events_of(self.result.strategy, 'CHOCH_CONFIRMED')))
        self.assertGreaterEqual(funnel['choch_confirmations'], 1)
        self.assertEqual(funnel['range_eq_exits'], 1)

    def test_trades_csv_carries_the_entry_model(self):
        with (self.out / 'trades.csv').open(encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]['entry_model'], 'CHOCH_FVG')


class DdSweepTests(unittest.TestCase):
    def test_the_sweep_pools_trades_by_entry_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root, out = Path(directory) / 'data', Path(directory) / 'out'
            dump(relabel(model_one_long_candles(), 'AAA-USDT'), root / 'AAA', 'AAA-USDT')
            dump(relabel(model_one_short_candles(), 'BBB-USDT'), root / 'BBB', 'BBB-USDT')
            self.assertEqual(sweep.main(['--data', str(root), '--output', str(out),
                                         *GRID, *DD_FLAGS]), 0)
            pooled = json.loads((out / 'sweep_summary.json').read_text('utf-8'))['pooled']
            self.assertEqual(pooled['by_entry_model']['CHOCH_FVG']['trades'], 2)
            self.assertEqual(pooled['by_entry_model']['HTF_FVG_REVERSAL']['trades'], 0)
            with (out / 'sweep_trades.csv').open(encoding='utf-8', newline='') as handle:
                self.assertEqual({row['entry_model'] for row in csv.DictReader(handle)},
                                 {'CHOCH_FVG'})


class DdNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_panel_hears_about_the_choch_and_the_eq_exit(self):
        bot = BotService(Config())
        bot.brain = StrategyV1(SYMBOL, dd_profile())
        bot.brain.feed(model_one_long_candles())
        bot._check_notifications()
        titles = [event['title'] for event in bot.ui_events]
        self.assertIn('CHOCH_CONFIRMED', titles)
        self.assertIn('RANGE_EQ_PARTIAL_EXIT', titles)


if __name__ == '__main__':
    unittest.main()
