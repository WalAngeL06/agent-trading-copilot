from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from agent_trading.api import create_app
from agent_trading.demo_config import DemoConfig
from agent_trading.bot_service import BotService
from agent_trading.config import Config
from agent_trading.telegram_bot import TelegramBot


class AccountPreferenceTests(unittest.TestCase):
    def test_preference_survives_restart_without_becoming_exchange_verification(self):
        with TemporaryDirectory() as root:
            def app():
                bot = BotService(Config())
                bot.private_state.update(account_auth='CONNECTED', auto_earn_status='OFF')
                return create_app(bot_service=bot, demo_config=DemoConfig(),
                                  preferences_path=Path(root) / 'preferences.json')
            client = TestClient(app())
            path = '/api/v1/account/preferences'
            self.assertEqual(client.get(path).json(), {'lira_auto_earn': None})
            for preference in ('ENABLED', 'DISABLED', None):
                self.assertEqual(client.put(path, json={'lira_auto_earn': preference}).status_code, 200)
                restarted = TestClient(app())
                self.assertEqual(restarted.get(path).json()['lira_auto_earn'], preference)
                status = restarted.get('/api/v1/bot/status').json()
                self.assertEqual(status['account_auth'], 'CONNECTED')
                self.assertEqual(status['lira_auto_earn'], {
                    'status': 'UNKNOWN', 'source': None, 'verified': False,
                    'api_verification': 'NOT_EXPOSED', 'user_preference': preference})
            for invalid in ({'lira_auto_earn': 'OFF'}, {'lira_auto_earn': True},
                            {'lira_auto_earn': 'ENABLED', 'verified': True}):
                self.assertEqual(client.put(path, json=invalid).status_code, 422)
            with patch('agent_trading.account_preferences.os.replace', side_effect=OSError('secret-path')):
                response = client.put(path, json={'lira_auto_earn': 'ENABLED'})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('secret-path', response.text)
            self.assertIsNone(client.get(path).json()['lira_auto_earn'])

    def test_first_save_creates_missing_config_directory(self):
        with TemporaryDirectory() as root:
            preferences = Path(root) / 'config' / 'preferences.json'
            client = TestClient(create_app(bot_service=BotService(Config()), demo_config=DemoConfig(),
                                           preferences_path=preferences))
            response = client.put('/api/v1/account/preferences', json={'lira_auto_earn': 'ENABLED'})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(preferences.is_file())

    def test_telegram_status_reports_lira_preference_without_claiming_verification(self):
        def lira_lines(text):
            lines = text.splitlines()
            index = next((i for i, line in enumerate(lines) if line.startswith('Lira Auto Earn:')), None)
            return [] if index is None else lines[index:index + 2]

        with TemporaryDirectory() as root:
            bot = BotService(Config(), telegram_token='test')
            client = TestClient(create_app(bot_service=bot, demo_config=DemoConfig(),
                                           preferences_path=Path(root) / 'preferences.json'))
            status_request = {'message': {'chat': {'id': 1}, 'text': '/status'}}
            with patch.object(bot.telegram, 'send_message') as send:
                bot.telegram.handle_update(status_request)
                self.assertEqual(lira_lines(send.call_args.args[1]),
                                 ['Lira Auto Earn: NOT SPECIFIED', 'API verification: NOT EXPOSED'])
                client.put('/api/v1/account/preferences', json={'lira_auto_earn': 'ENABLED'})
                bot.telegram.handle_update(status_request)
            status = send.call_args.args[1]
            self.assertEqual(lira_lines(status), ['Lira Auto Earn: ENABLED', 'API verification: NOT EXPOSED'])
            self.assertNotIn('Auto Earn: UNKNOWN', status)

    def test_local_telegram_start_has_no_invalid_webapp_button(self):
        bot = TelegramBot('test', 'http://localhost:5173', lambda: 'Status ready')
        with patch.object(bot, 'send_message') as send:
            bot.handle_update({'message': {'chat': {'id': 1}, 'text': '/start'}})
            self.assertIsNone(send.call_args.args[2])
            bot.handle_update({'message': {'chat': {'id': 1}, 'text': '/status'}})
            self.assertEqual(send.call_args.args[1], 'Status ready')
