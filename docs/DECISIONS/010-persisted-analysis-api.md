# 010 — Persisted public-market analysis API

- **Authority/date:** [U-ANALYSIS-API-001], explicit Ch.1 Backend Target #2, 2026-09-12.
- **Decision:** A bounded AnalysisService wraps the preserved async runtime
  MCP adapter and deterministic core. FastAPI only validates/transports requests.
  Freeze [analysis-api-v0.1](../specs/analysis-api-v0.1.md) before endpoints.
- **Knowledge boundary:** Capture cutoff before reads, independently validate
  4H/1H/15m freshness, select latest closed15m decision_as_of, and trim HTF
  evidence causally. Ticker/book remain separately time-qualified descriptive
  observations, never decision inputs. Decimal financial values serialize as strings.
- **Persistence:** stdlib sqlite3 with DELETE rollback journal, FULL synchronous,
  foreign keys, short transactions and bounded busy waits; no ORM/queue/server DB.
  Immutable terminal JSON and terminal timeline event commit atomically.
  SHA-256 idempotency key digest + public request fingerprint reserves identity.
  Existing schema2 JSONL core audit remains separate, unique per analysis.
- **Failure/ownership:** One worker/application instance owns the DB. Missing,
  stale or malformed required data yields FAILED/null action, never NO_TRADE.
  Startup marks crash-abandoned RUNNING reservations PROCESS_INTERRUPTED.
  SQLite/filesystem atomicity and multi-instance coordination are not claimed.
- **Readiness:** Bounded local storage health plus cached successful full MCP
  analysis, TTL/candle freshness and failure invalidation. No network GET,
  implicit startup market run, background retry or stale transport fallback.
  A first explicit POST validates prerequisites while readiness is initially503.
- **Explanation/intelligence:** Template wording derives only from structured
  report; actual current decision remains NO_TRADE/STRATEGY_NOT_CONFIGURED.
  Four intelligence modules NOT_IMPLEMENTED; no new algorithm/risk/execution policy.
- **Evidence:** [Real product smoke](../product-analysis-smoke.md) verified five
  public reads, real MTF/core, immutable SQLite/API retrieval and no order.
  79 preserved +71 new offline tests passed. No strategy performance validation.
- **Consequences/debt:** Claude reviews v0.1 before parallel UX. Full persisted
  chart arrays, auth/CORS, background readiness, multi-instance lease, locks and
  Linux/container/Compose remain later approved work. Ch.1 is incomplete.

Primary engineering references: [FastAPI lifespan testing](https://fastapi.tiangolo.com/advanced/testing-events/), [SQLite journal modes](https://www.sqlite.org/pragma.html#pragma_journal_mode), [pinned FastAPI release](https://pypi.org/project/fastapi/0.141.1/). Exact installed versions and compatibility are established by the local tests/smoke, not inferred from these moving docs.
