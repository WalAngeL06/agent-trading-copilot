# Next task — SOURCE INGESTION → RANGE

Updated: 2026-09-12, after shared-memory setup. No Range implementation started.

Goal: collect and formalize DD Range rules before implementation. Source
priority is recorded in [PROJECT_STATE](PROJECT_STATE.md); Market Structure's
unresolved N-1–N-7 remain open while the next source topic is Range.

## Required input

DD Range material or explicitly confirmed DD rules, with provenance and
examples if available. No confirmed DD Range rule set is currently recorded
in SOURCE_REGISTRY. Obtain that input before asserting Range semantics; do not
substitute textbook SMC, generic local extrema or a library's defaults.

## Expected next artifacts (not yet created)

- `docs/research/range-source-notes.md`: source IDs, exact claims, user
  clarifications, examples and confirmation/validation status.
- `docs/specs/range-v0.1.md`: formal inputs/state, boundary selection,
  recognition/availability, lifecycle and edge cases justified by those sources.
- Explicit unresolved decisions marked **ALGORITHMIC DEFINITION PENDING**.
- Future test cases with source-labelled expected behavior and causal times.

Do not invent boundary, touch-count, duration, ATR, retracement, volume or
tolerance rules. Preserve closed-candle causality and distinguish occurrence
from confirmation. Update SOURCE_REGISTRY, HANDOFF and PROJECT_STATE after
ingestion; record consequential decisions in DECISIONS.

## Completion boundary

Deliver source notes, draft Range spec and unresolved decisions for review.
**Do not begin implementation before the Range spec is approved** and its
required deterministic decisions are resolved. Do not implement
MarketStructureEngine while its own core gates remain unresolved. No live
execution, dependency/framework integration, push or remote creation.

Current documentation setup stops here and waits for the next instruction.
