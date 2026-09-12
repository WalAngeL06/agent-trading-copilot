"""Explicit REAL public product smoke: MCP -> MTF core/report -> SQLite."""

import argparse
import asyncio
import json
from pathlib import Path

from .analysis_config import AnalysisConfig
from .analysis_service import AnalysisService, ServiceError


async def smoke(config: AnalysisConfig, *, service=None) -> dict:
    service = service or AnalysisService(config)
    await service.startup()
    report = (await service.analyze("BTC-USDT")).report
    stored = await asyncio.to_thread(service.repository.get, report["analysis_id"])
    if stored != report:
        raise ServiceError("PERSISTENCE_UNAVAILABLE", 503, report["analysis_id"])
    calls = [s["provenance"] for s in report["sources"] if s["provenance"]["tool"].startswith("market_")]
    ticker = report["market"]["ticker"]
    spread = report["market"]["spread"]
    return {
        "status": report["status"], "analysis_id": report["analysis_id"], "symbol": report["symbol"],
        "site": report["site"], "decision": report["decision"], "decision_as_of": report["decision_as_of"],
        "latest_close_time": {tf: item["latest_close_time"] for tf, item in report["timeframes"].items()},
        "ticker_observed_at": ticker["observed_at"] if ticker is not None else None,
        "spread": spread["value"] if spread is not None else None,
        "mcp_tools_used": sorted({p["tool"] for p in calls}),
        "mcp_market_call_count": len(calls), "persistence_verified": True,
        "order_sent": report["decision"]["order_sent"], "error_codes": [e["code"] for e in report["errors"]],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Explicit real BTC-USDT public MCP product analysis; no credentials")
    parser.add_argument("--db-path", default="runs/product/analyses.sqlite3")
    parser.add_argument("--audit-dir", default="runs/analyses")
    parser.add_argument("--node-path")
    parser.add_argument("--server-path")
    parser.add_argument("--timeout", type=float, default=60, help="Total reserved analysis workflow seconds")
    parser.add_argument("--mcp-timeout", type=float, default=20, help="Individual MCP operation seconds")
    args = parser.parse_args(argv)
    try:
        config = AnalysisConfig(db_path=Path(args.db_path), audit_dir=Path(args.audit_dir),
                                node_path=args.node_path, server_path=args.server_path,
                                analysis_timeout_seconds=args.timeout, mcp_timeout_seconds=args.mcp_timeout)
        result = asyncio.run(smoke(config))
    except KeyboardInterrupt:
        print(json.dumps({"status": "INTERRUPTED", "error_code": "ANALYSIS_CANCELLED", "order_sent": False}))
        return 130
    except Exception as exc:
        code = exc.code if isinstance(exc, ServiceError) else "ANALYSIS_UNAVAILABLE"
        print(json.dumps({"status": "BLOCKED", "error_code": code, "order_sent": False}))
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
