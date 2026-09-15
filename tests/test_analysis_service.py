import asyncio
from contextlib import closing
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from analysis_fixtures import ASK, Clock, NOW, PRICE, QUANTITY, Runtime, candle
from agent_trading.analysis_config import AnalysisConfig
from agent_trading.analysis_report import deterministic_summary
from agent_trading.analysis_repository import SQLiteAnalysisRepository, RepositoryError
from agent_trading.analysis_service import AnalysisService, ServiceError
from agent_trading.engine import ReplayEngine
from agent_trading.models import Candle, utc_time


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.clock = Clock()
        self.runtime = Runtime(self.clock)
        self.config = AnalysisConfig(db_path=self.root / "history.sqlite3",
                                     audit_dir=self.root / "audit", history_limit=3)
        self.service = AnalysisService(self.config, mcp_factory=self.runtime, clock=self.clock)
        await self.service.startup()

    async def analyze(self, **kwargs):
        return (await self.service.analyze("BTC-USDT", **kwargs)).report

    async def test_public_btc_analysis_completes_and_persists_current_real_decision(self):
        report = await self.analyze()
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(report["decision"], {"action": "NO_TRADE",
                         "reason_codes": ["STRATEGY_NOT_CONFIGURED"], "order_sent": False})
        self.assertEqual(self.service.repository.get(report["analysis_id"]), report)
        self.assertEqual(report["errors"], [])
        self.assertTrue(self.runtime.closed)

    async def test_real_engine_receives_causal_decimal_mtf_snapshot(self):
        captured = []
        class CapturingEngine(ReplayEngine):
            def bootstrap(self, candles, as_of):
                snapshot = super().bootstrap(candles, as_of)
                captured.append(snapshot)
                return snapshot
        with patch("agent_trading.analysis_service.ReplayEngine", CapturingEngine):
            report = await self.analyze()
        snapshot = captured[0]
        self.assertEqual(snapshot.as_of, utc_time("2026-01-01T10:30:00Z"))
        self.assertEqual(set(snapshot.histories), {"4H", "1H", "15m"})
        self.assertEqual({tf: len(h) for tf, h in snapshot.histories.items()},
                         {"4H": 3, "1H": 3, "15m": 3})
        for tf, history in snapshot.histories.items():
            self.assertTrue(all(isinstance(c, Candle) and isinstance(c.close, Decimal) for c in history))
            self.assertTrue(all(c.close_time <= snapshot.as_of for c in history))
        self.assertEqual(str(snapshot.histories["15m"][-1].close), PRICE)

    async def test_long_financial_tokens_and_exact_spread_are_api_strings(self):
        report = await self.analyze()
        self.assertEqual(report["market"]["ticker"]["last"], PRICE)
        self.assertEqual(report["market"]["orderbook_summary"]["best_bid"]["quantity"], QUANTITY)
        self.assertEqual(report["market"]["spread"]["value"], "1.000000000000000000000000000003")
        self.assertEqual(report["timeframes"]["15m"]["latest_closed_candle"]["volume"], QUANTITY)
        self.assertIsInstance(report["timeframes"]["15m"]["candle_count"], int)

    async def test_utc_creation_decision_and_later_observations_remain_distinct(self):
        report = await self.analyze()
        self.assertEqual(report["started_at"], "2026-01-01T10:31:00Z")
        self.assertEqual(report["decision_as_of"], "2026-01-01T10:30:00Z")
        self.assertEqual(report["timeframes"]["4H"]["latest_close_time"], "2026-01-01T08:00:00Z")
        self.assertEqual(report["timeframes"]["1H"]["latest_close_time"], "2026-01-01T10:00:00Z")
        self.assertGreater(report["market"]["ticker"]["observed_at"], report["decision_as_of"])
        self.assertGreater(report["market"]["orderbook_summary"]["observed_at"], report["decision_as_of"])
        self.assertGreaterEqual(report["completed_at"], report["market"]["orderbook_summary"]["observed_at"])

    async def test_honest_modules_and_explanation_have_no_fabricated_levels(self):
        report = await self.analyze()
        for name in ("market_structure", "range", "deviation", "premium_discount"):
            self.assertEqual(report["modules"][name]["status"], "NOT_IMPLEMENTED")
            self.assertEqual(set(report["modules"][name]), {"status", "reason_codes"})
        self.assertEqual(report["modules"]["acceptance"], {"status": "NOT_EVALUATED",
                                                          "reason_codes": ["NO_CANDIDATE"]})
        self.assertEqual(report["modules"]["risk"]["reason_codes"], ["NO_ACCEPTED_CANDIDATE"])
        summary = report["explanation"]["deterministic_summary"]
        self.assertIn("No trading strategy", summary)
        self.assertIn("NO_TRADE", summary)
        self.assertEqual(summary, deterministic_summary(report))

    async def test_actual_timeline_and_sources_show_five_market_reads(self):
        report = await self.analyze()
        self.assertEqual([e["type"] for e in report["timeline"]],
            ["REQUEST_RECEIVED", "MCP_CONNECTED", "TICKER_FETCHED", "CANDLES_FETCHED",
             "CANDLES_FETCHED", "CANDLES_FETCHED", "ORDERBOOK_FETCHED", "SNAPSHOT_BUILT",
             "DECISION_EVALUATED", "ANALYSIS_COMPLETED"])
        self.assertEqual([e["sequence"] for e in report["timeline"]], list(range(1, 11)))
        self.assertEqual([s["provenance"]["tool"] for s in report["sources"]],
                         ["tools/list", "market_get_ticker", "market_get_candles",
                          "market_get_candles", "market_get_candles", "market_get_orderbook"])
        self.assertTrue(all(s["provenance"]["transport"] == "MCP" for s in report["sources"]))
        self.assertEqual([args.get("bar") for name, args in self.runtime.session.calls
                          if name == "market_get_candles"], ["4H", "1H", "15m"])
        self.assertTrue(all(args["instId"] == "BTC-USDT" for _, args in self.runtime.session.calls))

    async def test_live_evidence_is_never_a_candle_decision_input(self):
        report = await self.analyze()
        live = [e for e in report["evidence"] if e["kind"] in ("TICKER", "ORDERBOOK")]
        candles = [e for e in report["evidence"] if e["kind"] == "CLOSED_CANDLES"]
        self.assertEqual(len(live), 2)
        self.assertTrue(all(e["decision_input"] is False for e in live))
        self.assertEqual(len(candles), 3)
        self.assertTrue(all(e["decision_input"] is True and e["close_time"] <= report["decision_as_of"]
                            for e in candles))
        self.assertTrue(all(e["source_id"] in [s["source_id"] for s in report["sources"]]
                            for e in live + candles))

    async def test_open_and_future_closed_rows_are_excluded(self):
        self.runtime.session.rows["15m"][-1] = candle("2026-01-01T10:30:00Z", "1")
        report = await self.analyze()
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(report["timeframes"]["15m"]["candle_count"], 3)
        source = next(s for s in report["sources"] if s["provenance"]["timeframe"] == "15m")
        self.assertEqual(source["provenance"]["filtering"]["future_rows"], 1)

    async def test_missing_closed_timeframe_fails_without_decision_or_snapshot(self):
        self.runtime.session.rows["1H"] = [candle("2026-01-01T10:00:00Z", "0")]
        report = await self.analyze()
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["code"], "MISSING_TIMEFRAME")
        self.assertEqual(report["errors"][0]["timeframe"], "1H")
        self.assertIsNone(report["decision"]["action"])
        self.assertIsNone(report["decision_as_of"])
        self.assertEqual(report["timeframes"]["1H"]["data_status"], "MISSING")
        self.assertNotIn("SNAPSHOT_BUILT", [e["type"] for e in report["timeline"]])
        self.assertIn("1H", report["explanation"]["deterministic_summary"])

    async def test_stale_required_series_is_not_concealed_by_new_ticker_or_asof(self):
        self.runtime.session.rows["15m"] = [candle("2026-01-01T09:45:00Z")]
        report = await self.analyze()
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["code"], "STALE_TIMEFRAME")
        self.assertIsNone(report["decision"]["action"])
        self.assertEqual(report["timeframes"]["15m"]["freshness"]["status"], "STALE")
        self.assertEqual(report["timeframes"]["15m"]["freshness"]["checked_at"], "2026-01-01T10:31:00Z")
        self.assertIn("stale", report["explanation"]["deterministic_summary"])

    async def test_normal_four_hour_old_close_is_fresh_in_its_own_interval(self):
        report = await self.analyze()
        self.assertEqual(report["timeframes"]["4H"]["freshness"]["expected_close_time"],
                         "2026-01-01T08:00:00Z")
        self.assertEqual(report["timeframes"]["4H"]["freshness"]["status"], "FRESH")

    async def test_publication_grace_applies_only_near_the_close_boundary(self):
        self.clock.now = utc_time("2026-01-01T10:00:30Z")
        self.runtime.session.rows["15m"] = [candle("2026-01-01T09:30:00Z")]
        report = await self.analyze()
        self.assertEqual(report["status"], "COMPLETED")
        fresh = report["timeframes"]["15m"]["freshness"]
        self.assertEqual(fresh["expected_close_time"], "2026-01-01T10:00:00Z")
        self.assertEqual(fresh["required_close_time"], "2026-01-01T09:45:00Z")
        self.assertEqual(report["decision_as_of"], "2026-01-01T09:45:00Z")
        self.assertEqual(report["timeframes"]["1H"]["latest_close_time"], "2026-01-01T09:00:00Z")

    async def test_missing_required_tool_fails_with_truthful_discovery_evidence(self):
        self.runtime.session.tools.pop()
        report = await self.analyze()
        self.assertEqual(report["errors"][0]["code"], "REQUIRED_TOOLS_MISSING")
        self.assertEqual(report["sources"][0]["provenance"]["tool"], "tools/list")
        self.assertFalse(report["sources"][0]["provenance"]["success"])
        self.assertEqual(self.runtime.session.calls, [])
        self.assertNotIn("MCP_CONNECTED", [e["type"] for e in report["timeline"]])

    async def test_malformed_candle_rejects_normalization_without_raw_error_echo(self):
        self.runtime.session.rows["4H"][0][4] = "credential=do-not-echo"
        report = await self.analyze()
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["code"], "MALFORMED_RESPONSE")
        self.assertEqual(report["timeframes"]["4H"]["data_status"], "FAILED")
        self.assertNotIn("credential", json.dumps(report))
        self.assertIsNone(report["decision"]["action"])

    async def test_gapped_closed_history_fails_before_pipeline(self):
        self.runtime.session.rows["1H"] = [candle("2026-01-01T09:00:00Z"),
                                          candle("2026-01-01T07:00:00Z")]
        report = await self.analyze()
        self.assertEqual(report["errors"][0]["code"], "INVALID_HISTORY")
        self.assertIsNone(report["decision"]["action"])
        self.assertNotIn("DECISION_EVALUATED", [e["type"] for e in report["timeline"]])

    async def test_invalid_book_fails_without_order(self):
        self.runtime.session.bad_book = True
        report = await self.analyze()
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["code"], "MALFORMED_RESPONSE")
        self.assertFalse(report["decision"]["order_sent"])

    async def test_old_exchange_observation_does_not_pass_fresh_host_arrival(self):
        self.runtime.session.old_observation = True
        report = await self.analyze()
        self.assertEqual(report["errors"][0]["code"], "STALE_OBSERVATION")
        self.assertIsNone(report["decision"]["action"])

    async def test_provider_unavailability_is_sanitized_and_persisted(self):
        self.runtime.session.errors["market_get_ticker"] = OSError("Bearer token /private/store")
        report = await self.analyze()
        self.assertEqual(report["errors"][0]["code"], "MCP_UNAVAILABLE")
        self.assertNotIn("Bearer", json.dumps(report))
        self.assertEqual(report["timeline"][-1]["type"], "ANALYSIS_FAILED")
        self.assertEqual(self.service.repository.get(report["analysis_id"]), report)

    async def test_whole_workflow_timeout_is_bounded_and_closes_transport(self):
        config = AnalysisConfig(db_path=self.config.db_path, audit_dir=self.config.audit_dir,
                                history_limit=3, analysis_timeout_seconds=0.05, mcp_timeout_seconds=1)
        service = AnalysisService(config, mcp_factory=self.runtime, clock=self.clock)
        await service.startup()
        self.runtime.session.delay = 0.2
        result = await asyncio.wait_for(service.analyze("BTC-USDT"), 2)
        self.assertEqual(result.report["errors"][0]["code"], "MCP_TIMEOUT")
        self.assertTrue(self.runtime.closed)
        self.assertIsNone(result.report["decision"]["action"])

    async def test_session_shutdown_error_does_not_become_success(self):
        self.runtime.exit_error = OSError("private-path")
        report = await self.analyze()
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["code"], "MCP_UNAVAILABLE")
        self.assertNotIn("private-path", json.dumps(report))

    async def test_audit_creation_failure_persists_failed_resource(self):
        blocked = self.root / "blocked"
        blocked.write_text("file", encoding="utf-8")
        config = AnalysisConfig(db_path=self.config.db_path, audit_dir=blocked, history_limit=3)
        service = AnalysisService(config, mcp_factory=self.runtime, clock=self.clock)
        await service.startup()
        result = await service.analyze("BTC-USDT")
        self.assertEqual(result.report["errors"][0]["code"], "AUDIT_UNAVAILABLE")
        self.assertEqual(self.runtime.connections, 0)

    async def test_unique_core_audit_keeps_existing_schema_and_no_order(self):
        report = await self.analyze()
        path = self.config.audit_dir / (report["analysis_id"] + ".jsonl")
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([e["event"] for e in events], ["BOOTSTRAP_COMPLETE", "DECISION"])
        self.assertTrue(all(e["schema_version"] == 2 for e in events))
        self.assertFalse(events[-1]["execution"]["order_sent"])
        self.assertEqual(events[-1]["as_of"], "2026-01-01T10:30:00Z")

    async def test_idempotent_completed_report_does_not_repeat_provider_execution(self):
        first = await self.service.analyze("BTC-USDT", idempotency_key="same-request")
        second = await self.service.analyze("BTC-USDT", idempotency_key="same-request")
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(second.report, first.report)
        self.assertEqual(len(self.runtime.session.calls), 5)
        with closing(sqlite3.connect(self.config.db_path)) as connection:
            digest = connection.execute("SELECT key_digest FROM analyses").fetchone()[0]
            self.assertEqual(len(digest), 64)
            self.assertNotEqual(digest, "same-request")

    async def test_running_same_key_returns409_without_duplicate_execution(self):
        self.runtime.session.gate = asyncio.Event()
        first = asyncio.create_task(self.service.analyze("BTC-USDT", idempotency_key="running"))
        await asyncio.wait_for(self.runtime.session.entered.wait(), 1)
        try:
            with self.assertRaises(ServiceError) as error:
                await self.service.analyze("BTC-USDT", idempotency_key="running")
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(error.exception.code, "ANALYSIS_IN_PROGRESS")
            running = self.service.repository.get(error.exception.analysis_id)
            self.assertEqual(running["status"], "RUNNING")
            self.assertIsNone(running["decision"]["action"])
        finally:
            self.runtime.session.gate.set()
            await first

    async def test_excess_new_request_returns503_without_fictitious_reservation(self):
        self.runtime.session.gate = asyncio.Event()
        first = asyncio.create_task(self.service.analyze("BTC-USDT"))
        await asyncio.wait_for(self.runtime.session.entered.wait(), 1)
        try:
            with self.assertRaises(ServiceError) as error:
                await self.service.analyze("BTC-USDT")
            self.assertEqual(error.exception.code, "SERVICE_BUSY")
            self.assertEqual(error.exception.status_code, 503)
            self.assertEqual(self.service.repository.history(20, 0)["total"], 1)
        finally:
            self.runtime.session.gate.set()
            await first

    async def test_key_with_different_configured_symbol_returns409(self):
        config = AnalysisConfig(db_path=self.config.db_path, audit_dir=self.config.audit_dir,
                                history_limit=3, allowed_symbols=("BTC-USDT", "ETH-USDT"))
        service = AnalysisService(config, mcp_factory=self.runtime, clock=self.clock)
        await service.startup()
        await service.analyze("BTC-USDT", idempotency_key="conflict")
        with self.assertRaises(ServiceError) as error:
            await service.analyze("ETH-USDT", idempotency_key="conflict")
        self.assertEqual(error.exception.code, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(len(self.runtime.session.calls), 5)

    async def test_unknown_symbol_and_bad_key_are_rejected_before_mcp(self):
        for symbol, key in (("ETH-USDT", None), ("BTC-USDT", "secret header\nvalue"),
                            ("BTC-USDT", "a" * 129)):
            with self.subTest(symbol=symbol):
                with self.assertRaises(ServiceError) as error:
                    await self.service.analyze(symbol, idempotency_key=key)
                self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(self.runtime.connections, 0)
        self.assertEqual(self.service.repository.history(20, 0)["total"], 0)

    async def test_readiness_requires_validated_data_and_has_no_network_probe(self):
        before = await self.service.readiness()
        self.assertEqual(before["status"], "NOT_READY")
        self.assertIn("MARKET_DATA_NOT_VALIDATED", before["reason_codes"])
        await self.analyze()
        connections = self.runtime.connections
        ready = await self.service.readiness()
        self.assertEqual(ready["status"], "READY")
        self.assertEqual(self.runtime.connections, connections)

    async def test_analysis_failure_degrades_readiness_and_success_recovers_it(self):
        await self.analyze()
        self.runtime.session.bad_book = True
        await self.analyze()
        self.assertEqual((await self.service.readiness())["status"], "NOT_READY")
        self.runtime.session.bad_book = False
        await self.analyze()
        self.assertEqual((await self.service.readiness())["status"], "READY")

    async def test_readiness_cache_expiration_and_candle_boundary_are_visible(self):
        await self.analyze()
        self.clock.now += timedelta(seconds=61)
        expired = await self.service.readiness()
        self.assertEqual(expired["status"], "NOT_READY")
        self.assertIn("READINESS_EXPIRED", expired["reason_codes"])

    async def test_repository_health_failure_prevents_ready(self):
        await self.analyze()
        with patch.object(self.service.repository, "health", side_effect=RepositoryError()):
            ready = await self.service.readiness()
        self.assertEqual(ready["status"], "NOT_READY")
        self.assertIn("PERSISTENCE_UNAVAILABLE", ready["reason_codes"])

    async def test_failed_final_persistence_never_returns_false_success(self):
        with patch.object(self.service.repository, "finalize", side_effect=RepositoryError()):
            with self.assertRaises(ServiceError) as error:
                await self.analyze()
        self.assertEqual(error.exception.status_code, 503)
        record = self.service.repository.get(error.exception.analysis_id)
        self.assertEqual(record["status"], "RUNNING")
        await self.service.startup()
        self.assertEqual(self.service.repository.get(record["analysis_id"])["status"], "FAILED")

    async def test_invalid_operational_config_cannot_enable_live_or_unbounded_calls(self):
        for kwargs in ({"history_limit": 0}, {"publication_grace_seconds": 901},
                       {"analysis_timeout_seconds": float("inf")}, {"mcp_timeout_seconds": 0},
                       {"allowed_symbols": ("btc",)}, {"ready_ttl_seconds": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                AnalysisConfig(**kwargs)
        with self.assertRaises(TypeError):
            AnalysisConfig(mode="live")

    async def test_product_event_storage_failure_is_not_misreported_as_mcp_failure(self):
        original = self.service.repository.append_event
        def fail_ticker(analysis_id, event_type, at, data):
            if event_type == "TICKER_FETCHED":
                raise RepositoryError()
            return original(analysis_id, event_type, at, data)
        with patch.object(self.service.repository, "append_event", fail_ticker):
            report = await self.analyze()
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["code"], "PERSISTENCE_UNAVAILABLE")
        self.assertIsNone(report["decision"]["action"])

    async def test_core_failure_has_product_internal_error_and_no_transport_blame(self):
        with patch("agent_trading.analysis_service.ReplayEngine.evaluate_snapshot",
                   side_effect=ValueError("private internal detail")):
            report = await self.analyze()
        self.assertEqual(report["errors"][0]["code"], "ANALYSIS_INTERNAL_ERROR")
        self.assertNotIn("private internal", json.dumps(report))
        self.assertIsNone(report["decision"]["action"])

    async def test_audit_close_failure_invalidates_even_an_evaluated_decision(self):
        from agent_trading.journal import JsonlJournal
        class FailedClose(JsonlJournal):
            def __exit__(self, *args):
                super().__exit__(*args)
                raise OSError("private audit detail")
        with patch("agent_trading.analysis_service.JsonlJournal", FailedClose):
            report = await self.analyze()
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["code"], "AUDIT_UNAVAILABLE")
        self.assertIsNone(report["decision"]["action"])
        self.assertNotIn("private audit", json.dumps(report))
        self.assertIn("DECISION_EVALUATED", [e["type"] for e in report["timeline"]])
        self.assertEqual(report["timeline"][-1]["type"], "ANALYSIS_FAILED")

    async def test_request_cancellation_closes_transport_and_persists_failed_state(self):
        self.runtime.session.gate = asyncio.Event()
        task = asyncio.create_task(self.service.analyze("BTC-USDT"))
        await asyncio.wait_for(self.runtime.session.entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        report = self.service.repository.history(20, 0)["items"][0]
        self.assertTrue(self.runtime.closed)
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["code"], "ANALYSIS_CANCELLED")
        self.assertIsNone(report["decision"]["action"])
