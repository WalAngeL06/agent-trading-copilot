from contextlib import closing
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from agent_trading.analysis_report import new_report
from agent_trading.analysis_repository import SQLiteAnalysisRepository, RepositoryError
from agent_trading.models import utc_time


NOW = utc_time("2026-01-01T10:31:00Z")


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "product" / "history.sqlite3"
        self.repo = SQLiteAnalysisRepository(self.path, timeout=0.05)
        self.repo.initialize()

    def draft(self, symbol="BTC-USDT", now=NOW):
        return new_report(str(uuid4()), symbol, now, 60)

    def reserve(self, report=None, key=None, fingerprint="BTC/v0.1"):
        return self.repo.reserve(report or self.draft(), key, fingerprint)

    def test_reservation_persists_neutral_metadata_and_real_initial_event(self):
        result = self.reserve()
        stored = SQLiteAnalysisRepository(self.path).get(result.report["analysis_id"])
        self.assertEqual(stored["status"], "RUNNING")
        self.assertIsNone(stored["decision"]["action"])
        self.assertEqual(stored["timeline"][0]["type"], "REQUEST_RECEIVED")
        self.assertEqual(stored["timeline"][0]["sequence"], 1)

    def test_unique_key_replays_one_original_identity(self):
        first = self.reserve(key="digest")
        second = self.reserve(key="digest")
        self.assertFalse(second.created)
        self.assertEqual(second.report["analysis_id"], first.report["analysis_id"])
        self.assertEqual(self.repo.history(20, 0)["total"], 1)

    def test_key_payload_conflict_does_not_create_second_resource(self):
        self.reserve(key="digest")
        with self.assertRaises(RepositoryError) as error:
            self.reserve(self.draft("ETH-USDT"), "digest", "ETH/v0.1")
        self.assertEqual(error.exception.code, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.repo.history(20, 0)["total"], 1)

    def test_no_key_requests_have_distinct_identities(self):
        first, second = self.reserve(), self.reserve()
        self.assertNotEqual(first.report["analysis_id"], second.report["analysis_id"])
        self.assertEqual(self.repo.history(20, 0)["total"], 2)

    def test_terminal_report_and_event_are_immutable_across_reopen(self):
        draft = self.reserve().report
        self.repo.append_event(draft["analysis_id"], "MCP_CONNECTED", NOW, {"transport": "MCP"})
        draft.update(status="FAILED", completed_at="2026-01-01T10:31:01Z")
        draft["errors"] = [{"code": "MCP_TIMEOUT", "message": "Public market data timed out.",
                            "stage": "mcp", "timeframe": None}]
        final = self.repo.finalize(draft, "ANALYSIS_FAILED", NOW + timedelta(seconds=1),
                                  {"error_code": "MCP_TIMEOUT"})
        reopened = SQLiteAnalysisRepository(self.path).get(draft["analysis_id"])
        self.assertEqual(reopened, final)
        self.assertEqual([e["sequence"] for e in reopened["timeline"]], [1, 2, 3])
        self.assertEqual(reopened["timeline"][-1]["type"], "ANALYSIS_FAILED")
        with self.assertRaises(RepositoryError):
            self.repo.finalize(draft, "ANALYSIS_FAILED", NOW, {})
        self.assertEqual(self.repo.get(draft["analysis_id"]), final)

    def test_terminal_serialization_failure_rolls_back_terminal_event(self):
        draft = self.reserve().report
        broken = deepcopy(draft)
        broken.update(status="FAILED", completed_at="2026-01-01T10:31:01Z")
        broken["bad"] = float("nan")
        with self.assertRaises(RepositoryError):
            self.repo.finalize(broken, "ANALYSIS_FAILED", NOW, {})
        self.assertEqual(self.repo.get(draft["analysis_id"])["status"], "RUNNING")
        self.assertEqual(len(self.repo.get(draft["analysis_id"])["timeline"]), 1)

    def test_history_is_bounded_and_ordered_without_recomputation(self):
        first = self.reserve(self.draft(now=NOW))
        second = self.reserve(self.draft(now=NOW + timedelta(seconds=1)))
        page = self.repo.history(1, 0)
        self.assertEqual(page["total"], 2)
        self.assertEqual(page["items"][0]["analysis_id"], second.report["analysis_id"])
        self.assertEqual(self.repo.history(1, 1)["items"][0]["analysis_id"], first.report["analysis_id"])
        self.assertIsNone(self.repo.get(str(uuid4())))

    def test_startup_recovery_marks_abandoned_running_records_failed_once(self):
        draft = self.reserve().report
        self.repo.recover_interrupted(NOW + timedelta(seconds=2))
        final = self.repo.get(draft["analysis_id"])
        self.assertEqual(final["status"], "FAILED")
        self.assertIsNone(final["decision"]["action"])
        self.assertEqual(final["errors"][0]["code"], "PROCESS_INTERRUPTED")
        self.assertEqual(final["timeline"][-1]["type"], "ANALYSIS_FAILED")
        self.repo.recover_interrupted(NOW + timedelta(seconds=3))
        self.assertEqual(self.repo.get(draft["analysis_id"]), final)

    def test_delete_journal_schema_and_writable_health_probe(self):
        self.assertTrue(self.repo.health())
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_locked_database_fails_with_sanitized_bounded_category(self):
        with closing(sqlite3.connect(self.path)) as blocker:
            blocker.execute("BEGIN IMMEDIATE")
            with self.assertRaises(RepositoryError) as error:
                self.reserve()
            self.assertEqual(error.exception.code, "PERSISTENCE_UNAVAILABLE")
            self.assertNotIn(str(self.path), str(error.exception))
            blocker.rollback()

    def test_history_orders_fractional_utc_request_times_correctly(self):
        first = self.reserve(self.draft(now=NOW))
        second = self.reserve(self.draft(now=NOW + timedelta(microseconds=1)))
        self.assertEqual(self.repo.history(1, 0)["items"][0]["analysis_id"],
                         second.report["analysis_id"])

    def test_simultaneous_key_reservations_have_one_canonical_resource(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier = Barrier(2)
        def reserve():
            draft = self.draft()
            barrier.wait(timeout=2)
            return SQLiteAnalysisRepository(self.path, timeout=1).reserve(draft, "racing", "BTC/v0.1")
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(reserve), executor.submit(reserve)]
            results = [f.result(timeout=3) for f in futures]
        self.assertEqual(sum(r.created for r in results), 1)
        self.assertEqual(len({r.report["analysis_id"] for r in results}), 1)
        self.assertEqual(self.repo.history(20, 0)["total"], 1)
