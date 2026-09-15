"""Explicit public-network smoke: python -B -m agent_trading.mcp_smoke."""

import argparse
import asyncio
from datetime import datetime, timezone
import json

from .market import HistoryStore, snapshot_summary
from .models import to_jsonable
from .okx_mcp import McpMarketError, sanitized_failure
from .okx_mcp_runtime import open_atk_mcp


async def smoke(*, node_path=None, server_path=None, timeout=30, workdir=None) -> dict:
    async with open_atk_mcp(node_path=node_path, server_path=server_path,
                            timeout=timeout, workdir=workdir) as adapter:
        # Fix the candle knowledge boundary before any of the later live reads.
        as_of = datetime.now(timezone.utc)
        ticker = await adapter.ticker("BTC-USDT")
        candles = await adapter.candles("BTC-USDT", "15m", 10, as_of=as_of)
        book = await adapter.orderbook("BTC-USDT", 5)
        if not candles.value:
            raise McpMarketError("NO_CLOSED_CANDLES", provenance=candles.provenance)
        store = HistoryStore(10)
        for candle in candles.value:
            store.append(candle)
        snapshot = store.snapshot("BTC-USDT", as_of)
        result = {
            "status": "VERIFIED", "runtime": adapter.runtime_info,
            "site": "tr", "modules": ["market"], "read_only": True,
            "discovered_tools": adapter.discovered_tools,
            "ticker": ticker,
            "candles": {"count": len(candles.value), "latest": candles.value[-1],
                        "provenance": candles.provenance},
            "orderbook": {"bids": len(book.value.bids), "asks": len(book.value.asks),
                          "best_bid": book.value.bids[0], "best_ask": book.value.asks[0],
                          "exchange_time": book.value.exchange_time,
                          "observed_at": book.value.observed_at, "provenance": book.provenance},
            "snapshot": snapshot_summary(snapshot), "order_sent": False,
        }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Explicit real OKX TR public MCP smoke; no credentials")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--node-path", help="Operator-configured absolute Node executable path")
    parser.add_argument("--server-path", help="Installed ATK MCP 1.4.6 dist/index.js path")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(smoke(node_path=args.node_path, server_path=args.server_path,
                                   timeout=args.timeout))
    except Exception as exc:
        error = sanitized_failure(exc)
        print(json.dumps(to_jsonable({"status": "BLOCKED", "error_code": error.code,
                                     "rpc_error_code": error.rpc_error_code,
                                     "missing_tools": error.missing_tools,
                                     "provenance": error.provenance}), indent=2))
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"status": "INTERRUPTED", "error_code": "MCP_CANCELLED"}))
        return 130
    print(json.dumps(to_jsonable(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
