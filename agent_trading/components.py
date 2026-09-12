"""Unconfigured components report their state instead of inventing rules."""

from dataclasses import dataclass, replace
from typing import Protocol

from .models import MarketSnapshot, PatternResult, PatternStatus


class Detector(Protocol):
    name: str

    def evaluate(self, snapshot: MarketSnapshot) -> PatternResult: ...


@dataclass(frozen=True)
class UnconfiguredDetector:
    name: str

    def evaluate(self, snapshot: MarketSnapshot) -> PatternResult:
        return PatternResult(self.name, PatternStatus.NOT_IMPLEMENTED,
                             snapshot.as_of)


@dataclass(frozen=True)
class SingleTimeframeDetectorAdapter:
    """Explicit migration wrapper for the foundation's evaluate(history) API."""
    detector: object
    timeframe: str

    @property
    def name(self):
        return self.detector.name

    def evaluate(self, snapshot: MarketSnapshot) -> PatternResult:
        history = snapshot.histories.get(self.timeframe, ())
        if not history:
            return PatternResult(self.name, PatternStatus.INSUFFICIENT_DATA,
                                 snapshot.as_of, timeframe=self.timeframe)
        result = self.detector.evaluate(history)
        if not isinstance(result, PatternResult):
            raise ValueError("legacy detector returned an invalid result contract")
        # Never retime a result: stale or future detections fail engine validation.
        return replace(result, timeframe=self.timeframe)


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


class ShadowExecution:
    """Records intent only. Has no exchange client or order submission method."""

    def evaluate(self, decision: dict, acceptance: dict, risk: dict) -> dict:
        action = "NO_ACTION"
        reason = "NO_RISK_APPROVAL"
        if decision.get("action") == "NO_TRADE":
            reason = decision.get("reason") or "NO_CANDIDATE"
        elif acceptance.get("status") == "APPROVED" and risk.get("status") == "APPROVED":
            action = {"BUY": "WOULD_BUY", "SELL": "WOULD_SELL"}.get(
                decision.get("action"), "NO_ACTION")
            reason = (decision.get("reason") or "APPROVED_SHADOW_CANDIDATE") if action != "NO_ACTION" else "AMBIGUOUS_DECISION"
        return {"status": "SHADOW", "action": action, "reason": reason,
                "order_sent": False}
