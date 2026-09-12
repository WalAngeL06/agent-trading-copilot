"""Canonical immutable product history, with short stdlib SQLite transactions."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import sqlite3

from .analysis_report import EVENT_VERSION, deterministic_summary
from .models import to_jsonable, utc_time


class RepositoryError(RuntimeError):
    def __init__(self, code="PERSISTENCE_UNAVAILABLE", analysis_id=None):
        super().__init__("Product history operation failed.")
        self.code = code
        self.analysis_id = analysis_id


@dataclass(frozen=True)
class Reservation:
    report: dict
    created: bool


def _dump(value):
    return json.dumps(to_jsonable(value), ensure_ascii=False, sort_keys=True, allow_nan=False)


class SQLiteAnalysisRepository:
    def __init__(self, path, timeout=1):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 5:
            raise ValueError("SQLite timeout must be positive and at most five seconds")
        self.path = Path(path)
        self.timeout = timeout

    @contextmanager
    def _connection(self):
        connection = None
        try:
            connection = sqlite3.connect(self.path, timeout=self.timeout)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            with connection:
                yield connection
        except RepositoryError:
            raise
        except (sqlite3.Error, OSError, ValueError, TypeError, KeyError):
            raise RepositoryError() from None
        finally:
            if connection is not None:
                connection.close()

    def initialize(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise RepositoryError() from None
        with self._connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RepositoryError("PERSISTENCE_SCHEMA_MISMATCH")
            mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
            if mode != "delete":
                raise RepositoryError()
            connection.execute("""CREATE TABLE IF NOT EXISTS analyses (
                analysis_id TEXT PRIMARY KEY,
                key_digest TEXT UNIQUE,
                fingerprint TEXT NOT NULL,
                symbol TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETED','FAILED')),
                requested_at TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                report_json TEXT NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS analysis_events (
                analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                sequence INTEGER NOT NULL,
                type TEXT NOT NULL,
                at TEXT NOT NULL,
                data_json TEXT NOT NULL,
                PRIMARY KEY(analysis_id, sequence))""")
            connection.execute("CREATE INDEX IF NOT EXISTS analyses_recent ON analyses(requested_at DESC, analysis_id DESC)")
            connection.execute("PRAGMA user_version=1")
        self.health()

    @staticmethod
    def _events(connection, analysis_id):
        rows = connection.execute(
            "SELECT sequence,type,at,data_json FROM analysis_events WHERE analysis_id=? ORDER BY sequence",
            (analysis_id,)).fetchall()
        return [{"schema_version": EVENT_VERSION, "analysis_id": analysis_id,
                 "sequence": row["sequence"], "type": row["type"], "at": row["at"],
                 "data": json.loads(row["data_json"])} for row in rows]

    def _read(self, connection, row):
        report = json.loads(row["report_json"])
        if row["status"] == "RUNNING":
            report["timeline"] = self._events(connection, row["analysis_id"])
        return report

    def _match(self, connection, key_digest, fingerprint):
        if key_digest is None:
            return None
        row = connection.execute("SELECT * FROM analyses WHERE key_digest=?", (key_digest,)).fetchone()
        if row is None:
            return None
        if row["fingerprint"] != fingerprint:
            raise RepositoryError("IDEMPOTENCY_CONFLICT", row["analysis_id"])
        return Reservation(self._read(connection, row), False)

    def find_idempotent(self, key_digest, fingerprint):
        with self._connection() as connection:
            connection.execute("BEGIN")
            return self._match(connection, key_digest, fingerprint)

    @staticmethod
    def _insert_event(connection, analysis_id, event_type, at, data):
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM analysis_events WHERE analysis_id=?",
            (analysis_id,)).fetchone()[0]
        stamp = to_jsonable(at)
        connection.execute("INSERT INTO analysis_events VALUES (?,?,?,?,?)",
                           (analysis_id, sequence, event_type, stamp, _dump(data)))
        return {"schema_version": EVENT_VERSION, "analysis_id": analysis_id,
                "sequence": sequence, "type": event_type, "at": stamp, "data": to_jsonable(data)}

    def reserve(self, report, key_digest, fingerprint):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = self._match(connection, key_digest, fingerprint)
            if existing:
                return existing
            if report["status"] != "RUNNING":
                raise RepositoryError("INVALID_REPORT_STATE")
            connection.execute(
                "INSERT INTO analyses VALUES (?,?,?,?,?,?,?,?,?)",
                (report["analysis_id"], key_digest, fingerprint, report["symbol"], "RUNNING",
                 utc_time(report["requested_at"]).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                 report["started_at"], None, _dump(report)))
            event = self._insert_event(connection, report["analysis_id"], "REQUEST_RECEIVED",
                                       report["requested_at"], {"symbol": report["symbol"]})
            result = json.loads(_dump(report))
            result["timeline"] = [event]
            return Reservation(result, True)

    def append_event(self, analysis_id, event_type, at, data):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status FROM analyses WHERE analysis_id=?", (analysis_id,)).fetchone()
            if row is None or row["status"] != "RUNNING":
                raise RepositoryError("INVALID_REPORT_STATE", analysis_id)
            return self._insert_event(connection, analysis_id, event_type, at, data)

    def _finalize(self, connection, report, event_type, at, data):
        analysis_id = report["analysis_id"]
        row = connection.execute("SELECT status FROM analyses WHERE analysis_id=?", (analysis_id,)).fetchone()
        if row is None or row["status"] != "RUNNING":
            raise RepositoryError("INVALID_REPORT_STATE", analysis_id)
        if (report["status"] not in ("COMPLETED", "FAILED") or report["completed_at"] is None or
                report["decision"]["order_sent"] is not False or
                (report["status"] == "FAILED" and report["decision"]["action"] is not None) or
                event_type != ("ANALYSIS_COMPLETED" if report["status"] == "COMPLETED" else "ANALYSIS_FAILED")):
            raise RepositoryError("INVALID_REPORT_STATE", analysis_id)
        self._insert_event(connection, analysis_id, event_type, at, data)
        result = json.loads(_dump(report))
        result["timeline"] = self._events(connection, analysis_id)
        connection.execute(
            "UPDATE analyses SET status=?,completed_at=?,report_json=? WHERE analysis_id=? AND status='RUNNING'",
            (result["status"], result["completed_at"], _dump(result), analysis_id))
        return result

    def finalize(self, report, event_type, at, data):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return self._finalize(connection, report, event_type, at, data)

    def get(self, analysis_id):
        with self._connection() as connection:
            connection.execute("BEGIN")
            row = connection.execute("SELECT * FROM analyses WHERE analysis_id=?", (analysis_id,)).fetchone()
            return self._read(connection, row) if row is not None else None

    def history(self, limit=20, offset=0):
        if type(limit) is not int or not 1 <= limit <= 50 or type(offset) is not int or not 0 <= offset <= 10000:
            raise ValueError("history pagination is outside bounds")
        with self._connection() as connection:
            connection.execute("BEGIN")
            total = connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
            rows = connection.execute(
                "SELECT * FROM analyses ORDER BY requested_at DESC,analysis_id DESC LIMIT ? OFFSET ?",
                (limit, offset)).fetchall()
            return {"items": [self._read(connection, row) for row in rows],
                    "limit": limit, "offset": offset, "total": total}

    def health(self):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise RepositoryError("PERSISTENCE_SCHEMA_MISMATCH")
            connection.execute("UPDATE analyses SET symbol=symbol WHERE 0")
            connection.rollback()
        return True

    def recover_interrupted(self, now: datetime):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT * FROM analyses WHERE status='RUNNING'").fetchall()
            for row in rows:
                report = self._read(connection, row)
                report.update(status="FAILED", completed_at=to_jsonable(now))
                report["decision"] = {"action": None, "reason_codes": [], "order_sent": False}
                report["errors"] = [{"code": "PROCESS_INTERRUPTED",
                                     "message": "The previous analysis process was interrupted.",
                                     "stage": "analysis", "timeframe": None}]
                for name in ("acceptance", "risk"):
                    report["modules"][name] = {"status": "NOT_EVALUATED", "reason_codes": ["ANALYSIS_FAILED"]}
                report["explanation"]["deterministic_summary"] = deterministic_summary(report)
                self._finalize(connection, report, "ANALYSIS_FAILED", now,
                               {"error_code": "PROCESS_INTERRUPTED", "recovery": True})
