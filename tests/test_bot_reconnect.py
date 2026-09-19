import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from agent_trading.bot_service import BotService
from agent_trading.config import Config
from agent_trading.models import Candle
from agent_trading.okx_mcp import McpMarketError


T0 = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
QUARTER = timedelta(minutes=15)


def _candle(timeframe, close_time):
    return Candle("BTC-USDT", timeframe, close_time, Decimal("100"), Decimal("101"),
                  Decimal("99"), Decimal("100.5"), Decimal("10"))


class _ScriptedAdapter:
    """Serves closed candles per timeframe; each read round follows the script.

    A round is one full multi-timeframe read. Script steps: "ok", "fail"
    (the round raises like a dropped OKX connection) or a callable that edits
    the served series before the round succeeds. Past the script: "ok".
    """

    def __init__(self, script):
        self.series = {tf: [_candle(tf, T0)] for tf in ("4H", "1H", "15m")}
        self.script = list(script)
        self.rounds = 0
        self._round_open = False

    async def candles(self, symbol, timeframe, limit, *, as_of):
        if not self._round_open:
            self.rounds += 1
            self._round_open = True
            step = self.script[self.rounds - 1] if self.rounds <= len(self.script) else "ok"
            if step == "fail":
                self._round_open = False
                raise McpMarketError("MCP_UNAVAILABLE")
            if callable(step):
                step(self.series)
        if timeframe == "15m":
            self._round_open = False
        provenance = type("Provenance", (), {"response_observed_at": T0})()
        return type("Read", (), {"value": tuple(self.series[timeframe][-limit:]),
                                 "provenance": provenance})()


class _CountingFactory:
    def __init__(self, adapter, enter_failures=0):
        self.adapter = adapter
        self.enter_failures = enter_failures
        self.attempts = 0
        self.sessions = 0

    @asynccontextmanager
    async def __call__(self, **kwargs):
        self.attempts += 1
        if self.attempts <= self.enter_failures:
            raise OSError("connection reset by peer")
        self.sessions += 1
        yield self.adapter


def _next_quarter(series):
    series["15m"].append(_candle("15m", series["15m"][-1].close_time + QUARTER))


def _skip_a_quarter(series):
    series["15m"].append(_candle("15m", series["15m"][-1].close_time + 2 * QUARTER))


async def _wait_until(predicate, timeout=2):
    async def poll():
        while not predicate():
            await asyncio.sleep(0.005)
    await asyncio.wait_for(poll(), timeout)


def _bot(factory, retry_delays):
    return BotService(Config(bootstrap_limit=2, poll_interval_seconds=0.01),
                      mcp_factory=factory, retry_delays=retry_delays)


class MarketReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_dropped_connection_reconnects_and_keeps_strategy_state(self):
        adapter = _ScriptedAdapter(["ok", "fail", _next_quarter])
        factory = _CountingFactory(adapter)
        bot = _bot(factory, retry_delays=(0,))
        self.assertTrue(bot.start())
        brain = bot.brain

        with self.assertLogs(level="WARNING"):
            await _wait_until(lambda: bot.stream_as_of.get("15m") == T0 + QUARTER)

        self.assertEqual(factory.sessions, 2)
        self.assertTrue(bot.is_running)
        self.assertTrue(bot.market_connected)
        self.assertIs(bot.brain, brain)
        await bot.shutdown()

    async def test_initial_connection_failure_is_retried(self):
        adapter = _ScriptedAdapter([])
        factory = _CountingFactory(adapter, enter_failures=1)
        bot = _bot(factory, retry_delays=(0,))
        self.assertTrue(bot.start())

        with self.assertLogs(level="WARNING") as logs:
            await _wait_until(lambda: bot.market_connected)

        self.assertEqual(factory.attempts, 2)
        self.assertIn("MCP_UNAVAILABLE", logs.output[0])
        self.assertNotIn("connection reset by peer", "".join(logs.output))
        self.assertTrue(bot.is_running)
        await bot.shutdown()

    async def test_waiting_to_retry_reports_reconnecting_until_stopped(self):
        adapter = _ScriptedAdapter([])
        factory = _CountingFactory(adapter, enter_failures=10)
        bot = _bot(factory, retry_delays=(30,))
        self.assertTrue(bot.start())

        with self.assertLogs(level="WARNING"):
            await _wait_until(lambda: factory.attempts == 1 and bot.market_status == "RECONNECTING")
        self.assertTrue(bot.is_running)
        self.assertFalse(bot.market_connected)

        bot.stop()
        await _wait_until(lambda: bot.task is None)
        self.assertEqual(factory.attempts, 1)
        self.assertFalse(bot.is_running)

    async def test_retry_delay_restarts_from_first_step_after_a_successful_read(self):
        adapter = _ScriptedAdapter(["ok", "fail", "ok", "fail", _next_quarter])
        factory = _CountingFactory(adapter)
        bot = _bot(factory, retry_delays=(0, 30))
        self.assertTrue(bot.start())

        with self.assertLogs(level="WARNING"):
            await _wait_until(lambda: bot.stream_as_of.get("15m") == T0 + QUARTER)

        self.assertEqual(factory.sessions, 3)
        await bot.shutdown()

    async def test_history_gap_stops_the_agent_instead_of_retrying(self):
        adapter = _ScriptedAdapter(["ok", _skip_a_quarter])
        factory = _CountingFactory(adapter)
        bot = _bot(factory, retry_delays=(0,))
        self.assertTrue(bot.start())

        with self.assertLogs(level="WARNING"):
            await _wait_until(lambda: not bot.is_running)

        self.assertEqual(bot.market_status, "ERROR")
        self.assertEqual(factory.sessions, 1)
        self.assertEqual(bot.stream_as_of["15m"], T0)
        await bot.shutdown()

    def test_retry_schedule_must_be_nonempty_nonnegative_seconds(self):
        for delays in ((), (-1,), (float("nan"),), ("5",)):
            with self.subTest(delays=delays), self.assertRaises(ValueError):
                BotService(Config(), retry_delays=delays)


if __name__ == "__main__":
    unittest.main()
