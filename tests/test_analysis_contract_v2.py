"""Contract correction: real product boundaries, only SDK transport is fake."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from analysis_fixtures import Clock, PRICE, Runtime, candle
from agent_trading import analysis_api_models
from agent_trading.analysis_config import AnalysisConfig
from agent_trading.analysis_report import new_report
from agent_trading.analysis_service import AnalysisService, ServiceError
from agent_trading.api import create_app
from agent_trading.engine import ReplayEngine
from agent_trading.models import utc_time


def alternate_runtime(clock):
    runtime = Runtime(clock)
    candle_tool = next(t for t in runtime.session.tools if t.name == "market_get_candles")
    candle_tool.input_schema["properties"]["bar"]["enum"].extend(["5m", "1m"])
    runtime.session.rows["5m"] = [candle(t) for t in (
        "2026-01-01T10:25:00Z", "2026-01-01T10:20:00Z", "2026-01-01T10:15:00Z"
    )] + [candle("2026-01-01T10:30:00Z", "0")]
    runtime.session.rows["1m"] = [candle(t) for t in (
        "2026-01-01T10:30:00Z", "2026-01-01T10:29:00Z", "2026-01-01T10:28:00Z"
    )] + [candle("2026-01-01T10:31:00Z", "0")]
    return runtime


def validate(report):
    return TypeAdapter(analysis_api_models.AnyAnalysisReport).validate_python(report)


class CollectionTests(unittest.TestCase):
    def test_invalid_required_collection_is_rejected_before_runtime(self):
        for values in ((), [], "1H,5m", {"1H", "5m"}, ("1H", "1H"),
                       ("1D",), ("5m", 1), (["5m"],), ("0m",), ("5m;order",)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                AnalysisConfig(required_timeframes=values)

    def test_mutable_operator_collection_is_copied_and_frozen(self):
        values = ["1H", "5m"]
        config = AnalysisConfig(required_timeframes=values)
        values.append("1m")
        self.assertEqual(config.required_timeframes, ("1H", "5m"))
        with self.assertRaises(AttributeError):
            config.required_timeframes = ("1m",)

    def test_operator_environment_supplies_required_collection(self):
        with patch.dict("os.environ", {"ANALYSIS_REQUIRED_TIMEFRAMES": "1H, 5m"}, clear=True):
            self.assertEqual(AnalysisConfig.from_env().required_timeframes, ("1H", "5m"))
        with patch.dict("os.environ", {"ANALYSIS_REQUIRED_TIMEFRAMES": ""}, clear=True):
            with self.assertRaises(ValueError):
                AnalysisConfig.from_env()


class WireTests(unittest.TestCase):
    def draft(self):
        return new_report(str(uuid4()), "BTC-USDT", utc_time("2026-01-01T10:31:00Z"), 60)

    def test_v0_1_candle_keeps_original_timeframe_enum(self):
        report = self.draft()
        report.pop("strategy_context")
        report["schema_version"] = "analysis-report-v0.1"
        report["timeframes"]["4H"].update(latest_closed_candle={
            "symbol": "BTC-USDT", "timeframe": "5m",
            "close_time": "2026-01-01T08:00:00Z", "open": "100", "high": "103",
            "low": "99", "close": PRICE, "volume": "1", "closed": True,
        }, latest_close_time="2026-01-01T08:00:00Z", candle_count=1)
        with self.assertRaises(ValidationError):
            validate(report)

    def test_v0_1_error_keeps_original_timeframe_enum(self):
        report = self.draft()
        report.pop("strategy_context")
        report["schema_version"] = "analysis-report-v0.1"
        report["errors"] = [{
            "code": "MISSING_CLOSED_CANDLES", "message": "Required series unavailable",
            "stage": "candles", "timeframe": "1D",
        }]
        with self.assertRaises(ValidationError):
            validate(report)

    def test_future_calendar_identifier_is_representable_without_runtime_support(self):
        report = self.draft()
        frame = deepcopy(report["timeframes"]["4H"])
        frame["freshness"].update(expected_close_time="2026-01-01T00:00:00Z",
                                  required_close_time="2026-01-01T00:00:00Z")
        report.update(schema_version="analysis-report-v0.2",
                      strategy_context={"profile_id": None, "required_timeframes": ["1D"]},
                      timeframes={"1D": frame})
        self.assertEqual(validate(report).model_dump(), report)
        with self.assertRaises(ValueError):
            AnalysisConfig(required_timeframes=("1D",))

    def test_context_and_map_must_describe_one_unique_required_collection(self):
        report = self.draft()
        for values in (["4H", "1H"], ["4H", "1H", "15m", "4H"], []):
            bad = deepcopy(report)
            bad["strategy_context"] = {"profile_id": None, "required_timeframes": values}
            with self.subTest(values=values), self.assertRaises(ValidationError):
                validate(bad)
        bad = deepcopy(report)
        bad["timeframes"]["5m.shell"] = bad["timeframes"].pop("15m")
        bad["strategy_context"]["required_timeframes"] = ["4H", "1H", "5m.shell"]
        with self.assertRaises(ValidationError):
            validate(bad)

    def test_candle_must_match_the_timeframe_key_and_report_symbol(self):
        report = self.draft()
        frame = report["timeframes"]["15m"]
        frame.update(latest_closed_candle={
            "symbol": "BTC-USDT", "timeframe": "5m",
            "close_time": "2026-01-01T10:30:00Z", "open": "100", "high": "103",
            "low": "99", "close": PRICE, "volume": "1", "closed": True,
        }, latest_close_time="2026-01-01T10:30:00Z", candle_count=1)
        with self.assertRaises(ValidationError):
            validate(report)
        frame["latest_closed_candle"]["timeframe"] = "15m"
        frame["latest_closed_candle"]["symbol"] = "ETH-USDT"
        with self.assertRaises(ValidationError):
            validate(report)

    def test_closed_input_or_evidence_after_knowledge_cutoff_is_rejected(self):
        report = self.draft()
        report["decision_as_of"] = "2026-01-01T10:30:00Z"
        frame = report["timeframes"]["15m"]
        frame.update(latest_closed_candle={
            "symbol": "BTC-USDT", "timeframe": "15m",
            "close_time": "2026-01-01T10:45:00Z", "open": "100", "high": "103",
            "low": "99", "close": PRICE, "volume": "1", "closed": True,
        }, latest_close_time="2026-01-01T10:45:00Z", candle_count=1)
        with self.assertRaises(ValidationError):
            validate(report)
        frame.update(latest_closed_candle=None, latest_close_time=None, candle_count=0)
        report["evidence"] = [{
            "evidence_id": "evidence-1", "kind": "CLOSED_CANDLES",
            "reference": "timeframes.15m", "source_id": "source-1",
            "decision_input": True, "close_time": "2026-01-01T10:30:00.001Z",
            "observed_at": "2026-01-01T10:31:00Z",
        }]
        with self.assertRaises(ValidationError):
            validate(report)


class ConfiguredServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.clock = Clock()
        self.runtime = alternate_runtime(self.clock)
        self.config = AnalysisConfig(db_path=root / "history.sqlite3",
                                     audit_dir=root / "audit", history_limit=3)
        self.service = AnalysisService(self.config, mcp_factory=self.runtime, clock=self.clock)
        await self.service.startup()

    async def configured(self, timeframes):
        service = AnalysisService(replace(self.config, required_timeframes=timeframes),
                                  repository=self.service.repository,
                                  mcp_factory=self.runtime, clock=self.clock)
        await service.startup()
        return service

    async def test_default_analysis_keeps_verified_baseline_and_actual_decision(self):
        report = (await self.service.analyze("BTC-USDT")).report
        self.assertEqual(report["schema_version"], "analysis-report-v0.2")
        self.assertEqual(report["strategy_context"], {
            "profile_id": None, "required_timeframes": ["4H", "1H", "15m"]})
        self.assertEqual(set(report["timeframes"]), {"4H", "1H", "15m"})
        self.assertEqual(report["decision_as_of"], "2026-01-01T10:30:00Z")
        self.assertEqual(report["decision"], {"action": "NO_TRADE",
                         "reason_codes": ["STRATEGY_NOT_CONFIGURED"], "order_sent": False})
        self.assertEqual(validate(report).model_dump(), report)

    async def test_non_baseline_collection_reaches_real_snapshot_and_persistence(self):
        service = await self.configured(("1H", "5m"))
        captured = []
        class CapturingEngine(ReplayEngine):
            def bootstrap(self, candles, as_of):
                snapshot = super().bootstrap(candles, as_of)
                captured.append(snapshot)
                return snapshot
        with patch("agent_trading.analysis_service.ReplayEngine", CapturingEngine):
            report = (await service.analyze("BTC-USDT")).report
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(report["strategy_context"], {
            "profile_id": None, "required_timeframes": ["1H", "5m"]})
        self.assertEqual(set(captured[0].histories), {"1H", "5m"})
        self.assertEqual(captured[0].as_of, utc_time("2026-01-01T10:30:00Z"))
        self.assertTrue(all(c.closed and c.close_time <= captured[0].as_of
                            for rows in captured[0].histories.values() for c in rows))
        self.assertEqual(report["timeframes"]["5m"]["latest_closed_candle"]["close"], PRICE)
        self.assertEqual(service.repository.get(report["analysis_id"]), report)
        self.assertEqual(validate(report).model_dump(), report)
        self.assertEqual([e["data"]["timeframe"] for e in report["timeline"]
                          if e["type"] == "CANDLES_FETCHED"], ["1H", "5m"])
        self.assertEqual(set(name for name, _ in self.runtime.session.calls),
                         {"market_get_ticker", "market_get_candles", "market_get_orderbook"})
        self.assertFalse(report["decision"]["order_sent"])
        self.assertEqual((await service.readiness())["status"], "READY")

    async def test_cutoff_uses_shortest_required_interval_independent_of_collection_order(self):
        service = await self.configured(("1m", "1H", "5m"))
        report = (await service.analyze("BTC-USDT")).report
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(report["decision_as_of"], "2026-01-01T10:31:00Z")
        self.assertGreater(report["market"]["ticker"]["observed_at"], report["decision_as_of"])
        self.assertTrue(all(e["decision_input"] is False for e in report["evidence"]
                            if e["kind"] in ("TICKER", "ORDERBOOK")))
        self.assertTrue(all(utc_time(e["close_time"]) <= utc_time(report["decision_as_of"])
                            for e in report["evidence"] if e["decision_input"]))

    async def test_publication_lag_trims_later_hour_close_at_shorter_interval_cutoff(self):
        self.clock.now = utc_time("2026-01-01T10:00:30Z")
        self.runtime.session.rows["5m"] = [candle(t) for t in (
            "2026-01-01T09:50:00Z", "2026-01-01T09:45:00Z", "2026-01-01T09:40:00Z"
        )] + [candle("2026-01-01T10:00:00Z", "0")]
        service = await self.configured(("1H", "5m"))
        report = (await service.analyze("BTC-USDT")).report
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(report["decision_as_of"], "2026-01-01T09:55:00Z")
        self.assertEqual(report["timeframes"]["1H"]["latest_close_time"], "2026-01-01T09:00:00Z")
        self.assertEqual(report["timeframes"]["1H"]["freshness"]["expected_close_time"],
                         "2026-01-01T10:00:00Z")

    async def test_future_closed_five_minute_row_is_filtered(self):
        self.runtime.session.rows["5m"][-1] = candle("2026-01-01T10:30:00Z", "1")
        service = await self.configured(("1H", "5m"))
        report = (await service.analyze("BTC-USDT")).report
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(report["timeframes"]["5m"]["latest_close_time"], "2026-01-01T10:30:00Z")
        source = next(s for s in report["sources"] if s["provenance"]["timeframe"] == "5m")
        self.assertEqual(source["provenance"]["filtering"]["future_rows"], 1)

    async def test_missing_configured_series_is_failed_without_fake_strategy_outcome(self):
        self.runtime.session.rows["5m"] = [candle("2026-01-01T10:30:00Z", "0")]
        service = await self.configured(("1H", "5m"))
        report = (await service.analyze("BTC-USDT")).report
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["timeframe"], "5m")
        self.assertIsNone(report["decision"]["action"])
        self.assertIsNone(report["decision_as_of"])
        self.assertEqual(validate(report).model_dump(), report)

    async def test_discovery_rejects_unsupported_provider_bar_without_fallback(self):
        tool = next(t for t in self.runtime.session.tools if t.name == "market_get_candles")
        tool.input_schema["properties"]["bar"]["enum"].remove("5m")
        service = await self.configured(("1H", "5m"))
        report = (await service.analyze("BTC-USDT")).report
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["errors"][0]["code"], "TOOL_SCHEMA_DRIFT")
        self.assertIsNone(report["decision"]["action"])
        self.assertFalse(report["decision"]["order_sent"])

    async def test_idempotency_key_cannot_silently_reuse_a_different_required_collection(self):
        original = (await self.service.analyze("BTC-USDT", idempotency_key="context")).report
        service = await self.configured(("1H", "5m"))
        with self.assertRaises(ServiceError) as caught:
            await service.analyze("BTC-USDT", idempotency_key="context")
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(service.repository.get(original["analysis_id"]), original)


class VersionedApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.clock = Clock()
        self.runtime = alternate_runtime(self.clock)
        config = AnalysisConfig(db_path=root / "history.sqlite3", audit_dir=root / "audit", history_limit=3)
        self.service = AnalysisService(config, mcp_factory=self.runtime, clock=self.clock)
        self.client = TestClient(create_app(service=self.service))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_old_report_and_key_replay_stay_original_in_mixed_version_history(self):
        legacy = new_report(str(uuid4()), "BTC-USDT", self.clock.now, 60)
        legacy.pop("strategy_context", None)
        legacy["schema_version"] = "analysis-report-v0.1"
        key = sha256(b"legacy").hexdigest()
        fingerprint = sha256(b"analysis-api-v0.1:BTC-USDT").hexdigest()
        self.service.repository.reserve(legacy, key, fingerprint)
        self.service.repository.recover_interrupted(self.clock.now)
        old = self.service.repository.get(legacy["analysis_id"])
        replay = self.client.post("/api/v1/analyses", json={"symbol": "BTC-USDT"},
                                  headers={"Idempotency-Key": "legacy"})
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json(), old)
        self.assertNotIn("strategy_context", replay.json())
        self.assertEqual(self.client.get("/api/v1/analyses/" + old["analysis_id"]).json(), old)
        new = self.client.post("/api/v1/analyses", json={"symbol": "BTC-USDT"}).json()
        self.assertEqual(new["schema_version"], "analysis-report-v0.2")
        page = self.client.get("/api/v1/analyses").json()
        self.assertEqual({r["analysis_id"]: r for r in page["items"]},
                         {old["analysis_id"]: old, new["analysis_id"]: new})

    def test_display_or_user_decision_timeframe_is_not_an_http_trading_input(self):
        for field, value in (("chart_timeframe", "1m"), ("decision_timeframe", "1m"),
                             ("required_timeframes", ["1m"]), ("strategy_context", {}),
                             ("mode", "LIVE")):
            with self.subTest(field=field):
                response = self.client.post("/api/v1/analyses",
                                            json={"symbol": "BTC-USDT", field: value})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(self.runtime.connections, 0)

    def test_openapi_exposes_version_discrimination_and_dynamic_timeframe_keys(self):
        schema = self.client.get("/openapi.json").json()
        response = schema["paths"]["/api/v1/analyses"]["post"]["responses"]["201"]["content"]["application/json"]["schema"]
        self.assertEqual(response["discriminator"]["propertyName"], "schema_version")
        report = schema["components"]["schemas"]["AnalysisReportV2"]
        timeframes = report["properties"]["timeframes"]
        self.assertNotIn("enum", timeframes.get("propertyNames", {}))
        self.assertIn("strategy_context", report["required"])
        self.assertEqual(set(schema["paths"]), {
            "/health/live", "/health/ready", "/api/v1/analyses", "/api/v1/analyses/{analysis_id}",
            "/api/v1/bot/status", "/api/v1/bot/market", "/api/v1/bot/activity",
            "/api/v1/bot/start", "/api/v1/bot/stop"})
