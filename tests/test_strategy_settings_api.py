import asyncio
from datetime import timedelta
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from env_isolation import BLANK_LOCAL_SETTINGS, isolated_environment

from agent_trading.api import create_app
from agent_trading.analysis_config import AnalysisConfig
from agent_trading.bot_service import BotService
from agent_trading.config import Config
from test_demo_integration import _PublicAdapter, _PublicFactory



_environment = isolated_environment()


def setUpModule():
    _environment.start()


def tearDownModule():
    _environment.stop()

class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = AnalysisConfig(db_path=self.root / 'history.db', audit_dir=self.root / 'audit')

    def app(self, **overrides):
        return create_app(config=self.config, strategy_path=self.root / 'strategy.json',
                          preferences_path=self.root / 'preferences.json',
                          session_path=self.root / 'paper_session.pickle', **overrides)

    def test_save_survives_new_app_and_reaches_engine_profile(self):
        app = self.app()
        with TestClient(app) as client:
            response = client.get('/api/v1/strategy/config')
            self.assertEqual(response.status_code, 200)
            config = response.json()
            config['risk']['riskPct'] = '0.75'
            config['timeframes'] = {'bias': '1H', 'range': '15m', 'entry': '5m'}
            config['exits']['partialTakeProfits'] = [
                {'id': 'tp-1', 'rMultiple': '1', 'closePct': '20'},
                {'id': 'tp-2', 'rMultiple': '2', 'closePct': '30'}]
            self.assertEqual(client.put('/api/v1/strategy/config', json=config).status_code, 200)
            persisted = client.get('/api/v1/strategy/config').json()
            self.assertEqual(app.state.bot_service.strategy_profile.risk_fraction, Decimal('.0075'))
        restarted = self.app()
        with TestClient(restarted) as client:
            self.assertEqual(client.get('/api/v1/strategy/config').json(), persisted)
            self.assertEqual(restarted.state.bot_service.strategy_profile.timeframes.entry, '5m')

    def test_domain_validation_and_unsupported_fields_leave_config_unchanged(self):
        with TestClient(self.app()) as client:
            original = client.get('/api/v1/strategy/config').json()
            candidates = []
            for field, value in [('riskPct', '0'), ('riskPct', 'NaN'), ('minimumRR', '-1')]:
                candidate = deepcopy(original)
                candidate['risk'][field] = value
                candidates.append(candidate)
            for levels in [
                [{'id': 'a', 'rMultiple': '1', 'closePct': '20'},
                 {'id': 'b', 'rMultiple': '1.0', 'closePct': '30'}],
                [{'id': 'a', 'rMultiple': '1', 'closePct': '95'}],
                [{'id': 'a', 'rMultiple': '1', 'closePct': '-2'}],
            ]:
                candidate = deepcopy(original)
                candidate['exits']['partialTakeProfits'] = levels
                candidates.append(candidate)
            for field, value in [('timeframes', {'bias': '1H', 'range': '4H', 'entry': '5m'}),
                                 ('timeframes', {'bias': '1D', 'range': '1H', 'entry': '5m'}),
                                 ('executionMode', 'LIVE'), ('api_secret', 'must-not-echo')]:
                candidates.append({**original, field: value})
            candidate = deepcopy(original)
            candidate['management']['breakEvenEnabled'] = False
            candidates.append(candidate)
            candidate = deepcopy(original)
            candidate['risk']['maxDailyLoss'] = '5'
            candidates.append(candidate)
            for candidate in candidates:
                response = client.put('/api/v1/strategy/config', json=candidate)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertNotIn('must-not-echo', response.text)
                self.assertEqual(client.get('/api/v1/strategy/config').json(), original)

    def test_running_lock_and_failed_atomic_write(self):
        app = self.app()
        with TestClient(app) as client:
            original = client.get('/api/v1/strategy/config').json()
            candidate = deepcopy(original)
            candidate['entry']['level'] = 'FVG_LOW'
            app.state.bot_service.is_running = True
            response = client.put('/api/v1/strategy/config', json=candidate)
            self.assertEqual(response.status_code, 409)
            self.assertIn('Stop the agent', response.text)
            app.state.bot_service.is_running = False
            with patch('agent_trading.strategy_settings.os.replace', side_effect=OSError('private path')):
                response = client.put('/api/v1/strategy/config', json=candidate)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private path', response.text)
            self.assertEqual(client.get('/api/v1/strategy/config').json(), original)

    def test_dashboard_redirect_has_no_embedded_ui(self):
        with TestClient(self.app()) as client:
            response = client.get('/dashboard', follow_redirects=False)
            self.assertEqual(response.status_code, 307)
            self.assertIn(':5173', response.headers['location'])
            self.assertNotIn('<html', response.text)

    def test_http_start_stop_drains_loop_and_locks_saves(self):
        class PendingAdapter:
            async def candles(self, *args, **kwargs):
                await asyncio.Event().wait()
        app = self.app(mcp_factory=_PublicFactory(PendingAdapter()))
        with TestClient(app) as client:
            config = client.get('/api/v1/strategy/config').json()
            for _ in range(3):
                self.assertEqual(client.post('/api/v1/bot/start').status_code, 200)
                self.assertEqual(client.get('/api/v1/bot/status').json()['bot_status'], 'running')
                self.assertEqual(client.put('/api/v1/strategy/config', json=config).status_code, 409)
                self.assertEqual(client.post('/api/v1/bot/stop').status_code, 200)
                self.assertEqual(client.get('/api/v1/bot/status').json()['bot_status'], 'stopped')
                self.assertIsNone(app.state.bot_service.task)
                self.assertEqual(client.put('/api/v1/strategy/config', json=config).status_code, 200)


class StrategyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_trade_summary_uses_exact_paper_ledger_values(self):
        from agent_trading.strategy_v1 import StrategyV1
        from strategy_v1_fixtures import acceptance_candles, acceptance_profile
        candles = acceptance_candles()
        bot = BotService(Config())
        bot.brain = StrategyV1('BTC-USDT', acceptance_profile())
        for candle in sorted(candles, key=lambda c: (c.close_time, bot.brain.roles.rank(c.timeframe))):
            bot.brain.process(candle)
        bot._update_state([c for c in candles if c.timeframe == '15m'])
        trades = bot.latest_state['execution']['trades']
        self.assertTrue(trades)
        self.assertEqual(trades[-1]['range_high'], str(bot.brain.broker.trades[-1].tp))
        self.assertEqual(trades[-1]['pnl'], str(bot.brain.broker.trades[-1].ledger.total_realized_pnl))
        self.assertIsInstance(trades[-1]['remaining_quantity'], str)
        bot._check_notifications()
        self.assertIn('PARTIAL_TP_FILLED', [event['title'] for event in bot.ui_events])

    async def test_delayed_higher_timeframe_defers_equal_close_entry_until_ready(self):
        from datetime import datetime, timezone
        from agent_trading.models import Candle
        from agent_trading.strategy_v1 import StrategyV1
        noon = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)
        def candle(tf, at):
            return Candle('BTC-USDT', tf, at, Decimal('100'), Decimal('101'),
                          Decimal('99'), Decimal('100'), Decimal('10'))
        histories = {
            '4H': (candle('4H', noon - timedelta(hours=4)),),
            '1H': (candle('1H', noon - timedelta(hours=1)),),
            '15m': (candle('15m', noon - timedelta(minutes=15)),),
        }
        bot = BotService(Config())
        bot.brain = StrategyV1('BTC-USDT')
        async def fetch(*args):
            return histories, noon
        bot._fetch_candles = fetch
        await bot._accept_market_read(None, bootstrap=True)
        histories['1H'] += (candle('1H', noon),)
        histories['15m'] += (candle('15m', noon),)
        await bot._accept_market_read(None, bootstrap=False)
        self.assertEqual(bot.brain.as_of, noon - timedelta(minutes=15))
        self.assertEqual(bot.market_status, 'WAITING')
        histories['4H'] += (candle('4H', noon),)
        await bot._accept_market_read(None, bootstrap=False)
        self.assertEqual(bot.brain.as_of, noon)
        self.assertEqual(bot.market_status, 'CONNECTED')
        self.assertEqual(bot.brain._stream_as_of['4H'], noon)

    async def test_configured_timeframes_are_consumed_by_real_strategy(self):
        from agent_trading.strategy_v1 import StrategyV1, StrategyProfile, TimeframeRoles
        adapter = _PublicAdapter()
        bot = BotService(Config(bootstrap_limit=1, poll_interval_seconds=60),
                         mcp_factory=_PublicFactory(adapter))
        bot.strategy_profile = StrategyProfile(timeframes=TimeframeRoles('1H', '15m', '5m'),
                                              risk_fraction=Decimal('.0075'))
        bot.start()
        await asyncio.wait_for(adapter.called.wait(), 1)
        await asyncio.sleep(0)
        self.assertIsInstance(bot.brain, StrategyV1)
        self.assertEqual(set(bot.brain._stream_as_of), {'1H', '15m', '5m'})
        self.assertEqual(bot.brain.profile.risk_fraction, Decimal('.0075'))
        self.assertEqual(bot.market_status, 'CONNECTED')
        await bot.shutdown()
