# Next backend task — bounded closed-candle chart/history API

Updated: 2026-09-12. Ch.1 remains incomplete.
Backend Target #2 is verified under [U-ANALYSIS-API-001].
**Await the next explicit user instruction; do not auto-start this proposal.**

## Starting point

Read AGENTS → PROJECT_STATE → HANDOFF → this file, then
[analysis API v0.1](specs/analysis-api-v0.1.md),
[real product evidence](product-analysis-smoke.md), product spec and ADR010.
Backend worktree/branch: Agent Trading-backend / work/copilot-backend.
Parent checkpoint: cd686755cc1a01d032510806331ccf79267ed5af.
Obtain Target #2 commit hash from Git/final report; current baseline150.
Preserve integration/UX at Ch.0. No merge, push, tag or remote creation.

## Exact proposed Target #3

Codex defines and Claude reviews a bounded chart-history extension before
parallel frontend work. Persist the actual normalized closed 4H/1H/15m history
used by each analysis, then expose it through a typed read-only endpoint or
versioned report extension with explicit size limits, Decimal strings,
chronology, original analysis identity/as_of, provenance and available/error
states. Do not reconstruct historical evidence from fresh exchange reads.

Today's report deliberately exposes only latest closed candles/counts, not
large chart arrays. In-memory snapshots contain the histories; JSONL stores
core audit summaries. Neither source is a persistent full chart dataset.
Specify schema/version/backward compatibility, repository migration,
retention and limits before implementing the next extension. Review stable
v0.1 fields with Claude and provide hand-checked request/response examples.

Possible completion evidence for that separately approved target: chart data
retrieved after restart remains the original causal series; open/future rows
never appear; per-symbol/TF isolation, bounded pagination and exact JSON hold;
the existing150 tests remain green and meaningful new contract tests pass.

This is a proposal, not implemented work or authorization. No frontend,
Telegram, LLM, deployment or trading-intelligence code is implied.

## Preserved boundaries

Target #2 already provides real public MCP -> MTF/core -> report/SQLite/API,
deterministic explanation, failures/health/idempotency and real timeline.
Keep the independent CLI SHADOW flow intact. Request-driven readiness needs
a successful fresh analysis; no silent stale/CLI fallback.

P0 still needs shared UX, optional Telegram and Compose delivery. P0.5 final-demo
gate needs its own approved meaningful deterministic intelligence slice;
NO_TRADE / STRATEGY_NOT_CONFIGURED is honest infrastructure, not that slice.
MarketStructure N-1–N-7 remain ALGORITHMIC DEFINITION PENDING. Range remains
the next strategy-source intake; no confirmed DD Range source exists.
Premium/Discount remains context, no universal EQ reaction/reclaim, and DD HTF
side blocks remain separate. LIVE/private/order/PnL paths remain outside scope.
