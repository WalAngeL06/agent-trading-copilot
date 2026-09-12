import asyncio
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from agent_trading.mcp_smoke import main, smoke
from agent_trading.okx_mcp import McpMarketError
from agent_trading.okx_mcp_runtime import _sdk_client, open_atk_mcp
from test_okx_mcp import FakeSession


class FakeClient(FakeSession):
    def __init__(self):
        super().__init__()
        self.server_info = SimpleNamespace(version="1.4.6")
        self.protocol_version = "2025-11-25"
        self.entered = False
        self.exited = False
        self.start_delay = 0
        self.start_error = None

    async def __aenter__(self):
        await asyncio.sleep(self.start_delay)
        if self.start_error:
            raise self.start_error
        self.entered = True
        return self

    async def __aexit__(self, *args):
        self.exited = True


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.workspace = Path(self.folder.name)
        self.server = self.workspace / "package/dist/index.js"
        self.server.parent.mkdir(parents=True)
        self.server.write_text("", encoding="utf-8")
        self.manifest = self.server.parent.parent / "package.json"
        self.manifest.write_text(json.dumps({"name": "@okx_ai/okx-trade-mcp", "version": "1.4.6"}),
                                 encoding="utf-8")
        self.node = self.workspace / "node.exe"
        self.node.write_text("", encoding="utf-8")
        self.client = FakeClient()
        self.factory = patch("agent_trading.okx_mcp_runtime._sdk_client", return_value=self.client)
        self.create_client = self.factory.start()
        self.addCleanup(self.factory.stop)
        self.addCleanup(self.folder.cleanup)

    def connection(self, **kwargs):
        return open_atk_mcp(node_path=str(self.node), server_path=str(self.server),
                            workdir=self.workspace, **kwargs)

    async def test_runtime_initializes_discovers_and_closes(self):
        async with self.connection() as adapter:
            self.assertTrue(self.client.entered)
            read = await adapter.ticker("BTC-USDT")
            self.assertTrue(read.provenance.success)
            self.assertEqual(adapter.runtime_info["mcp_sdk_version"], "2.2.0")
            self.assertEqual(adapter.runtime_info["atk_version"], "1.4.6")
            self.assertEqual(adapter.runtime_info["protocol_version"], "2025-11-25")
        self.assertTrue(self.client.exited)

    async def test_launch_is_tr_market_readonly_without_private_environment(self):
        with patch.dict("os.environ", {"OKX_API_KEY": "secret", "OKX_SECRET_KEY": "secret",
                                       "OKX_AUTH_BIN": "private-auth", "OKX_API_BASE_URL": "https://other.invalid"}):
            async with self.connection():
                launch, timeout, errlog = self.create_client.call_args.args
                self.assertEqual(launch.command, str(self.node.resolve()))
                self.assertEqual(launch.args, (str(self.server.resolve()), "--site", "tr",
                                              "--modules", "market", "--read-only", "--no-log"))
                self.assertEqual(launch.env["OKX_API_BASE_URL"], "https://tr.okx.com")
                self.assertEqual(launch.env["OKX_SITE"], "tr")
                self.assertEqual(launch.env["OKX_UPDATE_CHECK"], "false")
                self.assertNotIn("OKX_API_KEY", launch.env)
                self.assertNotIn("OKX_SECRET_KEY", launch.env)
                self.assertNotIn("OKX_AUTH_BIN", launch.env)
                self.assertEqual(launch.env["HOME"], launch.env["USERPROFILE"])
                public_home = Path(launch.env["HOME"])
                self.assertTrue(public_home.is_relative_to((self.workspace / "runs").resolve()))
                self.assertFalse((public_home / ".okx/config.toml").exists())
                self.assertEqual(launch.cwd, public_home)
                self.assertEqual(timeout, 30)
        self.assertFalse(public_home.exists())
        self.assertTrue(errlog.closed)

    async def test_missing_installed_runtime_is_reported_without_cli_fallback(self):
        self.server.unlink()
        with self.assertRaises(McpMarketError) as error:
            async with self.connection():
                pass
        self.assertEqual(error.exception.code, "ATK_NOT_INSTALLED")
        self.create_client.assert_not_called()

    async def test_package_version_or_identity_drift_stops_startup(self):
        for metadata in [{"name": "@okx_ai/okx-trade-mcp", "version": "1.4.7"},
                         {"name": "other-package", "version": "1.4.6"}]:
            self.manifest.write_text(json.dumps(metadata), encoding="utf-8")
            with self.subTest(metadata=metadata), self.assertRaises(McpMarketError):
                async with self.connection():
                    pass
        self.create_client.assert_not_called()

    async def test_negotiated_server_version_drift_closes_session(self):
        self.client.server_info.version = "1.4.7"
        with self.assertRaises(McpMarketError) as error:
            async with self.connection():
                pass
        self.assertEqual(error.exception.code, "ATK_VERSION_MISMATCH")
        self.assertTrue(self.client.exited)
        self.assertEqual(self.client.calls, [])

    async def test_initialize_timeout_is_bounded_and_sanitized(self):
        self.client.start_delay = 0.1
        with self.assertRaises(McpMarketError) as error:
            async with self.connection(timeout=0.01):
                pass
        self.assertEqual(error.exception.code, "MCP_TIMEOUT")
        self.assertEqual(error.exception.provenance.tool, "initialize")
        self.assertEqual(list((self.workspace / "runs").iterdir()), [])

    async def test_process_start_failure_is_sanitized(self):
        self.client.start_error = OSError("secret private credential path")
        with self.assertRaises(McpMarketError) as error:
            async with self.connection():
                pass
        self.assertEqual(error.exception.code, "MCP_UNAVAILABLE")
        self.assertNotIn("secret", str(error.exception))

    async def test_discovery_failure_closes_session_and_preserves_category(self):
        self.client.tools = []
        with self.assertRaises(McpMarketError) as error:
            async with self.connection():
                pass
        self.assertEqual(error.exception.code, "REQUIRED_TOOLS_MISSING")
        self.assertTrue(self.client.exited)

    async def test_consumer_error_still_closes_and_removes_public_home(self):
        with self.assertRaises(McpMarketError) as error:
            async with self.connection():
                raise RuntimeError("secret consumer error")
        self.assertTrue(self.client.exited)
        self.assertEqual(list((self.workspace / "runs").iterdir()), [])
        self.assertEqual(error.exception.provenance.tool, "runtime")

    async def test_explicit_smoke_uses_mcp_for_all_three_reads_and_candle_snapshot(self):
        result = await smoke(node_path=str(self.node), server_path=str(self.server), workdir=self.workspace)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual([name for name, _ in self.client.calls], [
            "market_get_ticker", "market_get_candles", "market_get_orderbook"])
        self.assertEqual(result["snapshot"]["counts"], {"15m": 1})
        self.assertFalse(result["order_sent"])
        self.assertTrue(self.client.exited)

    async def test_invalid_timeout_is_rejected_before_process_start(self):
        for timeout in [True, 0, -1, float("inf")]:
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                async with self.connection(timeout=timeout):
                    pass
        self.create_client.assert_not_called()


class SdkBoundaryTests(unittest.TestCase):
    def test_missing_sdk_is_an_explicit_error(self):
        with patch.dict(sys.modules, {"mcp": None}):
            with self.assertRaises(McpMarketError) as error:
                _sdk_client(SimpleNamespace(), 30, StringIO())
        self.assertEqual(error.exception.code, "MCP_SDK_UNAVAILABLE")

    def test_v2_sdk_api_and_pinned_version_are_used(self):
        from unittest.mock import Mock
        mcp = ModuleType("mcp")
        mcp.Client = Mock()
        stdio = ModuleType("mcp.client.stdio")
        stdio.StdioServerParameters = lambda **kwargs: SimpleNamespace(**kwargs)
        stdio.stdio_client = Mock(return_value="stdio-transport")
        launch = SimpleNamespace(command="node", args=("server.js",), env={}, cwd=Path("public-home"))
        with patch.dict(sys.modules, {"mcp": mcp, "mcp.client.stdio": stdio}), \
                patch("agent_trading.okx_mcp_runtime.version", return_value="2.2.0"):
            _sdk_client(launch, 12, StringIO())
        mcp.Client.assert_called_once_with("stdio-transport", read_timeout_seconds=12, cache=None)
        self.assertEqual(stdio.stdio_client.call_args.args[0].args, ["server.js"])


class SmokeOutputTests(unittest.TestCase):
    def test_smoke_cli_errors_are_sanitized_and_exit_nonzero(self):
        output = StringIO()
        with patch("agent_trading.mcp_smoke.smoke", new=AsyncMock(side_effect=OSError("secret token"))), \
                redirect_stdout(output):
            exit_code = main([])
        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")
        self.assertNotIn("secret", output.getvalue())

    def test_smoke_cli_reports_success_after_workflow_returns(self):
        output = StringIO()
        with patch("agent_trading.mcp_smoke.smoke", new=AsyncMock(return_value={"status": "VERIFIED"})), \
                redirect_stdout(output):
            exit_code = main([])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "VERIFIED")
