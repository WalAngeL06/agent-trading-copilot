# Next task — shared product API contract

Updated: 2026-09-12. Chapter: **Ch.1 — Product MVP & UX**, incomplete.
Backend Target #1 runtime MCP gate is verified under [U-MCP-GATE-001].
**Do not auto-start this next task.** The current target ends after its requested
backend commit; await the next explicit user instruction.

## Read and verify the starting point

Read AGENTS.md → PROJECT_STATE → HANDOFF → this file, the
[product spec](specs/product-mvp-v0.1.md),
[runtime gate spec](specs/runtime-atk-mcp-gate.md),
[actual MCP evidence](runtime-atk-mcp-gate.md), SOURCE_REGISTRY and ADRs 006–009.
Inspect branch/status/log before edits; verify the target commit and current
suite. Backend is `work/copilot-backend` in
`C:/Users/Serdar Arif/Desktop/Agent Trading-backend`, descended from Ch.0
`24e1f465a886e2941a8ce2fce8fb51d53b643405`. Integration and UX remain at Ch.0;
preserve them. The current baseline is **79 tests** (36 original + 43 MCP).
No merge, push, remote creation or tag is authorized by the completed target.

## Proposed next deliverable — contract before parallel implementation

Codex defines; Claude reviews. Specify routes/request lifecycle, schema
version, exact Decimal string fields, symbol/timeframe limits, analysis identity,
candle decision `as_of`, separate ticker/book exchange/response observation
times, freshness/error/loading states, facts/evidence references, unavailable
modules, deterministic result/reasons, template explanation, history and
sanitized MCP provenance. Keep future intelligence labels distinct from
operational status and current `NO_TRADE / STRATEGY_NOT_CONFIGURED`.

Freeze request/response examples and expected behavior before frontend/backend
implement in parallel. This proposal does not create a schema, FastAPI endpoint,
SQLite store, frontend or Telegram flow. Current MCP returns immutable normalized
facts with provenance; it does not expose the raw ATK envelope to core callers.

## Later MCP/product wiring

The public SDK 2.2.0 / ATK MCP 1.4.6 TR gate passed real ticker/15m candles/book
calls and feeds an existing candle snapshot. Preserve it and the separate CLI
adapter; no silent fallback or development-tool MCP substitution.

After the shared contract and next implementation scope are approved, integrate
4H/1H/15m bootstrap/polling and report inputs with exact normalization,
per-symbol/timeframe isolation, causal closed filtering, visible errors and
explicit freshness. Keep later live facts out of past decision evidence.
Validate Linux/container operation and lock the actual deployment dependencies
when that deliverable is authorized. No exchange writes or LIVE switch.

## Preserved future priorities and algorithm gates

P0: BTC report/API, shared Analysis/History web/Mini App, chart, template
explanation, SQLite history, optional Telegram and easy Compose installation.
P0.5 before final demo requires an approved meaningful deterministic intelligence
slice with source-labelled causal fixtures. Data quality or renaming the
unconfigured placeholder to WAIT does not satisfy it.

Intended intelligence: Market Structure → Range → Deviation → LTF
confirmation/context. MarketStructure N-1–N-7 remain unresolved; no confirmed
DD Range source/spec exists. Range remains the next strategy-source ingestion
topic when authorized; record unresolved rules as **ALGORITHMIC DEFINITION
PENDING**, never substitute generic SMC/library defaults or magic thresholds.
Premium/Discount is context, not an entry trigger; EQ reaction is not universally
mandatory and DD ordinary HTF side blocks remain separate.

P1/P2 and excluded features remain governed by the frozen product spec. No
private/account tools, PnL, full portfolio or live execution are implied by the
completed public MCP gate. Ch.1 is not complete.
