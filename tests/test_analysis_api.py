from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from analysis_fixtures import Clock, PRICE, Runtime, candle
from agent_trading.analysis_config import AnalysisConfig
from agent_trading.analysis_repository import RepositoryError
from agent_trading.analysis_service import AnalysisService
from agent_trading.api import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.clock = Clock()
        self.runtime = Runtime(self.clock)
        self.config = AnalysisConfig(db_path=self.root / "history.sqlite3",
                                     audit_dir=self.root / "audit", history_limit=3)
        self.service = AnalysisService(self.config, mcp_factory=self.runtime, clock=self.clock)
        self.client = TestClient(create_app(service=self.service))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def post(self, **kwargs):
        return self.client.post("/api/v1/analyses", json={"symbol": "BTC-USDT"}, **kwargs)

    def test_strict_symbol_only_requests_reject_extra_fields_and_wrong_types(self):
        for body in ({}, {"symbol": 1}, {"symbol": None}, {"symbol": ["BTC-USDT"]},
                     {"symbol": "BTC-USDT", "mode": "live"}, {"symbol": "btc-usdt"},
                     {"symbol": "ETH-USDT"}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/v1/analyses", json=body).status_code, 422)
        self.assertEqual(self.runtime.connections, 0)

    def test_validation_errors_do_not_echo_untrusted_payload_or_credentials(self):
        response = self.client.post("/api/v1/analyses",
                                    json={"symbol": "BTC-USDT", "secret": "Bearer do-not-echo"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")
        self.assertNotIn("Bearer", response.text)
        self.assertNotIn("do-not-echo", response.text)

    def test_malformed_json_has_sanitized_contract_error(self):
        response = self.client.post("/api/v1/analyses", content='{"symbol":',
                                    headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")

    def test_completed_btc_post_and_by_id_return_the_same_original_report(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        report = response.json()
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(self.client.get("/api/v1/analyses/" + report["analysis_id"]).json(), report)

    def test_financial_values_remain_strings_through_fastapi_response(self):
        report = self.post().json()
        self.assertEqual(report["market"]["ticker"]["last"], PRICE)
        self.assertEqual(report["market"]["spread"]["value"], "1.000000000000000000000000000003")
        self.assertEqual(report["timeframes"]["15m"]["latest_closed_candle"]["close"], PRICE)

    def test_failed_data_analysis_is_a_persisted_failed_resource_with_null_action(self):
        self.runtime.session.rows["1H"] = [candle("2026-01-01T10:00:00Z", "0")]
        response = self.post()
        self.assertEqual(response.status_code, 201)
        report = response.json()
        self.assertEqual(report["status"], "FAILED")
        self.assertIsNone(report["decision"]["action"])
        self.assertEqual(report["errors"][0]["code"], "MISSING_TIMEFRAME")
        self.assertEqual(self.client.get("/api/v1/analyses/" + report["analysis_id"]).json(), report)

    def test_idempotency_header_replays_terminal_resource_with200(self):
        first = self.post(headers={"Idempotency-Key": "original"})
        second = self.post(headers={"Idempotency-Key": "original"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(len(self.runtime.session.calls), 5)

    def test_failed_idempotent_resource_is_replayed_without_silent_retry(self):
        self.runtime.entry_error = OSError("private-path")
        first = self.post(headers={"Idempotency-Key": "failed"})
        self.runtime.entry_error = None
        second = self.post(headers={"Idempotency-Key": "failed"})
        self.assertEqual(first.json()["status"], "FAILED")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(self.runtime.connections, 1)

    def test_bad_idempotency_header_is_rejected_without_echo(self):
        response = self.post(headers={"Idempotency-Key": "Bearer secret header"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_IDEMPOTENCY_KEY")
        self.assertNotIn("secret header", response.text)

    def test_unknown_uuid_and_invalid_uuid_have_distinct_404_422_contracts(self):
        self.assertEqual(self.client.get("/api/v1/analyses/" + str(uuid4())).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/analyses/not-a-uuid").status_code, 422)

    def test_history_pages_preserve_reports_and_total(self):
        first, second = self.post().json(), self.post().json()
        page = self.client.get("/api/v1/analyses?limit=1").json()
        self.assertEqual(page["total"], 2)
        self.assertEqual(page["items"], [second])
        self.assertEqual(self.client.get("/api/v1/analyses?limit=1&offset=1").json()["items"], [first])

    def test_history_pagination_is_bounded(self):
        for query in ("limit=0", "limit=51", "limit=abc", "offset=-1", "offset=10001"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/api/v1/analyses?" + query).status_code, 422)

    def test_live_has_no_storage_or_network_dependency(self):
        with patch.object(self.service.repository, "health", side_effect=RepositoryError()):
            response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ALIVE"})
        self.assertEqual(self.runtime.connections, 0)

    def test_ready_is_unvalidated_then_ready_after_success_without_network_get(self):
        before = self.client.get("/health/ready")
        self.assertEqual(before.status_code, 503)
        self.assertIn("MARKET_DATA_NOT_VALIDATED", before.json()["reason_codes"])
        self.post()
        calls = self.runtime.connections
        after = self.client.get("/health/ready")
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.json()["status"], "READY")
        self.assertEqual(self.runtime.connections, calls)

    def test_failed_analysis_makes_ready503_while_live200(self):
        self.post()
        self.runtime.session.bad_book = True
        self.post()
        self.assertEqual(self.client.get("/health/ready").status_code, 503)
        self.assertEqual(self.client.get("/health/live").status_code, 200)

    def test_unavailable_history_has_sanitized503(self):
        with patch.object(self.service.repository, "history", side_effect=RepositoryError()):
            response = self.client.get("/api/v1/analyses")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "PERSISTENCE_UNAVAILABLE")
        self.assertNotIn(str(self.root), response.text)

    def test_openapi_defines_string_financial_report_and_only_product_routes(self):
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(set(schema["paths"]), {"/health/live", "/health/ready",
                                               "/api/v1/analyses", "/api/v1/analyses/{analysis_id}",
                                               "/api/v1/bot/status", "/api/v1/bot/market", "/api/v1/bot/activity",
                                               "/api/v1/bot/start", "/api/v1/bot/stop", "/api/v1/strategy/config", "/api/v1/account/preferences"})
        ticker = schema["components"]["schemas"]["Ticker"]["properties"]["last"]
        self.assertEqual(ticker["type"], "string")
        self.assertIn("AnalysisReport", schema["components"]["schemas"])

    def test_private_order_live_and_generic_tool_routes_are_absent(self):
        for route in ("/api/v1/orders", "/api/v1/accounts", "/api/v1/live",
                      "/api/v1/tools", "/api/v1/shell"):
            with self.subTest(route=route):
                self.assertEqual(self.client.post(route, json={}).status_code, 404)
        report = self.post().json()
        self.assertFalse(report["decision"]["order_sent"])
        self.assertEqual(set(n for n, _ in self.runtime.session.calls),
                         {"market_get_ticker", "market_get_candles", "market_get_orderbook"})
