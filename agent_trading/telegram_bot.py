import asyncio
import json
import logging
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


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
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        request = Request(
            f"{self.base_url}/sendMessage", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=5):
                return True
        except Exception:
            logging.warning("Telegram send failed")
            return False

    def broadcast(self, text):
        for chat_id in tuple(self.chat_ids):
            self.send_message(chat_id, text)

    def handle_update(self, update):
        message = update.get("message") if isinstance(update, dict) else None
        if not isinstance(message, dict) or not isinstance(message.get("text"), str):
            return
        chat = message.get("chat")
        if not isinstance(chat, dict) or "id" not in chat:
            return
        chat_id = chat["id"]
        self.chat_ids.add(chat_id)
        text = message["text"]
        if text.startswith("/start"):
            url = urlsplit(self.webapp_url)
            markup = {"inline_keyboard": [[{
                "text": "Open Dashboard", "web_app": {"url": self.webapp_url},
            }]]} if url.scheme == 'https' and url.hostname not in {'localhost', '127.0.0.1', '::1'} else None
            self.send_message(chat_id, "Welcome to Agent Trading Copilot!", markup)
        elif text.startswith("/status"):
            status = (self.status_callback() if self.status_callback else
                      "Bot status is unavailable. Use the WebApp for details.")
            self.send_message(chat_id, status)

    async def _poll(self):
        while self.running:
            url = f"{self.base_url}/getUpdates?offset={self.offset}&timeout=10"

            def fetch():
                try:
                    with urlopen(url, timeout=12) as response:
                        return json.loads(response.read())
                except Exception:
                    return None

            try:
                data = await asyncio.to_thread(fetch)
                if isinstance(data, dict) and data.get("ok") and isinstance(data.get("result"), list):
                    for update in data["result"]:
                        if isinstance(update, dict) and type(update.get("update_id")) is int:
                            self.offset = update["update_id"] + 1
                        self.handle_update(update)
            except Exception:
                logging.warning("Telegram polling failed")
            await asyncio.sleep(1)

    def start(self):
        if not self.token or self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._poll())

    async def stop(self):
        self.running = False
        task, self.task = self.task, None
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
