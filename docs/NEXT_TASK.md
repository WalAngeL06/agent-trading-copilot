# Current next task — STOP after integration verification

2026-09-12. Only the requested three-commit integration and verification are
authorized on `work/hackathon-integration`. Run full Python tests, frontend
`npm install`, `npm run build`, `npm test`, and verify clean Git status. Report
HEAD, source/included commits and results, then STOP. No new features, push/tag
or automatic continuation of the historical source-branch plans below.

---

# Next task — Web App shell complete; awaiting instruction

Updated: 2026-09-12. Worktree/branch: Agent Trading-webapp / work/webapp.
Current frontend authority: [U-WEBAPP-SHELL-001].

Stop after the requested frontend checkpoint. Do not auto-start integration,
strategy algorithms, Swing, execution, bot, authentication or deployment.

When explicitly authorized later, read [shell handoff](webapp-shell.md), the
local spec and current analysis v0.2 contract. Review/freeze bot lifecycle,
strategy capabilities/versioned save and event contracts with the backend owner.
Replace src/api/index.ts's mock factory with a typed adapter. Preserve Decimal
strings/UTC, original report versions, actual errors/unconfigured outcomes,
unavailable modules and disabled LIVE execution.

Swing work is independent and is not a prerequisite for this shell.
The prior backend intelligence next-task record is retained below as history;
it is not the next instruction for this worktree.

---

---

# Next task — STOP after OKX capability audit

## Current branch boundary [U-OKX-CAP-001]

2026-09-12. `work/okx-capabilities` in Agent Trading-okx was created from
`9d842077581f51b8264344fb331d1123665955e7` for capability research only.
[Results](research/okx-tr-capabilities-2026-09-12.md);
[exact runtime names and evidence](research/okx-tr-capabilities-2026-09-12.json).

Commit `research: verify OKX account earn and execution capabilities`, then
STOP. No merge/push/tag or automatic integration. No Swing, strategy, frontend,
trades, fund movement, Earn enablement or LIVE work is authorized here.

A possible separately approved next integration is an owner-only read contract
for trading/funding balance, savings balance and balance-derived Auto Earn
flags. Independent TR authentication is required: connected desktop reads work,
local CLI and fresh self-hosted MCP have no private auth. Read-only server mode,
an explicit client allowlist, schema discovery, exact Decimal/UTC handling,
private-log sanitization and nonzero OKX-code gates precede a real-account read
proof. Earn simulation returned 50038; do not promise simulated Earn or tested
write support.

## Preserved backend next-task context

The historical checkpoint plan below is preserved as context and must not
auto-start from this capability branch.

# Next task — SWING ENGINE R&D / SPEC

Updated: 2026-09-12. Ch.1 remains incomplete.
Current contract correction: [U-AUTONOMOUS-CONTRACT-001].
**Await the next explicit user instruction; do not auto-start implementation.**

## Starting point

Read AGENTS -> PROJECT_STATE -> HANDOFF -> this file, then
[analysis v0.2](specs/analysis-api-v0.2.md),
[autonomous runtime ADR011](DECISIONS/011-autonomous-runtime-contract.md),
[Market Structure draft](specs/market-structure-v0.1.md) and
[SOURCE_REGISTRY](SOURCE_REGISTRY.md).
Preserve historical [v0.1](specs/analysis-api-v0.1.md) and smoke evidence.

Backend worktree/branch: Agent Trading-backend / work/copilot-backend.
Correction parent:6c1af4b6f6cd8c22986b8436dd26d61f64de469d.
Obtain correction hash from Git/final report; verified baseline170 tests.
Integration/UX remain at Ch.0. No merge/push/tag/remote creation.

## Exact next trading-intelligence task

**SWING ENGINE R&D / SPEC — Causal Swing Engine**, before strategy-engine code.

Study the existing source-confirmed DD rules [D-DD-MSB-001] and explicitly
separate their qualitative meaning from unresolved algorithmic definitions.
The repository lacks the original DD recording/transcript; request missing
source/clarifications when needed rather than creating an attestation.
Do not silently substitute generic SMC, a library pivot or a 2/3/5-bar rule.

The separately authorized R&D/spec should resolve or explicitly leave pending:

- Observable opposing movement that confirms a swing, and its first knowable
  closed-candle evaluation (N-1).
- Candidate identity/replacement/ties, meaningful-versus-incidental extremes
  and any responsibility linkage needed downstream (necessary N-2).
- Causal initialization, insufficient/truncated history, retention and
  immutable evidence identity (necessary N-3).
- swing_time versus confirmed_at/recognition time, no intrabar precision
  invented from OHLC, equal-time per-symbol/TF ordering (necessary N-7).
- Prefix-invariant replay/bootstrap and future-suffix tests, independent state
  by symbol/timeframe and safe missing/stale/revised-data behavior.

Document inputs/state/events/statuses and source-labelled hand-checked causal
fixtures. Any numerical threshold or confirmation predicate is
**ALGORITHMIC DEFINITION PENDING** until approved. No SwingEngine or downstream
implementation is authorized by the present correction. Full
MarketStructureEngine still needs N-1–N-7, not merely a Swing spec.

Dependency sequence:
Swing -> Market Structure -> Range -> Premium/Discount -> Deviation ->
Acceptance -> Trade Plan -> Risk -> Execution.
This does not authorize entries, sizing, acceptance or real execution.
Premium/Discount stays context, no universal EQ reclaim; DD HTF side blocks
and [U-PD-001] remain separate/preserved.

## Preserved product boundaries and deferred work

The intended product is an autonomous trading agent. Approved future profiles
own required timeframes; user display selection cannot choose trading inputs.
Current manual/debug analysis is bounded, default4H/1H/15m, honest
NO_TRADE / STRATEGY_NOT_CONFIGURED, Decimal/UTC and real MCP -> core ->
v0.2/SQLite/API. Original v0.1 records remain unchanged.

AutonomousRuntime, continuous monitoring/deduplication, PAPER simulator and
LIVE authorization/execution remain specs/future work. LIVE is disabled and
unimplemented. No private/account/order path or usable live switch exists.
P0.5 still needs a separately approved meaningful deterministic intelligence
slice; the unconfigured placeholder does not satisfy it.

Bounded full-chart-history persistence/API is a deferred product extension,
not the next intelligence foundation. UX/Telegram/LLM/deployment and later
Range/Deviation/source intake stay outside this next R&D/spec until authorized.
