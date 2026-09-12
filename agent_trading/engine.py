"""Causal replay orchestration. One engine instance represents one run."""

from collections import deque
from datetime import datetime
from typing import Sequence

from .components import (AcceptanceEngine, DecisionRouter, Detector,
                         DisabledExecution, RiskEngine, UnconfiguredDetector)
from .config import Config
from .journal import JsonlJournal
from .models import Candle, PatternResult, to_jsonable


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
        self.execution = DisabledExecution()
        self._histories: dict[tuple[str, str], deque[Candle]] = {}
        self._latest: datetime | None = None
        self._sequence = 0
        self._failed = False

    def process(self, candle: Candle) -> dict:
        if self._failed:
            raise RuntimeError("run has failed; create a new engine to restart")
        try:
            return self._process(candle)
        except Exception as exc:
            self._failed = True
            if self.journal is not None:
                self.journal.write({"schema_version": 1, "event": "ERROR",
                                    "sequence": self._sequence + 1,
                                    "symbol": candle.symbol, "timeframe": candle.timeframe,
                                    "as_of": candle.close_time,
                                    "error_type": type(exc).__name__, "message": str(exc)})
            raise

    def _process(self, candle: Candle) -> dict:
        key = (candle.symbol, candle.timeframe)
        history = self._histories.setdefault(key, deque(maxlen=self.config.history_limit))
        if self._latest is not None and candle.close_time < self._latest:
            raise ValueError("replay input is out of chronological order")
        if history and candle.close_time <= history[-1].close_time:
            raise ValueError("duplicate or old candle for this symbol/timeframe")
        history.append(candle)
        self._latest = candle.close_time
        snapshot = tuple(history)
        patterns = tuple(detector.evaluate(snapshot) for detector in self.detectors)
        for detector, result in zip(self.detectors, patterns):
            if not isinstance(result, PatternResult) or result.name != detector.name:
                raise ValueError("detector returned an invalid result contract")
            if result.detected_at != candle.close_time:
                raise ValueError("pattern detected_at must equal current decision time")
            if result.window is not None and result.window > len(snapshot):
                raise ValueError("pattern window exceeds available history")
        decision = self.router.route(patterns)
        acceptance = self.acceptance.evaluate(decision)
        risk = self.risk.evaluate(acceptance)
        execution = self.execution.evaluate(risk)
        event = to_jsonable({
            "schema_version": 1, "event": "DECISION", "sequence": self._sequence + 1,
            "mode": self.config.mode, "symbol": candle.symbol,
            "timeframe": candle.timeframe, "as_of": candle.close_time,
            "candle": candle, "config": {"history_limit": self.config.history_limit},
            "market_state": {"history_size": len(history),
                             "history_start": history[0].close_time,
                             "context_status": "NOT_IMPLEMENTED"},
            "patterns": patterns, "decision": decision, "acceptance": acceptance,
            "risk": risk, "execution": execution,
            "position": {"status": "NOT_IMPLEMENTED"},
        })
        if self.journal is not None:
            self.journal.write(event)
        self._sequence += 1
        return event
