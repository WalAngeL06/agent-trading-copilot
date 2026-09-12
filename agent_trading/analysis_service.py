"""Bounded public analysis application service. Routes never own domain decisions."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import re
from uuid import uuid4

from .analysis_config import AnalysisConfig
from .analysis_report import (
    TIMEFRAMES, deterministic_summary, exact_spread, new_report, series_freshness,
)
from .analysis_repository import RepositoryError, SQLiteAnalysisRepository
from .config import Config
from .engine import ReplayEngine
from .journal import JsonlJournal
from .market import bar_duration
from .market_observations import observation_time
from .models import Candle, to_jsonable, utc_time
from .okx_mcp import sanitized_failure
from .okx_mcp_runtime import open_atk_mcp


_PUBLIC_MESSAGES = {
    "PERSISTENCE_UNAVAILABLE": "Product timeline storage is unavailable.",
    "MCP_TIMEOUT": "Public market data timed out.",
    "MCP_UNAVAILABLE": "Public market data is unavailable.",
    "MCP_PROTOCOL_ERROR": "The public MCP protocol failed.",
    "MCP_SCHEMA_ERROR": "The public MCP schema is incompatible.",
    "MCP_TOOL_ERROR": "A public market tool failed.",
    "MALFORMED_RESPONSE": "Public market data could not be normalized.",
    "MALFORMED_DISCOVERY": "Public market tool discovery is malformed.",
    "REQUIRED_TOOLS_MISSING": "A required public market tool is unavailable.",
    "TOOL_SCHEMA_DRIFT": "A required public market tool schema changed.",
    "TOOLS_NOT_DISCOVERED": "Public market tools were not validated.",
    "PUBLIC_SCOPE_MISMATCH": "The runtime did not confirm the required public read-only scope.",
    "ATK_NOT_INSTALLED": "The pinned ATK runtime is unavailable.",
    "ATK_PACKAGE_MISMATCH": "The installed ATK package is incompatible.",
    "ATK_VERSION_MISMATCH": "The installed ATK version is incompatible.",
    "MCP_SDK_UNAVAILABLE": "The official MCP client dependency is unavailable.",
    "MCP_SDK_VERSION_MISMATCH": "The official MCP client version is incompatible.",
    "CLOCK_MOVED_BACKWARD": "The observation clock moved backward.",
    "INVALID_AS_OF": "The candle knowledge boundary is invalid.",
    "NO_CLOSED_CANDLES": "No closed market candles are available.",
    "PUBLIC_HOME_INVALID": "Public runtime isolation could not be established.",
    "STALE_TIMEFRAME": "A required closed-candle series is stale.",
    "MISSING_TIMEFRAME": "A required closed-candle series is missing.",
    "INVALID_HISTORY": "A required closed-candle history is inconsistent.",
    "STALE_OBSERVATION": "A live market observation is stale.",
    "AUDIT_UNAVAILABLE": "The analysis audit could not be written.",
    "ANALYSIS_CANCELLED": "The analysis request was cancelled.",
    "ANALYSIS_INTERNAL_ERROR": "The analysis could not be completed.",
}


class ServiceError(RuntimeError):
    def __init__(self, code, status_code=503, analysis_id=None):
        super().__init__("Product request could not be completed.")
        self.code = code
        self.status_code = status_code
        self.analysis_id = analysis_id


class _PrerequisiteError(RuntimeError):
    def __init__(self, code, timeframe=None):
        super().__init__(_PUBLIC_MESSAGES[code])
        self.code = code
        self.timeframe = timeframe


@dataclass(frozen=True)
class AnalysisResult:
    report: dict
    created: bool


class AnalysisService:
    def __init__(self, config: AnalysisConfig, repository=None, mcp_factory=open_atk_mcp, clock=None):
        from datetime import datetime, timezone
        self.config = config
        self.repository = repository or SQLiteAnalysisRepository(config.db_path, config.sqlite_timeout_seconds)
        self.mcp_factory = mcp_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._active = asyncio.Lock()
        self._repository_ready = False
        self._validated = None
        self._last_failure = None

    def _now(self):
        return observation_time(self.clock())

    async def startup(self):
        if self._active.locked():
            raise ServiceError("SERVICE_BUSY")
        self._validated = None
        try:
            await asyncio.to_thread(self.repository.initialize)
            await asyncio.to_thread(self.repository.recover_interrupted, self._now())
            self._repository_ready = True
        except RepositoryError:
            self._repository_ready = False

    @staticmethod
    def _request_key(key):
        if key is None:
            return None
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", key):
            raise ServiceError("INVALID_IDEMPOTENCY_KEY", 422)
        return sha256(key.encode("ascii")).hexdigest()

    @staticmethod
    def _replay(reservation):
        if reservation.report["status"] == "RUNNING":
            raise ServiceError("ANALYSIS_IN_PROGRESS", 409, reservation.report["analysis_id"])
        return AnalysisResult(reservation.report, False)

    async def analyze(self, symbol, idempotency_key=None):
        if type(symbol) is not str or symbol not in self.config.allowed_symbols:
            raise ServiceError("INVALID_SYMBOL", 422)
        key_digest = self._request_key(idempotency_key)
        fingerprint = sha256(("analysis-api-v0.1:" + symbol).encode("ascii")).hexdigest()
        if not self._repository_ready:
            await self.startup()
        if not self._repository_ready:
            raise ServiceError("PERSISTENCE_UNAVAILABLE")
        try:
            if key_digest is not None:
                existing = await asyncio.to_thread(self.repository.find_idempotent, key_digest, fingerprint)
                if existing:
                    return self._replay(existing)
            if self._active.locked():
                raise ServiceError("SERVICE_BUSY")
            async with self._active:
                now = self._now()
                draft = new_report(str(uuid4()), symbol, now, self.config.publication_grace_seconds)
                reservation = await asyncio.to_thread(self.repository.reserve, draft, key_digest, fingerprint)
                if not reservation.created:
                    return self._replay(reservation)
                return await self._run(reservation.report, now)
        except RepositoryError as exc:
            if exc.code == "IDEMPOTENCY_CONFLICT":
                raise ServiceError(exc.code, 409, exc.analysis_id) from None
            self._repository_ready = False
            raise ServiceError("PERSISTENCE_UNAVAILABLE", 503, exc.analysis_id) from None

    async def _event(self, report, event_type, data):
        await asyncio.to_thread(self.repository.append_event, report["analysis_id"],
                                event_type, self._now(), data)

    @staticmethod
    def _sources(adapter, failure):
        provenance = list(adapter.provenance) if adapter is not None else []
        error = sanitized_failure(failure) if failure is not None else None
        extra = error.provenance if error is not None else None
        if extra is not None and extra not in provenance:
            provenance.append(extra)
        return [{"source_id": f"source-{index}", "provenance": to_jsonable(item)}
                for index, item in enumerate(provenance, 1)]

    @staticmethod
    def _evidence(report):
        evidence = []
        for source in report["sources"]:
            p = source["provenance"]
            if not p["success"]:
                continue
            if p["tool"] == "market_get_ticker" and report["market"]["ticker"] is not None:
                kind, reference, close, used = "TICKER", "market.ticker", None, False
            elif p["tool"] == "market_get_orderbook" and report["market"]["orderbook_summary"] is not None:
                kind, reference, close, used = "ORDERBOOK", "market.orderbook_summary", None, False
            elif p["tool"] == "market_get_candles":
                tf = p["timeframe"]
                frame = report["timeframes"][tf]
                if frame["latest_closed_candle"] is None:
                    continue
                kind, reference, close = "CLOSED_CANDLES", f"timeframes.{tf}", frame["latest_close_time"]
                used = report["decision_as_of"] is not None and close <= report["decision_as_of"]
            else:
                continue
            evidence.append({"evidence_id": f"evidence-{len(evidence)+1}", "kind": kind,
                             "reference": reference, "source_id": source["source_id"],
                             "decision_input": used, "close_time": close,
                             "observed_at": p["response_observed_at"]})
        return evidence

    def _error(self, exc, stage, timeframe):
        if isinstance(exc, ExceptionGroup):
            def known_failure(group):
                for item in group.exceptions:
                    if isinstance(item, (_PrerequisiteError, RepositoryError)):
                        return item
                    if isinstance(item, ExceptionGroup):
                        found = known_failure(item)
                        if found is not None:
                            return found
                return None
            exc = known_failure(exc) or exc
        if isinstance(exc, RepositoryError):
            code, stage, timeframe = "PERSISTENCE_UNAVAILABLE", "persistence", None
        elif isinstance(exc, _PrerequisiteError):
            code, timeframe = exc.code, exc.timeframe
        elif isinstance(exc, asyncio.CancelledError):
            code = "ANALYSIS_CANCELLED"
        elif stage == "audit":
            code = "AUDIT_UNAVAILABLE"
        elif stage in ("snapshot", "decision"):
            code = "ANALYSIS_INTERNAL_ERROR"
        else:
            code = sanitized_failure(exc).code
            if not code.startswith(("MCP_", "ATK_")) and code not in _PUBLIC_MESSAGES:
                code = "ANALYSIS_INTERNAL_ERROR"
        if code not in _PUBLIC_MESSAGES:
            code = "ANALYSIS_INTERNAL_ERROR"
        return {"code": code, "message": _PUBLIC_MESSAGES[code], "stage": stage, "timeframe": timeframe}

    def _validate_histories(self, report, histories, cutoff):
        for tf in TIMEFRAMES:
            items = histories.get(tf, ())
            frame = report["timeframes"][tf]
            if not items:
                frame["data_status"] = "MISSING"
                raise _PrerequisiteError("MISSING_TIMEFRAME", tf)
            previous = None
            for candle in items:
                if (not isinstance(candle, Candle) or candle.symbol != report["symbol"] or
                        candle.timeframe != tf or candle.close_time > cutoff or
                        (previous is not None and candle.close_time - previous != bar_duration(tf))):
                    frame["data_status"] = "FAILED"
                    raise _PrerequisiteError("INVALID_HISTORY", tf)
                previous = candle.close_time
            frame["freshness"] = series_freshness(items[-1].close_time, tf, cutoff,
                                                  self.config.publication_grace_seconds)
            if frame["freshness"]["status"] == "STALE":
                frame["data_status"] = "FAILED"
                raise _PrerequisiteError("STALE_TIMEFRAME", tf)
        decision_as_of = histories["15m"][-1].close_time
        causal = []
        for tf in TIMEFRAMES:
            items = tuple(c for c in histories[tf] if c.close_time <= decision_as_of)[-self.config.history_limit:]
            if not items:
                report["timeframes"][tf]["data_status"] = "MISSING"
                raise _PrerequisiteError("MISSING_TIMEFRAME", tf)
            report["timeframes"][tf].update(
                latest_closed_candle=to_jsonable(items[-1]), candle_count=len(items),
                latest_close_time=to_jsonable(items[-1].close_time))
            causal.extend(items)
        return causal, decision_as_of

    def _validate_observation(self, observation):
        if observation.observed_at - observation.exchange_time > timedelta(seconds=self.config.observation_max_age_seconds):
            raise _PrerequisiteError("STALE_OBSERVATION")

    async def _run(self, report, cutoff):
        adapter = None
        failure = None
        stage, timeframe = "audit", None
        cancelled = False
        histories = {}
        try:
            async with asyncio.timeout(self.config.analysis_timeout_seconds):
                with JsonlJournal(self.config.audit_dir / (report["analysis_id"] + ".jsonl")) as journal:
                    try:
                        stage = "mcp"
                        async with self.mcp_factory(node_path=self.config.node_path, server_path=self.config.server_path,
                                                    timeout=self.config.mcp_timeout_seconds, workdir=Path.cwd()) as adapter:
                            await self._event(report, "MCP_CONNECTED", {"transport": "MCP", "site": "tr"})
                            stage = "ticker"
                            ticker = await adapter.ticker(report["symbol"])
                            report["market"]["ticker"] = to_jsonable(ticker.value)
                            self._validate_observation(ticker.value)
                            await self._event(report, "TICKER_FETCHED", {"symbol": report["symbol"]})
                            for tf in TIMEFRAMES:
                                stage, timeframe = "candles", tf
                                read = await adapter.candles(report["symbol"], tf, self.config.history_limit + 1, as_of=cutoff)
                                histories[tf] = read.value
                                items = read.value
                                report["timeframes"][tf].update(
                                    latest_closed_candle=to_jsonable(items[-1]) if items else None,
                                    candle_count=len(items), latest_close_time=to_jsonable(items[-1].close_time) if items else None,
                                    observed_at=to_jsonable(read.provenance.response_observed_at),
                                    data_status="AVAILABLE" if items else "MISSING")
                                await self._event(report, "CANDLES_FETCHED", {"timeframe": tf, "closed_count": len(items)})
                            stage, timeframe = "orderbook", None
                            book = await adapter.orderbook(report["symbol"], 5)
                            self._validate_observation(book.value)
                            b = book.value
                            report["market"]["orderbook_summary"] = to_jsonable({
                                "best_bid": b.bids[0], "best_ask": b.asks[0],
                                "bid_levels": len(b.bids), "ask_levels": len(b.asks),
                                "exchange_time": b.exchange_time, "observed_at": b.observed_at})
                            report["market"]["spread"] = to_jsonable({
                                "value": exact_spread(b.bids[0].price, b.asks[0].price), "source": "ORDERBOOK",
                                "exchange_time": b.exchange_time, "observed_at": b.observed_at})
                            await self._event(report, "ORDERBOOK_FETCHED", {"bid_levels": len(b.bids), "ask_levels": len(b.asks)})
                            stage = "mcp"
                        stage = "snapshot"
                        causal, decision_as_of = self._validate_histories(report, histories, cutoff)
                        core_config = Config(mode="shadow", symbol=report["symbol"], timeframes=TIMEFRAMES,
                                             history_limit=self.config.history_limit, bootstrap_limit=self.config.history_limit,
                                             output_path=str(self.config.audit_dir / (report["analysis_id"] + ".jsonl")))
                        engine = ReplayEngine(core_config, journal=journal)
                        snapshot = engine.bootstrap(causal, decision_as_of)
                        report["decision_as_of"] = to_jsonable(snapshot.as_of)
                        await self._event(report, "SNAPSHOT_BUILT", {
                            "decision_as_of": snapshot.as_of, "counts": {tf: len(h) for tf, h in snapshot.histories.items()}})
                        stage = "decision"
                        event = engine.evaluate_snapshot(report["symbol"], snapshot.as_of)
                        if event["execution"].get("order_sent") is not False or event["decision"]["action"] != "NO_TRADE":
                            raise _PrerequisiteError("ANALYSIS_INTERNAL_ERROR")
                        report["decision"] = {"action": event["decision"]["action"],
                                              "reason_codes": [event["decision"]["reason"]], "order_sent": False}
                        for name in ("acceptance", "risk"):
                            report["modules"][name] = {"status": event[name]["status"], "reason_codes": [event[name]["reason"]]}
                        await self._event(report, "DECISION_EVALUATED", report["decision"])
                        stage = "audit"
                    except (Exception, asyncio.CancelledError) as exc:
                        error = self._error(exc, stage, timeframe)
                        journal.write({"schema_version": 2, "event": "ERROR", "analysis_id": report["analysis_id"],
                                       "error_code": error["code"], "stage": error["stage"], "timeframe": error["timeframe"]})
                        raise
        except asyncio.CancelledError as exc:
            failure, cancelled = exc, True
        except Exception as exc:
            failure = exc
        if failure is not None:
            error = self._error(failure, stage, timeframe)
            if stage == "candles" and timeframe is not None:
                report["timeframes"][timeframe]["data_status"] = "FAILED"
            report["status"] = "FAILED"
            report["decision"] = {"action": None, "reason_codes": [], "order_sent": False}
            report["errors"] = [error]
            for name in ("acceptance", "risk"):
                report["modules"][name] = {"status": "NOT_EVALUATED", "reason_codes": ["ANALYSIS_FAILED"]}
            self._validated = None
            self._last_failure = error["code"]
        else:
            report["status"] = "COMPLETED"
        report["completed_at"] = to_jsonable(self._now())
        report["sources"] = self._sources(adapter, failure)
        report["evidence"] = self._evidence(report)
        report["explanation"]["deterministic_summary"] = deterministic_summary(report)
        event_type = "ANALYSIS_COMPLETED" if failure is None else "ANALYSIS_FAILED"
        data = {"action": report["decision"]["action"]} if failure is None else {"error_code": report["errors"][0]["code"]}
        try:
            final = await asyncio.to_thread(self.repository.finalize, report, event_type, self._now(), data)
        except RepositoryError:
            self._validated = None
            self._repository_ready = False
            raise ServiceError("PERSISTENCE_UNAVAILABLE", 503, report["analysis_id"]) from None
        if failure is None:
            self._validated = {"at": self._now(), "closes": {
                tf: utc_time(final["timeframes"][tf]["latest_close_time"]) for tf in TIMEFRAMES}}
            self._last_failure = None
        if cancelled:
            raise asyncio.CancelledError()
        return AnalysisResult(final, True)

    async def readiness(self):
        now = self._now()
        reasons = []
        try:
            await asyncio.to_thread(self.repository.health)
            self._repository_ready = True
        except RepositoryError:
            self._repository_ready = False
            reasons.append("PERSISTENCE_UNAVAILABLE")
        if self._validated is None:
            reasons.append("MARKET_DATA_NOT_VALIDATED")
            if self._last_failure:
                reasons.append("LAST_ANALYSIS_FAILED")
        else:
            age = now - self._validated["at"]
            if age < timedelta(0) or age > timedelta(seconds=self.config.ready_ttl_seconds):
                reasons.append("READINESS_EXPIRED")
            if any(series_freshness(close, tf, now, self.config.publication_grace_seconds)["status"] != "FRESH"
                   for tf, close in self._validated["closes"].items()):
                reasons.append("MARKET_DATA_STALE")
        return to_jsonable({"status": "READY" if not reasons else "NOT_READY", "checked_at": now,
                            "repository": "AVAILABLE" if self._repository_ready else "UNAVAILABLE",
                            "mcp_market": "VALIDATED" if self._validated is not None else "NOT_VALIDATED",
                            "last_success_at": self._validated["at"] if self._validated is not None else None,
                            "reason_codes": reasons})
