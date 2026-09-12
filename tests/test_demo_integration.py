import asyncio
from contextlib import asynccontextmanager, redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent_trading.account_snapshots import (
    AccountConfiguration,
    AccountSnapshot,
    AutoEarnState,
    EarnSnapshot,
    PrivateSnapshotRead,
)
from agent_trading.analysis_config import AnalysisConfig
from agent_trading.bot_service import BotService
from agent_trading.config import Config
from agent_trading.models import Candle
from agent_trading.telegram_bot import TelegramBot


NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


class _PublicAdapter:
    def __init__(self):
        self.called = asyncio.Event()

    async def candles(self, symbol, timeframe, limit, *, as_of):
        if limit != 2:
            raise AssertionError("bot must request one extra row so an open candle cannot reduce bootstrap history")
        self.called.set()
        candle = Candle(symbol, timeframe, NOW, Decimal("100"), Decimal("101"),
                        Decimal("99"), Decimal("100.5"), Decimal("10"))
        provenance = type("Provenance", (), {"response_observed_at": NOW})()
        return type("Read", (), {"value": (candle,), "provenance": provenance})()


class _PublicFactory:
    def __init__(self, adapter):
        self.adapter = adapter
        self.entered = False

    @asynccontextmanager
    async def __call__(self, **kwargs):
        self.entered = True
        yield self.adapter


class _TelegramLifecycle:
    def __init__(self):
        self.running = False
        self.started = 0
        self.stopped = 0

    def start(self):
        self.running = True
        self.started += 1

    async def stop(self):
        self.running = False
        self.stopped += 1


class DemoIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_bot_market_loop_uses_mcp_read_and_exposes_real_observation(self):
        adapter = _PublicAdapter()
        factory = _PublicFactory(adapter)
        bot = BotService(Config(bootstrap_limit=1, poll_interval_seconds=60),
                         mcp_factory=factory)

        self.assertTrue(bot.start())
        await asyncio.wait_for(adapter.called.wait(), timeout=1)
        await asyncio.sleep(0)

        self.assertTrue(factory.entered)
        self.assertTrue(bot.market_connected)
        self.assertEqual(bot.market_source, "OKX_ATK_MCP")
        self.assertEqual(bot.last_market_update, NOW)
        self.assertEqual(bot.latest_state["market_state"]["last_price"], "100.5")
        await bot.shutdown()

    async def test_private_read_maps_real_snapshot_fields_without_enabling_writes(self):
        flags = (AutoEarnState("USDT", "active", "unsupported"),)
        account = AccountSnapshot(NOW, NOW, (), (), Decimal("123.45"),
                                  AccountConfiguration("1", "net_mode", None, None), flags)
        earn = EarnSnapshot(NOW, (), flags, NOW)

        async def reader(config, **kwargs):
            return PrivateSnapshotRead("CONNECTED", account=account, earn=earn)

        configured = type("PrivateConfig", (), {"ready": True})()
        bot = BotService(Config(), private_reader=reader,
                         private_config_loader=lambda **kwargs: configured)
        await bot._update_private_state()

        self.assertEqual(bot.private_state["account_auth"], "CONNECTED")
        self.assertEqual(bot.private_state["auto_earn_status"], "ON")
        self.assertEqual(bot.private_state["balance"], "123.45")
        self.assertEqual(bot.last_private_update, NOW)
        self.assertEqual(bot.ui_events[0]["title"], "Auto Earn")


class TelegramTests(unittest.TestCase):
    def test_start_and_status_work_while_engine_is_stopped_and_use_webapp_url(self):
        sent = []

        def opener(request, timeout):
            sent.append(json.loads(request.data))
            return type("Response", (), {
                "__enter__": lambda self: self,
                "__exit__": lambda self, *args: None,
            })()

        bot = TelegramBot("token", "https://front.example/app",
                          status_callback=lambda: "Trading Bot: STOPPED")
        with patch("agent_trading.telegram_bot.urlopen", side_effect=opener):
            bot.handle_update({"update_id": 1, "message": {"chat": {"id": 7}, "text": "/start"}})
            bot.handle_update({"update_id": 2, "message": {"chat": {"id": 7}, "text": "/status"}})

        self.assertEqual(sent[0]["reply_markup"]["inline_keyboard"][0][0], {
            "text": "Open Dashboard", "web_app": {"url": "https://front.example/app"}})
        self.assertEqual(sent[1]["text"], "Trading Bot: STOPPED")

    def test_telegram_send_failures_are_contained(self):
        bot = TelegramBot("token", "https://front.example")
        with (patch("agent_trading.telegram_bot.urlopen", side_effect=RuntimeError("offline")),
              self.assertLogs(level="WARNING")):
            self.assertFalse(bot.send_message(7, "hello"))


class ApiDemoTests(unittest.TestCase):
    def test_default_app_configures_bot_and_does_not_print_secret_values(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "TELEGRAM_BOT_TOKEN=secret-token\n"
                "WEBAPP_URL=https://front.example/app\n"
                "ALLOWED_ORIGINS=https://front.example\n",
                encoding="utf-8",
            )
            config = AnalysisConfig(db_path=root / "history.sqlite3", audit_dir=root / "audit")
            previous = Path.cwd()
            try:
                import os
                os.chdir(root)
                output = StringIO()
                with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
                    from agent_trading.api import create_app
                    app = create_app(config=config)
                self.assertIsNotNone(app.state.bot_service)
                self.assertIsNotNone(app.state.bot_service.telegram)
                self.assertEqual(app.state.bot_service.telegram.webapp_url,
                                 "https://front.example/app")
                self.assertNotIn("secret-token", output.getvalue())
            finally:
                os.chdir(previous)

    def test_lifecycle_starts_telegram_without_starting_trading_engine(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            telegram = _TelegramLifecycle()
            bot = BotService(Config(), telegram=telegram)
            from agent_trading.api import create_app
            app = create_app(config=AnalysisConfig(db_path=root / "history.sqlite3",
                                                   audit_dir=root / "audit"),
                             bot_service=bot)
            with TestClient(app) as client:
                self.assertEqual(telegram.started, 1)
                self.assertEqual(client.get("/api/v1/bot/status").json()["bot_status"], "stopped")
            self.assertEqual(telegram.stopped, 1)

    def test_readiness_and_status_expose_sanitized_independent_components(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            bot = BotService(Config())
            bot.market_connected = True
            bot.last_market_update = NOW
            bot.private_state.update(account_auth="AUTH_MISSING", auto_earn_status="UNKNOWN")
            from agent_trading.api import create_app
            app = create_app(config=AnalysisConfig(db_path=root / "history.sqlite3",
                                                   audit_dir=root / "audit"),
                             bot_service=bot)
            with TestClient(app) as client:
                ready = client.get("/health/ready").json()
                status = client.get("/api/v1/bot/status").json()
            self.assertEqual(ready["backend"], "READY")
            self.assertEqual(ready["market"], "CONNECTED")
            self.assertEqual(ready["account"], "AUTH_MISSING")
            self.assertEqual(ready["telegram"], "DISABLED")
            self.assertEqual(ready["execution_mode"], "PAPER")
            self.assertEqual(status["market_source"], "OKX_ATK_MCP")
            self.assertTrue(status["market_connected"])
            self.assertEqual(status["last_market_update"], "2026-09-12T12:00:00Z")

    def test_cors_allows_configured_origin_without_wildcard(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            from agent_trading.api import create_app
            with patch.dict("os.environ", {"ALLOWED_ORIGINS": "https://front.example"}, clear=True):
                app = create_app(config=AnalysisConfig(db_path=root / "history.sqlite3",
                                                       audit_dir=root / "audit"))
            with TestClient(app) as client:
                response = client.options("/api/v1/bot/status", headers={
                    "Origin": "https://front.example",
                    "Access-Control-Request-Method": "GET",
                })
            self.assertEqual(response.headers["access-control-allow-origin"],
                             "https://front.example")
            self.assertNotEqual(response.headers["access-control-allow-origin"], "*")


if __name__ == "__main__":
    unittest.main()
