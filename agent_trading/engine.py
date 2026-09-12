"""Causal orchestration over one shared history store. One instance per run."""

from datetime import datetime
from typing import Sequence

from .components import (AcceptanceEngine, DecisionRouter, Detector,
                         DisabledExecution, RiskEngine, ShadowExecution,
                         UnconfiguredDetector)
from .config import Config
from .journal import JsonlJournal
from .market import HistoryStore, bar_duration, snapshot_summary
from .models import Candle, MarketSnapshot, PatternResult, to_jsonable


class ReplayEngine:
    def __init__(self, config: Config, detectors: Sequence[Detector] | None = None,
                 journal: JsonlJournal | None = None):
        self.config = config
        self.detectors = tuple(detectors) if detectors is not None else tuple(
            UnconfiguredDetector(name) for name in
            ("range", "deviation", "manipulation", "momentum", "distribution"))
        if len({d.name for d in self.detectors}) != len(self.detectors):
            raise ValueError("detector names must be unique")
        self.journal = journal
        self.router = DecisionRouter()
        self.acceptance = AcceptanceEngine()
        self.risk = RiskEngine()
        self.execution = ShadowExecution() if config.mode == "shadow" else DisabledExecution()
        self._history = HistoryStore(config.history_limit)
        self._latest: datetime | None = None
        self._context_as_of: datetime | None = None
        self._sequence = 0
        self._failed = False

    def _check_running(self):
        if self._failed:
            raise RuntimeError("run has failed; create a new engine to restart")

    def fail(self, exc: Exception, **context):
        """Permanently stop this run and record the first failure only."""
        if self._failed:
            return
        self._failed = True
        if self.journal is not None:
            self.journal.write({"schema_version": 2, "event": "ERROR",
                                "sequence": self._sequence + 1,
                                "error_type": type(exc).__name__,
                                "message": str(exc), **context})

    def snapshot(self, symbol: str, as_of: datetime) -> MarketSnapshot:
        """Public causal view; retained history only, with no engine internals."""
        self._check_running()
        return self._history.snapshot(symbol, as_of)

    def process(self, candle: Candle) -> dict:
        """Replay preserves input order; never silently reorders a replay file."""
        self._check_running()
        try:
            if self._latest is not None and candle.close_time < self._latest:
                raise ValueError("replay input is out of chronological order")
            self._history.append(candle)
            self._latest = candle.close_time
            return self._evaluate(self.snapshot(candle.symbol, candle.close_time), candle)
        except Exception as exc:
            self.fail(exc, symbol=candle.symbol, timeframe=candle.timeframe,
                       as_of=candle.close_time)
            raise

    def bootstrap(self, candles: Sequence[Candle], as_of: datetime) -> MarketSnapshot:
        """Context ingestion only. No detectors, router, policies or execution."""
        self._check_running()
        try:
            if self._latest is not None or self._context_as_of is not None:
                raise ValueError("bootstrap requires a fresh engine")
            ordered = self._context_input(candles, as_of)
            store = HistoryStore(self.config.history_limit)
            latest_by_tf = {}
            for candle in ordered:
                previous = latest_by_tf.get(candle.timeframe)
                if previous is not None and candle.close_time - previous != bar_duration(candle.timeframe):
                    raise ValueError("bootstrap candle series contains a gap")
                store.append(candle)
                latest_by_tf[candle.timeframe] = candle.close_time
            if set(latest_by_tf) != set(self.config.timeframes):
                raise ValueError("bootstrap has no closed candles for a required timeframe")
            snapshot = store.snapshot(self.config.symbol, as_of)
            self._history = store
            self._latest = ordered[-1].close_time
            self._context_as_of = snapshot.as_of
            if self.journal is not None:
                self.journal.write({"schema_version": 2, "event": "BOOTSTRAP_COMPLETE",
                                    "mode": self.config.mode, "symbol": snapshot.symbol,
                                    "timeframes": self.config.timeframes,
                                    **snapshot_summary(snapshot), "execution_called": False})
            return snapshot
        except Exception as exc:
            self.fail(exc, stage="bootstrap", as_of=as_of)
            raise

    def _context_input(self, candles: Sequence[Candle], as_of: datetime) -> list[Candle]:
        boundary = MarketSnapshot(self.config.symbol, as_of, {}).as_of
        unique = {}
        for candle in candles:
            if not isinstance(candle, Candle) or candle.closed is not True:
                raise ValueError("context requires closed Candle instances")
            if candle.symbol != self.config.symbol or candle.timeframe not in self.config.timeframes:
                raise ValueError("context symbol/timeframe mismatch")
            if candle.close_time > boundary:
                raise ValueError("context cannot contain future candles")
            key = (candle.timeframe, candle.close_time)
            if key in unique and unique[key] != candle:
                raise ValueError("conflicting duplicate context candle")
            unique[key] = candle
        return sorted(unique.values(), key=lambda c: (c.close_time, c.timeframe))

    def update_context(self, candles: Sequence[Candle], as_of: datetime) -> bool:
        """Merge a complete fetched batch before exposing its next snapshot."""
        self._check_running()
        try:
            if self._context_as_of is None:
                raise ValueError("context update requires completed bootstrap")
            if as_of < self._context_as_of:
                raise ValueError("context evaluation time moved backwards")
            ordered = self._context_input(candles, as_of)
            existing = self.snapshot(self.config.symbol, as_of)
            retained = {(tf, c.close_time): c for tf, history in existing.histories.items()
                        for c in history}
            latest = {tf: history[-1].close_time for tf, history in existing.histories.items()
                      if history}
            additions = []
            for candle in ordered:
                key = (candle.timeframe, candle.close_time)
                if key in retained:
                    if candle != retained[key]:
                        raise ValueError("exchange changed a retained closed candle")
                    continue
                previous = latest.get(candle.timeframe)
                if previous is not None:
                    if candle.close_time <= previous:
                        continue  # older than the bounded retained context
                    if candle.close_time - previous != bar_duration(candle.timeframe):
                        raise ValueError("poll missed closed candles; restart with bootstrap")
                latest[candle.timeframe] = candle.close_time
                additions.append(candle)
            for candle in additions:
                self._history.append(candle)
            if additions:
                self._latest = max(self._latest, additions[-1].close_time)
            self._context_as_of = as_of
            return bool(additions)
        except Exception as exc:
            self.fail(exc, stage="market_update", as_of=as_of)
            raise

    def evaluate_snapshot(self, symbol: str, as_of: datetime) -> dict:
        self._check_running()
        try:
            return self._evaluate(self.snapshot(symbol, as_of))
        except Exception as exc:
            self.fail(exc, stage="decision", symbol=symbol, as_of=as_of)
            raise

    def _evaluate(self, snapshot: MarketSnapshot, candle: Candle | None = None) -> dict:
        if not any(snapshot.histories.values()):
            raise ValueError("cannot evaluate an empty market snapshot")
        patterns = tuple(detector.evaluate(snapshot) for detector in self.detectors)
        for detector, result in zip(self.detectors, patterns):
            if not isinstance(result, PatternResult) or result.name != detector.name:
                raise ValueError("detector returned an invalid result contract")
            if result.detected_at != snapshot.as_of:
                raise ValueError("pattern detected_at must equal current decision time")
            if result.timeframe is not None and result.timeframe not in snapshot.histories:
                raise ValueError("pattern refers to an unavailable timeframe")
            if result.window is not None:
                tf = result.timeframe or (candle.timeframe if candle is not None else None)
                if tf is None or result.window > len(snapshot.histories.get(tf, ())):
                    raise ValueError("pattern window requires an available timeframe history")
        decision = self.router.route(patterns)
        acceptance = self.acceptance.evaluate(decision)
        risk = self.risk.evaluate(acceptance)
        execution = (self.execution.evaluate(decision, acceptance, risk)
                     if self.config.mode == "shadow" else self.execution.evaluate(risk))
        market_state = {"context_status": "CLOSED_CANDLE_HISTORIES", **snapshot_summary(snapshot)}
        if candle is not None:
            history = snapshot.histories[candle.timeframe]
            market_state.update(history_size=len(history), history_start=history[0].close_time)
        event = to_jsonable({
            "schema_version": 2, "event": "DECISION", "sequence": self._sequence + 1,
            "mode": self.config.mode, "symbol": snapshot.symbol, "as_of": snapshot.as_of,
            "config": {"history_limit": self.config.history_limit},
            "market_state": market_state,
            "patterns": patterns, "decision": decision, "acceptance": acceptance,
            "risk": risk, "execution": execution,
            "position": {"status": "NOT_IMPLEMENTED"},
            **({"timeframe": candle.timeframe, "candle": candle} if candle is not None else {}),
        })
        if self.journal is not None:
            self.journal.write(event)
        self._sequence += 1
        return event
