import asyncio
from datetime import datetime, timezone
import json
import logging
from .engine import ReplayEngine
from .okx import OkxMarketAdapter
from .config import Config

from .telegram_bot import TelegramBot
import os

class BotService:
    def __init__(self, config: Config, adapter: OkxMarketAdapter):
        self.config = config
        self.adapter = adapter
        self.engine = None
        self.task = None
        self.is_running = False
        self.latest_state = {}
        
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        webapp_url = os.environ.get("WEBAPP_URL", "http://127.0.0.1:5173")
        self.telegram = TelegramBot(token, webapp_url) if token else None
        self.seen_event_ids = set()

    def start(self):
        if self.is_running:
            return False
        self.is_running = True
        self.engine = ReplayEngine(self.config)
        if self.telegram:
            self.telegram.start()
        self.task = asyncio.create_task(self._run_loop())
        return True

    def stop(self):
        if not self.is_running:
            return False
        self.is_running = False
        if self.task:
            self.task.cancel()
        if self.telegram:
            self.telegram.stop()
        return True
        
    async def _fetch(self, as_of: datetime):
        from .shadow import _fetch
        return await asyncio.to_thread(_fetch, self.engine, self.adapter, as_of)

    def _check_notifications(self):
        if not self.telegram: return
        report = self.engine.trading_brain.report()
        for event in report.events:
            if event.id not in self.seen_event_ids:
                self.seen_event_ids.add(event.id)
                if event.kind in ("RANGE_CONFIRMED", "SWEEP", "TRADE_CANDIDATE", "BLOCKED", "PAPER_ORDER_OPENED", "PAPER_ORDER_CLOSED"):
                    self.telegram.broadcast(f"Notification: {event.kind}")

    async def _run_loop(self):
        try:
            as_of = datetime.now(timezone.utc)
            candles = await self._fetch(as_of)
            self.engine.bootstrap(candles, as_of)
            self.latest_state = self.engine.evaluate_snapshot(self.config.symbol, as_of)
            self._check_notifications()
            
            while self.is_running:
                await asyncio.sleep(self.config.poll_interval_seconds)
                as_of = datetime.now(timezone.utc)
                try:
                    candles = await self._fetch(as_of)
                    self.engine.update_context(candles, as_of)
                    self.latest_state = self.engine.evaluate_snapshot(self.config.symbol, as_of)
                    self._check_notifications()
                except Exception as e:
                    logging.error(f"Error in bot loop: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Bot failed to start: {e}")
            self.is_running = False
            self.engine.fail(e, stage="market_data", symbol=self.config.symbol)
