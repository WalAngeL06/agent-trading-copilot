# Analysis API v0.1 — frozen backend / UX contract

Status: **FROZEN FOR BACKEND TARGET #2**, 2026-09-12.
Authority: [U-ANALYSIS-API-001], the user's explicit Target #2 instruction.
Codex owns this contract; Claude UX review remains a handoff step before parallel
frontend implementation. This target does not complete Ch.1.
Starting checkpoint: `cd686755cc1a01d032510806331ccf79267ed5af`.

## Scope and architecture

One public BTC-USDT request calls the existing real runtime MCP adapter for
ticker, 4H/1H/15m closed histories and a depth-five book; the existing engine
bootstraps a fresh causal snapshot and evaluates its current deterministic
pipeline. A thin application service builds an immutable final report and
persists history/timeline in stdlib SQLite. FastAPI is a transport adapter.
No intelligence algorithms, LLM, private reads, orders, frontend or deployment.

Python >=3.11. Decimal internally; all financial JSON values are strings.
UTC ISO-8601 timestamps end in Z. Site is fixed to tr.
SQLite rollback journal DELETE; no ORM or network database.
Exactly one API worker / application instance owns a database and audit directory.
No queue, retry, CLI fallback, live toggle or generic tool/shell endpoint.

## HTTP contract

| Route | Behavior |
|---|---|
| GET /health/live | 200, `{"status":"ALIVE"}`; no market/network/storage check |
| GET /health/ready | 200 READY or 503 NOT_READY; detailed sanitized prerequisites below |
| POST /api/v1/analyses | Strict JSON `{"symbol":"BTC-USDT"}`; synchronous bounded analysis |
| GET /api/v1/analyses/{analysis_id} | 200 original report, including FAILED; unknown UUID 404 |
| GET /api/v1/analyses | `limit` 1..50 (default 20), `offset` 0..10000 (default 0); newest first |

A newly persisted terminal analysis returns **201**, including a FAILED resource:
clients MUST inspect `report.status`, not infer analytical success from HTTP.
A terminal idempotent replay returns 200 with the identical original report.
Invalid request/symbol/UUID/key/pagination: 422. Unknown ID: 404.
Idempotency conflict or running reservation: 409. Capacity unavailable: 503.
Storage failure preventing resource creation/finalization: 503; never report
successful persistence. Error envelopes are `{"error":{"code":...,"message":...,
"analysis_id":null-or-UUID}}`, with fixed public messages and no request echo.

Request fields beyond symbol are forbidden. Default allowlist: BTC-USDT only;
operator configuration may supply a small explicit instrument allowlist.
HTTP requests never configure site, executable paths, strategy or execution.
Optional `Idempotency-Key`: 1..128 ASCII letters/digits/._:-, first character
alphanumeric. Store its SHA-256 digest, never its raw value. Reserve identity
and normalized symbol/API-version fingerprint atomically before external reads.
Same key/request while RUNNING: 409 ANALYSIS_IN_PROGRESS (existing ID).
Same key/different allowed symbol: 409 IDEMPOTENCY_CONFLICT.
Without a key each request creates a distinct analysis; no inferred candle-key
deduplication. Capacity is one active analysis, acquired before reserving a new
resource; rejected excess requests do not create fictitious timeline work.

History response: `{"items":[AnalysisReport,...],"limit":20,"offset":0,"total":N}`.
Sort by requested_at descending, then analysis_id descending. Retrieval never
recomputes using current data. RUNNING GET contains metadata, null decision,
partial real timeline, and unevaluated prerequisites; terminal GET is immutable.
No SSE/WebSockets/event route is needed: the report includes its timeline.

## Stable AnalysisReport fields

`schema_version` is `analysis-report-v0.1`. Every field below is present;
unknown/unavailable values are null, never fabricated zero prices or empty signals.

| Field | Type / semantics |
|---|---|
| analysis_id | UUID string |
| symbol, site | Allowed instrument string; tr |
| status | RUNNING, COMPLETED, FAILED; COMPLETED means data/core/audit/persistence succeeded, not a configured strategy |
| requested_at, started_at, completed_at | UTC strings; completed_at null only while running |
| decision_as_of | Latest validated closed 15m close; null until a causal snapshot was built |
| market.ticker | Normalized symbol/last/bid/ask strings and exchange_time/observed_at; null if unavailable |
| market.spread | value string, source ORDERBOOK, exchange_time/observed_at; null if unavailable |
| market.orderbook_summary | best_bid/best_ask {price,quantity} strings, bid_levels/ask_levels integers, exchange_time/observed_at |
| timeframes | Exactly 4H, 1H, 15m |
| timeframes[tf].latest_closed_candle | Existing closed Candle JSON, with string OHLCV; null if unavailable |
| timeframes[tf].candle_count | Retained closed history count; snapshot inputs only after decision_as_of is set; 0 if unavailable |
| timeframes[tf].latest_close_time | UTC close boundary or null |
| timeframes[tf].observed_at | MCP response observation time or null |
| timeframes[tf].data_status | NOT_EVALUATED, AVAILABLE, MISSING, FAILED |
| timeframes[tf].freshness | status FRESH/STALE/UNKNOWN, checked_at, expected_close_time, required_close_time, publication_grace_seconds |
| modules | market_structure, range, deviation, premium_discount, acceptance, risk |
| modules[name] | status AVAILABLE/NOT_IMPLEMENTED/NOT_EVALUATED/FAILED, reason_codes array |
| decision | action null or current NO_TRADE, reason_codes array, order_sent false |
| explanation | deterministic_summary string, derived only from structured report |
| evidence | Structured evidence_id/kind/reference/source_id/decision_input/close_time/observed_at; no raw payload |
| sources | source_id plus sanitized existing MCP provenance (transport/provider/site/tool/symbol/timeframe/request/response times/latency/success/error/filtering) |
| errors | code/message/stage/timeframe, all sanitized; empty on COMPLETED |
| timeline | Ordered sequence/type/at/data with schema_version analysis-events-v0.1 and analysis_id |

The four intelligence modules are NOT_IMPLEMENTED, reason ALGORITHMIC_DEFINITION_PENDING.
No structure direction, range levels, deviation, EQ or premium/discount value exists.
For a completed current pipeline, acceptance/risk are NOT_EVALUATED with actual
NO_CANDIDATE / NO_ACCEPTED_CANDIDATE reasons. On prerequisite failure they remain
NOT_EVALUATED / ANALYSIS_FAILED. Unimplemented modules never emit success events.
COMPLETED decision is the actual engine NO_TRADE / STRATEGY_NOT_CONFIGURED,
order_sent false. FAILED has action null and empty decision reason_codes; errors
explain failure. Data failure is never WAIT, NO_TRADE or a strategy verdict.

## Decimal and knowledge times

Capture started_at once, before connecting; it is the fixed candle cutoff.
Use the existing OKX normalizer: source opening timestamp plus bar duration
defines Candle.close_time, confirm=0 is excluded, closes after cutoff excluded.
Never reinterpret opening time as knowledge time. Use request limit
history_limit + 1 to accommodate the current open row; history_limit defaults
100 (1..299), an operational retention bound, not strategy sufficiency.

Validate each required history independently against started_at before choosing
decision_as_of. Expected close is its UTC fixed interval floor. Required close
is the interval floor of (started_at - publication_grace_seconds), default
60s (0..300); this tolerates publication lag only immediately after a boundary.
A latest close older than required close is STALE and fails the entire analysis.
A missing series, malformed/conflicting/gapped/unordered history fails too.
No automatic stale cache fallback. Empty closed result is MISSING_TIMEFRAME.
Only retain evidence at or before latest closed 15m decision_as_of. Revalidate
nonempty HTF histories after trimming; use the existing immutable snapshot.

Ticker/book exchange_time is provider time; observed_at is response arrival.
Reject exchange observation older than observation_max_age_seconds at arrival
(default 60s; explicit operational config), independently of candle freshness.
Ticker/book are descriptive live observations, always decision_input false;
they are excluded from the candle snapshot and deterministic decision inputs.
Their times may exceed decision_as_of. Spread comes from the single book's
best ask minus best bid with exact Decimal arithmetic; no cross-time quote mixing.
requested_at/start/completion, candle close and response times retain distinct meanings.

## Timeline and storage

Real event types: REQUEST_RECEIVED, MCP_CONNECTED, TICKER_FETCHED,
CANDLES_FETCHED (one per timeframe), ORDERBOOK_FETCHED, SNAPSHOT_BUILT,
DECISION_EVALUATED, ANALYSIS_COMPLETED, ANALYSIS_FAILED.
Sequence is monotonic per analysis, independent of wall-clock resolution.
Events contain only small public summaries: timeframe/count/source outcome,
snapshot counts/as_of, actual decision/reasons or sanitized error code.
No MARKET_STRUCTURE_SUCCEEDED, synthetic signal or hidden LLM reasoning.

Configurable SQLite path defaults to runs/product/analyses.sqlite3.
Short parameterized transactions; never hold a DB transaction during MCP calls.
Store metadata, final JSON and ordered events, schema user_version=1.
Use DELETE journal, foreign keys, synchronous FULL and bounded busy timeout.
Terminal report and terminal event commit together; guard against overwriting
a terminal report. SQLite is canonical product history. Each analysis gets
a unique exclusive-created ignored runs/analyses/{analysis_id}.jsonl audit
using the existing JsonlJournal/core schema_version=2; preserve old audit code.
Audit writing/closing must succeed before committing analytical success.
SQLite and filesystem are not one atomic transaction; persistence failure
can leave a completed audit and a running reservation, never false success.
On next single-instance startup, abandoned RUNNING reservations become FAILED
PROCESS_INTERRUPTED with one real recovery event; no provider rerun.

## Bounds, readiness and errors

Default MCP operation timeout 20s; reserved workflow timeout 60s.
Reservation/finalization have separately bounded local SQLite waits (default1s). Config permits
positive finite bounded durations. SDK cancellation/process cleanup and bounded
SQLite finalization occur before returning a failed resource. Do not silently
switch transports. One active workflow; other new analyses receive SERVICE_BUSY.
Idempotent terminal replay remains available while a different analysis runs.

Startup initializes/tests the repository and recovers abandoned records; it
does not fetch market data implicitly. Until the first successful complete
public MCP analysis, readiness is 503 MARKET_DATA_NOT_VALIDATED.
POST can be attempted while unready to validate/recover prerequisites.
GET ready performs a bounded local SQLite write/rollback health probe and
checks cached successful MCP/full-market validation, with no network request.
A failed analysis invalidates cached readiness. Cache expires after
ready_ttl_seconds (default 60s), or when a required candle is no longer fresh.
Reasons are explicit (repository/MCP/market unvalidated, stale, expired or failed).
A later successful analysis restores readiness. This is request-driven readiness,
not continuous ingestion, retry or automatic monitoring.

Known public errors include MCP_TIMEOUT, MCP_UNAVAILABLE, REQUIRED_TOOLS_MISSING,
TOOL_SCHEMA_DRIFT, MALFORMED_RESPONSE, PUBLIC_SCOPE_MISMATCH, STALE_TIMEFRAME,
MISSING_TIMEFRAME, INVALID_HISTORY, STALE_OBSERVATION, AUDIT_UNAVAILABLE,
PROCESS_INTERRUPTED, ANALYSIS_CANCELLED, PERSISTENCE_UNAVAILABLE and ANALYSIS_INTERNAL_ERROR. Preserve fixed known runtime
dependency/version categories; unknown provider exception text is discarded.
Failure reports may retain successfully retrieved public facts with their
honest freshness/data status, but never claim a successful decision.

## Examples and UX handoff

Request: `{"symbol":"BTC-USDT"}`.

Successful current decision:
`{"action":"NO_TRADE","reason_codes":["STRATEGY_NOT_CONFIGURED"],"order_sent":false}`.
Summary: "No trading strategy is currently configured. Market data was retrieved
successfully and the deterministic decision pipeline returned NO_TRADE."
A missing/stale error explicitly names the missing/stale timeframe in the summary.
FAILED decision: `{"action":null,"reason_codes":[],"order_sent":false}`.

Stable: the field names/types, null meanings, enums, decimal strings, time
boundaries, error-envelope shape, lifecycle/idempotency/history behavior and
real event types above. Frontend uses source/evidence IDs and paths to report
fields, not backend filesystem paths. Small event data values vary by action.
Provisional: exact template wording, future error additions, operational default
retention/grace/timeouts/readiness policy, source ordering and future intelligence
payloads. Additions require contract review; intelligence remains absent.
Claude must review this frozen backend contract before implementing shared UX.
Authentication/CORS, chart history arrays, background readiness refresh,
multi-instance ownership, Linux/deployment smoke and transitive locks are
separate future work. Existing CLI SHADOW entry point stays intact.
