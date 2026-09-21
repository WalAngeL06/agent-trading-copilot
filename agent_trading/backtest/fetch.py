"""SEPARATE read-only dataset fetcher. The replay never imports this module.

It reuses the shipped public market adapter, whose allowlist holds public
market reads only: ticker, candles, order book and, for [U-MULTI-PAIR-001], the
spot instrument and ticker listings. No private read, no credential, no order
and no write of any kind is reachable from here.

    python -m agent_trading.backtest.fetch --symbol BTC-USDT --out data/btc
    python -m agent_trading.backtest.fetch --universe --quote USDT --top 30         --limits 4H=10000,1H=10000,15m=36000 --out data/okx_tr_usdt_top30

The multi-pair form writes one folder per pair plus `universe.json` and
`fetch_manifest.json`; an interrupted run continues with `--resume`. Backtests
then run entirely from the frozen files this writes.
"""
import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time

from ..market import bar_duration
from ..okx import _symbol
from ..okx_mcp import McpMarketError
from ..okx_mcp_runtime import open_atk_mcp
from ..strategy_v1 import TimeframeRoles
from .files import write_atomic
from .universe import STABLE_BASES, _code, read_universe, select_universe, write_universe

PAGE_LIMIT = 300          # the shipped adapter refuses more than 300 per call
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
# Page-level faults worth another try. Anything else is a session or contract
# fault that a retry of the same page cannot fix.
RETRYABLE = frozenset({'MCP_TOOL_ERROR', 'MCP_TIMEOUT', 'MALFORMED_RESPONSE',
                       'CLOCK_MOVED_BACKWARD'})


def milliseconds(moment):
    return (moment - EPOCH) // timedelta(milliseconds=1)


def candle_row(candle):
    """The same JSONL shape `agent_trading.data.read_candles` already reads."""
    return {'symbol': candle.symbol, 'timeframe': candle.timeframe,
            'close_time': candle.close_time.isoformat().replace('+00:00', 'Z'),
            'open': str(candle.open), 'high': str(candle.high), 'low': str(candle.low),
            'close': str(candle.close), 'volume': str(candle.volume), 'closed': True}


def slug(symbol):
    return symbol.replace('-', '').lower()


def write_stream(out_dir, symbol, timeframe, candles):
    """Freeze one stream as `<slug>_<tf>.jsonl`, atomically."""
    text = ''.join(json.dumps(candle_row(candle), sort_keys=True) + '\n' for candle in candles)
    return write_atomic(Path(out_dir) / f'{slug(symbol)}_{timeframe}.jsonl', text)


def open_ms(candle):
    """OKX pages by the bar's OPEN timestamp; our candles carry close_time."""
    return milliseconds(candle.close_time - bar_duration(candle.timeframe))


def parse_limits(text, timeframes, fallback):
    """`4H=10000,1H=10000,15m=36000`; unnamed timeframes take `fallback`."""
    if type(fallback) is not int or fallback <= 0:
        raise ValueError('the fallback limit must be a positive integer')
    limits = dict.fromkeys(timeframes, fallback)
    seen = set()
    for chunk in (text.split(',') if text else ()):
        timeframe, separator, value = chunk.strip().partition('=')
        if (not separator or timeframe not in limits or timeframe in seen
                or not value.isdigit() or int(value) <= 0):
            raise ValueError(f'invalid limit {chunk.strip()!r}')
        seen.add(timeframe)
        limits[timeframe] = int(value)
    return limits


def latest_contiguous(candles, timeframe):
    """The newest unbroken run of bars. Nothing is invented to bridge a gap.

    Returns (kept, dropped_bars, gaps, latest_gap), where `latest_gap` is the
    (earlier, later) close-time pair that bounds what was kept.
    """
    candles = tuple(candles)
    step = bar_duration(timeframe)
    start, gaps, latest = 0, 0, None
    for index in range(1, len(candles)):
        if candles[index].close_time - candles[index - 1].close_time != step:
            gaps += 1
            start = index
            latest = (candles[index - 1].close_time, candles[index].close_time)
    return candles[start:], start, gaps, latest


@dataclass(frozen=True)
class StreamFetch:
    timeframe: str
    candles: tuple
    wanted: int
    exhausted: bool
    dropped_bars: int = 0
    gaps: int = 0
    latest_gap: tuple | None = None

    def as_dict(self):
        return {'bars': len(self.candles), 'wanted': self.wanted, 'exhausted': self.exhausted,
                'first': self.candles[0].close_time.isoformat() if self.candles else None,
                'last': self.candles[-1].close_time.isoformat() if self.candles else None,
                'dropped_bars': self.dropped_bars, 'gaps': self.gaps,
                'latest_gap': None if self.latest_gap is None
                              else [moment.isoformat() for moment in self.latest_gap]}


async def fetch_stream(read_page, symbol, timeframe, wanted, as_of, page=PAGE_LIMIT):
    """Page backwards from `as_of` until `wanted` bars or the venue runs out.

    `read_page(symbol, timeframe, size, after)` returns closed candles that open
    strictly before `after` (epoch milliseconds). Every stream of a run starts
    from the same `as_of`, so all pairs end at the same moment.
    """
    if type(wanted) is not int or wanted <= 0:
        raise ValueError('wanted must be a positive integer')
    collected, cursor, asked_twice = {}, milliseconds(as_of), False
    exhausted = False
    while len(collected) < wanted:
        candles = await read_page(symbol, timeframe, min(page, wanted - len(collected)), cursor)
        if not candles:
            if asked_twice:
                exhausted = True               # confirmed: no older data exists
                break
            asked_twice = True                 # one more ask before calling it the end
            continue
        asked_twice = False
        oldest = min(open_ms(candle) for candle in candles)
        if oldest >= cursor:
            raise ValueError('the venue ignored the paging cursor')
        for candle in candles:
            collected.setdefault(candle.close_time, candle)
        cursor = oldest
    ordered = tuple(collected[stamp] for stamp in sorted(collected))
    kept, dropped, gaps, latest = latest_contiguous(ordered, timeframe)
    return StreamFetch(timeframe, kept, wanted, exhausted, dropped, gaps, latest)


class Pacer:
    """Spaces calls to the venue and retries page-level faults with backoff.

    OKX limits history reads per IP more tightly than ATK's client-side bucket,
    and on the VPS the live bot shares that IP, so every call is spaced.
    """

    def __init__(self, pace=0.2, retries=4, *, sleep=asyncio.sleep, monotonic=time.monotonic):
        if pace < 0 or type(retries) is not int or retries < 0:
            raise ValueError('pace must be nonnegative and retries a nonnegative integer')
        self.pace, self.retries = pace, retries
        self.sleep, self.monotonic = sleep, monotonic
        self._last = None

    async def call(self, operation):
        for attempt in range(self.retries + 1):
            if self._last is not None:
                wait = self.pace - (self.monotonic() - self._last)
                if wait > 0:
                    await self.sleep(wait)
            self._last = self.monotonic()
            try:
                return await operation()
            except McpMarketError as error:
                if error.code not in RETRYABLE or attempt == self.retries:
                    raise
                await self.sleep(min(2 * 2 ** attempt, 60))


def page_reader(adapter, pacer, as_of):
    async def read_page(symbol, timeframe, size, after):
        read = await pacer.call(lambda: adapter.candles(symbol, timeframe, size,
                                                        as_of=as_of, after=after))
        return read.value
    return read_page


async def fetch_streams(mcp_factory, pacer, symbol, timeframes, limits, as_of, timeout):
    """Every stream of one pair from one fresh session. Nothing is written here:
    the runtime renames any error raised inside the session block."""
    streams = {}
    async with mcp_factory(timeout=timeout) as adapter:     # discovery runs on open
        read_page = page_reader(adapter, pacer, as_of)
        for timeframe in timeframes:
            streams[timeframe] = await fetch_stream(read_page, symbol, timeframe,
                                                    limits[timeframe], as_of)
    return streams


async def fetch(symbol, timeframes, limits, out_dir, timeout=30, *, mcp_factory=open_atk_mcp,
                pacer=None, now=None):
    """The original single-pair download, written flat into `out_dir`."""
    as_of = (now or (lambda: datetime.now(timezone.utc)))()
    streams = await fetch_streams(mcp_factory, pacer if pacer is not None else Pacer(),
                                  symbol, timeframes, limits, as_of, timeout)
    return {timeframe: (write_stream(out_dir, symbol, timeframe, stream.candles),
                        len(stream.candles))
            for timeframe, stream in streams.items()}


# ---------------------------------------------------------------- multi-pair
MANIFEST, UNIVERSE = 'fetch_manifest.json', 'universe.json'
MANIFEST_SCHEMA = 'okx-fetch-manifest-v0.1'
LAYOUT = '<out>/<instId>/<slug>_<tf>.jsonl'
# A pair that fails this many times in a row means the venue itself is down.
MAX_CONSECUTIVE_FAILURES = 3
# Installation, version, contract and scope faults: no other pair can succeed.
FATAL = frozenset({'ATK_NOT_INSTALLED', 'ATK_PACKAGE_MISMATCH', 'ATK_VERSION_MISMATCH',
                   'MCP_SDK_UNAVAILABLE', 'MCP_SDK_VERSION_MISMATCH', 'REQUIRED_TOOLS_MISSING',
                   'TOOL_SCHEMA_DRIFT', 'PUBLIC_SCOPE_MISMATCH', 'MALFORMED_DISCOVERY',
                   'PUBLIC_HOME_INVALID', 'INVALID_AS_OF', 'TOOLS_NOT_DISCOVERED'})


class RunStopped(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _save(path, manifest):
    write_atomic(path, json.dumps(manifest, indent=2, sort_keys=True) + '\n')


def _say(*parts, error=False):
    print(*parts, file=sys.stderr if error else sys.stdout)


async def select_pairs(mcp_factory, pacer, *, quote, top, exclude_bases, as_of, timeout):
    async with mcp_factory(timeout=timeout) as adapter:
        instruments = (await pacer.call(adapter.spot_instruments)).value
        volumes = (await pacer.call(adapter.spot_tickers)).value
    return select_universe(instruments, volumes, quote=quote, top=top,
                           exclude_bases=exclude_bases, as_of=as_of)


async def fetch_pairs(request, args, roles, limits, pacer, mcp_factory, now):
    out = args.out
    manifest_path = out / MANIFEST
    if manifest_path.exists():
        if not args.resume:
            _say(f'{manifest_path} already exists; rerun the same command with --resume',
                 error=True)
            return 2
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('schema_version') != MANIFEST_SCHEMA or manifest['request'] != request:
            _say('--resume needs the same selection and limits as the first run', error=True)
            return 2
        as_of = datetime.fromisoformat(manifest['as_of'])
    elif args.resume:
        _say(f'nothing to resume in {out}', error=True)
        return 2
    else:
        as_of = now().astimezone(timezone.utc)
        manifest = {'schema_version': MANIFEST_SCHEMA, 'as_of': as_of.isoformat(),
                    'source': {'provider': 'OKX Agent Trade Kit', 'site': 'tr',
                               'read_only': True},
                    'request': request, 'layout': LAYOUT, 'symbols': {},
                    'run': {'stopped': None}, 'source_ids': ['[U-MULTI-PAIR-001]']}
    try:
        if request['mode'] == 'universe':
            universe_path = out / UNIVERSE
            if universe_path.exists():
                universe = read_universe(universe_path)       # chosen once, never re-ranked
            else:
                universe = await select_pairs(mcp_factory, pacer, quote=request['quote'],
                                              top=request['top'],
                                              exclude_bases=tuple(request['exclude_bases']),
                                              as_of=as_of, timeout=args.timeout)
                write_universe(universe, universe_path)
            if args.universe_only:
                _say(json.dumps({'universe': list(universe.symbols),
                                 'counts': universe.counts}, indent=2))
                return 0
            symbols = list(universe.symbols)
        else:
            symbols = list(request['symbols'])
        for symbol in symbols:
            manifest['symbols'].setdefault(symbol, {'status': 'PENDING', 'error': None,
                                                    'streams': {}})
        _save(manifest_path, manifest)
        await _fetch_each(symbols, manifest, manifest_path, roles, limits, pacer,
                          mcp_factory, as_of, args.timeout)
    except RunStopped as stop:
        manifest['run']['stopped'] = stop.reason
        if manifest['symbols']:
            _save(manifest_path, manifest)
        _say(f'run stopped: {stop.reason}', error=True)
        return 2
    statuses = {symbol: manifest['symbols'][symbol]['status'] for symbol in symbols}
    failed = sorted(symbol for symbol, status in statuses.items() if status == 'FAILED')
    _say(json.dumps({'complete': sum(status == 'COMPLETE' for status in statuses.values()),
                     'failed': {symbol: manifest['symbols'][symbol]['error']
                                for symbol in failed}}, indent=2, sort_keys=True))
    return 1 if failed else 0


async def _fetch_each(symbols, manifest, manifest_path, roles, limits, pacer, mcp_factory,
                      as_of, timeout):
    consecutive = 0
    for symbol in symbols:
        entry = manifest['symbols'][symbol]
        if entry['status'] == 'COMPLETE':
            _say(f'{symbol}: COMPLETE (kept from the earlier run)')
            continue
        streams = code = None
        for _attempt in range(2):          # one restart with a fresh session
            try:
                streams = await fetch_streams(mcp_factory, pacer, symbol, roles.ordered,
                                              limits, as_of, timeout)
                break
            except McpMarketError as error:
                if error.code in FATAL:
                    raise RunStopped(f'FATAL:{error.code}') from None
                code = error.code
            except ValueError:
                code = 'PAGING_ERROR'
        if streams is None:
            entry.update(status='FAILED', error=code, streams={})
            _save(manifest_path, manifest)
            _say(f'{symbol}: FAILED {code}')
            consecutive += 1
            if consecutive >= MAX_CONSECUTIVE_FAILURES:
                raise RunStopped('CONSECUTIVE_FAILURES')
            continue
        consecutive = 0
        for timeframe, stream in streams.items():
            write_stream(manifest_path.parent / symbol, symbol, timeframe, stream.candles)
        entry.update(status='COMPLETE', error=None,
                     streams={timeframe: stream.as_dict() for timeframe, stream in streams.items()})
        _save(manifest_path, manifest)
        _say(f'{symbol}: COMPLETE '
             + ' '.join(f'{timeframe}={len(stream.candles)}' for timeframe, stream in streams.items()))


def build_parser():
    parser = argparse.ArgumentParser(
        prog='python -m agent_trading.backtest.fetch',
        description='Download and freeze public OKX TR candles for offline backtests')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--symbol', help='one pair written flat into --out (default BTC-USDT)')
    mode.add_argument('--symbols', help='comma-separated pairs, one folder each')
    mode.add_argument('--universe', action='store_true',
                      help='choose the pairs from the OKX TR spot listing by 24h volume')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--quote', default='USDT')
    parser.add_argument('--top', type=int, default=30)
    parser.add_argument('--exclude-bases',
                        help='comma-separated bases; replaces the stablecoin/fiat default')
    parser.add_argument('--universe-only', action='store_true',
                        help='write universe.json and stop, to review the list first')
    parser.add_argument('--bias-timeframe', default='4H')
    parser.add_argument('--range-timeframe', default='1H')
    parser.add_argument('--entry-timeframe', default='15m')
    parser.add_argument('--limit', type=int, default=1440,
                        help='bars per timeframe unless --limits names it')
    parser.add_argument('--limits', help="per timeframe, e.g. '4H=10000,1H=10000,15m=36000'")
    parser.add_argument('--pace', type=float, default=0.2, help='seconds between venue calls')
    parser.add_argument('--retries', type=int, default=4, help='retries per page')
    parser.add_argument('--timeout', type=int, default=30)
    parser.add_argument('--resume', action='store_true',
                        help='continue an interrupted multi-pair run with the same choices')
    return parser


def _request(args, roles, limits):
    if args.universe:
        _code(args.quote, 'quote')
        if args.top <= 0:
            raise ValueError('--top must be positive')
        excluded = (STABLE_BASES if args.exclude_bases is None else
                    tuple(base.strip() for base in args.exclude_bases.split(',') if base.strip()))
        for base in excluded:
            _code(base, 'excluded base')
        return {'mode': 'universe', 'quote': args.quote, 'top': args.top,
                'exclude_bases': list(excluded), 'timeframes': list(roles.ordered),
                'limits': limits}
    if args.universe_only:
        raise ValueError('--universe-only needs --universe')
    symbols = [symbol.strip() for symbol in args.symbols.split(',') if symbol.strip()]
    for symbol in symbols:
        _symbol(symbol)
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError('--symbols needs distinct pairs')
    return {'mode': 'symbols', 'symbols': symbols, 'timeframes': list(roles.ordered),
            'limits': limits}


def main(argv=None, *, mcp_factory=open_atk_mcp, sleep=asyncio.sleep, monotonic=time.monotonic,
         now=lambda: datetime.now(timezone.utc)):
    parser = build_parser()
    args = parser.parse_args(argv)
    batch = bool(args.symbols or args.universe)
    try:
        roles = TimeframeRoles(args.bias_timeframe, args.range_timeframe, args.entry_timeframe)
        limits = parse_limits(args.limits, roles.ordered, args.limit)
        pacer = Pacer(args.pace, args.retries, sleep=sleep, monotonic=monotonic)
        if not batch and (args.universe_only or args.resume):
            raise ValueError('--universe-only and --resume apply to multi-pair runs only')
        request = _request(args, roles, limits) if batch else None
    except ValueError as exc:
        parser.error(str(exc))
    try:
        if batch:
            return asyncio.run(fetch_pairs(request, args, roles, limits, pacer,
                                           mcp_factory, now))
        written = asyncio.run(fetch(args.symbol or 'BTC-USDT', roles.ordered, limits, args.out,
                                    args.timeout, mcp_factory=mcp_factory, pacer=pacer,
                                    now=now))
    except KeyboardInterrupt:
        _say('interrupted; rerun the same command with --resume', error=True)
        return 130
    except McpMarketError as error:               # codes only, never raw provider text
        _say(f'fetch failed: {error.code}', error=True)
        return 2
    except ValueError as exc:                     # our own validation messages
        _say(f'fetch failed: {exc}', error=True)
        return 2
    except OSError as exc:
        _say(f'could not write the dataset: {type(exc).__name__}', error=True)
        return 2
    for timeframe, (path, count) in written.items():
        print(f'{timeframe}: {count} candles -> {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
