# Structure-aware RiskEngine Implementation Plan

> Execute inline for this user-authorized urgent change; independent read-only
> review uses the requesting-code-review skill. One task-scoped feature commit.

**Goal:** Gate PAPER execution on a modular, evidenced risk-approved plan.
**Architecture:** Separate immutable risk vocabulary, approval/stop strategies,
zone-support adapter and broker. Runtime composes them after existing signals.
**Tech Stack:** Python standard library, Decimal, frozen dataclasses, unittest.
**Spec:** docs/specs/risk-engine-v0.1.md.

Constraints: preserve SwingEngine/Range semantics; closed candles/UTC/Decimal;
no LIVE, dependencies, merge/push/tag; exact corrected base; commit then STOP.

## Task 1: Risk approval and stop management

Files: risk_models.py (configuration/contracts), risk.py (approval/management),
tests/test_risk_engine.py (literal prices and gate expectations).
Interfaces: RiskEngine.evaluate(candidate, equity, zones, symbol, timeframe)
returns RiskDecision. RiskEngine.revalidate_fill(plan, entry, equity, observed_at)
preserves original SL/TP. RiskEngine.manage(trade, candle) returns immutable trade.

- [x] Write literal LONG100 / zone90..95 / buffer1 / TP120 expectations:
  stop89, distance11, reward20, budget10, quantity.90 with step.01.
- [x] Run focused tests and observe missing RiskEngine behavior.
- [x] Implement typed configuration, support selection, complete blocked evidence,
  rounded sizing and engine-issued immutable plans; test all directional gates.
- [x] Implement configurable 1R break-even and fixed profile behind the monotonic
  guard; verify LONG90->100 and SHORT110->100, preserving TP/initial evidence.
- [x] Run focused tests to verify the approval/management contract.

## Task 2: Approved plan execution and causal composition

Files: zones.py, paper.py, models.py, runtime.py, __init__.py, __main__.py;
tests/test_risk_engine.py and existing paper/replay contract tests.
Interfaces: SupportingZoneBook observes closed candles and directional gap
publications; PaperBroker.submit(ApprovedTradePlan) rejects unapproved inputs.

- [x] Write no-plan/no-order, gapped-fill R:R rejection and prior-stop-first tests.
- [x] Observe expected failures, then require issued plans in broker, publish
  actual-fill approval/BLOCKED before order events and manage surviving stops.
- [x] Wire causal fresh zone support without altering signal detection; expose
  profile/min-RR/max-stop-distance/break-even-R CLI configuration.
- [x] Update only superseded literal risk/execution expectations, preserving
  unchanged range-boundary and raw-swing assertions.
- [x] Verify deterministic replay and every-prefix evidence/state equality.

## Task 3: Evidence, review and checkpoint

Files: risk-engine-evidence.json / risk-engine.md, SOURCE_REGISTRY, ADR013,
AGENTS, PROJECT_STATE, HANDOFF, NEXT_TASK; this completion checklist.

- [x] Run full suite using the existing backend interpreter, no installs.
- [x] Produce one approved and one blocked literal example, exact defaults/gaps.
- [x] Request independent read-only review; fix material findings and rerun
  affected/full verification when justified.
- [x] Check diff/whitespace, unchanged Swing/Range files, exact base ancestry.
The requested commit follows this verified documentation freeze. Git/final report
records its exact hash and clean state: `feat: add configurable structure-aware risk engine`.
No merge/push/tag; STOP after the checkpoint.

Verification: baseline292, final323 tests passed,31 new risk methods;7 post-fix
CLI smokes passed. Independent read-only review defects fixed and re-review clear.
