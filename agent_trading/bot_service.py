import asyncio
from datetime import datetime, timezone
import logging

from .config import Config
from .okx_mcp_runtime import open_atk_mcp
from .okx_private_config import load_private_config
from .okx_private_runtime import read_private_snapshots
from .telegram_bot import TelegramBot
from .trading_brain.models import BrainConfig
from .trading_brain.runtime import TradingBrain


def _iso(value):
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class BotService:
    """PAPER TradingBrain coordinator backed by explicit read-only MCP adapters."""

    market_source = "OKX_ATK_MCP"

    def __init__(self, config: Config, *, mcp_factory=open_atk_mcp,
                 node_path=None, server_path=None, mcp_timeout=20,
                 private_reader=read_private_snapshots,
                 private_config_loader=load_private_config,
                 telegram_token="", webapp_url="http://127.0.0.1:5173",
                 telegram=None):
        self.config = config
        self.mcp_factory = mcp_factory
        self.node_path = node_path
        self.server_path = server_path
        self.mcp_timeout = mcp_timeout
        self.private_reader = private_reader
        self.private_config_loader = private_config_loader
        self.brain = None
        self.task = None
        self.private_task = None
        self.is_running = False
        self.market_connected = False
        self.last_market_update = None
        self.last_private_update = None
        self.latest_state = {}
        self.telegram = telegram or (TelegramBot(
            telegram_token, webapp_url, status_callback=self._get_telegram_status)
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
        if self.is_running:
            return False
        self.is_running = True
        self.brain = TradingBrain(self.config.symbol, "15m", config=BrainConfig(target="BOUNDARY"))
        self.seen_event_ids = set()
        self.task = asyncio.create_task(self._run_loop())
        return True

    def stop(self):
        if not self.is_running and self.task is None:
            return False
        self.is_running = False
        self.market_connected = False
        if self.task:
            self.task.cancel()
            self.task = None
        return True

    async def _fetch_candles(self, adapter, as_of: datetime):
        request_limit = min(self.config.bootstrap_limit + 1, 300)
        read = await adapter.candles(
            self.config.symbol, "15m", request_limit, as_of=as_of)
        if not read.value:
            raise ValueError("OKX has no closed candles")
        return tuple(read.value[-self.config.bootstrap_limit:]), read.provenance.response_observed_at

    def _check_notifications(self):
        if not self.telegram or not self.brain:
            return
        for event in self.brain.report().get("events", []):
            if event.id in self.seen_event_ids:
                continue
            self.seen_event_ids.add(event.id)
            if event.kind in (
                "RANGE_CONFIRMED", "SWEEP", "TRADE_CANDIDATE", "BLOCKED",
                "PAPER_ORDER_OPENED", "PAPER_ORDER_CLOSED",
            ):
                try:
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
    def _auto_earn_status(flags):
        states = [state for item in flags for state in (item.auto_lend, item.auto_staking)]
        if "active" in states:
            return "ON"
        if states and all(state in ("off", "unsupported") for state in states):
            return "OFF"
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
        self.latest_state = {
            "decision": {"action": (snapshot["pending_plan"].direction
                                      if snapshot.get("pending_plan") else "NO_TRADE")},
            "market_state": {
                "symbol": self.config.symbol,
                "last_price": str(candles[-1].close),
                "observed_at": _iso(self.last_market_update),
                "market_source": self.market_source,
                "market_connected": self.market_connected,
            },
            "execution": {"trades": snapshot.get("trades", ())},
        }

    async def _accept_market_read(self, adapter, *, bootstrap):
        candles, observed_at = await self._fetch_candles(adapter, datetime.now(timezone.utc))
        self.market_connected = True
        self.last_market_update = observed_at
        if bootstrap:
            self.brain.bootstrap(candles)
        else:
            last_processed = self.brain.as_of
            for candle in candles:
                if last_processed is None or candle.close_time > last_processed:
                    self.brain.process(candle)
        self._update_state(candles)
        self._add_ui_event("OKX ATK", "candles updated")
        self._check_notifications()

    async def _run_loop(self):
        try:
            async with self.mcp_factory(
                node_path=self.node_path, server_path=self.server_path,
                timeout=self.mcp_timeout) as adapter:
                await self._accept_market_read(adapter, bootstrap=True)
                while self.is_running:
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    try:
                        await self._accept_market_read(adapter, bootstrap=False)
                    except Exception:
                        self.market_connected = False
                        self._add_ui_event("OKX ATK", "market read failed", "warning")
                        logging.warning("Bot market read failed")
        except asyncio.CancelledError:
            pass
        except Exception:
            self._add_ui_event("OKX ATK", "market connection failed", "warning")
            logging.warning("Bot market runtime failed")
        finally:
            self.market_connected = False
            self.is_running = False
            self.task = None
