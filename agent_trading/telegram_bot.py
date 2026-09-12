import asyncio
import json
import logging
import os
from urllib.request import Request, urlopen
from urllib.error import URLError

class TelegramBot:
    def __init__(self, token: str, webapp_url: str, status_callback=None):
        self.token = token
        self.webapp_url = webapp_url
        self.status_callback = status_callback
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.running = False
        self.task = None
        self.chat_ids = set()

    def send_message(self, chat_id, text, reply_markup=None):
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        req = Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=5) as resp:
                pass
        except URLError as e:
            logging.error(f"Telegram send error: {e}")

    def broadcast(self, text):
        for chat_id in self.chat_ids:
            self.send_message(chat_id, text)

    async def _poll(self):
        while self.running:
            url = f"{self.base_url}/getUpdates?offset={self.offset}&timeout=10"
            try:
                # Use to_thread since urlopen is blocking
                def fetch():
                    try:
                        with urlopen(url, timeout=12) as resp:
                            return json.loads(resp.read())
                    except URLError:
                        return None
                data = await asyncio.to_thread(fetch)
                if data and data.get("ok"):
                    for update in data["result"]:
                        self.offset = update["update_id"] + 1
                        message = update.get("message")
                        if message and "text" in message:
                            chat_id = message["chat"]["id"]
                            self.chat_ids.add(chat_id)
                            text = message["text"]
                            if text.startswith("/start"):
                                markup = {
                                    "inline_keyboard": [
                                        [{"text": "Open Dashboard", "web_app": {"url": self.webapp_url}}]
                                    ]
                                }
                                self.send_message(chat_id, "Welcome to Agent Trading Copilot!", reply_markup=markup)
                            elif text.startswith("/status"):
                                if self.status_callback:
                                    status_text = self.status_callback()
                                    self.send_message(chat_id, status_text)
                                else:
                                    self.send_message(chat_id, "Bot is running. Use the WebApp for detailed status.")
            except Exception as e:
                logging.error(f"Telegram poll error: {e}")
            await asyncio.sleep(1)

    def start(self):
        if not self.token or self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._poll())

    def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
