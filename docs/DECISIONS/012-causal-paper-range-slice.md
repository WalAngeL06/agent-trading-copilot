# ADR 012 — Opt-in causal PAPER range slice

2026-09-12. Accepted for isolated [U-TRADING-BRAIN-001] task only.

The user explicitly authorizes a historical PAPER chain from adbafa4, preserving
SwingEngine and labelling provisional trading definitions [H]. Inherited
no-strategy/STOP gates do not bar this authorized slice; general DD engine
completion and LIVE remain excluded.

Compose separate raw/valid level, frozen range, sweep/reclaim, gap, candidate,
risk and paper-broker components in agent_trading/trading_brain. Keep existing
production decision/API behavior intact. A single closed contiguous Candle
process path drives historical replay and live-prefix equivalence. Next-open
fills are published at the processed close, with effective filled_at separate.
Risk approval and every paper order reference causal immutable evidence IDs.

Current corrected evidence provides a bounded real15m FVG-short and synthetic
full chain; original full-fixture real1H/4H examples are withdrawn;
it does not approve provisional selection/thresholds as DD rules or validate
profitability. Missing source/acceptance/risk/lifecycle semantics remain explicit
blockers. No network/exchange client, usable LIVE option, merge/push/tag.
[Spec](../specs/trading-brain-v0.1.md), [evidence](../trading-brain-replay.md).

## Boundary correction

[U-RANGE-BOUNDARIES-001] supersedes symmetric outside proximity. Every candidate
candle including its forming/confirming bar is checked before touches; any strict
wick breach records terminal RANGE_INVALIDATED with immutable candle/reasons.
Raw swings/valid levels continue unchanged; later touches cannot revive it.
Only previously confirmed ranges can manipulate. Initial pair selection and
no-reseed remain existing [H]; do not add a reseed policy to force real trades.
