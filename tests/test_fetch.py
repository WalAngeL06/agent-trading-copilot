"""Multi-pair history fetcher building blocks [U-MULTI-PAIR-001].

Offline only: pages come from an in-memory venue that honours OKX's `after`
cursor (records strictly older than the cursor's open time, newest first).
"""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import io
import json
from pathlib import Path
import tempfile
import unittest

from agent_trading.backtest.config import BacktestConfig
from agent_trading.backtest.dataset import load_dataset, load_stream
from agent_trading.backtest.fetch import (Pacer, fetch_stream, latest_contiguous, main, open_ms,
                                          parse_limits, write_stream)
from agent_trading.market import bar_duration
from agent_trading.models import Candle
from agent_trading.okx_mcp import McpMarketError
from fetch_fixtures import FakeVenue

AS_OF = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
AS_OF_MS = int(AS_OF.timestamp() * 1000)
ROLES = ('4H', '1H', '15m')


def bar(close_time, timeframe='15m', symbol='ETH-USDT', price='100'):
    price = D(price)
    return Candle(symbol, timeframe, close_time, price, price + 1, price - 1, price, D('5'))


def history(count, timeframe='15m', end=AS_OF, symbol='ETH-USDT'):
    step = bar_duration(timeframe)
    return [bar(end - step * index, timeframe, symbol) for index in range(count)][::-1]


class Venue:
    """Serves closed candles older than `after`, newest first, at most `cap`."""

    def __init__(self, candles, cap=300):
        self.candles = sorted(candles, key=lambda c: c.close_time, reverse=True)
        self.cap = cap
        self.calls = []

    async def __call__(self, symbol, timeframe, size, after):
        self.calls.append((size, after))
        older = [c for c in self.candles if open_ms(c) < after][:min(size, self.cap)]
        return tuple(sorted(older, key=lambda c: c.close_time))


class LimitTests(unittest.TestCase):
    def test_limits_are_set_per_timeframe_with_a_fallback(self):
        self.assertEqual(parse_limits('4H=10000,1H=10000,15m=36000', ROLES, 1440),
                         {'4H': 10000, '1H': 10000, '15m': 36000})
        self.assertEqual(parse_limits('15m=600', ROLES, 1440),
                         {'4H': 1440, '1H': 1440, '15m': 600})
        self.assertEqual(parse_limits(None, ROLES, 1440), dict.fromkeys(ROLES, 1440))

    def test_malformed_limits_are_rejected(self):
        for text in ('15m', '15m=0', '15m=-5', '15m=1.5', '5m=10', '15m=1,15m=2', '15m=abc'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_limits(text, ROLES, 1440)


class ContiguityTests(unittest.TestCase):
    def test_an_unbroken_stream_is_kept_whole(self):
        candles = history(5)
        self.assertEqual(latest_contiguous(candles, '15m'), (tuple(candles), 0, 0, None))

    def test_only_the_newest_unbroken_segment_survives_a_gap(self):
        candles = history(6)
        broken = candles[:2] + candles[3:]                    # the third bar is missing
        kept, dropped, gaps, latest = latest_contiguous(broken, '15m')
        self.assertEqual(kept, tuple(candles[3:]))
        self.assertEqual((dropped, gaps), (2, 1))
        self.assertEqual(latest, (candles[1].close_time, candles[3].close_time))


class WriteTests(unittest.TestCase):
    def test_a_stream_is_written_atomically_as_lf_jsonl_that_loads_back(self):
        candles = history(4)
        with tempfile.TemporaryDirectory() as directory:
            path = write_stream(directory, 'ETH-USDT', '15m', candles)
            self.assertEqual(path.name, 'ethusdt_15m.jsonl')
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['ethusdt_15m.jsonl'])
            self.assertNotIn(b'\r\n', path.read_bytes())
            self.assertEqual(load_stream(path, 'ETH-USDT', '15m').candles, tuple(candles))


class PagingTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_first_page_ends_at_the_shared_as_of(self):
        venue = Venue(history(10))
        await fetch_stream(venue, 'ETH-USDT', '15m', 5, AS_OF)
        self.assertEqual(venue.calls[0], (5, AS_OF_MS))

    async def test_cursors_strictly_decrease_until_the_wanted_count(self):
        candles = history(700)
        venue = Venue(candles)
        result = await fetch_stream(venue, 'ETH-USDT', '15m', 650, AS_OF)
        self.assertEqual(result.candles, tuple(candles[-650:]))
        cursors = [after for _size, after in venue.calls]
        self.assertEqual(cursors, sorted(cursors, reverse=True))
        self.assertEqual(len(set(cursors)), len(cursors))
        self.assertEqual([size for size, _after in venue.calls], [300, 300, 50])
        self.assertFalse(result.exhausted)

    async def test_short_pages_from_the_venue_are_accepted(self):
        venue = Venue(history(250), cap=100)
        result = await fetch_stream(venue, 'ETH-USDT', '15m', 250, AS_OF)
        self.assertEqual(len(result.candles), 250)

    async def test_an_empty_page_is_confirmed_once_then_history_is_exhausted(self):
        venue = Venue(history(120))
        result = await fetch_stream(venue, 'ETH-USDT', '15m', 1000, AS_OF)
        self.assertEqual(len(result.candles), 120)
        self.assertTrue(result.exhausted)
        self.assertEqual(venue.calls[-1][1], venue.calls[-2][1])      # asked twice

    async def test_a_gap_keeps_the_newest_segment_and_says_so(self):
        candles = history(10)
        venue = Venue(candles[:4] + candles[5:])
        result = await fetch_stream(venue, 'ETH-USDT', '15m', 10, AS_OF)
        self.assertEqual(result.candles, tuple(candles[5:]))
        self.assertEqual((result.dropped_bars, result.gaps), (4, 1))

    async def test_a_cursor_that_does_not_move_is_an_error(self):
        stuck = history(3)

        async def ignores_after(symbol, timeframe, size, after):
            return tuple(stuck)

        with self.assertRaises(ValueError):
            await fetch_stream(ignores_after, 'ETH-USDT', '15m', 100, AS_OF)


class Clock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class PacerTests(unittest.IsolatedAsyncioTestCase):
    def pacer(self, **kwargs):
        self.clock = Clock()
        settings = dict(pace=0.2, retries=4, sleep=self.clock.sleep,
                        monotonic=self.clock.monotonic)
        settings.update(kwargs)
        return Pacer(**settings)

    async def test_calls_are_spaced_by_the_pace(self):
        pacer = self.pacer()

        async def ok():
            return 'ok'

        self.assertEqual(await pacer.call(ok), 'ok')
        self.assertEqual(await pacer.call(ok), 'ok')
        self.assertEqual(self.clock.sleeps, [0.2])

    async def test_retryable_errors_back_off_and_retry(self):
        pacer = self.pacer()
        failures = iter(['MCP_TOOL_ERROR', 'MCP_TIMEOUT'])

        async def flaky():
            code = next(failures, None)
            if code:
                raise McpMarketError(code)
            return 'ok'

        self.assertEqual(await pacer.call(flaky), 'ok')
        self.assertEqual(self.clock.sleeps, [2, 4])

    async def test_session_and_contract_errors_are_not_retried(self):
        for code in ('MCP_UNAVAILABLE', 'TOOL_SCHEMA_DRIFT'):
            pacer = self.pacer()
            attempts = []

            async def broken():
                attempts.append(code)
                raise McpMarketError(code)

            with self.subTest(code=code), self.assertRaises(McpMarketError):
                await pacer.call(broken)
            self.assertEqual(len(attempts), 1)

    async def test_retries_are_bounded_and_the_backoff_is_capped(self):
        pacer = self.pacer(retries=6)
        attempts = []

        async def always():
            attempts.append(1)
            raise McpMarketError('MCP_TIMEOUT')

        with self.assertRaises(McpMarketError):
            await pacer.call(always)
        self.assertEqual(len(attempts), 7)
        self.assertEqual(self.clock.sleeps, [2, 4, 8, 16, 32, 60])



# ------------------------------------------------------------ orchestration
LIMITS = '4H=40,1H=60,15m=80'


def series_for(symbols, counts=(40, 60, 80)):
    series = {}
    for symbol in symbols:
        for timeframe, count in zip(ROLES, counts):
            series[(symbol, timeframe)] = history(count, timeframe, symbol=symbol)
    return series


async def no_sleep(seconds):
    return None


class OrchestrationTests(unittest.TestCase):
    """`python -m agent_trading.backtest.fetch` against an offline venue."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / 'okx_tr'

    def tearDown(self):
        self._tmp.cleanup()

    def run_main(self, venue, *arguments, now=AS_OF):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = main(['--out', str(self.out), '--limits', LIMITS, *arguments],
                            mcp_factory=venue.factory, sleep=no_sleep,
                            monotonic=lambda: 0.0, now=lambda: now)
            except SystemExit as stop:
                code = stop.code
        self.output = stdout.getvalue() + stderr.getvalue()
        return code

    def manifest(self):
        return json.loads((self.out / 'fetch_manifest.json').read_text('utf-8'))

    def test_universe_mode_writes_one_loadable_folder_per_selected_pair(self):
        venue = FakeVenue(series_for(['BTC-USDT', 'ETH-USDT', 'SOL-USDT']),
                          {'BTC-USDT': 900, 'ETH-USDT': 500, 'SOL-USDT': 100,
                           'USDC-USDT': 99999}, AS_OF)
        self.assertEqual(self.run_main(venue, '--universe', '--quote', 'USDT', '--top', '2'), 0)
        self.assertEqual(sorted(path.name for path in self.out.iterdir()),
                         ['BTC-USDT', 'ETH-USDT', 'fetch_manifest.json', 'universe.json'])
        for symbol in ('BTC-USDT', 'ETH-USDT'):
            dataset = load_dataset(BacktestConfig(symbol, self.out / symbol))
            self.assertEqual({tf: load.count for tf, load in dataset.streams.items()},
                             {'4H': 40, '1H': 60, '15m': 80})
        manifest = self.manifest()
        self.assertEqual(manifest['as_of'], AS_OF.isoformat())
        self.assertEqual(manifest['symbols']['BTC-USDT']['status'], 'COMPLETE')
        self.assertEqual(manifest['symbols']['BTC-USDT']['streams']['15m']['bars'], 80)
        self.assertEqual(venue.opens, 3)                  # the listing plus one per pair

    def test_explicit_symbols_use_the_same_layout_without_a_listing(self):
        venue = FakeVenue(series_for(['ETH-USDT']), {}, AS_OF)
        self.assertEqual(self.run_main(venue, '--symbols', 'ETH-USDT'), 0)
        self.assertTrue((self.out / 'ETH-USDT' / 'ethusdt_15m.jsonl').exists())
        self.assertFalse((self.out / 'universe.json').exists())
        self.assertEqual(venue.opens, 1)

    def test_a_single_symbol_keeps_the_flat_original_layout(self):
        venue = FakeVenue(series_for(['ETH-USDT']), {}, AS_OF)
        self.assertEqual(self.run_main(venue, '--symbol', 'ETH-USDT'), 0)
        self.assertEqual(sorted(path.name for path in self.out.iterdir()),
                         ['ethusdt_15m.jsonl', 'ethusdt_1H.jsonl', 'ethusdt_4H.jsonl'])

    def test_a_pair_that_keeps_failing_is_recorded_and_the_rest_continue(self):
        venue = FakeVenue(series_for(['AAA-USDT', 'BBB-USDT']), {}, AS_OF)
        venue.unavailable['AAA-USDT'] = 99
        self.assertEqual(self.run_main(venue, '--symbols', 'AAA-USDT,BBB-USDT'), 1)
        self.assertFalse((self.out / 'AAA-USDT').exists())
        self.assertTrue((self.out / 'BBB-USDT').exists())
        entry = self.manifest()['symbols']['AAA-USDT']
        self.assertEqual((entry['status'], entry['error']), ('FAILED', 'MCP_UNAVAILABLE'))
        self.assertEqual(venue.opens, 3)                  # AAA twice, BBB once
        self.assertNotIn('secret', self.output)

    def test_page_faults_are_retried_without_losing_the_pair(self):
        venue = FakeVenue(series_for(['AAA-USDT']), {}, AS_OF)
        venue.tool_errors['AAA-USDT'] = 2
        self.assertEqual(self.run_main(venue, '--symbols', 'AAA-USDT'), 0)
        self.assertEqual(self.manifest()['symbols']['AAA-USDT']['status'], 'COMPLETE')
        self.assertEqual(venue.opens, 1)

    def test_consecutive_failures_stop_the_run(self):
        symbols = ['AAA-USDT', 'BBB-USDT', 'CCC-USDT', 'DDD-USDT']
        venue = FakeVenue(series_for(symbols), {}, AS_OF)
        venue.unavailable.update(dict.fromkeys(symbols, 99))
        self.assertEqual(self.run_main(venue, '--symbols', ','.join(symbols)), 2)
        manifest = self.manifest()
        self.assertEqual(manifest['run']['stopped'], 'CONSECUTIVE_FAILURES')
        self.assertEqual(manifest['symbols']['DDD-USDT']['status'], 'PENDING')

    def test_contract_faults_abort_the_whole_run(self):
        venue = FakeVenue(series_for(['AAA-USDT']), {}, AS_OF)
        venue.open_error = McpMarketError('ATK_NOT_INSTALLED')
        self.assertEqual(self.run_main(venue, '--symbols', 'AAA-USDT'), 2)
        self.assertEqual(self.manifest()['run']['stopped'], 'FATAL:ATK_NOT_INSTALLED')
        drifted = FakeVenue(series_for(['AAA-USDT']), {'AAA-USDT': 5}, AS_OF)
        drifted.tools[-1].input_schema['properties']['instType']['enum'] = ['SWAP']
        self.out = Path(self._tmp.name) / 'second'
        self.assertEqual(self.run_main(drifted, '--universe'), 2)
        self.assertFalse((self.out / 'universe.json').exists())

    def test_an_existing_run_needs_resume_and_resume_keeps_its_choices(self):
        venue = FakeVenue(series_for(['AAA-USDT', 'BBB-USDT']),
                          {'AAA-USDT': 9, 'BBB-USDT': 5}, AS_OF)
        venue.unavailable['BBB-USDT'] = 99
        self.assertEqual(self.run_main(venue, '--universe', '--top', '2'), 1)
        self.assertEqual(self.run_main(venue, '--universe', '--top', '2'), 2)
        self.assertEqual(self.run_main(venue, '--universe', '--top', '3', '--resume'), 2)
        later = AS_OF + timedelta(days=3)
        resumed = FakeVenue(series_for(['AAA-USDT', 'BBB-USDT', 'CCC-USDT']),
                            {'AAA-USDT': 1, 'BBB-USDT': 999, 'CCC-USDT': 5000}, later)
        self.assertEqual(self.run_main(resumed, '--universe', '--top', '2', '--resume',
                                       now=later), 0)
        self.assertEqual(resumed.candle_calls('AAA-USDT'), [])      # already complete
        self.assertEqual(int(resumed.candle_calls('BBB-USDT')[0]['after']), AS_OF_MS)
        self.assertNotIn('market_get_tickers', [name for name, _ in resumed.calls])
        members = json.loads((self.out / 'universe.json').read_text('utf-8'))['members']
        self.assertEqual([member['symbol'] for member in members], ['AAA-USDT', 'BBB-USDT'])

    def test_universe_only_writes_the_list_and_nothing_else(self):
        venue = FakeVenue(series_for(['AAA-USDT']), {'AAA-USDT': 5}, AS_OF)
        self.assertEqual(self.run_main(venue, '--universe', '--universe-only'), 0)
        self.assertEqual([path.name for path in self.out.iterdir()], ['universe.json'])
        self.assertEqual((venue.opens, venue.candle_calls()), (1, []))

    def test_short_and_gapped_histories_are_recorded_honestly(self):
        series = series_for(['AAA-USDT'])
        series[('AAA-USDT', '15m')] = history(30, '15m', symbol='AAA-USDT')   # a young pair
        hourly = history(60, '1H', symbol='AAA-USDT')
        series[('AAA-USDT', '1H')] = hourly[:20] + hourly[21:]                # one bar missing
        venue = FakeVenue(series, {}, AS_OF)
        self.assertEqual(self.run_main(venue, '--symbols', 'AAA-USDT'), 0)
        streams = self.manifest()['symbols']['AAA-USDT']['streams']
        self.assertEqual((streams['15m']['bars'], streams['15m']['exhausted']), (30, True))
        self.assertEqual((streams['1H']['bars'], streams['1H']['dropped_bars'],
                          streams['1H']['gaps']), (39, 20, 1))

    def test_bad_arguments_are_usage_errors(self):
        venue = FakeVenue(series_for(['AAA-USDT']), {}, AS_OF)
        for arguments in (('--symbols', 'AAA-USDT,AAA-USDT'), ('--symbols', 'btc-usdt'),
                          ('--universe', '--top', '0'), ('--universe', '--quote', 'usdt'),
                          ('--symbols', 'AAA-USDT', '--universe-only'),
                          ('--symbols', 'AAA-USDT', '--resume')):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_main(venue, *arguments), 2)
        self.assertEqual(venue.opens, 0)


if __name__ == '__main__':
    unittest.main()
