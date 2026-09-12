"""Private reads must fail closed without ever using desktop authentication."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import importlib
from io import StringIO
import json
import logging
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


NOW = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)
SECRETS = {"OKX_API_KEY": "fixture-api-key", "OKX_SECRET_KEY": "fixture-secret-key",
           "OKX_PASSPHRASE": "fixture-passphrase"}
TOOLS = ("account_get_balance", "account_get_asset_balance", "account_get_config",
         "earn_get_savings_balance")
ENDPOINTS = ("/api/v5/account/balance", "/api/v5/asset/balances",
             "/api/v5/account/config", "/api/v5/finance/savings/balance")


def envelope(name, rows, **overrides):
    payload = {"tool": name, "ok": True, "capabilities": {
        "readOnly": True, "hasAuth": True, "demo": False},
        "data": {"endpoint": ENDPOINTS[TOOLS.index(name)], "requestTime": "2026-09-12T12:00:00Z",
                 "data": rows}, "timestamp": "2026-09-12T12:00:00Z"}
    payload.update(overrides)
    return SimpleNamespace(is_error=False, content=[SimpleNamespace(type="text", text=json.dumps(payload))],
                           structured_content=payload)


class PrivateClient:
    """Only the external SDK transport is replaced; real adapter parses full envelopes."""
    def __init__(self):
        self.tools = [SimpleNamespace(name=name, input_schema={"type": "object", "properties": (
            {} if name == TOOLS[2] else {"ccy": {"type": "string"}})},
            annotations=SimpleNamespace(read_only_hint=True, destructive_hint=False)) for name in TOOLS]
        self.responses = {
            TOOLS[0]: envelope(TOOLS[0], [{"totalEq": "123.1234567890123456789", "uTime": "1789214400000",
                "details": [{"ccy": "USDT", "cashBal": "100.000000000000000001", "availBal": "98.5",
                             "eq": "100.000000000000000001", "frozenBal": "1.5", "uTime": "1789214400000",
                             "autoLendStatus": "off", "autoStakingStatus": "unsupported"}]}]),
            TOOLS[1]: envelope(TOOLS[1], [{"ccy": "BTC", "bal": "0.1234567890123456789",
                                        "availBal": "0.1", "frozenBal": "0.0234567890123456789"}]),
            TOOLS[2]: envelope(TOOLS[2], [{"acctLv": "1", "posMode": "net_mode", "autoLoan": False,
                                         "enableSpotBorrow": False, "perm": "", "uid": "private-uid"}]),
            TOOLS[3]: envelope(TOOLS[3], [{"ccy": "USDT", "amt": "2.000000000000000001",
                                         "loanAmt": "1", "rate": "0.02", "earnings": "0.001"}]),
        }
        self.calls = []
        self.delay = 0
        self.error = None
        self.server_info = SimpleNamespace(version="1.4.6")
        self.protocol_version = "2025-11-25"
        self.entered = self.exited = False

    async def list_tools(self, cursor=None):
        return SimpleNamespace(tools=self.tools, next_cursor=None)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.responses[name]

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *args):
        self.exited = True


class PrivateConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = importlib.import_module("agent_trading.okx_private_config")

    def test_absent_or_partial_credentials_are_missing_not_desktop_auth(self):
        for env in [{}, {"OKX_API_KEY": "fixture-api-key"}, dict(SECRETS, OKX_PASSPHRASE=" ")]:
            with self.subTest(fields=list(env)):
                value = self.config.load_private_config(env=env)
                self.assertEqual(value.status, "AUTH_MISSING")
                self.assertFalse(value.ready)

    def test_complete_credentials_have_redacted_repr_and_only_owner_fields(self):
        value = self.config.load_private_config(env=dict(SECRETS, OKX_AUTH_BIN="desktop-auth"))
        self.assertTrue(value.ready)
        for secret in SECRETS.values():
            self.assertNotIn(secret, repr(value))
        self.assertNotIn("desktop-auth", repr(value))

    def test_local_dotenv_quotes_and_environment_precedence_without_interpolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("# Owner file\nOKX_API_KEY='local-key'\nOKX_SECRET_KEY=local-secret\n"
                            'OKX_PASSPHRASE="literal-$VALUE-#-phrase"\n', encoding="utf-8")
            value = self.config.load_private_config(path, env={"OKX_API_KEY": "env-key"})
            self.assertTrue(value.ready)
            self.assertEqual(value.api_key, "env-key")
            self.assertEqual(value.passphrase, "literal-$VALUE-#-phrase")

    def test_malformed_duplicate_or_unreadable_env_is_sanitized(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            for text in ["bad secret text", "OKX_API_KEY=a\nOKX_API_KEY=b", 'OKX_API_KEY="unclosed-secret']:
                path.write_text(text, encoding="utf-8")
                value = self.config.load_private_config(path, env={})
                self.assertEqual(value.status, "ERROR")
                self.assertEqual(value.error_code, "CONFIG_INVALID")
                self.assertNotIn("secret", repr(value))
            value = self.config.load_private_config(Path(folder), env={})
            self.assertEqual(value.status, "ERROR")
            self.assertEqual(value.error_code, "ENV_UNREADABLE")


class PrivateAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = importlib.import_module("agent_trading.okx_private")
        self.client = PrivateClient()
        self.adapter = self.module.OkxPrivateReadAdapter(self.client, clock=lambda: NOW)

    async def read(self):
        await self.adapter.discover()
        return await self.adapter.snapshot()

    async def test_success_normalizes_account_earn_decimal_utc_and_configuration(self):
        result = await self.read()
        self.assertEqual(result.status, "CONNECTED")
        self.assertEqual(result.account.trading[0].balance, Decimal("100.000000000000000001"))
        self.assertEqual(result.account.funding[0].balance, Decimal("0.1234567890123456789"))
        self.assertEqual(result.account.total_equity_usd, Decimal("123.1234567890123456789"))
        self.assertEqual(result.account.configuration.position_mode, "net_mode")
        self.assertEqual(result.account.exchange_time, NOW)
        self.assertEqual(result.earn.savings[0].amount, Decimal("2.000000000000000001"))
        self.assertEqual(result.earn.auto_earn[0].auto_lend, "off")
        self.assertEqual(result.earn.auto_earn[0].auto_staking, "unsupported")
        self.assertEqual(result.earn.auto_earn_source, "account_get_balance.details")
        self.assertEqual(self.client.calls, [(name, {}) for name in TOOLS])
        output = json.dumps(result.to_dict())
        self.assertIn('"100.000000000000000001"', output)
        self.assertNotIn("private-uid", output)
        self.assertNotIn("requestTime", output)

    async def test_empty_funding_and_savings_are_success_not_unavailable(self):
        self.client.responses[TOOLS[1]] = envelope(TOOLS[1], [])
        self.client.responses[TOOLS[3]] = envelope(TOOLS[3], [])
        result = await self.read()
        self.assertEqual(result.status, "CONNECTED")
        self.assertEqual(result.account.funding, ())
        self.assertEqual(result.earn.savings, ())

    async def test_absent_flags_and_inapplicable_values_are_unknown_not_off_or_zero(self):
        rows = deepcopy(self.client.responses[TOOLS[0]].structured_content["data"]["data"])
        rows[0]["details"][0].pop("autoLendStatus")
        rows[0]["details"][0]["autoStakingStatus"] = ""
        rows[0]["details"][0]["availBal"] = ""
        self.client.responses[TOOLS[0]] = envelope(TOOLS[0], rows)
        result = await self.read()
        self.assertEqual(result.status, "CONNECTED")
        self.assertIsNone(result.account.trading[0].available)
        self.assertEqual(result.earn.auto_earn[0].auto_lend, "UNKNOWN")
        self.assertEqual(result.earn.auto_earn[0].auto_staking, "UNKNOWN")

    async def test_bad_auth_business_error_is_sanitized_and_stops_other_reads(self):
        for code in ["50111", "50113", "50114", "AUTH_MISSING", "50038"]:
            response = envelope(TOOLS[0], [], ok=False, error={"code": code, "message": "fixture-secret-key"})
            response.is_error = True
            self.client.responses[TOOLS[0]] = response
            self.client.calls.clear()
            result = await self.read()
            self.assertEqual(result.status, "AUTH_MISSING" if code == "AUTH_MISSING" else "ERROR")
            self.assertEqual(result.error_code, "AUTH_MISSING" if code == "AUTH_MISSING" else
                             "AUTH_FAILED" if code.startswith("501") else "OKX_READ_FAILED")
            self.assertEqual(self.client.calls, [(TOOLS[0], {})])
            self.assertIsNone(result.account)
            self.assertNotIn("fixture-secret-key", json.dumps(result.to_dict()))

    async def test_nonzero_code_never_means_success_even_without_mcp_error(self):
        response = envelope(TOOLS[0], [])
        response.structured_content["data"]["code"] = "50038"
        response.content[0].text = json.dumps(response.structured_content)
        self.client.responses[TOOLS[0]] = response
        result = await self.read()
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.error_code, "OKX_READ_FAILED")

    async def test_pinned_atk_top_level_auth_error_without_code_is_auth_failed(self):
        payload = {"tool": TOOLS[0], "error": True, "type": "AuthenticationError",
                   "message": "fixture-passphrase", "serverVersion": "1.4.6",
                   "capabilities": {"readOnly": True, "hasAuth": True, "demo": False}}
        self.client.responses[TOOLS[0]] = SimpleNamespace(is_error=True,
            content=[SimpleNamespace(type="text", text=json.dumps(payload))], structured_content=payload)
        result = await self.read()
        self.assertEqual((result.status, result.error_code), ("ERROR", "AUTH_FAILED"))
        self.assertNotIn("fixture", json.dumps(result.to_dict()))

    async def test_pinned_atk_top_level_network_error_is_unavailable(self):
        payload = {"tool": TOOLS[0], "error": True, "type": "NetworkError", "message": "fixture-api-key",
                   "capabilities": {"readOnly": True, "hasAuth": True, "demo": False}}
        self.client.responses[TOOLS[0]] = SimpleNamespace(is_error=True,
            content=[SimpleNamespace(type="text", text=json.dumps(payload))], structured_content=payload)
        result = await self.read()
        self.assertEqual((result.status, result.error_code), ("ERROR", "MCP_UNAVAILABLE"))

    async def test_timeout_is_bounded_and_sanitized(self):
        self.client.delay = 0.1
        self.adapter.timeout = 0.01
        result = await self.read()
        self.assertEqual((result.status, result.error_code), ("ERROR", "MCP_TIMEOUT"))

    async def test_exception_group_transport_failure_never_echoes_secrets(self):
        self.client.error = ExceptionGroup("fixture-passphrase", [OSError("fixture-api-key")])
        result = await self.read()
        self.assertEqual(result.status, "ERROR")
        self.assertNotIn("fixture", json.dumps(result.to_dict()))

    async def test_malformed_json_or_scope_or_wrong_endpoint_fails_closed(self):
        good = self.client.responses[TOOLS[0]]
        bad = deepcopy(good)
        bad.content[0].text = "malformed-secret"
        cases = [(bad, "MALFORMED_RESPONSE")]
        for field, value in [("readOnly", False), ("hasAuth", False), ("demo", True)]:
            payload = deepcopy(good.structured_content)
            payload["capabilities"][field] = value
            changed = deepcopy(good)
            changed.content[0].text = json.dumps(payload)
            cases.append((changed, "PRIVATE_SCOPE_MISMATCH"))
        changed = deepcopy(good)
        changed.structured_content["data"]["endpoint"] = "/api/v5/asset/transfer"
        changed.content[0].text = json.dumps(changed.structured_content)
        cases.append((changed, "MALFORMED_RESPONSE"))
        for response, error in cases:
            with self.subTest(error=error):
                self.client.responses[TOOLS[0]] = response
                result = await self.read()
                self.assertEqual((result.status, result.error_code), ("ERROR", error))

    async def test_malformed_domain_values_or_duplicate_currencies_rejected(self):
        for field, value in [("cashBal", 0.123), ("cashBal", "NaN"), ("ccy", "secret-ccy"),
                             ("uTime", "9999999999999")]:
            rows = deepcopy(self.client.responses[TOOLS[0]].structured_content["data"]["data"])
            rows[0]["details"][0][field] = value
            self.client.responses[TOOLS[0]] = envelope(TOOLS[0], rows)
            result = await self.read()
            self.assertEqual((result.status, result.error_code), ("ERROR", "MALFORMED_RESPONSE"))
            self.client = PrivateClient()
            self.adapter = self.module.OkxPrivateReadAdapter(self.client, clock=lambda: NOW)
        rows = deepcopy(self.client.responses[TOOLS[1]].structured_content["data"]["data"])
        self.client.responses[TOOLS[1]] = envelope(TOOLS[1], rows + rows)
        result = await self.read()
        self.assertEqual(result.error_code, "MALFORMED_RESPONSE")

    async def test_earn_failure_retains_valid_account_but_not_fake_earn(self):
        self.client.responses[TOOLS[3]] = envelope(TOOLS[3], [], ok=False, error={"code": "50038"})
        result = await self.read()
        self.assertEqual(result.status, "ERROR")
        self.assertIsNotNone(result.account)
        self.assertIsNone(result.earn)
        self.assertEqual(result.account.auto_earn[0].auto_lend, "off")

    async def test_arbitrary_tools_and_arguments_are_blocked_before_transport(self):
        await self.adapter.discover()
        for name in ["earn_auto_set", "account_transfer", "spot_place_order", "account_get_positions"]:
            with self.assertRaises(self.module.PrivateReadError):
                await self.adapter._read(name)
        with self.assertRaises(TypeError):
            await self.adapter._read(TOOLS[0], {"action": "turn_on"})
        self.assertEqual(self.client.calls, [])

    async def test_discovery_rejects_write_hints_missing_tools_and_schema_drift(self):
        for mutate in [lambda c: c.tools.pop(),
                       lambda c: setattr(c.tools[0].annotations, "read_only_hint", False),
                       lambda c: c.tools[0].input_schema.update(required=["simulatedTrading"]),
                       lambda c: c.tools.append(c.tools[0])]:
            self.client = PrivateClient()
            mutate(self.client)
            adapter = self.module.OkxPrivateReadAdapter(self.client)
            with self.assertRaises(self.module.PrivateReadError):
                await adapter.discover()
            self.assertEqual(self.client.calls, [])

    async def test_discovery_timeout_and_pagination_cycle_do_not_authorize_reads(self):
        async def slow_page(cursor=None):
            await asyncio.sleep(0.1)
        self.client.list_tools = slow_page
        self.adapter.timeout = 0.01
        with self.assertRaises(self.module.PrivateReadError) as error:
            await self.adapter.discover()
        self.assertEqual(error.exception.code, "MCP_TIMEOUT")
        result = await self.adapter.snapshot()
        self.assertEqual(result.error_code, "TOOLS_NOT_DISCOVERED")
        self.assertEqual(self.client.calls, [])
        async def loop_page(cursor=None):
            return SimpleNamespace(tools=[], next_cursor="repeat")
        self.client.list_tools = loop_page
        with self.assertRaises(self.module.PrivateReadError) as error:
            await self.adapter.discover()
        self.assertEqual(error.exception.code, "MALFORMED_DISCOVERY")

    async def test_structured_only_float_is_rejected_and_decimal_strings_supported(self):
        response = self.client.responses[TOOLS[0]]
        response.content = []
        response.structured_content["data"]["data"][0]["totalEq"] = 123.123
        result = await self.read()
        self.assertEqual(result.error_code, "MALFORMED_RESPONSE")
        response.structured_content["data"]["data"][0]["totalEq"] = "123.123"
        result = await self.read()
        self.assertEqual(result.status, "CONNECTED")

    async def test_all_account_and_earn_response_shape_failures_are_sanitized(self):
        for name, rows in [(TOOLS[0], []), (TOOLS[1], [{"ccy": "BTC", "bal": "secret"}]),
                           (TOOLS[2], [{"acctLv": "secret", "posMode": "net_mode"}]),
                           (TOOLS[3], [{"ccy": "USDT", "amt": "secret"}])]:
            with self.subTest(tool=name):
                self.client = PrivateClient()
                self.adapter = self.module.OkxPrivateReadAdapter(self.client, clock=lambda: NOW)
                self.client.responses[name] = envelope(name, rows)
                result = await self.read()
                self.assertEqual((result.status, result.error_code), ("ERROR", "MALFORMED_RESPONSE"))
                self.assertNotIn("secret", json.dumps(result.to_dict()))


class PrivateRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = importlib.import_module("agent_trading.okx_private_runtime")
        self.config_module = importlib.import_module("agent_trading.okx_private_config")
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.workspace = Path(self.folder.name)
        self.server = self.workspace / "package/dist/index.js"
        self.server.parent.mkdir(parents=True)
        self.server.write_text("", encoding="utf-8")
        (self.server.parent.parent / "package.json").write_text(json.dumps({
            "name": "@okx_ai/okx-trade-mcp", "version": "1.4.6"}), encoding="utf-8")
        self.node = self.workspace / "node.exe"
        self.node.write_text("", encoding="utf-8")
        self.client = PrivateClient()

    async def read(self, config=None, **kwargs):
        return await self.module.read_private_snapshots(
            config or self.config_module.load_private_config(env=SECRETS),
            node_path=str(self.node), server_path=str(self.server), workdir=self.workspace, **kwargs)

    async def test_missing_auth_never_starts_sdk_or_uses_desktop_session(self):
        with patch("agent_trading.okx_private_runtime._sdk_client") as factory:
            result = await self.read(self.config_module.load_private_config(env={}))
        factory.assert_not_called()
        self.assertEqual(result.status, "AUTH_MISSING")
        self.assertEqual(list(self.workspace.glob("runs/*")), [])

    async def test_private_child_only_receives_owner_auth_fixed_tr_readonly_and_redacted_launch(self):
        with patch("agent_trading.okx_private_runtime._sdk_client", return_value=self.client) as factory, \
                patch.dict("os.environ", {"OKX_AUTH_BIN": "desktop-auth", "OKX_API_BASE_URL": "https://evil.invalid",
                                         "OKX_ACCESS_TOKEN": "desktop-token", "OKX_DEMO": "true"}):
            result = await self.read()
            launch, timeout, errlog = factory.call_args.args
            self.assertEqual(launch.args, (str(self.server.resolve()), "--site", "tr", "--modules", "account,earn",
                                          "--read-only", "--no-log"))
            self.assertEqual(launch.env["OKX_API_BASE_URL"], "https://tr.okx.com")
            self.assertEqual(launch.env["OKX_DEMO"], "false")
            for key, secret in SECRETS.items():
                self.assertEqual(launch.env[key], secret)
                self.assertNotIn(secret, repr(launch))
            self.assertNotIn("OKX_AUTH_BIN", launch.env)
            self.assertNotIn("OKX_ACCESS_TOKEN", launch.env)
            isolated = Path(launch.env["HOME"])
            self.assertEqual(launch.cwd, isolated)
        self.assertEqual(result.status, "CONNECTED")
        self.assertTrue(self.client.exited)
        self.assertFalse(isolated.exists())
        self.assertTrue(errlog.closed)

    async def test_initialize_discover_and_shutdown_failures_return_safe_states(self):
        with patch("agent_trading.okx_private_runtime._sdk_client", side_effect=OSError("fixture-secret-key")):
            result = await self.read()
        self.assertEqual((result.status, result.error_code), ("ERROR", "MCP_UNAVAILABLE"))
        self.assertNotIn("fixture", json.dumps(result.to_dict()))
        self.client.server_info.version = "1.5.0"
        with patch("agent_trading.okx_private_runtime._sdk_client", return_value=self.client):
            result = await self.read()
        self.assertEqual(result.error_code, "ATK_VERSION_MISMATCH")
        self.assertTrue(self.client.exited)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(list((self.workspace / "runs").iterdir()), [])

    async def test_invalid_timeout_is_normalized_before_launch(self):
        with patch("agent_trading.okx_private_runtime._sdk_client") as factory:
            for timeout in [0, -1, True, float("inf")]:
                result = await self.read(timeout=timeout)
                self.assertEqual((result.status, result.error_code), ("ERROR", "CONFIG_INVALID"))
        factory.assert_not_called()

    async def test_initialize_timeout_and_shutdown_exception_are_terminal_safe_errors(self):
        class SlowClient(PrivateClient):
            async def __aenter__(self):
                await asyncio.sleep(0.1)
                return self
        with patch("agent_trading.okx_private_runtime._sdk_client", return_value=SlowClient()):
            result = await self.read(timeout=0.01)
        self.assertEqual((result.status, result.error_code), ("ERROR", "MCP_TIMEOUT"))
        self.assertEqual(list((self.workspace / "runs").iterdir()), [])
        class BadShutdown(PrivateClient):
            async def __aexit__(self, *args):
                self.exited = True
                raise OSError("fixture-passphrase")
        client = BadShutdown()
        with patch("agent_trading.okx_private_runtime._sdk_client", return_value=client):
            result = await self.read()
        self.assertEqual(result.status, "ERROR")
        self.assertIsNone(result.account)
        self.assertNotIn("fixture", json.dumps(result.to_dict()))
        self.assertTrue(client.exited)
        self.assertEqual(list((self.workspace / "runs").iterdir()), [])

    async def test_discovery_failure_closes_child_and_never_calls_private_tools(self):
        self.client.tools = []
        with patch("agent_trading.okx_private_runtime._sdk_client", return_value=self.client):
            result = await self.read()
        self.assertEqual(result.error_code, "REQUIRED_TOOLS_MISSING")
        self.assertTrue(self.client.exited)
        self.assertEqual(self.client.calls, [])

    async def test_private_sdk_parse_error_and_logging_arguments_never_reach_handlers(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        logger = logging.getLogger("mcp.client.stdio")
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)

        def factory(*args):
            try:
                raise ValueError("fixture-secret-key OK-ACCESS-KEY Authorization: Bearer fixture-token")
            except ValueError:
                logger.exception("Failed to parse JSONRPC message from server")
            logger.error("auth=%s", SECRETS)
            return self.client

        with patch("agent_trading.okx_private_runtime._sdk_client", side_effect=factory):
            result = await self.read()
        self.assertEqual(result.status, "CONNECTED")
        self.assertEqual(output.getvalue(), "")
        logger.error("outside-private-runtime")
        self.assertIn("outside-private-runtime", output.getvalue())


class PrivateCliTests(unittest.TestCase):
    def test_owner_cli_missing_auth_has_safe_state_and_nonzero_exit(self):
        module = importlib.import_module("agent_trading.account_read")
        output = StringIO()
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {}, clear=True), \
                patch("sys.stdout", output):
            code = module.main(["--env-file", str(Path(folder) / ".env")])
        self.assertEqual(code, 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "AUTH_MISSING")
        self.assertIsNone(result["account"])
        self.assertIsNone(result["earn"])
