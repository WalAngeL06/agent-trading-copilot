import asyncio
from datetime import datetime, timezone
import logging
import os
from .okx import OkxMarketAdapter, normalize_candles
from .config import Config
from .trading_brain.runtime import TradingBrain
from .trading_brain.models import BrainConfig
from .telegram_bot import TelegramBot

class BotService:
    def __init__(self, config: Config, adapter: OkxMarketAdapter):
        self.config = config
        self.adapter = adapter
        self.brain = None
        self.task = None
        self.is_running = False
        self.latest_state = {}
        
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        webapp_url = os.environ.get("WEBAPP_URL", "http://127.0.0.1:5173")
        self.telegram = TelegramBot(token, webapp_url, status_callback=self._get_telegram_status) if token else None
        self.seen_event_ids = set()
        self.private_state = {"account_auth": "UNKNOWN", "autoEarn": "UNKNOWN", "balance": None}
        self.ui_events = []

    def _get_telegram_status(self):
        bot_status = "RUNNING" if self.is_running else "STOPPED"
        strategy = self.latest_state.get("decision", {}).get("action", "UNKNOWN") if self.latest_state else "UNKNOWN"
        auth = self.private_state.get("account_auth", "UNKNOWN")
        earn = self.private_state.get("autoEarn", "UNKNOWN")
        return (f"Trading Bot: {bot_status}\n"
                f"Execution Mode: PAPER\n"
                f"Market Connection: CONNECTED (OKX ATK MCP)\n"
                f"Account Auth: {auth}\n"
                f"Auto Earn: {earn}\n"
                f"Strategy State: {strategy}")

    def startup(self):
        if self.telegram:
            self.telegram.start()
        self.private_task = asyncio.create_task(self._private_loop())

    def shutdown(self):
        self.stop()
        if self.telegram:
            self.telegram.stop()
        if hasattr(self, 'private_task') and self.private_task:
            self.private_task.cancel()

    def start(self):
        if self.is_running:
            return False
        self.is_running = True
        
        brain_config = BrainConfig(target='BOUNDARY')
        self.brain = TradingBrain(self.config.symbol, '15m', config=brain_config)
        self.seen_event_ids = set()
        
        self.task = asyncio.create_task(self._run_loop())
        return True

    def stop(self):
        if not self.is_running:
            return False
        self.is_running = False
        if self.task:
            self.task.cancel()
            self.task = None
        return True

    async def _fetch_candles(self, as_of: datetime):
        def _do_fetch():
            limit = self.config.bootstrap_limit
            # We must fetch slightly more to normalize correctly
            rows = self.adapter.candles(self.config.symbol, '15m', limit + 5)
            history = normalize_candles(rows, self.config.symbol, '15m', as_of)
            if not history:
                raise ValueError("OKX has no closed candles")
            return history[-limit:]
        return await asyncio.to_thread(_do_fetch)

    def _check_notifications(self):
        if not self.telegram or not self.brain: return
        report = self.brain.report()
        for event in report.get('events', []):
            if event.id not in self.seen_event_ids:
                self.seen_event_ids.add(event.id)
                if event.kind in ("RANGE_CONFIRMED", "SWEEP", "TRADE_CANDIDATE", "BLOCKED", "PAPER_ORDER_OPENED", "PAPER_ORDER_CLOSED"):
                    self.telegram.broadcast(f"Notification: {event.kind}")

    def _add_ui_event(self, title, detail, tone="neutral"):
        import uuid
        from datetime import datetime, timezone
        self.ui_events.insert(0, {
            "id": str(uuid.uuid4()),
            "at": datetime.now(timezone.utc).isoformat(),
            "title": title,
            "detail": detail,
            "tone": tone
        })
        self.ui_events = self.ui_events[:50]  # keep last 50

    async def _update_private_state(self):
        from .okx_private_config import load_private_config
        from .okx_private_runtime import read_private_snapshots
        config = load_private_config(env_file=".env")
        if not config.ready:
            self.private_state["account_auth"] = "AUTH_MISSING"
            return
        
        try:
            res = await read_private_snapshots(config, timeout=5)
            self.private_state["account_auth"] = res.status
            self._add_ui_event("OKX Private Auth", f"Status: {res.status}")
            
            if res.status == "CONNECTED":
                # Check Auto Earn
                earn_val = "UNKNOWN"
                if res.earn and res.earn.auto_earn is not None:
                    earn_val = "ON" if res.earn.auto_earn == "active" else "OFF"
                elif res.account and res.account.flags:
                    earn_val = "ON" if res.account.flags[0].auto_earn == "active" else "OFF"
                self.private_state["autoEarn"] = earn_val
                self._add_ui_event("Auto Earn", earn_val)
                
                if res.account and res.account.equity is not None:
                    self.private_state["balance"] = str(res.account.equity)
        except Exception as e:
            logging.error(f"Failed to read private snapshot: {e}")
            self.private_state["account_auth"] = "ERROR"
            self._add_ui_event("OKX Private Auth", "ERROR", tone="warning")

    async def _private_loop(self):
        try:
            while True:
                await self._update_private_state()
                await asyncio.sleep(60) # check every minute
        except asyncio.CancelledError:
            pass

    def _update_state(self):
        if not self.brain: return
        snap = self.brain.snapshot()
        self.latest_state = {
            "decision": {"action": snap.get("pending_plan", {}).get("direction", "NO_TRADE") if snap.get("pending_plan") else "NO_TRADE"},
            "market_state": {"prices": [snap.get("range", {}).eq if snap.get("range") else 0]},
            "execution": {"trades": snap.get("trades", [])}
        }

    async def _run_loop(self):
        try:
            as_of = datetime.now(timezone.utc)
            candles = await self._fetch_candles(as_of)
            if candles:
                self._add_ui_event("OKX ATK", "15m candles updated")
            self.brain.bootstrap(candles)
            self._update_state()
            self._check_notifications()
            
            while self.is_running:
                await asyncio.sleep(self.config.poll_interval_seconds)
                as_of = datetime.now(timezone.utc)
                try:
                    candles = await self._fetch_candles(as_of)
                    # Feed only new candles
                    last_processed = self.brain.as_of
                    for c in candles:
                        if last_processed is None or c.close_time > last_processed:
                            self.brain.process(c)
                    self._update_state()
                    self._check_notifications()
                except Exception as e:
                    logging.error(f"Error in bot loop: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Bot failed to start: {e}")
            self.is_running = False
