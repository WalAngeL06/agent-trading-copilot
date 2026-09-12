import asyncio
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from analysis_fixtures import Clock, Runtime
from agent_trading.analysis_config import AnalysisConfig
from agent_trading.analysis_service import AnalysisService, ServiceError
from agent_trading.product_smoke import main, smoke


class ProductSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.config = AnalysisConfig(db_path=root / "history.sqlite3",
                                     audit_dir=root / "audit", history_limit=3)
        self.clock = Clock()
        self.runtime = Runtime(self.clock)
        self.service = AnalysisService(self.config, mcp_factory=self.runtime, clock=self.clock)

    async def test_smoke_runs_same_mtf_core_repository_and_concise_public_summary(self):
        summary = await smoke(self.config, service=self.service)
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertTrue(summary["persistence_verified"])
        stored = self.service.repository.get(summary["analysis_id"])
        self.assertEqual(stored["status"], "COMPLETED")
        self.assertEqual(summary["latest_close_time"],
                         {"4H": "2026-01-01T08:00:00Z", "1H": "2026-01-01T10:00:00Z",
                          "15m": "2026-01-01T10:30:00Z"})
        self.assertEqual(summary["mcp_market_call_count"], 5)
        self.assertFalse(summary["order_sent"])
        self.assertNotIn("candles", summary)
        self.assertNotIn("payload", json.dumps(summary))

    async def test_failed_product_smoke_keeps_persisted_failure_and_no_decision(self):
        self.runtime.entry_error = OSError("token=do-not-echo")
        summary = await smoke(self.config, service=self.service)
        self.assertEqual(summary["status"], "FAILED")
        self.assertEqual(summary["error_codes"], ["MCP_UNAVAILABLE"])
        self.assertIsNone(summary["decision"]["action"])
        self.assertTrue(summary["persistence_verified"])
        self.assertNotIn("token", json.dumps(summary))


class SmokeCliTests(unittest.TestCase):
    def test_cli_exception_is_sanitized_and_nonzero(self):
        async def unavailable(*args, **kwargs):
            raise OSError("private credential path")
        output = StringIO()
        with patch("agent_trading.product_smoke.smoke", unavailable), redirect_stdout(output):
            result = main([])
        self.assertEqual(result, 1)
        self.assertNotIn("credential", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")

    def test_cli_failed_report_does_not_exit_zero(self):
        async def failed(*args, **kwargs):
            return {"status": "FAILED", "error_codes": ["MCP_TIMEOUT"], "order_sent": False}
        output = StringIO()
        with patch("agent_trading.product_smoke.smoke", failed), redirect_stdout(output):
            result = main([])
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "FAILED")
