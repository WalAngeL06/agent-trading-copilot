# 005 — Specs before strategy implementation

- **Decision:** Trading modules require formal specifications before
  implementation; unresolved deterministic rules stay explicitly pending.
- **Reason:** Source-confirmed qualitative DD concepts are not complete
  algorithms or empirical validation. Silent defaults would change semantics.
- **Consequence:** Preserve provenance and specify inputs/state, transitions,
  causality, edge cases and tests. Do not code MarketStructureEngine yet;
  Range is the next source-ingestion task, with implementation gated by approval.
- **Date:** 2026-09-12.
