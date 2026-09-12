# Handoff — reusable current-state template

Replace the values under these same fields at each safe handoff. Preserve
pre-existing work, list uncommitted paths explicitly, and distinguish fresh
verification from historical evidence. PROJECT_STATE is the current fact
record; NEXT_TASK defines the next authorized boundary.

## LAST AGENT

Codex. Updated: 2026-09-12.

## CURRENT BRANCH

`strategy-v0.1`; HEAD `667135804a30d8e998d3fc49f0fb2dce236f4a20`.
Existing `foundation-v0.1` and `shadow-foundation-v0.2` tags remain unchanged.

## LAST COMPLETED WORK

- Previous specification task: created
  `docs/specs/market-structure-v0.1.md`; no Python was changed.
- Current handoff setup: added shared constitution, both agent bootstrap
  guides, state/next-task/source records, five ADRs and actionable OSS notes.
- The pre-existing `docs/research/open-source-kaynak-taramasi-2026-09-12.md`
  was inspected and preserved. It was already untracked before this task.

## FILES CHANGED / UNCOMMITTED WORK

The following docs are worktree-only and uncommitted. No completed-docs commit
was created because the current task explicitly says **do not commit**.

| Path | Handoff status |
|---|---|
| `AGENTS.md` | New in current setup |
| `CLAUDE.md` | New in current setup |
| `CODEX.md` | New in current setup |
| `docs/PROJECT_STATE.md` | New in current setup |
| `docs/HANDOFF.md` | New in current setup; this reusable current handoff |
| `docs/NEXT_TASK.md` | New in current setup |
| `docs/SOURCE_REGISTRY.md` | New in current setup |
| `docs/DECISIONS/001-okx-agent-trade-kit.md` | New in current setup |
| `docs/DECISIONS/002-shadow-before-live.md` | New in current setup |
| `docs/DECISIONS/003-premium-discount-context.md` | New in current setup |
| `docs/DECISIONS/004-market-structure-state.md` | New in current setup |
| `docs/DECISIONS/005-spec-first-strategy.md` | New in current setup |
| `docs/research/open-source-notes.md` | New in current setup |
| `docs/specs/market-structure-v0.1.md` | Pre-existing uncommitted spec; user context/EQ clarification added in current setup |
| `docs/research/open-source-kaynak-taramasi-2026-09-12.md` | Pre-existing untracked research; unchanged |

`docs/specs/` and `docs/research/` were reused; `docs/DECISIONS/` was added.
Do not assume untracked docs are present in another checkout/worktree.
No extra worktree, remote or push was created.

## CURRENT TEST STATUS

No Python code changed during the spec or shared-memory setup.
Last verified system checkpoint: **36 passing tests**.
Fresh verification after documentation setup on 2026-09-12:
**36 tests passed, 0 failures/errors**, command
`py -B -m unittest discover -s tests -v`, exit 0.
Use PROJECT_STATE's test command/fallback. These are infrastructure tests,
not empirical DD validation.

## IMPORTANT DECISIONS

- Market Structure is state/context, not just a boolean pattern; no current
  Python API was rewritten to implement that decision.
- BreakQuality / Deviation / Manipulation remain separate future specs.
- Source-confirmed DD rules are not yet empirical validation.
- Premium/Discount is confirmation/context, not an independent entry trigger.
- EQ reaction/reclaim is not globally mandatory; specific approved setups
  may define it. Preserve ordinary HTF side-block semantics separately.
- OKX Agent Trade Kit stays primary; SHADOW precedes explicitly authorized live.
- Formal specs precede strategy implementation. See DECISIONS and SOURCE_REGISTRY.

## UNRESOLVED

N-1–N-7 in [market-structure-v0.1](specs/market-structure-v0.1.md) are core engine
gates: confirmation, meaningful/responsible swings, initialization/retention,
protection/transitions, scale/boundaries, EQ inputs/lifecycle and event/time
representation. N-8 is a setup-integration gate; N-9–N-10 are deferred quality
and rejection work. No deterministic algorithm or numeric threshold was chosen.

Confirmed DD Range inputs are not yet registered. NEXT_TASK records required
source ingestion; do not manufacture a Range spec from the OSS note.

## DO NOT

- Implement MarketStructureEngine yet or silently bypass N-1–N-7.
- Invent pivot counts, thresholds, confidence or trend scores.
- Treat Premium/Discount or EQ reaction as a universal entry setup.
- Enable live execution, add frameworks/dependencies, commit automatically,
  push, create a remote or create extra worktrees for this setup.

## NEXT

Continue source ingestion, with **Range** the highest-priority next spec.
Read AGENTS → PROJECT_STATE → HANDOFF → NEXT_TASK → relevant spec before work.
This setup stops and waits; Range implementation requires its own approved
specification and resolved deterministic decisions.
