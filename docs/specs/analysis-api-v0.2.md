# Analysis API v0.2 — autonomous-agent contract correction

Status: **CURRENT CONTRACT CORRECTION**, 2026-09-12.
Authority: [U-AUTONOMOUS-CONTRACT-001]. Starting checkpoint:
`6c1af4b6f6cd8c22986b8436dd26d61f64de469d`.
Codex owns the contract; Claude UX review precedes frontend implementation.
Ch.1 remains incomplete.

## Product direction and boundaries

The intended product is an open-source, self-hosted autonomous trading agent.
Its future START BOT runtime maintains market state, evaluates approved
strategy requirements, constructs candidates/plans, passes Acceptance and Risk,
routes authorized execution and notifies/logs results. Users configure symbol
scope, permissions and risk. They do not choose a trading decision timeframe.

`POST /api/v1/analyses` remains the existing bounded manual/debug/testing,
audit/demo and inspection entry point. It does not start a bot. This correction
adds no autonomous loop, scheduler, queue, WebSocket, Swing/strategy engine,
frontend, Telegram, LLM, private account integration or exchange write path.
The future runtime and execution boundaries are specified in
[ADR 011](../DECISIONS/011-autonomous-runtime-contract.md).

**DISPLAY / INSPECTION TIMEFRAME** chooses which existing evidence a UI displays.
**STRATEGY REQUIRED TIMEFRAME** determines the data/state needed by an approved
strategy profile. Display choice never changes required inputs or decisions.
The HTTP request remains strict symbol-only JSON. No chart_timeframe, user
decision timeframe, execution mode or strategy parameters are accepted.

## Timeframe architecture

An eventual approved strategy profile supplies required timeframes to the
market-data/runtime layer. State is isolated by symbol and timeframe; all
required states pass normalization, closed-candle, freshness and causal gates.
4H / 1H / 15m is the **CURRENT VERIFIED BASELINE**, not a permanent schema limit
or a completed trading strategy.

Current `AnalysisConfig.required_timeframes` is an operator-owned immutable,
nonempty, unique ordered collection. Default: (`4H`, `1H`, `15m`).
`ANALYSIS_REQUIRED_TIMEFRAMES` may configure a comma-separated collection
before startup. It is an operational inspection baseline while no strategy
profile is implemented; it does not supply missing trading algorithms.
The future profile must supply requirements through this boundary rather than
letting a chart selector override them.

Current execution supports only the existing fixed-interval normalizer/core:
1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H.
Collection bound: 1..16 unique identifiers; unsupported runtime bars fail
configuration before a provider call. Discovery must still accept each
requested bar in the actual MCP tool schema; no undocumented fallback.

The wire identifier is a bounded positive interval label matching
`^[1-9][0-9]{0,2}(?:m|H|D|W|M)(?:utc)?$`, maximum16 characters.
A contract can therefore represent future daily/calendar evidence without
claiming today's normalizer can process it. Calendar/session bars, including
1D, need explicit exchange-boundary semantics before runtime support.
Example-only roles context=1D/4H, setup=1H/15m, execution=5m/1m are not strategy
rules, defaults or implemented permissions.

## Versioning and HTTP compatibility

[Analysis API v0.1](analysis-api-v0.1.md) is preserved unchanged as historical
Target #2 contract. Existing SQLite reports stay v0.1 and are returned exactly
as stored, with no synthetic strategy_context or recalculation.

New reports use `schema_version: analysis-report-v0.2`.
The existing five endpoints, request, status codes, bounded workflow/history,
sanitized errors, live/readiness policy, Decimal/UTC rules and audit behavior
remain. GET/history/idempotent replay accept both report versions, discriminated
by schema_version. Consumers inspect the version; v0.2 is a contract revision,
not a new /api/v2 route or an automatic v0.1 migration.
Mixed-version history returns each original report. The original v0.1 nested
candle/error timeframe enums and report schema stay unchanged; extensible
CandleV2/TimeframeV2/ProductErrorV2 models belong only to v0.2.

SQLite user_version remains1: the existing final JSON column already supports
versioned reports. No schema migration or historical JSON rewrite is needed.
Core JSONL remains schema_version2; timeline remains analysis-events-v0.1.

Idempotency still identifies an original manual request. The default baseline
retains the historical symbol fingerprint so old keys replay their original
v0.1 report. A different required-timeframe set has a distinct canonical
fingerprint and conflicts with reuse of an old key (409); a new key is needed.
Collection order is not a different input set. No duplicate evaluation policy
for the future continuous runtime is implemented by this manual mechanism.

## v0.2 report

All v0.1 top-level fields remain, with the following corrections/addition:

| Field | v0.2 semantics |
|---|---|
| schema_version | analysis-report-v0.2 |
| strategy_context.profile_id | Nullable profile identifier (1..128 characters when present); current service always emits null because no strategy exists |
| strategy_context.required_timeframes | Nonempty unique list of actual configured requirements for this analysis, 1..16 |
| timeframes | Map keyed by those identifiers; exactly matches required_timeframes, independent of the default three |
| decision_as_of | Causal knowledge cutoff actually used by the deterministic analysis; null before a snapshot is built |

The unchanged fields are analysis_id, symbol/site/status,
requested_at/started_at/completed_at, market ticker/spread/orderbook_summary,
per-timeframe latest_closed_candle/count/latest_close_time/observed_at/
data_status/freshness, six modules, current decision, deterministic explanation,
sanitized evidence/sources/errors and real timeline.
Each candle must match its map key and report symbol. Missing or unattempted
requirements remain explicit MISSING/FAILED/NOT_EVALUATED entries; their presence
does not claim successful data retrieval.

All financial values remain strings at JSON boundaries and Decimal internally.
UTC timestamps retain separate creation, decision, provider and observation
meanings. Ticker/book remain descriptive with decision_input=false.

Example current context (not an implemented strategy):
`{"profile_id":null,"required_timeframes":["4H","1H","15m"]}`.
An operator inspection using 1H/5m produces those two entries/context values;
it still returns the existing unconfigured-strategy decision, not a setup.

## Causal knowledge time

decision_as_of describes causal input availability, not a permanently selected
15m timeframe, display choice, completion time, or later ticker/book arrival.
Every decision input must be closed and causally available at that cutoff.
Future derived evidence also requires confirmed_at <= decision_as_of;
swing_time and confirmed_at are separate. A future suffix cannot change a
past then-known evaluation.

The current manual fixed-interval implementation retains a simple compatibility
policy: validate all required histories against the initial started_at cutoff
first; select the latest closed candle of the shortest required interval as the
snapshot cutoff; trim every required history to closes <= that cutoff; require
each remaining history to be nonempty. With the default collection this is
the same latest closed15m cutoff already verified.

This is an operational policy for the current unconfigured inspection path,
not a synchronization or setup rule imposed on future strategies. The later
Swing/Strategy/runtime spec must define its own causal evaluation trigger,
availability and equal-time ordering before implementation. No all-timeframe
same-close requirement, invented pivot threshold or intrabar ordering is added.

Freshness still compares each series independently with its own expected
close/publication grace at started_at. An older normal4H close is not measured
by ticker age. Required-tool/schema failure, missing/stale/malformed/gapped data,
observation failure, audit/storage/core failure remains FAILED with null action.
Successful default behavior remains NO_TRADE / STRATEGY_NOT_CONFIGURED.
No WAIT/NO_SETUP label is inferred from missing strategy configuration.

## Future decisions and execution

Report lifecycle RUNNING/COMPLETED/FAILED is operational, separate from future
strategy/execution outcomes. Current decision keeps action/reason_codes/
order_sent unchanged. NO_TRADE / STRATEGY_NOT_CONFIGURED is not a strategy verdict.

Reserve a future decision outcome extension that distinguishes NO_SETUP, WAIT,
TRADE_CANDIDATE, BLOCKED and EXECUTED, with candidate/acceptance/risk/execution
evidence and explicit reasons. These names are conceptual, absent from current
responses and current active action enums. Introducing them requires the
approved strategy/acceptance/risk/execution contracts; it cannot rename the
current placeholder or convert a data failure into a trading outcome.
[ADR 011](../DECISIONS/011-autonomous-runtime-contract.md) defines the boundaries.

Conceptual final-product modes: ANALYZE produces analysis/plans without orders;
PAPER simulates execution; LIVE performs real exchange execution only when
explicitly enabled and authorized. PAPER and LIVE are unimplemented now.
ANALYZE is the conceptual current behavior, not a new mode input or live switch.
Historical SHADOW means intent-only logging and is not PAPER execution or PnL.
LIVE remains disabled and outside the current hackathon execution scope.

## UX handoff and verification

Stable: version-discriminated original retrieval, dynamic timeframe map/context,
causal knowledge meaning, financial strings/UTC, honest modules/decisions,
unchanged request/routes/errors and real events. UI iterates actual map keys;
any later display selector stays outside strategy requirements.
Provisional: operational collection/retention/freshness defaults, exact template
wording, future profile roles, causal triggers and future outcome payloads.
No intelligence values or future outcomes are fabricated.

Focused verification must exercise default4H/1H/15m, a non-baseline configured
collection through real normalization/core/SQLite/HTTP, old-version retrieval,
strict symbol-only requests, invalid collections, causal cutoff/evidence and
zero exchange writes. Preserve all150 existing tests. Real default smoke is
the unchanged explicit product-smoke path; prior evidence remains historical.

Next trading-intelligence task: **SWING ENGINE R&D / SPEC — Causal Swing Engine**.
Resolve the necessary source-labelled definitions/causal fixtures first;
MarketStructure N-1–N-7 and original [D-DD-MSB-001]/[U-PD-001] remain unresolved
or preserved. This correction does not implement or approve a Swing algorithm.
