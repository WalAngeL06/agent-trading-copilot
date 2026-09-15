# ADR013 — risk-approved PAPER plans and monotonic stop management

2026-09-12; accepted for the opt-in offline PAPER slice [U-RISK-ENGINE-001].

The old broker accepted a TradeCandidate and computed its own sizing, so an
execution consumer could bypass a future risk gate. Signals now remain immutable
inputs; RiskEngine issues an ApprovedTradePlan with complete evidence. PaperBroker
requires a plan issued by its own engine and revalidates original SL/TP at the
actual next open before opening. Fill approval has its own causal event.
No plan means no PAPER_ORDER_OPENED. Rejected fills publish BLOCKED/cancellation.

SupportingZone is a provider-independent validated/fresh record. Risk chooses
directional support and protects its invalidation; no support falls back to the
observed sweep extreme [H]. FVG/iFVG detector semantics remain preserved behind
a separate conservative risk-freshness adapter [H]. Future providers can implement
their own source-approved zone validation without changing risk approval.

STRUCTURE_BE is default, configurable favorable-excursion R trigger1 [H]. Resolve
current-bar old-stop/TP exits first; only survivors update at close, effective
next bar. One monotonic guard prevents LONG decreases/SHORT increases, including
break-even after a tighter stop. FIXED_SL_TP keeps original candidate SL/TP.
StopManagement Protocol permits future profiles, which remain unimplemented.
All original approval evidence and stop-update measurements/times remain retained.

Consequences: stricter defaults can block previously filled examples, particularly
poor R:R or insufficient unleveraged equity. Exact [H] thresholds and source/
validation distinction are in [risk spec](../specs/risk-engine-v0.1.md). Offline
wire version is trading-brain-paper-v0.2; production analysis contracts are unchanged.
Plan issuance is process-local, with no durable restore, exchange writes or LIVE.
Tests/replay establish deterministic infrastructure behavior, not trading validity.
