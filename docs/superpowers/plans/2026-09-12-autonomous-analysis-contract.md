# Autonomous analysis contract correction implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> inline, task by task. Only the existing backend worktree is authorized.

**Goal:** Correct product direction and version/configure the existing analysis
contract for strategy-required timeframe collections, preserving real defaults.
**Architecture:** Keep the existing MCP/core/repository; pass one immutable
required-timeframe collection through report/service/config. New reports are
v0.2; strict schema-discriminated HTTP reads retain original v0.1 history.
Future autonomous runtime/modes/outcomes are documentation only.
**Tech stack:** Existing Python >=3.11, Decimal/UTC, pinned MCP/FastAPI/Pydantic,
stdlib SQLite and unchanged JSONL; no dependency changes.
**Spec:** [analysis-api-v0.2](../../specs/analysis-api-v0.2.md) and
[ADR011](../../DECISIONS/011-autonomous-runtime-contract.md).

## Global constraints

- Work only Agent Trading-backend / work/copilot-backend, clean starting HEAD
  6c1af4b6f6cd8c22986b8436dd26d61f64de469d; initial150 tests verified.
- Preserve v0.1 file/history and all existing150 tests unchanged.
- Default required collection4H/1H/15m; no user decision/display timeframe input.
- Operator collection1..16 unique existing fixed intervals; profile_id null.
- Preserve Decimal financial strings, UTC, closed-only state and causal evidence.
- No new strategy rules, Swing implementation, autonomous loop or exchange writes.
- Final one coherent commit: chore: generalize analysis contract for autonomous trading.
- No merge/push/tag; stop after verification/commit. Ch.1 incomplete.

## Task 1 — Versioned dynamic analysis boundary (TDD)

**Files:** modify analysis_config.py, analysis_report.py, analysis_service.py,
analysis_api_models.py, api.py; create tests/test_analysis_contract_v2.py.
Paths are under agent_trading/ unless tests/ is specified.
**Consumes:** existing bar_duration(tf), MCP adapter, ReplayEngine,
SQLiteAnalysisRepository, unchanged symbol-only HTTP request.
**Produces:** AnalysisConfig.required_timeframes; optional new_report collection
argument; v0.2 StrategyContext/AnalysisReportV2 and discriminated AnyAnalysisReport.

- [x] Write focused tests using existing complete fake SDK transport and real
  normalizer/core/SQLite/HTTP. Independently assert the defaults and1H/5m payload:
  `{"profile_id":null,"required_timeframes":["1H","5m"]}`,
  decision_as_of10:30Z from5m even without15m, exact price strings, real two-series
  snapshot/timeline/provenance, immutable retrieval and no exchange orders.
- [x] Reject empty/duplicate/unsupported/malformed operator collections and HTTP
  chart/decision timeframe inputs. Verify future1D can be represented safely
  by the wire without claiming runtime calendar support.
- [x] Verify original v0.1 GET/history/key replay and mixed versions, context-key
  conflict, v0.2 key/context/candle consistency and causal rejection.
- [x] Run focused tests before production changes:
  `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_analysis_contract_v2.py -v`.
  Confirm failures identify missing collection/version support, not bad fixtures.
- [x] Add BASELINE_TIMEFRAMES in analysis_config.py, immutable validated
  required_timeframes and ANALYSIS_REQUIRED_TIMEFRAMES env handling.
- [x] Build new_report(..., required_timeframes=BASELINE_TIMEFRAMES) with
  analysis-report-v0.2 and honest strategy_context. Keep events version unchanged.
- [x] Replace service's fixed loops/core config/readiness with configured collection.
  Select cutoff with:
  `min(self.config.required_timeframes, key=bar_duration)`;
  validate all histories before selection and retain existing causal trimming.
  Keep the legacy default symbol fingerprint; include canonical alternative
  requirements in non-baseline fingerprints.
- [x] Keep AnalysisReport as v0.1 legacy model; add AnalysisReportV2 with generic
  bounded interval identifiers and strategy_context. Match keys/context/candles
  and reject decision evidence later than cutoff. Route/history response types
  use `Annotated[AnalysisReport | AnalysisReportV2, Field(discriminator="schema_version")]`.
- [x] Reproduce two legacy nested-schema regressions before their correction:
  v0.1 must reject a5m candle and1D error. Retain Candle/Timeframe/ProductError
  legacy types and add v0.2-only nested overrides; both regressions then pass.
- [x] Run focused and full suite; fix implementation regressions, preserve150 tests.

## Task 2 — Current shared memory and completion audit

**Files:** existing AGENTS.md, README.md, docs/PROJECT_STATE.md, HANDOFF.md,
NEXT_TASK.md, SOURCE_REGISTRY.md and specs/product-mvp-v0.1.md;
new v0.2 spec/ADR011 and this plan.
**Consumes:** actual test/runtime compatibility evidence.
**Produces:** current autonomous direction/architecture, honest state, exact
SWING ENGINE R&D / SPEC next task, handoff and source record.

- [x] Preserve old v0.1 spec, ADR010, original smoke evidence and core/CLI/MCP/
  repository/JSONL files byte-for-byte. Record present manual behavior separately
  from future autonomous responsibilities, execution modes and decision outcomes.
- [x] Update next-task direction to Causal Swing R&D/spec with source/causal gates;
  chart-history extension is deferred rather than the next intelligence task.
- [x] Run full offline suite once after final implementation changes. Inspect
  all local Markdown references, diff whitespace, exact files and no-exchange-write
  route/tool evidence. Default real smoke command/path remains unchanged.
- [x] Audit attachment sections A..K against docs, code and tests; no unsupported
  module/outcome/candidate or live capability may be represented as implemented.
- [ ] Stage only scoped files and commit exact requested message; then verify
  clean branch, exact parent/hash and unchanged integration/UX checkpoint.

The final Git checkbox is verified after this document's containing commit;
use actual Git/final report for that result, avoiding a self-referential hash.
