import asyncio
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent_trading.analysis_config import AnalysisConfig
from agent_trading.api import create_app
from fastapi.testclient import TestClient
from env_isolation import BLANK_LOCAL_SETTINGS, isolated_environment
from agent_trading.backtest.dataset import load_stream
from agent_trading.bot_service import BotService
from agent_trading.config import Config
from agent_trading.paper_session import PaperSessionStore
from agent_trading.strategy_v1 import StrategyProfile, StrategyV1

from test_bot_reconnect import QUARTER, T0, _CountingFactory, _ScriptedAdapter, _next_quarter, _wait_until


DATA = Path(__file__).parent / "data"


def _real_candles():
    """Recorded BTC-USDT 4H/1H/15m candles in the order the strategy consumes them."""
    roles = StrategyProfile().timeframes
    streams = [load_stream(DATA / f"btcusdt_{tf}.jsonl", "BTC-USDT", tf).candles for tf in roles.ordered]
    return sorted((c for s in streams for c in s), key=lambda c: (c.close_time, roles.rank(c.timeframe)))



_environment = isolated_environment()


def setUpModule():
    _environment.start()


def tearDownModule():
    _environment.stop()

class PaperSessionStoreTests(unittest.TestCase):
    def test_restored_strategy_continues_exactly_like_the_uninterrupted_one(self):
        candles = _real_candles()
        cut = len(candles) * 2 // 3
        profile = StrategyProfile()
        uninterrupted = StrategyV1("BTC-USDT", profile)
        for candle in candles[:cut]:
            uninterrupted.process(candle)
        with TemporaryDirectory() as directory:
            store = PaperSessionStore(Path(directory) / "paper_session.pickle")
            store.save("BTC-USDT", profile, uninterrupted, {"15m": candles[cut - 1].close_time})
            brain, stream_as_of = store.load("BTC-USDT", profile)

        self.assertEqual(stream_as_of, {"15m": candles[cut - 1].close_time})
        for candle in candles[cut:]:
            uninterrupted.process(candle)
            brain.process(candle)
        self.assertGreater(len(uninterrupted.report()["events"]), 0)
        self.assertEqual(repr(brain.report()), repr(uninterrupted.report()))

    def test_session_is_not_reused_for_other_settings_symbols_or_unreadable_files(self):
        profile = StrategyProfile()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper_session.pickle"
            store = PaperSessionStore(path)
            self.assertIsNone(store.load("BTC-USDT", profile))
            store.save("BTC-USDT", profile, StrategyV1("BTC-USDT", profile), {})
            self.assertIsNotNone(store.load("BTC-USDT", profile))
            self.assertIsNone(store.load("ETH-USDT", profile))
            self.assertIsNone(store.load("BTC-USDT", replace(profile, equity=profile.equity + Decimal("1"))))
            path.write_bytes(b"not a saved session")
            with self.assertLogs(level="WARNING"):
                self.assertIsNone(store.load("BTC-USDT", profile))
            store.clear()
            self.assertFalse(path.exists())


class _AnnouncedOrderBrain:
    """Saved strategy whose report already holds a PAPER order announced before the restart."""

    def report(self):
        return {"events": (SimpleNamespace(id="order-1", kind="PAPER_ORDER_OPENED",
                                           timeframe="15m", observed_at=T0),)}


class _RecordingTelegram:
    running = False

    def __init__(self):
        self.broadcasts = []

    def broadcast(self, text):
        self.broadcasts.append(text)

    def start(self):
        pass

    async def stop(self):
        pass


def _bot(factory, store):
    return BotService(Config(bootstrap_limit=2, poll_interval_seconds=0.01),
                      mcp_factory=factory, retry_delays=(0,), session_store=store)


class BotSessionResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_restarted_agent_resumes_the_saved_session_and_reads_only_new_candles(self):
        with TemporaryDirectory() as directory:
            store = PaperSessionStore(Path(directory) / "paper_session.pickle")
            adapter = _ScriptedAdapter(["ok", _next_quarter])
            first = _bot(_CountingFactory(adapter), store)
            self.assertTrue(first.start())
            await _wait_until(lambda: first.stream_as_of.get("15m") == T0 + QUARTER)
            await first.shutdown()

            adapter.script = []
            adapter.rounds = 0
            _next_quarter(adapter.series)
            second = _bot(_CountingFactory(adapter), store)
            self.assertTrue(second.start())
            self.assertEqual(second.stream_as_of["15m"], T0 + QUARTER)
            self.assertEqual(second.brain.as_of, T0 + QUARTER)
            await _wait_until(lambda: second.stream_as_of.get("15m") == T0 + 2 * QUARTER)

            self.assertTrue(second.is_running)
            self.assertIn("Resumed", " ".join(event["detail"] for event in second.ui_events))
            await second.shutdown()

    async def test_session_older_than_the_available_history_starts_fresh_instead_of_stopping(self):
        with TemporaryDirectory() as directory:
            store = PaperSessionStore(Path(directory) / "paper_session.pickle")
            profile = StrategyProfile()
            stale = StrategyV1("BTC-USDT", profile)
            store.save("BTC-USDT", profile, stale, {tf: T0 - timedelta(days=10) for tf in ("4H", "1H", "15m")})
            bot = _bot(_CountingFactory(_ScriptedAdapter([])), store)
            self.assertTrue(bot.start())
            self.assertEqual(bot.stream_as_of["15m"], T0 - timedelta(days=10))

            await _wait_until(lambda: bot.stream_as_of.get("15m") == T0)

            self.assertTrue(bot.is_running)
            self.assertEqual(store.load("BTC-USDT", profile)[1]["15m"], T0)
            self.assertIn("fresh", " ".join(event["detail"] for event in bot.ui_events))
            await bot.shutdown()

    async def test_resumed_session_does_not_announce_its_old_events_again(self):
        with TemporaryDirectory() as directory:
            store = PaperSessionStore(Path(directory) / "paper_session.pickle")
            store.save("BTC-USDT", StrategyProfile(), _AnnouncedOrderBrain(), {"15m": T0})
            telegram = _RecordingTelegram()
            bot = BotService(Config(), mcp_factory=_CountingFactory(_ScriptedAdapter([])),
                             session_store=store, telegram=telegram)
            self.assertTrue(bot.start())

            bot._check_notifications()

            self.assertEqual(telegram.broadcasts, [])
            self.assertNotIn("PAPER_ORDER_OPENED", [event["title"] for event in bot.ui_events])
            await bot.shutdown()

    def test_default_app_keeps_the_paper_session_at_the_configured_path(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict("os.environ", BLANK_LOCAL_SETTINGS, clear=True):
                app = create_app(config=AnalysisConfig(db_path=root / "history.sqlite3",
                                                       audit_dir=root / "audit"),
                                 strategy_path=root / "strategy.json",
                                 preferences_path=root / "preferences.json",
                                 session_path=root / "paper_session.pickle")
            self.assertEqual(app.state.bot_service.session_store.path, root / "paper_session.pickle")

    async def test_a_failed_session_save_does_not_stop_trading(self):
        with TemporaryDirectory() as directory:
            store = PaperSessionStore(Path(directory) / "paper_session.pickle")
            bot = _bot(_CountingFactory(_ScriptedAdapter([])), store)
            with patch.object(store, "save", side_effect=OSError("disk full")), \
                    self.assertLogs(level="WARNING") as logs:
                self.assertTrue(bot.start())
                await _wait_until(lambda: bot.market_connected)
            self.assertTrue(bot.is_running)
            self.assertNotIn("disk full", "".join(logs.output))
            await bot.shutdown()


if __name__ == "__main__":
    unittest.main()


class _PendingAdapter:
    """Connected market that never publishes a candle: the agent stays running."""

    async def candles(self, *args, **kwargs):
        await asyncio.Event().wait()


class AgentAutoResumeTests(unittest.TestCase):
    def _app(self, root):
        return create_app(config=AnalysisConfig(db_path=root / "history.sqlite3", audit_dir=root / "audit"),
                          mcp_factory=_CountingFactory(_PendingAdapter()),
                          strategy_path=root / "strategy.json", preferences_path=root / "preferences.json",
                          session_path=root / "paper_session.pickle")

    def _status(self, client):
        return client.get("/api/v1/bot/status").json()["bot_status"]

    def test_agent_started_by_the_owner_is_running_again_after_a_backend_restart(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with TestClient(self._app(root)) as client:
                self.assertEqual(client.post("/api/v1/bot/start").status_code, 200)
            with TestClient(self._app(root)) as client:
                self.assertEqual(self._status(client), "running")

    def test_agent_stopped_by_the_owner_stays_stopped_after_a_backend_restart(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with TestClient(self._app(root)) as client:
                client.post("/api/v1/bot/start")
                self.assertEqual(client.post("/api/v1/bot/stop").status_code, 200)
            with TestClient(self._app(root)) as client:
                self.assertEqual(self._status(client), "stopped")
            with TestClient(self._app(root)) as client:
                self.assertEqual(self._status(client), "stopped")
