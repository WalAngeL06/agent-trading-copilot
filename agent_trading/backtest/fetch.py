"""SEPARATE read-only dataset fetcher. The replay never imports this module.

It reuses the shipped public market adapter, whose allowlist contains only
`market_get_ticker`, `market_get_candles` and `market_get_orderbook`. No private
read, no credential, no order and no write of any kind is reachable from here.

    python -m agent_trading.backtest.fetch --symbol BTC-USDT --out data/btc

Backtests then run entirely from the frozen files this writes.
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from ..market import bar_duration
from ..okx_mcp_runtime import open_atk_mcp
from ..strategy_v1 import TimeframeRoles

DEFAULT_LIMITS = {'4H': 1440, '1H': 1440, '15m': 1440, '5m': 1440, '1m': 1440}


def candle_row(candle):
    """The same JSONL shape `agent_trading.data.read_candles` already reads."""
    return {'symbol': candle.symbol, 'timeframe': candle.timeframe,
            'close_time': candle.close_time.isoformat().replace('+00:00', 'Z'),
            'open': str(candle.open), 'high': str(candle.high), 'low': str(candle.low),
            'close': str(candle.close), 'volume': str(candle.volume), 'closed': True}


def write_stream(out_dir, symbol, timeframe, candles):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = symbol.replace('-', '').lower()
    path = out_dir / f'{slug}_{timeframe}.jsonl'
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        for candle in candles:
            handle.write(json.dumps(candle_row(candle), sort_keys=True) + '\n')
    return path


PAGE_LIMIT = 300          # the shipped adapter refuses more than 300 per call


def _open_ms(candle):
    """OKX pages by the bar's OPEN timestamp; our candles carry close_time."""
    opened = candle.close_time - bar_duration(candle.timeframe)
    return int(opened.timestamp() * 1000)


async def fetch_stream(adapter, symbol, timeframe, wanted, as_of, page=PAGE_LIMIT):
    """Page backwards with `after` until `wanted` candles are collected."""
    collected, cursor = {}, None
    while len(collected) < wanted:
        size = min(page, wanted - len(collected))
        read = await adapter.candles(symbol, timeframe, size, as_of=as_of, after=cursor)
        # `McpMarketRead.value` is already the normalised Candle tuple; the
        # adapter unpacks the (candles, filtering) pair before returning.
        candles = read.value if hasattr(read, 'value') else read
        fresh = [candle for candle in candles if candle.close_time not in collected]
        if not fresh:
            break                                  # the venue has no older data
        for candle in fresh:
            collected[candle.close_time] = candle
        cursor = min(_open_ms(candle) for candle in candles)
    return tuple(collected[stamp] for stamp in sorted(collected))


async def fetch(symbol, timeframes, limits, out_dir, timeout=30):
    written = {}
    as_of = datetime.now(timezone.utc)
    async with open_atk_mcp(timeout=timeout) as adapter:
        await adapter.discover()
        for timeframe in timeframes:
            candles = await fetch_stream(adapter, symbol, timeframe,
                                         limits[timeframe], as_of)
            written[timeframe] = (write_stream(out_dir, symbol, timeframe, candles),
                                  len(candles))
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='python -m agent_trading.backtest.fetch',
        description='Download and freeze public OKX candles for offline backtests')
    parser.add_argument('--symbol', default='BTC-USDT')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--bias-timeframe', default='4H')
    parser.add_argument('--range-timeframe', default='1H')
    parser.add_argument('--entry-timeframe', default='15m')
    parser.add_argument('--limit', type=int, default=1440)
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args(argv)
    roles = TimeframeRoles(args.bias_timeframe, args.range_timeframe, args.entry_timeframe)
    limits = {timeframe: args.limit for timeframe in roles.ordered}
    try:
        written = asyncio.run(fetch(args.symbol, roles.ordered, limits, args.out,
                                    args.timeout))
    except Exception as exc:                   # surfaced, never silently swallowed
        parser.error(f'{type(exc).__name__}: {exc}')
    for timeframe, (path, count) in written.items():
        print(f'{timeframe}: {count} candles -> {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
