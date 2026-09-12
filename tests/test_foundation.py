import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trading.config import Config
from agent_trading.components import AcceptanceEngine, RiskEngine, DisabledExecution
from agent_trading.data import read_candles
from agent_trading.engine import ReplayEngine
from agent_trading.journal import JsonlJournal
from agent_trading.models import Candle, PatternResult, PatternStatus


def candle(minute=1, symbol="TEST-USDT", **changes):
    row = dict(symbol=symbol, timeframe="1m",
               close_time=f"2026-01-01T00:{minute:02d}:00Z",
               open="100", high="102", low="99", close="101",
               volume="10", closed=True)
    row.update(changes)
    return Candle.from_dict(row)


class FoundationTests(unittest.TestCase):
    def test_unconfigured_policies_cannot_approve_a_candidate(self):
        acceptance = AcceptanceEngine().evaluate({"action": "BUY"})
        self.assertEqual(acceptance["status"], "REJECTED")
        risk = RiskEngine().evaluate({"status": "APPROVED"})
        self.assertEqual(risk["status"], "REJECTED")
        with self.assertRaises(RuntimeError):
            DisabledExecution().evaluate({"status": "APPROVED"})

    def test_score_requires_an_explained_method(self):
        with self.assertRaises(ValueError):
            PatternResult("range", PatternStatus.DETECTED, candle().close_time,
                          score=Decimal("0.83"))

    def test_future_dated_detector_result_is_rejected(self):
        class FutureDetector:
            name = "future"

            def evaluate(self, history):
                return PatternResult(self.name, PatternStatus.DETECTED,
                                     history[-1].close_time + timedelta(minutes=1))

        with self.assertRaises(ValueError):
            ReplayEngine(Config(), detectors=[FutureDetector()]).process(candle())

    def test_timezone_is_normalized_without_rounding_prices(self):
        result = ReplayEngine(Config()).process(candle(
            close_time="2026-01-01T03:01:00+03:00", close="101.1234567890123456789"))
        self.assertEqual(result["as_of"], "2026-01-01T00:01:00Z")
        self.assertEqual(result["candle"]["close"], "101.1234567890123456789")

    def test_cli_rejects_live_before_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            log = Path(folder) / "run.jsonl"
            config.write_text(json.dumps({"mode": "live"}))
            result = subprocess.run([sys.executable, "-m", "agent_trading",
                                     "--config", str(config), "--output", str(log)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(log.exists())

    def test_invalid_or_open_candles_are_rejected(self):
        for changes in [dict(closed=False), dict(closed="true"),
                        dict(high="99"), dict(low="103"), dict(volume="-1"),
                        dict(close="NaN"), dict(open="0"), dict(symbol=""),
                        dict(close_time="2026-01-01T00:01:00")]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                candle(**changes)

    def test_unconfigured_strategy_never_produces_an_order(self):
        result = ReplayEngine(Config()).process(candle())
        self.assertEqual(result["decision"]["action"], "NO_TRADE")
        self.assertEqual(result["decision"]["reason"], "STRATEGY_NOT_CONFIGURED")
        self.assertEqual(result["risk"]["status"], "NOT_EVALUATED")
        self.assertEqual(result["execution"]["status"], "NOT_REQUESTED")
        self.assertTrue(all(p["status"] == "NOT_IMPLEMENTED"
                            for p in result["patterns"]))

    def test_detector_only_sees_current_and_past_candles(self):
        seen = []

        class Recorder:
            name = "recorder"

            def evaluate(self, history):
                seen.append([c.close_time.minute for c in history])
                return PatternResult(self.name, PatternStatus.NOT_DETECTED,
                                     history[-1].close_time)

        engine = ReplayEngine(Config(history_limit=2), detectors=[Recorder()])
        for minute in [1, 2, 3]:
            engine.process(candle(minute))
        self.assertEqual(seen, [[1], [1, 2], [2, 3]])

    def test_duplicate_and_out_of_order_data_are_rejected(self):
        for second in [candle(2), candle(1), candle(1, "OTHER-USDT")]:
            engine = ReplayEngine(Config())
            engine.process(candle(2))
            with self.assertRaises(ValueError):
                engine.process(second)

    def test_histories_do_not_mix_symbols(self):
        engine = ReplayEngine(Config())
        engine.process(candle(1))
        result = engine.process(candle(1, "OTHER-USDT"))
        self.assertEqual(result["market_state"]["history_size"], 1)

    def test_replay_is_deterministic(self):
        a, b = ReplayEngine(Config()), ReplayEngine(Config())
        self.assertEqual([a.process(candle(i)) for i in [1, 2, 3]],
                         [b.process(candle(i)) for i in [1, 2, 3]])

    def test_detector_failure_is_logged_and_stops_the_run(self):
        class Broken:
            name = "broken"

            def evaluate(self, history):
                raise RuntimeError("detector failed")

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.jsonl"
            with JsonlJournal(path) as journal:
                engine = ReplayEngine(Config(), detectors=[Broken()], journal=journal)
                with self.assertRaises(RuntimeError):
                    engine.process(candle())
                with self.assertRaises(RuntimeError):
                    engine.process(candle(2))
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(rows[0]["event"], "ERROR")
            self.assertEqual(rows[0]["error_type"], "RuntimeError")

    def test_journal_refuses_to_overwrite_existing_run(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "run.jsonl"
            path.write_text("original")
            with self.assertRaises(FileExistsError):
                JsonlJournal(path)
            self.assertEqual(path.read_text(), "original")

    def test_configuration_rejects_unsupported_modes_and_invalid_limits(self):
        for value in [0, -1, True, 1.5]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Config(history_limit=value)
        for mode in ["live", "shadow", "backtest"]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                Config(mode=mode)

    def test_sample_replay_cli_writes_decisions(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "events.jsonl"
            result = subprocess.run(
                [sys.executable, "-m", "agent_trading", "--config",
                 "config.example.json", "--output", str(log)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(r["decision"]["action"] == "NO_TRADE" for r in rows))

    def test_input_reader_reports_bad_line(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.jsonl"
            path.write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "line 1"):
                list(read_candles(path))


if __name__ == "__main__":
    unittest.main()
