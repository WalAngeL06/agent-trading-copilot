"""Unconfigured components report their state instead of inventing rules."""

from dataclasses import dataclass
from typing import Protocol

from .models import Candle, PatternResult, PatternStatus


class Detector(Protocol):
    name: str

    def evaluate(self, history: tuple[Candle, ...]) -> PatternResult: ...


@dataclass(frozen=True)
class UnconfiguredDetector:
    name: str

    def evaluate(self, history: tuple[Candle, ...]) -> PatternResult:
        return PatternResult(self.name, PatternStatus.NOT_IMPLEMENTED,
                             history[-1].close_time)


class DecisionRouter:
    def route(self, patterns: tuple[PatternResult, ...]) -> dict:
        return {"action": "NO_TRADE", "reason": "STRATEGY_NOT_CONFIGURED"}


class AcceptanceEngine:
    def evaluate(self, decision: dict) -> dict:
        if decision["action"] == "NO_TRADE":
            return {"status": "NOT_EVALUATED", "reason": "NO_CANDIDATE"}
        return {"status": "REJECTED", "reason": "ACCEPTANCE_POLICY_NOT_CONFIGURED"}


class RiskEngine:
    def evaluate(self, acceptance: dict) -> dict:
        if acceptance["status"] != "APPROVED":
            return {"status": "NOT_EVALUATED", "reason": "NO_ACCEPTED_CANDIDATE"}
        return {"status": "REJECTED", "reason": "RISK_POLICY_NOT_CONFIGURED"}


class DisabledExecution:
    def evaluate(self, risk: dict) -> dict:
        if risk["status"] == "APPROVED":
            raise RuntimeError("execution is not implemented")
        return {"status": "NOT_REQUESTED", "reason": "NO_RISK_APPROVAL"}
