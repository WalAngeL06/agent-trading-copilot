"""Explicit public-network collection of offline swing benchmark fixtures.

    python -B -m agent_trading.swing_smoke --out tests/data \
        --node-path "C:/Program Files/nodejs/node.exe" \
        --server-path ".../@okx_ai/okx-trade-mcp/dist/index.js"

Read-only public market data through the existing ATK MCP adapter: no
credentials, no account access, no order path. Writes sanitized candle JSONL
(symbol/timeframe/OHLCV/close_time only) so the normal test suite and the
review tooling stay completely offline.

This is a research/benchmark collector. It is never imported by the decision
pipeline and it establishes nothing about any trading rule.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

from .models import to_jsonable
from .okx_mcp import McpMarketError, sanitized_failure
from .okx_mcp_runtime import open_atk_mcp

DEFAULT_TIMEFRAMES = ("5m", "15m", "1H", "4H")


def fixture_path(out_dir: Path, symbol: str, timeframe: str) -> Path:
    return Path(out_dir) / ("%s_%s.jsonl" % (symbol.replace("-", "").lower(), timeframe))


def write_candles(path: Path, candles) -> int:
    """Sanitized rows only: nothing about the transport or the operator host."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for candle in candles:
            handle.write(json.dumps({
                "symbol": candle.symbol, "timeframe": candle.timeframe,
                "close_time": to_jsonable(candle.close_time),
                "open": str(candle.open), "high": str(candle.high),
                "low": str(candle.low), "close": str(candle.close),
                "volume": str(candle.volume), "closed": True,
            }, sort_keys=True) + "\n")
    return len(candles)


async def collect(*, symbol="BTC-USDT", timeframes=DEFAULT_TIMEFRAMES, limit=300,
                  out_dir="tests/data", node_path=None, server_path=None, timeout=30):
    results = []
    async with open_atk_mcp(node_path=node_path, server_path=server_path,
                            timeout=timeout) as adapter:
        # Fix the knowledge boundary once, before any read, so every saved
        # series shares one causal cutoff.
        as_of = datetime.now(timezone.utc)
        for timeframe in timeframes:
            read = await adapter.candles(symbol, timeframe, limit, as_of=as_of)
            candles = read.value
            if not candles:
                raise McpMarketError("NO_CLOSED_CANDLES", provenance=read.provenance)
            path = fixture_path(Path(out_dir), symbol, timeframe)
            write_candles(path, candles)
            results.append({
                "timeframe": timeframe, "file": str(path), "closed_candles": len(candles),
                "first_close": candles[0].close_time, "last_close": candles[-1].close_time,
            })
    return {"status": "VERIFIED", "symbol": symbol, "as_of": as_of,
            "requested_limit": limit, "series": results, "order_sent": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect offline BTC swing benchmark fixtures from public OKX MCP")
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES))
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--out", default="tests/data")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--node-path")
    parser.add_argument("--server-path")
    args = parser.parse_args(argv)
    frames = tuple(tf.strip() for tf in args.timeframes.split(",") if tf.strip())
    try:
        result = asyncio.run(collect(
            symbol=args.symbol, timeframes=frames, limit=args.limit, out_dir=args.out,
            node_path=args.node_path, server_path=args.server_path, timeout=args.timeout))
    except Exception as exc:
        error = sanitized_failure(exc)
        print(json.dumps(to_jsonable({"status": "BLOCKED", "error_code": error.code,
                                      "rpc_error_code": error.rpc_error_code,
                                      "missing_tools": error.missing_tools}), indent=2))
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"status": "INTERRUPTED", "error_code": "MCP_CANCELLED"}))
        return 130
    print(json.dumps(to_jsonable(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
