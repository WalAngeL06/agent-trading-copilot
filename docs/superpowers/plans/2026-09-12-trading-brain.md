# Trading Brain Implementation Plan

**Goal:** One deterministic causal PAPER trade from historical candles.
**Architecture:** Preserve raw SwingEngine; compose independent derived state,
gaps, explicit risk and a local paper broker. One Candle process path for replay
and live prefixes, immutable provenance events and Decimal financial fields.
**Tech Stack:** Python >=3.11 stdlib; reuse existing optional product test runtime.
**Spec:** docs/specs/trading-brain-v0.1.md
**Execution:** Inline within the user's authorized task; one final requested commit.

## Constraints
Exact user base/worktree/branch; no SwingEngine edits, exchange writes, merge,
push or tag. Provisional rules labelled [H]; closed contiguous candles only.

## Task 1: Derived structure/range and manipulation
Create agent_trading/trading_brain/{models,structure,range,manipulation}.py.
Create tests/test_trading_brain.py: hand-built closed candles/raw identities;
assert wick-only break fails, valid wick survives body break, low-first frozen
pair and ordered proximity touches permit arbitrary internal swings.
- [x] Write tests and observe missing behavior fail.
- [x] Implement strict knowledge-time checks and derived immutable states.
- [x] Run focused tests and verify both-sided sweeps/ambiguous bars.

## Task 2: Gap recognition, risk and broker
Create gaps.py, paper.py; tests assert three-bar gaps, inversion crossing,
risk rounding and next-open fill/cancel/stop-first exits from literal prices.
- [x] Write tests and observe missing behavior fail.
- [x] Implement GapEngine.process(Candle), RiskPolicy.plan and PaperBroker.
- [x] Verify candidate geometry, affordable size and no signal-bar fill.

## Task 3: Full replay/evidence
Create runtime.py, __init__.py, __main__.py and synthetic JSONL fixture.
TradingBrain.process(Candle) returns current immutable evidence events;
replay iterates process. CLI reads JSONL and prints exact-string JSON evidence.
- [x] Test full raw SwingEngine chain and prefix/batch-stream equivalence.
- [x] Implement composition and demonstrate PAPER_ORDER_OPENED.
- [x] Smoke all saved BTC fixtures and run full suite.
- [x] Record evidence, source distinctions, limitations; update memory docs.
- [x] Review diff, verify Swing unchanged, commit requested message; clean status.
