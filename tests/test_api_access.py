from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from agent_trading.access import telegram_user_id
from agent_trading.analysis_config import AnalysisConfig
from agent_trading.api import create_app
from agent_trading.bot_service import BotService
from agent_trading.config import Config
from agent_trading.demo_config import DemoConfig
from agent_trading.telegram_bot import TelegramBot


BOT_TOKEN = "123456:TEST-bot-token"
ACCESS_KEY = "k" * 32
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
OWNER = 111222333
STRANGER = 999888777


def _init_data(user_id=OWNER, *, auth_date=NOW, token=BOT_TOKEN, extra=None):
    """Mini App initData signed as Telegram documents it (HMAC-SHA-256 over sorted fields)."""
    fields = {"auth_date": str(int(auth_date.timestamp())), "query_id": "AAH-test",
              "user": json.dumps({"id": user_id, "first_name": "Owner"}, separators=(",", ":"))}
    fields.update(extra or {})
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class TelegramInitDataTests(unittest.TestCase):
    def test_signed_init_data_identifies_the_telegram_user(self):
        self.assertEqual(telegram_user_id(_init_data(), BOT_TOKEN, now=NOW), OWNER)

    def test_signature_field_is_covered_by_the_bot_token_hash(self):
        signed = _init_data(extra={"signature": "ed25519-sig"})
        self.assertEqual(telegram_user_id(signed, BOT_TOKEN, now=NOW), OWNER)
        self.assertIsNone(telegram_user_id(signed.replace("ed25519-sig", "forged-sig"), BOT_TOKEN, now=NOW))

    def test_tampered_foreign_or_malformed_init_data_is_rejected(self):
        tampered = _init_data().replace(str(OWNER), str(STRANGER))
        for data in (tampered, _init_data(token="654321:OTHER-bot"), "auth_date=1&user=%7B%7D",
                     "", "%%%", _init_data() + "&auth_date=1"):
            with self.subTest(data=data[:40]):
                self.assertIsNone(telegram_user_id(data, BOT_TOKEN, now=NOW))
        self.assertIsNone(telegram_user_id(_init_data(), "", now=NOW))

    def test_init_data_older_than_a_day_or_from_the_future_is_rejected(self):
        self.assertEqual(telegram_user_id(_init_data(auth_date=NOW - timedelta(hours=23)),
                                          BOT_TOKEN, now=NOW), OWNER)
        self.assertIsNone(telegram_user_id(_init_data(auth_date=NOW - timedelta(hours=25)),
                                           BOT_TOKEN, now=NOW))
        self.assertIsNone(telegram_user_id(_init_data(auth_date=NOW + timedelta(minutes=10)),
                                           BOT_TOKEN, now=NOW))


def _app(root, demo, bot=None):
    return create_app(config=AnalysisConfig(db_path=root / "history.sqlite3", audit_dir=root / "audit"),
                      bot_service=bot or BotService(Config()), demo_config=demo,
                      strategy_path=root / "strategy.json", preferences_path=root / "preferences.json")


class ApiAccessTests(unittest.TestCase):
    def test_access_key_is_required_for_api_routes_but_not_liveness(self):
        with TemporaryDirectory() as directory:
            bot = BotService(Config())
            client = TestClient(_app(Path(directory), DemoConfig(api_access_token=ACCESS_KEY), bot))

            denied = client.get("/api/v1/bot/status")
            self.assertEqual(denied.status_code, 401)
            self.assertEqual(denied.json()["error"]["code"], "UNAUTHORIZED")
            wrong = {"Authorization": "Bearer " + "x" * 32}
            self.assertEqual(client.get("/api/v1/bot/status", headers=wrong).status_code, 401)
            self.assertEqual(client.post("/api/v1/bot/start").status_code, 401)
            self.assertFalse(bot.is_running)
            self.assertEqual(client.put("/api/v1/strategy/config", json={}).status_code, 401)

            owner = {"Authorization": "Bearer " + ACCESS_KEY}
            self.assertEqual(client.get("/api/v1/bot/status", headers=owner).status_code, 200)
            self.assertEqual(client.get("/health/live").status_code, 200)

    def test_only_allowlisted_telegram_users_pass_with_mini_app_init_data(self):
        with TemporaryDirectory() as directory:
            demo = DemoConfig(telegram_bot_token=BOT_TOKEN, telegram_allowed_user_ids=(OWNER,))
            client = TestClient(_app(Path(directory), demo))
            now = datetime.now(timezone.utc)

            owner = {"X-Telegram-Init-Data": _init_data(OWNER, auth_date=now)}
            stranger = {"X-Telegram-Init-Data": _init_data(STRANGER, auth_date=now)}
            self.assertEqual(client.get("/api/v1/bot/status", headers=owner).status_code, 200)
            self.assertEqual(client.get("/api/v1/bot/status", headers=stranger).status_code, 401)
            self.assertEqual(client.get("/api/v1/bot/status").status_code, 401)

    def test_browser_can_preflight_and_read_rejections_across_origins(self):
        with TemporaryDirectory() as directory:
            demo = DemoConfig(api_access_token=ACCESS_KEY,
                              allowed_origins=("http://localhost:5173", "https://front.example"))
            client = TestClient(_app(Path(directory), demo))
            origin = {"Origin": "https://front.example"}

            preflight = client.options("/api/v1/bot/start", headers={
                **origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,x-telegram-init-data"})
            self.assertEqual(preflight.status_code, 200)
            denied = client.post("/api/v1/bot/start", headers=origin)
            self.assertEqual(denied.status_code, 401)
            self.assertEqual(denied.headers["access-control-allow-origin"], "https://front.example")

    def test_public_https_deployment_without_access_control_refuses_to_start(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                _app(root, DemoConfig(webapp_url="https://bot.example.com"))
            with self.assertRaises(ValueError):
                _app(root, DemoConfig(allowed_origins=("http://localhost:5173", "https://front.example")))
            self.assertIsNotNone(_app(root, DemoConfig(webapp_url="https://bot.example.com",
                                                       api_access_token=ACCESS_KEY)))
            local = TestClient(_app(root, DemoConfig()))
            self.assertEqual(local.get("/api/v1/bot/status").status_code, 200)


class AccessEnvironmentTests(unittest.TestCase):
    def test_access_settings_are_parsed_from_the_environment_file(self):
        with TemporaryDirectory() as directory:
            env = Path(directory) / ".env"
            env.write_text(f"API_ACCESS_TOKEN={ACCESS_KEY}\nTELEGRAM_ALLOWED_USER_IDS= {OWNER}, 42\n",
                           encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                demo = DemoConfig.from_env(env)
            self.assertEqual(demo.api_access_token, ACCESS_KEY)
            self.assertEqual(demo.telegram_allowed_user_ids, (OWNER, 42))
            self.assertNotIn(ACCESS_KEY, repr(demo))

    def test_weak_access_key_or_malformed_user_ids_are_rejected(self):
        for env in ({"API_ACCESS_TOKEN": "short"}, {"TELEGRAM_ALLOWED_USER_IDS": "owner"},
                    {"TELEGRAM_ALLOWED_USER_IDS": "12,,34"}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                DemoConfig.from_env(env_file="missing.env", env=env)


class TelegramAllowlistTests(unittest.TestCase):
    def _message(self, user_id, text):
        return {"message": {"chat": {"id": user_id}, "from": {"id": user_id}, "text": text}}

    def test_private_bot_answers_and_notifies_only_allowlisted_users(self):
        bot = TelegramBot("token", "https://front.example", lambda: "Status ready",
                          allowed_user_ids=(OWNER,))
        with patch.object(bot, "send_message") as send:
            bot.handle_update(self._message(STRANGER, "/status"))
            self.assertNotIn("Status ready", send.call_args.args[1])
            self.assertIn(str(STRANGER), send.call_args.args[1])
            bot.handle_update(self._message(OWNER, "/status"))
            self.assertEqual(send.call_args.args[1], "Status ready")
        self.assertEqual(bot.chat_ids, {OWNER})

    def test_unlocked_bot_tells_the_owner_their_user_id_on_start(self):
        bot = TelegramBot("token", "https://front.example")
        with patch.object(bot, "send_message") as send:
            bot.handle_update(self._message(OWNER, "/start"))
        self.assertIn(str(OWNER), send.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
