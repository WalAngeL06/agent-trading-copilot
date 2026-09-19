import asyncio
from datetime import datetime, timezone
import logging
import math

from .config import Config
from .okx_mcp import sanitized_failure
from .okx_mcp_runtime import open_atk_mcp
from .okx_private_config import load_private_config
from .okx_private_runtime import read_private_snapshots
from .telegram_bot import TelegramBot
from .strategy_v1 import StrategyV1, StrategyProfile
from .market import bar_duration


class MarketHistoryGap(ValueError):
    """Closed candles are missing between the processed history and the new read."""


def _iso(value):
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class BotService:
    """PAPER multi-timeframe strategy coordinator using read-only MCP adapters."""

    market_source = "OKX_ATK_MCP"

    def __init__(self, config: Config, *, mcp_factory=open_atk_mcp,
                 node_path=None, server_path=None, mcp_timeout=20,
                 private_reader=read_private_snapshots,
                 private_config_loader=load_private_config,
                 telegram_token="", webapp_url="http://127.0.0.1:5173",
                 telegram=None, retry_delays=(5, 15, 30, 60, 120, 300),
                 telegram_allowed_user_ids=(), session_store=None):
        self.config = config
        self.session_store = session_store
        self._resumed = False
        self.retry_delays = tuple(retry_delays)
        if not self.retry_delays or any(
                type(delay) not in (int, float) or not math.isfinite(delay) or delay < 0
                for delay in self.retry_delays):
            raise ValueError("retry_delays must be nonnegative finite seconds")
        self.mcp_factory = mcp_factory
        self.node_path = node_path
        self.server_path = server_path
        self.mcp_timeout = mcp_timeout
        self.private_reader = private_reader
        self.private_config_loader = private_config_loader
        self.strategy_profile = StrategyProfile()
        self.market_status = "WAITING"
        self.stream_as_of = {}
        self.brain = None
        self.task = None
        self.private_task = None
        self.is_running = False
        self.market_connected = False
        self.last_market_update = None
        self.last_private_update = None
        self.latest_state = {}
        self.telegram = telegram or (TelegramBot(
            telegram_token, webapp_url, status_callback=self._get_telegram_status,
            allowed_user_ids=telegram_allowed_user_ids)
            if telegram_token else None)
        self.seen_event_ids = set()
        self.private_state = {
            "account_auth": "UNKNOWN", "auto_earn_status": "UNKNOWN", "balance": None,
        }
        self.ui_events = []

    def _get_telegram_status(self):
        bot_status = "RUNNING" if self.is_running else "STOPPED"
        strategy = (self.latest_state.get("decision", {}).get("action", "UNKNOWN")
                    if self.latest_state else "UNKNOWN")
        market = "CONNECTED" if self.market_connected else "DISCONNECTED"
        return (f"Trading Bot: {bot_status}\n"
                f"Execution Mode: PAPER\n"
                f"Market Connection: {market} (OKX ATK MCP)\n"
                f"Account Auth: {self.private_state['account_auth']}\n"
                f"Auto Earn: {self.private_state['auto_earn_status']}\n"
                f"Strategy State: {strategy}")

    def startup(self):
        if self.telegram:
            self.telegram.start()
        if self.private_task is None or self.private_task.done():
            self.private_task = asyncio.create_task(self._private_loop())

    async def shutdown(self):
        market_task = self.task
        self.stop()
        tasks = [task for task in (market_task, self.private_task) if task is not None]
        if self.private_task:
            self.private_task.cancel()
            self.private_task = None
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self.telegram:
            await self.telegram.stop()

    def start(self):
        if self.is_running or (self.task and not self.task.done()):
            return False
        self.is_running = True
        restored = (self.session_store.load(self.config.symbol, self.strategy_profile)
                    if self.session_store else None)
        self._resumed = restored is not None
        if restored:
            self.brain, self.stream_as_of = restored
            # Events of the resumed session were already announced before the restart.
            self.seen_event_ids = {event.id for event in self.brain.report().get("events", ())}
            self._add_ui_event("Agent", "Resumed saved PAPER session")
        else:
            self._new_session()
            self._add_ui_event("Agent", "Started in PAPER mode; historical bootstrap")
        self.latest_state = {}
        self.market_status = "WAITING"
        self.task = asyncio.create_task(self._run_loop())
        return True

    def _new_session(self):
        self.brain = StrategyV1(self.config.symbol, self.strategy_profile)
        self.stream_as_of = {}
        self.seen_event_ids = set()
        if self.session_store:
            self.session_store.clear()

    def _save_session(self):
        if not self.session_store:
            return
        try:
            self.session_store.save(self.config.symbol, self.strategy_profile,
                                    self.brain, self.stream_as_of)
        except Exception as exc:
            logging.warning("PAPER session could not be saved (%s)", type(exc).__name__)

    def stop(self):
        if not self.is_running and self.task is None:
            return False
        self.is_running = False
        self.market_connected = False
        self.market_status = "WAITING"
        self._add_ui_event("Agent", "Stopped")
        if self.task:
            self.task.cancel()
        return True

    async def _fetch_candles(self, adapter, as_of: datetime):
        request_limit = min(self.config.bootstrap_limit + 1, 300)
        histories = {}
        observations = []
        for timeframe in self.strategy_profile.timeframes.ordered:
            read = await adapter.candles(self.config.symbol, timeframe, request_limit, as_of=as_of)
            if not read.value:
                raise ValueError("OKX has no closed candles")
            histories[timeframe] = tuple(read.value[-self.config.bootstrap_limit:])
            observations.append(read.provenance.response_observed_at)
        return histories, max(observations)

    def _check_notifications(self):
        if not self.brain:
            return
        for event in self.brain.report().get("events", []):
            if event.id in self.seen_event_ids:
                continue
            self.seen_event_ids.add(event.id)
            if event.kind in (
                "RANGE_CONFIRMED", "SWEEP", "TRADE_CANDIDATE", "BLOCKED",
                "PAPER_ORDER_OPENED", "PAPER_ORDER_CLOSED",
                "PARTIAL_TP_FILLED", "BREAK_EVEN_PROTECTED", "TRAILING_STOP_UPDATED",
                "RANGE_HIGH_PARTIAL_EXIT", "RUNNER_OPEN", "RUNNER_STOPPED",
            ):
                self._add_ui_event(event.kind, f"PAPER · {event.timeframe} · {_iso(event.observed_at)}")
                try:
                    if self.telegram:
                        self.telegram.broadcast(f"Notification: {event.kind}")
                except Exception:
                    logging.warning("Telegram notification failed")

    def _add_ui_event(self, title, detail, tone="neutral"):
        import uuid
        self.ui_events.insert(0, {
            "id": str(uuid.uuid4()),
            "at": _iso(datetime.now(timezone.utc)),
            "title": title,
            "detail": detail,
            "tone": tone,
        })
        self.ui_events = self.ui_events[:50]

    @staticmethod
    def _auto_earn_status(_flags):
        # The balance flags describe generic per-currency auto-lend/staking,
        # not the OKX TR Lira Earn setting shown in the app.
        return "UNKNOWN"

    async def _update_private_state(self):
        config = self.private_config_loader(env_file=".env")
        old_auth = self.private_state["account_auth"]
        old_earn = self.private_state["auto_earn_status"]
        if not config.ready:
            self.private_state.update(account_auth="AUTH_MISSING", auto_earn_status="UNKNOWN",
                                      balance=None)
        else:
            try:
                result = await self.private_reader(
                    config, node_path=self.node_path, server_path=self.server_path,
                    timeout=self.mcp_timeout)
                self.private_state["account_auth"] = result.status
                if result.status == "CONNECTED":
                    flags = result.earn.auto_earn if result.earn else (
                        result.account.auto_earn if result.account else ())
                    self.private_state["auto_earn_status"] = self._auto_earn_status(flags)
                    self.private_state["balance"] = (
                        str(result.account.total_equity_usd)
                        if result.account and result.account.total_equity_usd is not None else None)
                    self.last_private_update = (
                        result.earn.observed_at if result.earn else result.account.observed_at)
                else:
                    self.private_state.update(auto_earn_status="UNKNOWN", balance=None)
            except Exception:
                logging.warning("OKX private read failed")
                self.private_state.update(account_auth="ERROR", auto_earn_status="UNKNOWN",
                                          balance=None)
        if self.private_state["account_auth"] != old_auth:
            tone = "neutral" if self.private_state["account_auth"] == "CONNECTED" else "warning"
            self._add_ui_event("OKX private auth", self.private_state["account_auth"], tone)
        if self.private_state["auto_earn_status"] != old_earn:
            self._add_ui_event("Auto Earn", self.private_state["auto_earn_status"])

    async def _private_loop(self):
        try:
            while True:
                await self._update_private_state()
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass

    def _update_state(self, candles):
        snapshot = self.brain.snapshot()
        trades = []
        for trade in snapshot.get("trades", ())[-20:]:
            ledger = trade.ledger
            trades.append({"status": trade.status, "entry": str(trade.entry),
                           "stop": str(trade.stop), "range_high": str(trade.tp),
                           "remaining_quantity": str(ledger.remaining_quantity),
                           "pnl": str(ledger.total_realized_pnl)})
        self.latest_state = {
            "decision": {"action": snapshot["phase"]},
            "market_state": {
                "symbol": self.config.symbol,
                "last_price": str(candles[-1].close),
                "price_kind": "LAST_CLOSED_ENTRY_CANDLE",
                "candle_closed_at": _iso(candles[-1].close_time),
                "observed_at": _iso(self.last_market_update),
                "market_source": self.market_source,
                "market_connected": self.market_connected,
            },
            "execution": {"trades": trades},
        }

    async def _accept_market_read(self, adapter, *, bootstrap):
        histories, observed_at = await self._fetch_candles(adapter, datetime.now(timezone.utc))
        self._apply_market_read(histories, observed_at)

    def _apply_market_read(self, histories, observed_at):
        roles = self.strategy_profile.timeframes
        # A higher timeframe may publish later than a lower one at the same
        # boundary. Do not advance past a missing candle and consume it later.
        ready_before = min(candles[-1].close_time + bar_duration(timeframe)
                           for timeframe, candles in histories.items())
        deferred = any(c.close_time >= ready_before
                       for candles in histories.values() for c in candles)
        incoming = []
        for timeframe, candles in histories.items():
            previous = self.stream_as_of.get(timeframe)
            new = [c for c in candles if c.close_time < ready_before
                   and (previous is None or c.close_time > previous)]
            for candle in new:
                if previous is not None and candle.close_time != previous + bar_duration(timeframe):
                    raise MarketHistoryGap("Market history gap; restart to bootstrap")
                previous = candle.close_time
            incoming.extend(new)
        incoming.sort(key=lambda c: (c.close_time, roles.rank(c.timeframe)))
        for candle in incoming:
            self.brain.process(candle)
            self.stream_as_of[candle.timeframe] = candle.close_time
        if incoming:
            self._save_session()
        self.market_connected = True
        self.market_status = "WAITING" if deferred else "CONNECTED"
        self.last_market_update = observed_at
        self._update_state(histories[roles.entry])
        self._add_ui_event("OKX ATK", "Closed candles updated: " + " / ".join(roles.ordered))
        self._check_notifications()

    async def _run_loop(self):
        # Reading OKX can fail transiently (network, MCP process). Those failures
        # reconnect with backoff and keep the strategy state. Data the strategy
        # rejects (history gap, processing error) stops the agent instead.
        failures = 0
        try:
            while self.is_running:
                processing = False
                try:
                    async with self.mcp_factory(
                        node_path=self.node_path, server_path=self.server_path,
                        timeout=self.mcp_timeout) as adapter:
                        while self.is_running:
                            histories, observed_at = await self._fetch_candles(
                                adapter, datetime.now(timezone.utc))
                            processing = True
                            self._apply_market_read(histories, observed_at)
                            processing = False
                            self._resumed = False
                            if failures:
                                failures = 0
                                self._add_ui_event("OKX ATK", "market reconnected")
                            await asyncio.sleep(self.config.poll_interval_seconds)
                except Exception as exc:
                    self.market_connected = False
                    if processing and self._resumed and isinstance(exc, MarketHistoryGap):
                        # The saved session ends before the history OKX still serves.
                        self._resumed = False
                        self._new_session()
                        self._add_ui_event("Agent", "Saved PAPER session is too old to resume; "
                                           "started a fresh session", "warning")
                        continue
                    if processing:
                        self.market_status = "ERROR"
                        self._add_ui_event("OKX ATK", "market data rejected; agent stopped", "warning")
                        logging.warning("Bot market data rejected (%s)", type(exc).__name__)
                        break
                    delay = self.retry_delays[min(failures, len(self.retry_delays) - 1)]
                    failures += 1
                    self.market_status = "RECONNECTING"
                    self._add_ui_event("OKX ATK", f"market read failed; retrying in {delay:g}s", "warning")
                    logging.warning("Bot market read failed (%s); retrying in %gs",
                                    sanitized_failure(exc).code, delay)
                    await asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass
        finally:
            self.market_connected = False
            self.is_running = False
            self.task = None
