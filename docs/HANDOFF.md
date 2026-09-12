# Handoff — Ch.1 Backend Target #1

Updated: 2026-09-12. Last agent: Codex.
Status: **Runtime ATK MCP market gate VERIFIED; Ch.1 incomplete.**
The user explicitly started this narrow target [U-MCP-GATE-001]. Stop after its
requested commit; do not auto-start the next feature.

## Branch and checkpoint

Work exclusively in `C:/Users/Serdar Arif/Desktop/Agent Trading-backend` on
`work/copilot-backend`. Starting HEAD was the exact Ch.0 checkpoint
`24e1f465a886e2941a8ce2fce8fb51d53b643405`, clean, with 36 tests passing.
Target commit: `feat: add runtime OKX ATK MCP market adapter`, containing this
handoff; obtain its exact hash from Git/final report rather than inventing a
self-referential hash. Integration `strategy-v0.1` and UX `work/copilot-ux`
remain at Ch.0; neither worktree was edited. No merge/push/tag/remote creation.

## Completed work and evidence

- Added an async public-only MCP market adapter alongside the untouched CLI.
- Official Python SDK `mcp==2.2.0` / `mcp-types==2.2.0`, installed ATK MCP
  `1.4.6`, protocol `2025-11-25`; fixed TR endpoint, market/read-only launch.
- Verified real runtime initialization, authoritative discovery of 21 tools,
  BTC-USDT ticker, ten 15m rows and depth-five book through actual MCP calls.
- Reused existing candle normalization/HistoryStore/MarketSnapshot: nine closed
  candles retained, one open excluded; live observations stay outside snapshots.
- Added immutable Decimal ticker/book facts and sanitized, bounded in-memory
  provenance, timeout/failure gates, package/server version checks and cleanup.
- Empty temporary public home isolates account configuration/credentials;
  toolkit logs/update checks disabled. SDK process cleanup verified.
- Resolved the real ATK nested-response mismatch with source inspection and a
  regression test; no SDK/ATK interoperability blocker remains.

Read [target spec](specs/runtime-atk-mcp-gate.md),
[full smoke evidence/tools/compatibility](runtime-atk-mcp-gate.md), and
[implementation plan](superpowers/plans/2026-09-12-runtime-atk-mcp.md).

## Tests

**36 baseline + 43 new = 79 passing**, zero failures/errors, full command:
`py -B -m unittest discover -s tests -v`.
The host suite needs no installed SDK, ATK, Node, credentials or network.
Fake-session/lifecycle tests cover discovery/drift, exact normalization,
causal filters/isolation, malformed responses, unavailable/timeouts,
provenance, launch restrictions and cleanup. A separate real smoke succeeded
and exited 0; dependency checks passed. No empirical strategy validation.

## Files in the target commit

No pre-existing uncommitted changes. These 18 files constitute the target;
verify `git status` for any changes made after this checkpoint.

| File | Change |
|---|---|
| agent_trading/market_observations.py | New immutable exact live observation contracts/normalization |
| agent_trading/okx_mcp.py | New normalized async read-only market adapter/discovery/provenance |
| agent_trading/okx_mcp_runtime.py | New lazy official SDK and pinned public process lifecycle |
| agent_trading/mcp_smoke.py | New explicit real public smoke entry point |
| tests/test_okx_mcp.py | New deterministic adapter/normalization/failure tests |
| tests/test_atk_mcp_runtime.py | New SDK/process/smoke lifecycle tests |
| pyproject.toml | Optional runtime-mcp extra, pinned mcp 2.2.0 |
| README.md | Actual optional MCP setup/smoke and current limitations |
| AGENTS.md | Current narrow approval/chapter/runtime state |
| docs/PROJECT_STATE.md | Actual state, checkpoints, tests and limitations |
| docs/HANDOFF.md | This target handoff |
| docs/NEXT_TASK.md | Next contract task, pending its next user instruction |
| docs/SOURCE_REGISTRY.md | Explicit authorization and narrow runtime evidence IDs |
| docs/specs/product-mvp-v0.1.md | Distinguish historical Ch.0 freeze from current narrow gate |
| docs/specs/runtime-atk-mcp-gate.md | Approved narrow adapter/runtime contract |
| docs/DECISIONS/007-runtime-atk-mcp.md | Actual narrow verification consequence |
| docs/runtime-atk-mcp-gate.md | Permanent sanitized evidence/discovery/compatibility summary |
| docs/superpowers/plans/2026-09-12-runtime-atk-mcp.md | Target implementation/verification plan |

Ignored host-local artifacts: `.venv` and
`runs/runtime-atk-mcp-20260912.json` (sanitized repeat smoke output).
No credential stores were read/copied. Temporary public homes were removed.
The original CLI adapter, deterministic core and original tests are unchanged.

## Remaining limitations and responsibilities

MCP is not yet wired into the synchronous SHADOW command or a product report,
API, full MTF workflow or persistence. Linux/container smoke and a transitive
lock are pending. Public discovery alone does not validate other TR products.
An independent peer review has not been performed; inline contract review was
kept within the single authorized backend worktree.

Codex owns backend/MCP/API/core/persistence/tests/Compose/shared memory and API
contract. Claude owns React/Vite/TypeScript/Mini App/bot/frontend tests and
reviews the shared contract before parallel feature work. Trading intelligence
has one owner at a time; agents must use separate worktrees and branches.

No real strategy, structure/range/deviation, acceptance/risk policy, positions,
fills/PnL, Telegram/LLM/frontend/API/SQLite/Compose or LIVE feature was added.
MarketStructure N-1–N-7 remain unresolved; Range remains the next strategy-source
intake. Premium/Discount remains context, no universal EQ-entry requirement.
Preserve source vs empirical validation, Decimal/UTC and closed-candle causality.

## Next stopping boundary

Stop after the coherent backend commit and report its actual hash/checks/diff.
No merge into `strategy-v0.1`, push, tag, UX edits or further implementation.
[NEXT_TASK](NEXT_TASK.md) proposes the shared API contract for the next explicit
user instruction; this completed gate is not permission to begin it.
