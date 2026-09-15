# Persisted market analysis API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Execute inline in the single authorized backend worktree; no concurrent checkout edits.

**Goal:** Deliver real BTC MTF MCP analysis through the preserved core, an exact report, SQLite history and thin FastAPI.
**Architecture:** AnalysisService owns one bounded workflow and a fresh engine per analysis. SQLiteAnalysisRepository owns short transactions; report dataclasses and deterministic explanation have no HTTP semantics. FastAPI and the explicit product smoke consume the same service.
**Tech Stack:** Python >=3.11, stdlib sqlite3, official mcp==2.2.0, ATK 1.4.6, FastAPI 0.141.1, Uvicorn 0.52.4; offline unittest with HTTPX 0.28.1.
**Spec:** [analysis-api-v0.1](../../specs/analysis-api-v0.1.md).

## Global Constraints

- Python >=3.11. Decimal internally; all financial JSON values are strings.
- UTC ISO-8601 timestamps end in Z. Site is fixed to tr.
- SQLite rollback journal DELETE; no ORM or network database.
- Exactly one API worker / application instance owns a database and audit directory.
- No queue, retry, CLI fallback, live toggle or generic tool/shell endpoint.
- Only Agent Trading-backend / work/copilot-backend, starting cd686755cc1a01d032510806331ccf79267ed5af.
- Preserve all 79 tests and core/CLI; one final requested commit, no merge/push/tag.
- User approved the detailed target; routine design choices execute under that authorization.

### Task 1: Freeze contract and persistence lifecycle

Files: create docs/specs/analysis-api-v0.1.md, agent_trading/analysis_report.py,
agent_trading/analysis_repository.py, tests/test_analysis_repository.py.

Interfaces:
`new_report(analysis_id: str, symbol: str, now: datetime, grace: int) -> dict`;
`deterministic_summary(report: dict) -> str`;
`SQLiteAnalysisRepository(path, timeout=1)`;
`initialize(), reserve(report, key_digest, fingerprint), append_event(id,type,at,data),
finalize(report,type,at,data), get(id), history(limit,offset), health(),
recover_interrupted(now)`. All repository IO is synchronous and service calls it
with asyncio.to_thread. Terminal reports are wire dictionaries.

- [x] Read current docs/Git and verify clean checkpoint with 79 passing tests.
- [x] Write/freeze spec above before any endpoint implementation.
- [x] Write tests: reserve twice, changed fingerprint, terminal immutability,
  atomic terminal timeline, restart persistence/recovery, DELETE journal and
  bounded locked database failure. Representative independent assertions:
```python
first = repo.reserve(draft, "same-digest", "BTC/v0.1")
second = repo.reserve(other_draft, "same-digest", "BTC/v0.1")
assert second.created is False
assert second.report["analysis_id"] == first.report["analysis_id"]
assert repo.get(first.report["analysis_id"])["decision"]["action"] is None
```
- [x] Run `python -B -m unittest discover -s tests -p test_analysis_repository.py -v`;
  expected missing-feature failure; implement focused models/repository, rerun green.
  Atomic finalize transaction: insert terminal event, serialize final report including
  ordered events, update only WHERE status='RUNNING'; rollback both on error.
- [x] Review against storage/time/null/idempotency contract before service work.

### Task 2: Bounded real service with causal prerequisites

Files: create agent_trading/analysis_config.py, agent_trading/analysis_service.py,
tests/analysis_fixtures.py, tests/test_analysis_service.py.

Interfaces:
`AnalysisConfig` operational DB/audit/runtime/freshness/timeouts/allowlist fields;
`AnalysisService(config, repository=None, mcp_factory=open_atk_mcp, clock=UTCnow)`;
`await startup()`, `await analyze(symbol, idempotency_key=None) -> AnalysisResult`
(report,created), `await readiness() -> dict`. ServiceError carries only fixed
code/status/optional ID. No shared mutable engine.

- [x] Write complete real-shaped fake MCP fixtures with separate 4H/1H/15m
  closed/current-open rows and exact long Decimal tokens. Fake only SDK transport;
  keep existing normalization, observation models, snapshot/core/journal/SQLite real.
- [x] Write service tests before implementation. Key expected behavior:
```python
result = await service.analyze("BTC-USDT")
assert result.report["decision"] == {
    "action": "NO_TRADE", "reason_codes": ["STRATEGY_NOT_CONFIGURED"],
    "order_sent": False}
assert result.report["decision_as_of"] == "2026-01-01T10:30:00Z"
assert result.report["timeframes"]["4H"]["latest_close_time"] == "2026-01-01T08:00:00Z"
assert result.report["market"]["ticker"]["observed_at"] > result.report["decision_as_of"]
```
- [x] Run service tests red. Implement reserve -> exclusive audit -> MCP five
  public reads -> independent cutoff freshness -> trim -> bootstrap -> evaluate
  -> deterministic report -> successful audit close -> atomic finalize.
- [x] Test stale/missing/malformed/gaps/timeout/tool drift/audit/store errors,
  neutral failed decision, real ordered timeline, recovery and no orders.
- [x] Test simultaneous same-key reservation, running409, different-key capacity503,
  cached readiness startup/degradation/recovery/expiration without network GET.
- [x] Run new repository/service tests and all 79 existing tests green.

### Task 3: Thin FastAPI contract and explicit product smoke

Files: create agent_trading/analysis_api_models.py, agent_trading/api.py, agent_trading/product_smoke.py,
tests/test_analysis_api.py, tests/test_product_smoke.py; modify pyproject.toml.

Interfaces: `create_app(config=None, service=None) -> FastAPI`;
strict symbol-only request; five spec routes; `await product_smoke.smoke(config) -> dict`
and `main(argv=None) -> int`, same service and SQLite, concise sanitized summary.

- [x] Install pinned optional product/test-product extras in existing ignored
  backend .venv; leave host Python untouched.
- [x] Write offline API tests red: validation without raw request echo, resource201,
  failed-resource201 with action null, replay200/conflict409/running409, byID404,
  pagination limits/history, live/ready, repository503, no private/tool/order routes.
```python
response = client.post("/api/v1/analyses", json={"symbol":"BTC-USDT"})
assert response.status_code == 201
assert client.get("/api/v1/analyses/" + response.json()["analysis_id"]).json() == response.json()
assert client.post("/api/v1/analyses", json={"symbol":"BTC-USDT","mode":"live"}).status_code == 422
```
- [x] Implement lifespan initialization and transport-only routes; no strategy code.
- [x] Write smoke tests red; implement summary without arrays/raw MCP/errors and
  verify persisted report can be retrieved by ID. Add --db-path/--audit-dir/
  --node-path/--server-path operator-only arguments.
- [x] Run API/smoke tests green then full suite in .venv.

### Task 4: Actual runtime proof, handoff and requested commit

Files: update README.md, AGENTS.md, docs/PROJECT_STATE.md, docs/HANDOFF.md,
docs/NEXT_TASK.md, docs/SOURCE_REGISTRY.md, docs/specs/product-mvp-v0.1.md;
create docs/product-analysis-smoke.md, docs/DECISIONS/010-persisted-analysis-api.md.

- [x] Run real product smoke from backend .venv: BTC ticker +4H/1H/15m+book MCP,
  core/report/audit/SQLite. Record concise exact public evidence and tool provenance.
- [x] Inspect stored report and events from a new repository instance; verify
  final immutable history, Decimal strings/UTC/closed cutoff/no orders.
- [x] Update docs with old/new counts, smoke status, stable/provisional UX contract,
  SQLite ownership/recovery/bounds and exact next backend task pending instruction.
- [x] Check every user section A-N against files/results; repair gaps, run relevant
  checks after repairs, inspect Git diff and confirm core/CLI/old tests untouched.
- [x] Run full suite and dependency check; no broader testing without new concerns.
- [ ] Commit only authorized task files on work/copilot-backend:
```text
feat: add persisted market analysis API
```
- [ ] Verify clean status and commit hash, report all required outcomes, STOP.

The final two Git steps are verified after this document's containing commit.
Consult Git and the final target report for their completion, not a self-referential
commit hash or an extra documentation-only commit. This never authorizes Target #3.
