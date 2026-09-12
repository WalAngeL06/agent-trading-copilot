# Handoff — autonomous analysis contract v0.2 correction

Updated: 2026-09-12. Last agent: Codex.
Status: **Contract/configurability correction verified; Ch.1 incomplete.**
Authorization: [U-AUTONOMOUS-CONTRACT-001]. Stop after the requested commit.

## Branch and scope

Only Agent Trading-backend / work/copilot-backend, initially clean at
`6c1af4b6f6cd8c22986b8436dd26d61f64de469d` with150 passing tests.
Target commit: `chore: generalize analysis contract for autonomous trading`;
obtain its exact hash from Git/final report, not this containing document.
Integration strategy-v0.1 and UX work/copilot-ux remain at
`24e1f465a886e2941a8ce2fce8fb51d53b643405`. No merge/push/tag/remote creation.

## Product correction and current behavior

The intended product is a self-hosted autonomous trading agent. Future START BOT
maintains required market state and evaluates approved strategies, Acceptance,
Trade Plan, Risk and authorized execution, with notification/audit.
Users configure permissions/risk/symbol scope; strategy profiles own required
timeframes. Display/inspection timeframe never changes strategy requirements.

Current POST /api/v1/analyses remains bounded manual/debug/test/audit/demo and
inspection. It does not start monitoring or execute a strategy. No full bot
loop, scheduler, queue, WebSocket, profile engine, Swing/strategy, frontend,
Telegram, LLM, PAPER execution, account/private path or LIVE switch was added.
[Future runtime/modes/outcomes ADR](DECISIONS/011-autonomous-runtime-contract.md).

## Exact v0.2 correction and compatibility

[Current contract](specs/analysis-api-v0.2.md).
[Historical v0.1](specs/analysis-api-v0.1.md) is byte-for-byte preserved.

- New reports use analysis-report-v0.2 and strategy_context with profile_id=null
  and actual required_timeframes. Null identifies absent strategy, not a fake profile.
- Timeframes is a bounded dynamic map matching that unique collection, not a
  forever-fixed4H/1H/15m schema. Per-timeframe status/freshness/evidence remain honest.
- AnalysisConfig.required_timeframes is immutable operator configuration, default
  4H/1H/15m, with ANALYSIS_REQUIRED_TIMEFRAMES environment support. Current runtime
  accepts the existing10 fixed intervals; wire can represent future calendar labels
  without claiming runtime calendar support. Bound1..16; no request-side selection.
- decision_as_of means the causal deterministic knowledge cutoff. Current manual
  compatibility policy uses the latest closed candle of the shortest required
  fixed interval, after independent initial-cutoff freshness validation; trim
  every history to that cutoff. Default remains the same latest closed15m.
  A future strategy must specify its own causal trigger/ordering, not inherit a
  universal shortest-timeframe synchronization rule.
- Existing v0.1 SQLite JSON remains original. GET/history/key replay use strict
  schema-version discrimination for both versions; no synthetic context is
  inserted into old reports. Default key fingerprint stays compatible; differing
  required input sets conflict rather than silently replay another context.
- Five routes, strict symbol-only body, lifecycle/status/error/null rules,
  Decimal strings/UTC, deterministic wording, JSONL2 and SQLite1 remain.
- Current decision remains NO_TRADE / STRATEGY_NOT_CONFIGURED, no fake NO_SETUP,
  WAIT, TRADE_CANDIDATE, BLOCKED or EXECUTED. Those outcomes and ANALYZE/PAPER/LIVE
  are documented future concepts; PAPER/LIVE are unimplemented and LIVE disabled.

| Endpoint | Retained contract |
|---|---|
| GET /health/live | 200 ALIVE |
| GET /health/ready | Request-driven local probe/cached complete market validation; no network GET |
| POST /api/v1/analyses | Symbol-only, terminal resource201 including FAILED; idempotent replay200 |
| GET /api/v1/analyses/{analysis_id} | Original versioned report, invalid UUID422/unknown404 |
| GET /api/v1/analyses | Bounded limit1..50/offset0..10000, mixed original reports newest first |

Market Structure, Range, Deviation and Premium/Discount remain NOT_IMPLEMENTED;
Acceptance/Risk remain real placeholders NOT_EVALUATED. No fabricated prices,
levels, strategy signals, risk approval, simulated fills or PnL.

## Verification and real compatibility evidence

Initial150 passed. After correction: **150 preserved +20 focused =170 passed**,
zero failures/errors, exit0. New:3 collection,6 wire,8 configured service,
3 versioned HTTP tests. Existing150 test files unchanged.
Normal suite uses complete fake external SDK transport and real normalization,
Decimal/UTC domain, causal core, audit, SQLite and HTTP; no live network needed.

`./.venv/Scripts/python.exe -B -m unittest discover -s tests -v`

Focused tests verify non-baseline1H/5m and1m/1H/5m states, latest closed cutoff,
publication-lag trimming, future filtering, required collection validation,
provider enum drift/no fallback, original/mixed v0.1/v0.2 history/key replay,
context conflicts, honest absent profile and forbidden user/display timeframe
or mode input. Wire rejects mismatched map/candle identities and future evidence.
Two additional regressions preserve v0.1 nested candle/error timeframe enums;
the full legacy report JSON schema matches the Target #2 checkpoint exactly.

The existing unchanged **real product smoke command passed again**:

`./.venv/Scripts/python.exe -B -m agent_trading.product_smoke --node-path 'C:/Program Files/nodejs/node.exe' --server-path 'C:/Users/Serdar Arif/AppData/Roaming/npm/node_modules/@okx_ai/okx-trade-mcp/dist/index.js'`

| Fact | Actual new result |
|---|---|
| analysis_id / version | 517c6e4d-265b-4a9b-9860-cf7f8aa7e4a2 / analysis-report-v0.2 |
| symbol/site/status | BTC-USDT / tr / COMPLETED |
| requested_at | 2026-09-12T09:46:45.857565Z |
| completed_at | 2026-09-12T09:46:50.329515Z |
| decision_as_of | 2026-09-12T09:45:00Z |
| latest close4H /1H /15m | 08:00Z /09:00Z /09:45Z |
| retained candles | 100 per required baseline timeframe |
| profile_id / required_timeframes | null /4H,1H,15m |
| decision/reason | NO_TRADE / STRATEGY_NOT_CONFIGURED |
| spread / order_sent | string0.1 / false |
| reads/runtime | 5 public MCP reads; SDK2.2.0/ATK1.4.6, no CLI fallback |
| storage/audit | SQLite original report +10 real events; unchanged JSONL audit |

Fresh typed HTTP GET/history returned this report and the prior real
v0.1 report580b88e9-a183-4889-8cc7-b861fef405a4 identically to SQLite.
Old v0.1 received no strategy_context. No smoke-created market child remained;
pre-existing desktop MCP processes are unrelated to this product proof.
Original [Target #2 smoke record](product-analysis-smoke.md) remains unchanged.
An additional unchanged direct MCP-adapter smoke passed at 10:04 UTC:21 discovered
tools, all3 required public reads,10 received15m candles/1 open excluded/9 retained,
depth5 on both book sides, SDK2.2.0/ATK1.4.6/TR and order_sent=false.
This verifies baseline/runtime/contract compatibility, not autonomous operation,
strategy correctness or profitability.

## Files changed

No pre-existing uncommitted work; this correction changes16 files.

| File | Responsibility |
|---|---|
| agent_trading/analysis_config.py | Immutable required collection/operator environment |
| agent_trading/analysis_report.py | v0.2 context and collection-driven report |
| agent_trading/analysis_service.py | Collection-driven reads/state/cutoff/readiness and context-safe manual idempotency |
| agent_trading/analysis_api_models.py | Dynamic v0.2 validation and retained v0.1 schema discriminator |
| agent_trading/api.py | Same routes with versioned response types/OpenAPI metadata |
| tests/test_analysis_contract_v2.py | 20 focused real-boundary regression tests |
| docs/specs/analysis-api-v0.2.md | Current wire/product correction |
| docs/DECISIONS/011-autonomous-runtime-contract.md | Future runtime/modes/outcomes/dependency responsibilities only |
| docs/superpowers/plans/2026-09-12-autonomous-analysis-contract.md | Implementation/completion checklist |
| AGENTS.md | Persisted user direction/current boundary |
| README.md | Current product intent/API/configuration/compatibility |
| docs/PROJECT_STATE.md | Actual state/counts/evidence/debt |
| docs/HANDOFF.md | This handoff |
| docs/NEXT_TASK.md | SWING ENGINE R&D / SPEC, pending next instruction |
| docs/SOURCE_REGISTRY.md | Separate user correction and compatibility evidence |
| docs/specs/product-mvp-v0.1.md | Current direction amendment and historical baseline annotations |

Original trading core, CLI/MCP adapters/runtime, SQLite repository, JSONL journal,
product_smoke.py, dependency configuration, all150 prior tests and v0.1 analysis
spec/ADR010/original smoke evidence are unchanged. Ignored .venv/runs/SQLite/audit
and credential stores never enter the commit. No exchange write path exists.

## Next task and limitations

**SWING ENGINE R&D / SPEC — Causal Swing Engine** is the next intelligence task,
only under the next explicit user instruction. Resolve source-labelled swing
confirmation, swing_time/confirmed_at, candidate initialization/ties/retention,
causal prefix invariance and necessary equal-time ordering before any engine code.
Full MarketStructure N-1–N-7 stay blocked; [D-DD-MSB-001]/[U-PD-001] preserved.
Dependency: Swing -> Market Structure -> Range -> Premium/Discount -> Deviation
-> Acceptance -> Trade Plan -> Risk -> Execution.

Chart-history extension is deferred; reports still retain latest/counts rather
than persistent full candle arrays. Future autonomous trigger/durable evaluation
identity, approved profiles, calendar bars, PAPER accounting, authorization,
continuous recovery/refresh, multi-instance leases, UX review, auth/CORS,
transitive locks and Linux/deployment validation remain unimplemented.
ANALYZE/PAPER/LIVE are contract concepts; current SHADOW is intent logging only.
Do not auto-start Swing, chart/UX or bot work after this commit. Ch.1 incomplete.
