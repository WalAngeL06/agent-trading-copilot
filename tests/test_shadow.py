from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from agent_trading.components import ShadowExecution
from agent_trading.config import Config
from agent_trading.engine import ReplayEngine
from agent_trading.journal import JsonlJournal
from agent_trading.market import HistoryStore
from agent_trading.models import Candle, MarketSnapshot, to_jsonable, utc_time
from agent_trading.okx import OkxMarketAdapter, normalize_candles
from agent_trading.shadow import run_shadow


AS_OF = utc_time("2026-01-01T10:15:00Z")


def candle(tf="15m", close="2026-01-01T10:15:00Z", symbol="BTC-USDT"):
    return Candle(symbol, tf, utc_time(close), Decimal("100"), Decimal("102"),
                  Decimal("99"), Decimal("101"), Decimal("10"))


def raw(open_time, confirm="1", close="101"):
    epoch = utc_time("1970-01-01T00:00:00Z")
    ms = (utc_time(open_time) - epoch) // timedelta(milliseconds=1)
    return [str(ms), "100", "102", "99", close, "10", "10", "10", confirm]


def series():
    return [candle("4H", "2026-01-01T08:00:00Z"),
            candle("1H", "2026-01-01T10:00:00Z"), candle()]


class SnapshotTests(unittest.TestCase):
    def test_symbol_timeframe_and_causal_isolation(self):
        store = HistoryStore(10)
        for item in series() + [candle(symbol="ETH-USDT"),
                                candle(close="2026-01-01T10:30:00Z")]:
            store.append(item)
        snapshot = store.snapshot("BTC-USDT", AS_OF)
        self.assertEqual(set(snapshot.histories), {"4H", "1H", "15m"})
        self.assertEqual(len(snapshot.histories["15m"]), 1)
        for tf, history in snapshot.histories.items():
            self.assertTrue(all(c.symbol == "BTC-USDT" and c.timeframe == tf
                                and c.close_time <= AS_OF for c in history))

    def test_snapshot_copies_and_freezes_histories(self):
        source = {"15m": [candle()]}
        snapshot = MarketSnapshot("BTC-USDT", AS_OF, source)
        source["15m"].clear()
        self.assertEqual(snapshot.histories["15m"], (candle(),))
        with self.assertRaises(TypeError):
            snapshot.histories["1H"] = ()

    def test_invalid_snapshot_contracts_reject_future_and_mixed_data(self):
        for histories in [{"15m": (candle(symbol="ETH-USDT"),)},
                          {"1H": (candle(),)},
                          {"15m": (candle(close="2026-01-01T10:30:00Z"),)},
                          {"15m": (candle(), candle())}]:
            with self.subTest(histories=histories), self.assertRaises(ValueError):
                MarketSnapshot("BTC-USDT", AS_OF, histories)

    def test_snapshot_remains_stable_when_store_advances(self):
        store = HistoryStore(1)
        store.append(candle())
        snapshot = store.snapshot("BTC-USDT", AS_OF)
        store.append(candle(close="2026-01-01T10:30:00Z"))
        self.assertEqual(snapshot.histories["15m"], (candle(),))


class OkxTests(unittest.TestCase):
    def test_normalization_converts_open_to_close_without_rounding(self):
        row = raw("2026-01-01T10:00:00Z", close="101.1234567890123456789")
        row[5] = Decimal("0.1234567890123456789")
        result = normalize_candles([row], "BTC-USDT", "15m", AS_OF)[0]
        self.assertEqual(result.close_time, AS_OF)
        self.assertEqual(result.close, Decimal("101.1234567890123456789"))
        self.assertEqual(result.volume, Decimal("0.1234567890123456789"))

    def test_open_and_future_htf_candles_are_excluded(self):
        rows = [raw("2026-01-01T08:00:00Z", "0"),
                raw("2026-01-01T08:00:00Z", "1"),
                raw("2026-01-01T04:00:00Z")]
        result = normalize_candles(rows, "BTC-USDT", "4H", AS_OF)
        self.assertEqual([c.close_time for c in result],
                         [utc_time("2026-01-01T08:00:00Z")])

    def test_normalization_rejects_float_malformed_and_conflicting_data(self):
        float_row = raw("2026-01-01T10:00:00Z")
        float_row[4] = 101.1
        for rows in [[float_row], [["bad"]],
                     [raw("2026-01-01T10:00:00Z", "unknown")],
                     [raw("2026-01-01T10:00:00Z"),
                      raw("2026-01-01T10:00:00Z", close="100")]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                normalize_candles(rows, "BTC-USDT", "15m", AS_OF)

    def test_adapter_has_only_allowlisted_market_commands_and_precise_json(self):
        response = Mock(returncode=0, stdout='[101.1234567890123456789]', stderr="")
        with patch("agent_trading.okx.subprocess.run", return_value=response) as invoke:
            adapter = OkxMarketAdapter(node_path="node", cli_path="okx.js")
            data = adapter.ticker("BTC-USDT")
            adapter.candles("BTC-USDT", "15m", 10)
            adapter.orderbook("BTC-USDT")
            with self.assertRaises(ValueError):
                adapter._read("place", "BTC-USDT")
            with self.assertRaises(ValueError):
                adapter.ticker("--help")
        self.assertEqual(data[0], Decimal("101.1234567890123456789"))
        self.assertEqual(invoke.call_count, 3)
        for call in invoke.call_args_list:
            argv = call.args[0]
            self.assertEqual(argv[2], "market")
            self.assertIn(argv[3], {"ticker", "candles", "orderbook"})
            self.assertFalse(call.kwargs.get("shell", False))

    def test_adapter_suppresses_private_or_raw_errors(self):
        response = Mock(returncode=1, stdout="secret", stderr="secret")
        with patch("agent_trading.okx.subprocess.run", return_value=response):
            with self.assertRaises(RuntimeError) as error:
                OkxMarketAdapter(node_path="node", cli_path="okx.js").ticker("BTC-USDT")
        self.assertNotIn("secret", str(error.exception))


class ShadowTests(unittest.TestCase):
    def test_bootstrap_skips_every_decision_component_and_is_deterministic(self):
        outputs = []
        for items in [series(), list(reversed(series()))]:
            engine = ReplayEngine(Config(mode="shadow"))
            engine.router = Mock(side_effect=AssertionError("bootstrap routed"))
            engine.execution = Mock(side_effect=AssertionError("bootstrap executed"))
            snapshot = engine.bootstrap(items, AS_OF)
            engine.router.route.assert_not_called()
            engine.execution.evaluate.assert_not_called()
            outputs.append(to_jsonable(snapshot))
        self.assertEqual(outputs[0], outputs[1])

    def test_snapshot_detector_receives_all_series(self):
        seen = []
        from agent_trading.models import PatternResult, PatternStatus
        class Recorder:
            name = "recorder"
            def evaluate(self, snapshot):
                seen.append(snapshot)
                return PatternResult(self.name, PatternStatus.NOT_IMPLEMENTED,
                                     snapshot.as_of)
        engine = ReplayEngine(Config(mode="shadow"), detectors=[Recorder()])
        engine.bootstrap(series(), AS_OF)
        result = engine.evaluate_snapshot("BTC-USDT", AS_OF)
        self.assertEqual(set(seen[0].histories), {"4H", "1H", "15m"})
        self.assertEqual(result["execution"]["action"], "NO_ACTION")

    def test_shadow_records_intent_and_fails_closed_on_ambiguity(self):
        execution = ShadowExecution()
        for action, expected in [("BUY", "WOULD_BUY"), ("SELL", "WOULD_SELL")]:
            result = execution.evaluate({"action": action, "reason": "test"},
                                        {"status": "APPROVED"}, {"status": "APPROVED"})
            self.assertEqual(result["action"], expected)
            self.assertFalse(result["order_sent"])
        for decision, acceptance, risk in [
                ({"action": "BUY"}, {"status": "REJECTED"}, {"status": "APPROVED"}),
                ({"action": "BUY"}, {"status": "APPROVED"}, {}),
                ({"action": "UNKNOWN"}, {"status": "APPROVED"}, {"status": "APPROVED"})]:
            self.assertEqual(execution.evaluate(decision, acceptance, risk)["action"], "NO_ACTION")

    def test_real_order_capable_adapter_is_never_called_for_execution(self):
        adapter = Mock()
        adapter.candles.side_effect = lambda symbol, tf, limit: {
            "4H": [raw("2026-01-01T04:00:00Z")],
            "1H": [raw("2026-01-01T09:00:00Z")],
            "15m": [raw("2026-01-01T10:00:00Z")]}[tf]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shadow.jsonl"
            with JsonlJournal(path) as journal:
                engine = ReplayEngine(Config(mode="shadow"), journal=journal)
                result = run_shadow(engine, adapter, clock=lambda: AS_OF)
            records = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual([r["event"] for r in records], ["BOOTSTRAP_COMPLETE", "DECISION"])
        self.assertEqual(result["decision"]["action"], "NO_TRADE")
        self.assertEqual(result["execution"]["action"], "NO_ACTION")
        self.assertTrue(all(call[0] == "candles" for call in adapter.mock_calls))
        self.assertFalse(result["execution"]["order_sent"])

    def test_empty_required_series_fails_before_evaluation(self):
        engine = ReplayEngine(Config(mode="shadow"))
        engine.execution = Mock()
        with self.assertRaises(ValueError):
            engine.bootstrap(series()[:-1], AS_OF)
        engine.execution.evaluate.assert_not_called()

    def test_approved_buy_still_only_records_shadow_intent(self):
        engine = ReplayEngine(Config(mode="shadow"))
        engine.bootstrap(series(), AS_OF)
        engine.router = Mock()
        engine.router.route.return_value = {"action": "BUY", "reason": "test candidate"}
        engine.acceptance = Mock()
        engine.acceptance.evaluate.return_value = {"status": "APPROVED"}
        engine.risk = Mock()
        engine.risk.evaluate.return_value = {"status": "APPROVED"}
        with patch("agent_trading.okx.subprocess.run", side_effect=AssertionError("order attempted")):
            result = engine.evaluate_snapshot("BTC-USDT", AS_OF)
        self.assertEqual(result["execution"]["action"], "WOULD_BUY")
        self.assertFalse(result["execution"]["order_sent"])

    def test_delayed_closed_htf_update_does_not_use_global_replay_order(self):
        config = Config(mode="shadow", timeframes=["4H", "15m"])
        engine = ReplayEngine(config)
        boundary = utc_time("2026-01-01T12:15:00Z")
        engine.bootstrap([candle("4H", "2026-01-01T08:00:00Z"),
                          candle("15m", "2026-01-01T12:15:00Z")], boundary)
        engine.update_context([candle("4H", "2026-01-01T12:00:00Z")],
                              boundary + timedelta(minutes=1))
        snapshot = engine.snapshot("BTC-USDT", boundary + timedelta(minutes=1))
        self.assertEqual(snapshot.histories["4H"][-1].close_time,
                         utc_time("2026-01-01T12:00:00Z"))

    def test_polling_data_failure_stops_engine_and_logs_once(self):
        adapter = Mock()
        adapter.candles.side_effect = [
            [raw("2026-01-01T04:00:00Z")],
            [raw("2026-01-01T09:00:00Z")],
            [raw("2026-01-01T10:00:00Z")], RuntimeError("public data unavailable")]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shadow.jsonl"
            with JsonlJournal(path) as journal:
                engine = ReplayEngine(Config(mode="shadow", shadow_cycles=2), journal=journal)
                with self.assertRaises(RuntimeError):
                    run_shadow(engine, adapter, clock=lambda: AS_OF, sleep=lambda _: None)
                with self.assertRaises(RuntimeError):
                    engine.evaluate_snapshot("BTC-USDT", AS_OF)
            events = [json.loads(line)["event"] for line in path.read_text().splitlines()]
        self.assertEqual(events, ["BOOTSTRAP_COMPLETE", "DECISION", "ERROR"])

    def test_poll_overlap_is_idempotent_and_missing_bars_stop_run(self):
        engine = ReplayEngine(Config(mode="shadow"))
        engine.bootstrap(series(), AS_OF)
        self.assertFalse(engine.update_context(series(), AS_OF))
        with self.assertRaises(ValueError):
            engine.update_context([candle(close="2026-01-01T10:45:00Z")],
                                  AS_OF + timedelta(minutes=30))
        with self.assertRaises(RuntimeError):
            engine.evaluate_snapshot("BTC-USDT", AS_OF)

    def test_configuration_accepts_shadow_and_rejects_invalid_operational_parameters(self):
        self.assertEqual(Config(mode="shadow").timeframes, ("4H", "1H", "15m"))
        for changes in [dict(timeframes=[]), dict(timeframes=["4H", "4H"]),
                        dict(timeframes=["1M"]), dict(symbol="--help"),
                        dict(shadow_cycles=-1), dict(bootstrap_limit=0),
                        dict(poll_interval_seconds=0)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Config(mode="shadow", **changes)
