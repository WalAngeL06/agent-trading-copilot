# Handoff — Ch.1 Backend Target #2

Updated: 2026-09-12. Last agent: Codex.
Status: **Product analysis service/API/persistence verified; Ch.1 incomplete.**
Authorization: [U-ANALYSIS-API-001]. Stop after the requested backend commit.

## Branch and scope

Only `C:/Users/Serdar Arif/Desktop/Agent Trading-backend`,
`work/copilot-backend`, starting clean at
`cd686755cc1a01d032510806331ccf79267ed5af` (79 passing tests).
Target commit: `feat: add persisted market analysis API`; obtain its exact
hash from Git/final report, not this self-containing document.
Integration `strategy-v0.1` and UX `work/copilot-ux` stay at Ch.0
`24e1f465a886e2941a8ce2fce8fb51d53b643405`; no working files there were edited.
No merge, push, tag or remote creation.

## Delivered product flow

AnalysisService validates an operator allowlist (BTC-USDT default), atomically
reserves identity, owns one bounded workflow and calls the preserved real SDK
MCP adapter for ticker, 4H/1H/15m and depth-five book. Existing normalization,
a fresh causal MarketSnapshot/ReplayEngine, real current decision and separate
live observations produce the stable report, deterministic explanation and
SQLite history. FastAPI routes contain no trading semantics.

| Endpoint | Contract |
|---|---|
| GET /health/live | ALIVE, no dependencies |
| GET /health/ready | Bounded local storage probe + cached successful full-market validation; 503 until first success, after failure, expiry or stale candle boundary |
| POST /api/v1/analyses | Strict symbol-only JSON, terminal resource201 (COMPLETED or FAILED), idempotent replay200 |
| GET /api/v1/analyses/{analysis_id} | Original report; unknown UUID404, invalid UUID422 |
| GET /api/v1/analyses | Default20/max50, offset0..10000, original reports newest first |

[Frozen wire/UX contract](specs/analysis-api-v0.1.md) and strict OpenAPI models
define schema_version, identity/status, requested/start/completion times,
decision_as_of, ticker/spread/book summary, 4H/1H/15m latest closed candle/count/
times/freshness/status, six module statuses, actual decision/reasons/order_sent,
template explanation, evidence, MCP sources, sanitized errors and real timeline.
All financial JSON is string-valued; domain Candle/observations and spread
arithmetic retain Decimal. Opening timestamps never become close knowledge times.
Later ticker/book are descriptive, decision_input false, outside the snapshot.

Market Structure, Range, Deviation and Premium/Discount are NOT_IMPLEMENTED,
with ALGORITHMIC_DEFINITION_PENDING. Actual acceptance/risk are NOT_EVALUATED.
Current success is NO_TRADE / STRATEGY_NOT_CONFIGURED, never a valid-setup claim.
Missing/stale/malformed/gapped data or MCP/normalization failure produces FAILED,
null action, no order and a report-derived explanation; no WAIT/NO_TRADE fallback.

## SQLite, concurrency and audit

Stdlib sqlite3, user_version1, DELETE rollback journal, foreign keys,
synchronous FULL and bounded busy timeout. Configurable DB/audit/runtime paths,
limits and operational freshness settings; no strategy or live configuration.
One API worker/instance owns one database. Short parameterized transactions;
MCP calls never hold a database transaction. Final report and terminal event
commit together; terminal reports/events cannot be overwritten through repository.
UTC metadata is normalized to fixed microsecond precision for exact history sorting.

Optional Idempotency-Key is validated and only its SHA-256 digest is stored.
Atomic unique-key reservation + symbol/version fingerprint resolves racing claims.
Same key/request terminal replay has no provider rerun; running409,
changed request409; excess new workflow503 with no fictitious reservation.
No key creates a distinct analysis. Startup recovers abandoned RUNNING records
as FAILED PROCESS_INTERRUPTED once, under the single-instance ownership model.

Each analysis has an exclusive-created ignored JSONL file using unchanged core
schema_version2. SQLite is canonical product history; it does not replace audit.
Audit must write/close before committing analytical success. Filesystem/SQLite
are not atomic together: a storage failure may leave an audit and running
reservation, returns503, and startup later marks the reservation interrupted.

Readiness is request-driven: startup initializes/recovers storage without market
reads, first successful POST validates prerequisites, GET ready has no network.
Default validation cache TTL60s and required-candle freshness are checked.
Use a fresh request to recover/refresh; there is no retry/background ingestion.

## Verification

**79 old + 71 new = 150 tests passed**, zero failures/errors, exit0.
New: 12 repository +37 service +18 API +4 product smoke.
Full Windows command after installing optional extras in ignored .venv:
`./.venv/Scripts/python.exe -B -m unittest discover -s tests -v`.
Normal tests are offline: only the SDK transport is fake; normalization,
Decimal domain contracts, immutable MTF snapshot, core, audit, SQLite and HTTP
serialization are real. FastAPI/HTTPX test dependencies are installed once;
normal tests require no Node/ATK/MCP connection, credentials or internet.
The original 79 test files and all trading/CLI/MCP foundation code are unchanged.

Separate **real product smoke PASSED** at 2026-09-12T09:07 UTC:
analysis `580b88e9-a183-4889-8cc7-b861fef405a4`.
MCP SDK2.2.0 / ATK1.4.6; five actual public reads; 100 closed candles per TF;
decision_as_of09:00Z; 4H latest08:00Z, 1H/15m09:00Z; spread string0.1;
NO_TRADE / STRATEGY_NOT_CONFIGURED, order_sent false.
A new SQLite connection and actual API GET/history returned the identical
real stored report; strict wire validation/UTC/financial strings/audit/10 events/
DELETE journal verified. No smoke child or temporary public home remained.
Dependency check passed. [Permanent real evidence](product-analysis-smoke.md).
No empirical strategy/profitability claim.

## Files changed

No pre-existing uncommitted work. This target changes 25 files:

| File | Responsibility |
|---|---|
| agent_trading/analysis_config.py | Operator-only bounded product configuration |
| agent_trading/analysis_report.py | Wire construction, freshness, exact spread, deterministic wording |
| agent_trading/analysis_repository.py | SQLite metadata/report/events, idempotency/recovery/health |
| agent_trading/analysis_service.py | Serialized bounded MCP/MTF/core/report workflow |
| agent_trading/analysis_api_models.py | Strict financial-string OpenAPI schemas |
| agent_trading/api.py | Five thin product transport endpoints/lifespan/errors |
| agent_trading/product_smoke.py | Explicit real full-product smoke, concise sanitized summary |
| tests/analysis_fixtures.py | Complete public ATK-shaped fake external transport |
| tests/test_analysis_repository.py | Persistence, atomicity, race, exact history/recovery tests |
| tests/test_analysis_service.py | Real core/normalization/failure/readiness/causality tests |
| tests/test_analysis_api.py | HTTP/wire/idempotency/history/health/no-orders tests |
| tests/test_product_smoke.py | Same-service smoke/persistence/sanitization/exit behavior |
| pyproject.toml | Optional pinned product/test-product extras |
| docs/specs/analysis-api-v0.1.md | Frozen report/API/UX contract, stable vs provisional fields |
| docs/superpowers/plans/2026-09-12-persisted-market-analysis.md | Implementation and completion checklist |
| docs/DECISIONS/010-persisted-analysis-api.md | Product service/SQLite/knowledge/readiness decisions |
| docs/product-analysis-smoke.md | Actual real-data interoperability/core/persistence/API evidence |
| README.md | Product setup, API/sample request, readiness/config/smoke |
| AGENTS.md | Current authorization, implemented architecture and stopping boundary |
| CODEX.md | Current full-suite invocation reference |
| docs/PROJECT_STATE.md | Actual checkpoint/state/tests/debt |
| docs/HANDOFF.md | This handoff |
| docs/NEXT_TASK.md | Exact next backend proposal, pending instruction |
| docs/SOURCE_REGISTRY.md | Separate user authority and narrow infrastructure evidence |
| docs/specs/product-mvp-v0.1.md | Historical scope versus current delivered Target #2 |

Ignored artifacts: existing .venv and runs/product/analyses.sqlite3,
runs/analyses/580b88e9-a183-4889-8cc7-b861fef405a4.jsonl.
Runtime data/credential stores are never committed. No environment secrets copied.

## UX handoff and debt

Stable: v0.1 field names/types/nulls, statuses, Decimal strings/UTC,
time-qualified evidence, timeline event names, lifecycle/history/idempotency
and error envelope. Claude can rely on these after its contract review.
Provisional: exact template wording, operational defaults/readiness cadence,
source ordering, future error additions/intelligence/chart payloads.
Intelligence values do not exist. Retained histories are used in memory;
only latest closed candles plus counts are in the current persisted report.

Known debt: Claude's UX contract review; bounded chart-history persistence/API
extension; authentication/CORS before externally exposed personal deployment;
continuous freshness/recovery (currently explicit requests), multi-instance
ownership/lease enforcement, transitive lock and Linux/container/deployment
verification. No ownership coordination between multiple server instances is
claimed. Normal API lifespan shutdown assumes requests finish/cancel normally;
single-instance startup recovery handles crash-abandoned reservations.

Trading/domain semantics and original CLI are unchanged. No trade/private
adapter/client/route/live switch exists. No Telegram/frontend/LLM/intelligence/
PnL/own-MCP/Compose/Caddy was added. MarketStructure N-1–N-7 remain blocked;
Range source intake remains separate. [D-DD-MSB-001] / [U-PD-001] preserved.

Next backend proposal: **Target #3 — bounded closed-candle chart/history contract
and API**, with Claude review, only under the user's next explicit instruction.
Do not start it, merge, push or tag after this commit. Ch.1 remains incomplete.
