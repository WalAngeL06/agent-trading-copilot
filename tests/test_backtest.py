"""Causal Strategy V1 backtest engine: data, causality, accounting and metrics.

The engine owns no strategy rule. These tests check the replay order, the
loading discipline, the accounting that reads production ledgers, and the
metric arithmetic. Nothing here asserts profitability.
"""
import csv
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from agent_trading.backtest import report
from agent_trading.backtest.config import BacktestConfig, CostModel, utc
from agent_trading.backtest.dataset import discover, load_dataset, load_stream
from agent_trading.backtest.engine import run
from agent_trading.backtest.metrics import compute
from agent_trading.backtest.recorder import (EquityPoint, SliceRecord, TradeRecord,
                                             equity_curve)
from agent_trading.market import bar_duration
from agent_trading.strategy_v1 import StrategyProfile

from guide_fixtures import guide_acceptance_profile, short_acceptance_candles
from strategy_v1_fixtures import (D, SYMBOL, acceptance_candles, acceptance_profile,
                                  all_candles, bias_candles)

FIXTURES = Path(__file__).with_name('data')


def dump(candles, directory, symbol=SYMBOL):
    """Freeze candles as the project's JSONL candle shape."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for candle in candles:
        grouped.setdefault(candle.timeframe, []).append(candle)
    slug = symbol.replace('-', '').lower()
    for timeframe, stream in grouped.items():
        path = directory / f'{slug}_{timeframe}.jsonl'
        with path.open('w', encoding='utf-8', newline='\n') as handle:
            for candle in sorted(stream, key=lambda c: c.close_time):
                handle.write(json.dumps({
                    'symbol': candle.symbol, 'timeframe': candle.timeframe,
                    'close_time': candle.close_time.isoformat().replace('+00:00', 'Z'),
                    'open': str(candle.open), 'high': str(candle.high),
                    'low': str(candle.low), 'close': str(candle.close),
                    'volume': str(candle.volume), 'closed': True}, sort_keys=True) + '\n')
    return directory


class DatasetLoadingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _one(self, rows, name='btcusdt_4H.jsonl'):
        path = self.dir / name
        with path.open('w', encoding='utf-8', newline='\n') as handle:
            for row in rows:
                handle.write(json.dumps(row) + '\n')
        return path

    def _row(self, close_time, changes=None):
        row = {'symbol': SYMBOL, 'timeframe': '4H', 'close_time': close_time,
               'open': '100', 'high': '101', 'low': '99', 'close': '100.5',
               'volume': '1', 'closed': True}
        row.update(changes or {})
        return row

    def test_open_candles_are_excluded_and_counted(self):
        path = self._one([self._row('2026-01-01T04:00:00Z'),
                          self._row('2026-01-01T08:00:00Z', {'closed': False})])
        load = load_stream(path, SYMBOL, '4H')
        self.assertEqual(load.count, 1)
        self.assertEqual(load.excluded_open, 1)

    def test_a_malformed_row_is_rejected_with_its_line_number(self):
        for changes in ({'close': None}, {'high': '1'}, {'open': 1.5}, {'close_time': 'x'}):
            with self.subTest(changes=changes):
                path = self._one([self._row('2026-01-01T04:00:00Z', changes)])
                with self.assertRaises(ValueError) as caught:
                    load_stream(path, SYMBOL, '4H')
                self.assertIn('row 1', str(caught.exception))

    def test_a_gap_in_a_stream_is_rejected(self):
        path = self._one([self._row('2026-01-01T04:00:00Z'),
                          self._row('2026-01-01T16:00:00Z')])
        with self.assertRaises(ValueError) as caught:
            load_stream(path, SYMBOL, '4H')
        self.assertIn('gap', str(caught.exception))

    def test_a_duplicate_candle_is_rejected(self):
        path = self._one([self._row('2026-01-01T04:00:00Z'),
                          self._row('2026-01-01T04:00:00Z')])
        with self.assertRaises(ValueError):
            load_stream(path, SYMBOL, '4H')

    def test_a_foreign_symbol_or_timeframe_is_rejected(self):
        path = self._one([self._row('2026-01-01T04:00:00Z', {'symbol': 'ETH-USDT'})])
        with self.assertRaises(ValueError):
            load_stream(path, SYMBOL, '4H')

    def test_a_window_filter_excludes_outside_candles(self):
        path = self._one([self._row('2026-01-01T04:00:00Z'),
                          self._row('2026-01-01T08:00:00Z'),
                          self._row('2026-01-01T12:00:00Z')])
        load = load_stream(path, SYMBOL, '4H', start=utc('2026-01-01T08:00:00Z'),
                           end=utc('2026-01-01T12:00:00Z'))
        self.assertEqual(load.count, 2)
        self.assertEqual(load.excluded_window, 1)

    def test_csv_datasets_load_identically(self):
        rows = [self._row('2026-01-01T04:00:00Z'), self._row('2026-01-01T08:00:00Z')]
        self._one(rows)
        csv_path = self.dir / 'btcusdt_csv_4H.csv'
        with csv_path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        self.assertEqual([c.close for c in load_stream(csv_path, SYMBOL, '4H').candles],
                         [c.close for c in load_stream(self.dir / 'btcusdt_4H.jsonl',
                                                       SYMBOL, '4H').candles])

    def test_discovery_reports_missing_and_ambiguous_files(self):
        with self.assertRaises(ValueError):
            discover(self.dir, '4H')
        self._one([self._row('2026-01-01T04:00:00Z')])
        self._one([self._row('2026-01-01T04:00:00Z')], name='other_4H.jsonl')
        with self.assertRaises(ValueError):
            discover(self.dir, '4H')


class CausalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = dump(acceptance_candles(), Path(cls._tmp.name))
        cls.config = BacktestConfig(SYMBOL, cls.dir, D('10000'),
                                    profile=acceptance_profile())
        cls.result = run(cls.config)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_replay_order_is_time_then_highest_timeframe(self):
        roles = self.config.timeframes
        keys = [(c.close_time, roles.rank(c.timeframe))
                for c in self.result.dataset.candles(roles)]
        self.assertEqual(keys, sorted(keys))

    def test_every_event_is_chronological(self):
        times = [event.observed_at for event in self.result.events]
        self.assertEqual(times, sorted(times))

    def test_no_event_precedes_the_evidence_it_cites(self):
        seen = {}
        for event in self.result.events:
            for reference in event.evidence_ids:
                self.assertIn(reference, seen)
                self.assertLessEqual(seen[reference], event.observed_at)
            seen[event.id] = event.observed_at

    def test_no_entry_uses_a_higher_timeframe_bar_that_had_not_closed(self):
        roles = self.config.timeframes
        for record in self.result.trades:
            for timeframe in (roles.bias, roles.range):
                closes = [c.close_time for c in self.result.dataset.streams[timeframe].candles
                          if c.close_time <= record.entry_at]
                self.assertTrue(closes, 'entry must follow a closed higher timeframe bar')
                self.assertLessEqual(max(closes), record.entry_at)

    def test_an_entry_never_precedes_its_own_setup(self):
        for record in self.result.trades:
            self.assertGreater(record.entry_at, record.setup_at)

    def test_a_regressing_dataset_is_refused(self):
        roles = self.config.timeframes
        ordered = self.result.dataset.candles(roles)
        broken = replace(self.result.dataset,
                         streams=dict(self.result.dataset.streams))

        class Reversed:
            symbol = SYMBOL
            streams = broken.streams

            def candles(self, _roles):
                return list(reversed(ordered))

            def as_dict(self):
                return broken.as_dict()

        with self.assertRaises(ValueError):
            run(self.config, dataset=Reversed())

    def test_the_replay_is_deterministic(self):
        again = run(self.config)
        self.assertEqual([(e.id, e.kind, e.observed_at) for e in self.result.events],
                         [(e.id, e.kind, e.observed_at) for e in again.events])
        self.assertEqual([t.as_dict() for t in self.result.trades],
                         [t.as_dict() for t in again.trades])
        self.assertEqual(self.result.summary, again.summary)


class ProductionStrategyTests(unittest.TestCase):
    def test_the_engine_drives_the_shipped_strategy_class(self):
        from agent_trading.backtest import engine as module
        from agent_trading.strategy_v1 import StrategyV1
        self.assertIs(module.StrategyV1, StrategyV1)

    def test_no_backtest_module_reimplements_a_strategy_rule(self):
        # Calls, not substrings: `entry_price` as a local parameter name is fine,
        # `entry_price(` would mean the backtester priced an entry itself.
        banned = ('RangeEngine(', 'ManipulationEngine(', 'GapEngine(', 'BiasEngine(',
                  'StructureEngine(', 'SwingEngine(', 'RiskEngine(', 'entry_price(',
                  'partial_target(', 'tighten_stop(', 'PendingLimitPaperBroker(')
        package = Path(module_dir())
        for path in sorted(package.glob('*.py')):
            if path.name == 'fetch.py':
                continue
            text = path.read_text(encoding='utf-8')
            for name in banned:
                self.assertNotIn(name, text, f'{path.name} must not reimplement {name}')


def module_dir():
    from agent_trading import backtest
    return Path(backtest.__file__).parent


class AccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = dump(acceptance_candles(), Path(cls._tmp.name))
        cls.result = run(BacktestConfig(SYMBOL, cls.dir, D('10000'),
                                        profile=acceptance_profile()))
        cls.record = cls.result.trades[0]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_one_logical_trade_not_one_per_partial(self):
        self.assertEqual(len(self.result.trades), 1)
        self.assertEqual(len(self.record.slices), 4)
        self.assertEqual(self.result.summary['filled_logical_trades'], 1)

    def test_partial_take_profit_accounting(self):
        partials = [s for s in self.record.slices if s.kind == 'PARTIAL_TP']
        self.assertEqual([s.trigger_r for s in partials], [D('1.0'), D('2.0')])
        self.assertEqual([s.quantity for s in partials],
                         [D('2.00000000'), D('2.00000000')])
        self.assertEqual([s.net_pnl for s in partials], [D('20'), D('40')])
        self.assertEqual(self.record.partial_count, 2)

    def test_range_high_partial_exit_accounting(self):
        found = [s for s in self.record.slices if s.kind == 'RANGE_HIGH']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].quantity, D('5.00000000'))
        self.assertEqual(found[0].exit_price, D('170'))
        self.assertEqual(found[0].net_pnl, D('210'))
        self.assertTrue(self.record.range_high_reached)

    def test_runner_accounting(self):
        found = [s for s in self.record.slices if s.kind == 'RUNNER']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].quantity, D('1.00000000'))
        self.assertEqual(found[0].exit_price, D('160'))
        self.assertEqual(found[0].net_pnl, D('32'))
        self.assertTrue(self.record.runner_opened)
        self.assertTrue(self.record.runner_stopped)
        self.assertEqual(self.record.exit_reason, 'RUNNER_STOP')

    def test_break_even_and_trailing_are_recorded(self):
        self.assertTrue(self.record.break_even_reached)
        self.assertEqual(self.record.trailing_updates, 3)

    def test_quantity_and_pnl_reconcile(self):
        self.assertEqual(sum(s.quantity for s in self.record.slices),
                         self.record.original_quantity)
        self.assertEqual(self.record.net_pnl, D('302'))
        self.assertEqual(self.record.gross_pnl, D('302'))
        self.assertEqual(self.record.cost, D('0'))
        self.assertEqual(self.record.initial_r, D('10'))
        self.assertEqual(self.record.r_multiple, D('302') / D('100'))

    def test_equity_calculation_follows_the_realised_slices(self):
        curve = self.result.curve
        self.assertEqual(curve[0].equity, D('10000'))
        self.assertEqual(curve[-1].equity, D('10302'))
        self.assertEqual(len(curve), 1 + len(self.record.slices))
        self.assertEqual(self.result.summary['ending_equity'], '10302')

    def test_costs_reduce_net_pnl_when_supplied(self):
        result = run(BacktestConfig(SYMBOL, self.dir, D('10000'),
                                    profile=acceptance_profile(),
                                    costs=CostModel(Decimal('0.001'), Decimal('1'))))
        record = result.trades[0]
        self.assertGreater(record.cost, 0)
        self.assertLess(record.net_pnl, record.gross_pnl)
        self.assertEqual(record.gross_pnl, D('302'))


class ZeroTradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run(BacktestConfig(SYMBOL, FIXTURES, D('10000')))

    def test_the_real_fixture_window_produces_no_trade(self):
        self.assertEqual(self.result.trades, ())
        self.assertEqual(self.result.summary['filled_logical_trades'], 0)

    def test_zero_denominators_are_null_not_fabricated(self):
        for key in ('win_rate', 'profit_factor', 'average_r', 'median_r', 'expectancy_r',
                    'average_winning_r', 'average_losing_r'):
            self.assertIsNone(self.result.summary[key], key)
        self.assertIsNone(self.result.summary['average_trade_duration_seconds'])

    def test_equity_is_unchanged_and_drawdown_is_zero(self):
        self.assertEqual(self.result.summary['starting_equity'], '10000')
        self.assertEqual(self.result.summary['ending_equity'], '10000')
        self.assertEqual(self.result.summary['max_drawdown_absolute'], '0')
        self.assertEqual(self.result.summary['max_drawdown_percent'], '0')

    def test_the_funnel_still_reports_what_happened(self):
        funnel = self.result.summary_document()['funnel']
        self.assertGreater(funnel['bias_breaks'], 0)
        self.assertGreater(funnel['fvgs_detected'], 0)
        self.assertEqual(funnel['setups'], 0)


def synthetic_record(trade_id, net, r_multiple, seconds=3600, offset=0):
    """A hand-built record for unit-testing the aggregator only."""
    base = bias_candles()[0].close_time
    opened = base + timedelta(seconds=offset)
    exited = opened + timedelta(seconds=seconds)
    net = D(str(net))
    item = SliceRecord('RANGE_HIGH' if net >= 0 else 'STOP', None, None, D('1'),
                       D('100'), net, D('0'), net, D('0'), exited)
    return TradeRecord(trade_id, SYMBOL, 'LONG', opened, opened, D('100'), D('90'),
                       D('10'), D('1'), D('10'), (item,), exited,
                       'STOP_LOSS' if net < 0 else 'RANGE_HIGH', 'CLOSED',
                       net, D('0'), net, D(str(r_multiple)), seconds,
                       0, False, False, False, False, 0)


class MetricArithmeticTests(unittest.TestCase):
    """Unit tests for the aggregator, using hand-built records.

    These are NOT backtest results: they exercise the metric arithmetic on a
    multi-trade ledger, which one replay cannot currently produce because
    Strategy V1 evaluates a single range per run.
    """

    class _Strategy:
        events = ()

    def _summary(self, records, starting=D('1000')):
        curve = equity_curve(records, starting, records[0].setup_at)
        return compute(self._Strategy(), records, curve, starting), curve

    def test_win_rate_profit_factor_and_r_statistics(self):
        records = (synthetic_record('T1', 200, 2, offset=0),
                   synthetic_record('T2', -100, -1, offset=7200),
                   synthetic_record('T3', 100, 1, offset=14400),
                   synthetic_record('T4', -100, -1, offset=21600))
        summary, _ = self._summary(records)
        self.assertEqual(summary['wins'], 2)
        self.assertEqual(summary['losses'], 2)
        self.assertEqual(summary['break_even_trades'], 0)
        self.assertEqual(summary['win_rate'], '0.5')
        self.assertEqual(summary['gross_profit'], '300')
        self.assertEqual(summary['gross_loss'], '200')
        self.assertEqual(summary['profit_factor'], '1.5')
        self.assertEqual(Decimal(summary['average_r']), Decimal('0.25'))
        self.assertEqual(Decimal(summary['expectancy_r']), Decimal('0.25'))
        self.assertEqual(Decimal(summary['median_r']), Decimal('0'))
        self.assertEqual(Decimal(summary['average_winning_r']), Decimal('1.5'))
        self.assertEqual(Decimal(summary['average_losing_r']), Decimal('-1'))

    def test_break_even_trades_are_counted_separately(self):
        summary, _ = self._summary((synthetic_record('T1', 0, 0, offset=0),
                                    synthetic_record('T2', 50, 1, offset=7200)))
        self.assertEqual(summary['break_even_trades'], 1)
        self.assertEqual(summary['wins'], 1)
        self.assertEqual(summary['losses'], 0)
        self.assertIsNone(summary['profit_factor'])     # no losing side at all

    def test_drawdown_is_measured_from_the_running_peak(self):
        records = (synthetic_record('T1', 500, 5, offset=0),
                   synthetic_record('T2', -300, -3, offset=7200),
                   synthetic_record('T3', 100, 1, offset=14400))
        summary, curve = self._summary(records)
        self.assertEqual([point.equity for point in curve],
                         [D('1000'), D('1500'), D('1200'), D('1300')])
        self.assertEqual(summary['max_drawdown_absolute'], '300')
        self.assertEqual(Decimal(summary['max_drawdown_percent']), Decimal('20'))
        self.assertEqual(summary['ending_equity'], '1300')
        self.assertEqual(Decimal(summary['total_return_percent']), Decimal('30'))

    def test_average_duration_and_exit_reasons(self):
        summary, _ = self._summary((synthetic_record('T1', 100, 1, 1000, offset=0),
                                    synthetic_record('T2', -50, -1, 3000, offset=7200)))
        self.assertEqual(summary['average_trade_duration_seconds'], 2000)
        self.assertEqual(summary['exit_reason_counts'],
                         {'RANGE_HIGH': 1, 'STOP_LOSS': 1})


class ReportArtifactTests(unittest.TestCase):
    def setUp(self):
        self._data = tempfile.TemporaryDirectory()
        self._out = tempfile.TemporaryDirectory()
        self.addCleanup(self._data.cleanup)
        self.addCleanup(self._out.cleanup)
        data_dir = dump(acceptance_candles(), Path(self._data.name))
        self.result = run(BacktestConfig(SYMBOL, data_dir, D('10000'),
                                         profile=acceptance_profile()))
        self.paths = report.write(self.result, Path(self._out.name))
        self.out = Path(self._out.name)

    def test_every_documented_artifact_is_written(self):
        names = {path.name for path in self.paths}
        for expected in report.FILES:
            self.assertIn(expected, names)

    def test_the_summary_is_json_with_stable_sections(self):
        payload = json.loads((self.out / 'backtest_summary.json').read_text('utf-8'))
        self.assertEqual(payload['schema_version'], 'strategy-v1-backtest-v0.1')
        for section in ('dataset', 'costs', 'metrics', 'funnel', 'demo', 'limitations'):
            self.assertIn(section, payload)

    def test_the_demo_card_carries_only_real_values(self):
        demo = json.loads((self.out / 'backtest_summary.json').read_text('utf-8'))['demo']
        self.assertEqual(demo['status'], 'completed')
        self.assertEqual(demo['symbol'], SYMBOL)
        self.assertEqual(demo['total_trades'], 1)
        self.assertEqual(demo['ending_equity'], '10302')
        self.assertEqual(demo['starting_equity'], '10000')

    def test_trades_csv_has_one_row_per_logical_trade(self):
        with (self.out / 'trades.csv').open(encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['trade_id'], 'T0001')
        self.assertEqual(rows[0]['exit_reason'], 'RUNNER_STOP')
        self.assertEqual(rows[0]['net_pnl'], '302')

    def test_equity_curve_csv_is_chart_ready(self):
        with (self.out / 'equity_curve.csv').open(encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(list(rows[0]), list(report.EQUITY_COLUMNS))
        self.assertEqual(rows[0]['equity'], '10000')
        self.assertEqual(rows[-1]['equity'], '10302')
        for row in rows:
            Decimal(row['equity'])
            Decimal(row['drawdown_percent'])

    def test_events_jsonl_is_one_object_per_line(self):
        lines = (self.out / 'events.jsonl').read_text('utf-8').strip().splitlines()
        self.assertEqual(len(lines), len(self.result.events))
        first = json.loads(lines[0])
        for key in ('id', 'kind', 'timeframe', 'observed_at', 'payload'):
            self.assertIn(key, first)

    def test_run_config_records_the_exact_strategy_used(self):
        payload = json.loads((self.out / 'run_config.json').read_text('utf-8'))
        self.assertEqual(payload['symbol'], SYMBOL)
        self.assertEqual(payload['costs'], {'fee_rate': '0', 'slippage': '0',
                                            'applied': False})
        self.assertEqual(payload['strategy']['runner_fraction'], '0.10')
        self.assertEqual(payload['strategy']['partial_take_profits'],
                         [{'r_multiple': '1.0', 'close_fraction': '0.20'},
                          {'r_multiple': '2.0', 'close_fraction': '0.20'}])


class ConfigTests(unittest.TestCase):
    def test_starting_equity_is_pushed_into_the_strategy_profile(self):
        config = BacktestConfig(SYMBOL, FIXTURES, D('2500'))
        self.assertEqual(config.profile.equity, D('2500'))

    def test_costs_default_to_zero_and_are_never_assumed(self):
        config = BacktestConfig(SYMBOL, FIXTURES)
        self.assertEqual(config.costs.fee_rate, D('0'))
        self.assertEqual(config.costs.slippage, D('0'))
        self.assertFalse(config.costs.enabled)

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            BacktestConfig('', FIXTURES)
        with self.assertRaises(ValueError):
            BacktestConfig(SYMBOL, FIXTURES, D('0'))
        with self.assertRaises(ValueError):
            CostModel(D('-1'))
        with self.assertRaises(ValueError):
            BacktestConfig(SYMBOL, FIXTURES, start='2026-02-01', end='2026-01-01')

    def test_the_window_accepts_iso_text_and_normalises_to_utc(self):
        config = BacktestConfig(SYMBOL, FIXTURES, start='2026-01-01T00:00:00Z')
        self.assertEqual(config.start.tzinfo.utcoffset(config.start), timedelta(0))


class ShortAccountingTests(unittest.TestCase):
    """[U-RANGE-GUIDE-002] A reflected short run is recorded like its long twin."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = dump(short_acceptance_candles(), Path(cls._tmp.name))
        cls.result = run(BacktestConfig(SYMBOL, cls.dir, D('10000'),
                                        profile=guide_acceptance_profile()))
        cls.record = cls.result.trades[0]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_one_short_logical_trade_is_recorded(self):
        self.assertEqual(len(self.result.trades), 1)
        self.assertEqual(self.record.direction, 'SHORT')
        self.assertEqual(self.result.summary['filled_logical_trades'], 1)

    def test_the_boundary_slice_is_the_range_low(self):
        found = [s for s in self.record.slices if s.kind == 'RANGE_LOW']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].exit_price, D('118'))
        self.assertTrue(self.record.range_high_reached)

    def test_the_funnel_counts_the_htf_context_verdicts(self):
        funnel = self.result.summary_document()['funnel']
        self.assertEqual(funnel['htf_context_checks'], 1)

    def test_the_short_risk_and_result_are_measured_on_the_right_side(self):
        self.assertGreater(self.record.initial_r, 0)
        self.assertGreater(self.record.initial_stop, self.record.entry_price)
        self.assertGreater(self.record.r_multiple, 0)
        self.assertEqual(self.record.partial_count, 2)

class CliTests(unittest.TestCase):
    def test_the_cli_runs_a_whole_backtest_and_writes_artifacts(self):
        from agent_trading.backtest.__main__ import main
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as out:
            dump(acceptance_candles(), Path(data))
            # The shipped acceptance scenario predates [U-RANGE-GUIDE-002] and
            # replays under the superseded gate it was designed for.
            code = main(['--symbol', SYMBOL, '--data', data, '--output', out,
                         '--starting-equity', '10000', '--stop-buffer', '1',
                         '--boundary-proximity', '5',
                         '--direction', 'LONG_ONLY',
                         '--direction-gate', 'BIAS_LONG_PERMISSION',
                         '--partial-tp', '1.0:0.20,2.0:0.20',
                         '--runner-fraction', '0.10',
                         # [U-DD-DEVIATION-001] this scenario is pre-DD.
                         '--entry-models', 'HTF_FVG_REVERSAL', '--model2-htf-fvg', 'false',
                         '--eq-scale-out', 'none', '--break-even-trigger', 'R_MULTIPLE',
                         '--secondary-fvg'])
            self.assertEqual(code, 0)
            payload = json.loads((Path(out) / 'backtest_summary.json').read_text('utf-8'))
            self.assertEqual(payload['metrics']['filled_logical_trades'], 1)
            self.assertEqual(payload['metrics']['ending_equity'], '10302')

    def test_the_direction_rules_are_selectable(self):
        from agent_trading.backtest.__main__ import build_config, build_parser

        def profile(extra):
            return build_config(build_parser().parse_args(
                ['--data', '.', '--output', '.'] + extra)).profile

        default = profile([])
        self.assertEqual((default.direction, default.direction_gate),
                         ('BOTH', 'GUIDE_HTF_CONTEXT'))
        self.assertTrue(default.htf_confluence_required)
        tuned = profile(['--direction', 'SHORT_ONLY', '--htf-zone-tolerance', '250',
                         '--no-htf-confluence'])
        self.assertEqual(tuned.direction, 'SHORT_ONLY')
        self.assertEqual(tuned.effective_htf_zone_tolerance, D('250'))
        self.assertFalse(tuned.htf_confluence_required)


if __name__ == '__main__':
    unittest.main()
