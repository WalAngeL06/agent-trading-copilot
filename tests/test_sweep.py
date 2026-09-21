"""Replay one profile over many frozen datasets [U-MULTI-PAIR-001].

Every dataset is synthetic here: the guide scenarios (a discount long and a
premium short) relabelled as different pairs, plus broken copies.
"""
from contextlib import redirect_stderr, redirect_stdout
import csv
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from agent_trading.backtest import sweep
from agent_trading.backtest.config import BacktestConfig
from agent_trading.backtest.dataset import Dataset, load_stream, peek_symbol
from agent_trading.backtest.engine import run
from agent_trading.backtest.universe import select_universe, write_universe
from agent_trading.market_observations import SpotInstrument, SpotVolume
from agent_trading.strategy_v1 import StrategyProfile
from guide_fixtures import long_candles, short_candles
from strategy_v1_fixtures import entry_candles
from test_backtest import dump

# The guide scenarios are drawn on a grid where 5 and 1 are the right tolerances.
GRID = ('--scale', 'none', '--boundary-proximity', '5', '--stop-buffer', '1')


def relabel(candles, symbol):
    return [replace(candle, symbol=symbol) for candle in candles]


def rescaled(candles, factor):
    factor = D(factor)
    return [replace(c, open=c.open * factor, high=c.high * factor, low=c.low * factor,
                    close=c.close * factor) for c in candles]


def gapped(candles):
    """Drop one 15m bar from the middle: a defect the loader must refuse."""
    entry = [candle for candle in candles if candle.timeframe == '15m']
    victim = entry[len(entry) // 2]
    return [candle for candle in candles if candle is not victim]


class PeekSymbolTests(unittest.TestCase):
    def test_the_symbol_is_read_from_the_first_row(self):
        with tempfile.TemporaryDirectory() as directory:
            dump(relabel(long_candles(), 'AAA-USDT'), Path(directory), 'AAA-USDT')
            self.assertEqual(peek_symbol(Path(directory) / 'aaausdt_15m.jsonl'), 'AAA-USDT')

    def test_an_empty_or_symbol_less_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / 'x_15m.jsonl'
            empty.write_text('', encoding='utf-8')
            nameless = Path(directory) / 'y_15m.jsonl'
            nameless.write_text(json.dumps({'timeframe': '15m'}) + '\n', encoding='utf-8')
            for path in (empty, nameless):
                with self.subTest(path=path.name), self.assertRaises(ValueError):
                    peek_symbol(path)


class ScaleTests(unittest.TestCase):
    def test_both_price_knobs_scale_with_the_reference_price(self):
        profile = sweep.scale_profile(StrategyProfile(), D('127'), D('0.005'), D('0.001'))
        self.assertEqual((profile.boundary_proximity, profile.stop_buffer),
                         (D('0.635'), D('0.127')))
        self.assertEqual(profile.effective_htf_zone_tolerance, D('0.635'))
        self.assertEqual(profile.effective_trailing_buffer, D('0.127'))


class SweepTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.root, self.output = base / 'data', base / 'runs'

    def tearDown(self):
        self._tmp.cleanup()

    def add(self, name, candles, symbol):
        dump(relabel(candles, symbol), self.root / name, symbol)

    def standard_root(self):
        self.add('AAA', long_candles(), 'AAA-USDT')
        self.add('BBB', short_candles(), 'BBB-USDT')
        self.add('CCC', gapped(long_candles()), 'CCC-USDT')

    def run_sweep(self, *flags, output=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = sweep.main(['--data', str(self.root),
                                   '--output', str(output or self.output), *flags])
            except SystemExit as stop:
                code = stop.code
        self.text = stdout.getvalue() + stderr.getvalue()
        return code

    def summary(self, output=None):
        return json.loads(((output or self.output) / 'sweep_summary.json').read_text('utf-8'))

    def rows(self, output=None):
        return {row['dataset']: row for row in self.summary(output)['datasets']}

    def trades(self, output=None):
        path = (output or self.output) / 'sweep_trades.csv'
        with path.open(encoding='utf-8', newline='') as handle:
            return list(csv.DictReader(handle))

    def test_each_dataset_runs_and_a_broken_one_is_skipped_with_its_reason(self):
        self.standard_root()
        self.assertEqual(self.run_sweep(*GRID), 0)
        rows = self.rows()
        self.assertEqual({name: row['status'] for name, row in rows.items()},
                         {'AAA': 'COMPLETED', 'BBB': 'COMPLETED', 'CCC': 'SKIPPED'})
        self.assertIn('gap', rows['CCC']['reason'])
        self.assertEqual((rows['AAA']['symbol'], rows['AAA']['trades']), ('AAA-USDT', 1))
        for name in ('AAA', 'BBB'):
            self.assertTrue((self.output / name / 'backtest_summary.json').exists())
        self.assertFalse((self.output / 'CCC').exists())
        pooled = self.summary()['pooled']
        self.assertEqual(pooled['trades'], 2)
        self.assertEqual({side: pooled['by_direction'][side]['trades']
                          for side in ('LONG', 'SHORT')}, {'LONG': 1, 'SHORT': 1})
        self.assertEqual(self.summary()['counts'],
                         {'completed': 2, 'skipped': 1, 'failed': 0})

    def test_the_sweep_matches_a_single_backtest_of_the_same_dataset(self):
        self.add('AAA', long_candles(), 'AAA-USDT')
        self.assertEqual(self.run_sweep(*GRID), 0)
        direct = run(BacktestConfig('AAA-USDT', self.root / 'AAA', D('10000'),
                                    profile=StrategyProfile(boundary_proximity=D('5'),
                                                            stop_buffer=D('1'))))
        written = json.loads((self.output / 'AAA' / 'backtest_summary.json').read_text('utf-8'))
        self.assertEqual(written['metrics'], json.loads(json.dumps(direct.summary)))
        self.assertEqual(self.rows()['AAA']['ending_equity'], direct.summary['ending_equity'])

    def test_price_scaling_reads_the_first_entry_close(self):
        self.add('AAA', long_candles(), 'AAA-USDT')
        self.assertEqual(self.run_sweep(), 0)
        row = self.rows()['AAA']
        self.assertEqual((row['reference_price'], row['boundary_proximity'], row['stop_buffer']),
                         ('127', '0.635', '0.127'))

    def test_the_reference_is_the_first_entry_close_inside_the_window(self):
        self.add('AAA', long_candles(), 'AAA-USDT')
        later = entry_candles()[16].close_time                        # first close of 124
        windowed = load_stream(self.root / 'AAA' / 'aaausdt_15m.jsonl', 'AAA-USDT', '15m',
                               start=later)
        self.assertEqual(sweep.reference_price(Dataset('AAA-USDT', {'15m': windowed}), '15m'),
                         D('124'))

    def test_price_scaling_makes_the_result_independent_of_the_price_level(self):
        self.add('LOW', long_candles(), 'LOW-USDT')
        self.add('HIGH', rescaled(long_candles(), 1000), 'HIGH-USDT')
        self.assertEqual(self.run_sweep('--proximity-ratio', '0.04',
                                        '--stop-buffer-ratio', '0.008'), 0)
        trades = {row['symbol']: row for row in self.trades()}
        self.assertEqual(set(trades), {'LOW-USDT', 'HIGH-USDT'})
        low, high = trades['LOW-USDT'], trades['HIGH-USDT']
        self.assertEqual((low['direction'], low['exit_reason']),
                         (high['direction'], high['exit_reason']))
        self.assertLess(abs(D(low['r_multiple']) - D(high['r_multiple'])), D('0.0001'))

    def test_a_run_error_is_failed_not_skipped(self):
        self.add('AAA', long_candles(), 'AAA-USDT')
        with mock.patch('agent_trading.backtest.engine.run', side_effect=ValueError('boom')):
            self.assertEqual(self.run_sweep(*GRID), 1)
        row = self.rows()['AAA']
        self.assertEqual(row['status'], 'FAILED')
        self.assertIn('boom', row['reason'])

    def test_only_skipped_datasets_is_not_a_success(self):
        self.add('CCC', gapped(long_candles()), 'CCC-USDT')
        self.assertEqual(self.run_sweep(*GRID), 1)

    def test_absolute_price_flags_are_refused_under_price_scaling(self):
        self.add('AAA', long_candles(), 'AAA-USDT')
        for flags in (('--stop-buffer', '1'), ('--trailing-buffer', '1'),
                      ('--slippage', '5'), ('--proximity-ratio', '0')):
            with self.subTest(flags=flags):
                self.assertEqual(self.run_sweep(*flags), 2)
        self.assertEqual(self.run_sweep('--scale', 'none', '--stop-buffer', '1'), 0)

    def test_duplicate_symbols_are_flagged(self):
        self.add('AAA', long_candles(), 'AAA-USDT')
        self.add('AAA_copy', long_candles(), 'AAA-USDT')
        self.assertEqual(self.run_sweep(*GRID), 0)
        self.assertIn('DUPLICATE_SYMBOL AAA-USDT: AAA, AAA_copy', self.summary()['warnings'])
        self.assertIn('POOLED_TRADES_NOT_INDEPENDENT', self.summary()['limitations'])

    def test_the_universe_limitations_travel_into_the_summary(self):
        self.add('AAA', long_candles(), 'AAA-USDT')
        universe = select_universe((SpotInstrument('AAA-USDT', 'AAA', 'USDT', 'live'),),
                                   (SpotVolume('AAA-USDT', None, D('1')),),
                                   as_of=long_candles()[-1].close_time)
        write_universe(universe, self.root / 'universe.json')
        self.assertEqual(self.run_sweep(*GRID), 0)
        self.assertEqual(list(self.rows()), ['AAA'])
        self.assertIn('SURVIVORSHIP_BIAS', self.summary()['limitations'])

    def test_reruns_produce_identical_bytes(self):
        self.standard_root()
        second = self.output.with_name('again')
        self.assertEqual(self.run_sweep(*GRID), 0)
        self.assertEqual(self.run_sweep(*GRID, output=second), 0)
        for name in ('sweep_summary.json', 'sweep_symbols.csv', 'sweep_trades.csv'):
            self.assertEqual((self.output / name).read_bytes(), (second / name).read_bytes())

    def test_the_sweep_never_reaches_the_network(self):
        source = Path(sweep.__file__).read_text(encoding='utf-8')
        for name in ('okx_mcp', 'open_atk_mcp', 'from .fetch', 'import fetch'):
            self.assertNotIn(name, source)



async def no_sleep(seconds):
    return None


class EndToEndTests(unittest.TestCase):
    def test_a_fetched_universe_is_swept_without_the_network(self):
        from agent_trading.backtest import fetch
        from fetch_fixtures import FakeVenue
        series = {}
        for symbol, candles in (('AAA-USDT', long_candles()), ('BBB-USDT', short_candles())):
            for candle in relabel(candles, symbol):
                series.setdefault((symbol, candle.timeframe), []).append(candle)
        as_of = max(candle.close_time for candle in long_candles()) + timedelta(hours=1)
        venue = FakeVenue(series, {'AAA-USDT': 10, 'BBB-USDT': 5, 'USDC-USDT': 99}, as_of)
        with tempfile.TemporaryDirectory() as directory:
            data, runs = Path(directory) / 'data', Path(directory) / 'runs'
            with redirect_stdout(io.StringIO()):
                self.assertEqual(fetch.main(['--universe', '--top', '2', '--out', str(data),
                                             '--limits', '4H=500,1H=500,15m=500'],
                                            mcp_factory=venue.factory, sleep=no_sleep,
                                            monotonic=lambda: 0.0, now=lambda: as_of), 0)
                self.assertEqual(sweep.main(['--data', str(data), '--output', str(runs),
                                             *GRID]), 0)
            summary = json.loads((runs / 'sweep_summary.json').read_text('utf-8'))
            self.assertEqual({row['dataset']: (row['symbol'], row['trades'])
                              for row in summary['datasets']},
                             {'AAA-USDT': ('AAA-USDT', 1), 'BBB-USDT': ('BBB-USDT', 1)})
            self.assertEqual(summary['pooled']['by_direction']['LONG']['trades'], 1)
            self.assertEqual(summary['pooled']['by_direction']['SHORT']['trades'], 1)
            self.assertIn('SURVIVORSHIP_BIAS', summary['limitations'])


if __name__ == '__main__':
    unittest.main()
