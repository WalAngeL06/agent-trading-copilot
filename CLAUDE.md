# Claude bootstrap

## Current product consolidation and project-root policy - 2026-09-16

Canonical project root: `C:\Users\Serdar Arif\Desktop\Agent Trading`.
Do not create sibling `Agent Trading-*` directories or new Git worktrees unless
the user explicitly requests it. Use the canonical project directory for all
normal development. Preserve existing nested folders and registered worktrees;
several registered sibling paths are stale and must not be pruned blindly.

[U-PRODUCT-CONSOLIDATION-001] authorizes consolidation of the existing React/Vite
UI, FastAPI, read-only MCP and PAPER multi-timeframe strategy in this root.
It supersedes historical chapter-stop, task-isolation and frontend-ownership
restrictions for this task. Current truth: docs/PROJECT_STATE.md and
[consolidation plan](docs/plans/2026-09-16-product-consolidation.md).
The canonical UI is src/. Embedded emergency HTML is removed. Settings persist
in ignored config/strategy.json, use engine validation, and cannot change while
running. No LIVE mode, exchange-write path or new algorithm is authorized.
Commit the consolidation after verification; do not push as part of this task.
Historical exception sections below are provenance, not new instructions to
recreate their worktrees or redo their completed tasks.

Before work:

1. Read [AGENTS.md](AGENTS.md), the shared constitution.
2. Read [PROJECT_STATE](docs/PROJECT_STATE.md).
3. Read [HANDOFF](docs/HANDOFF.md).
4. Read [NEXT_TASK](docs/NEXT_TASK.md).
5. Read the relevant file under [docs/specs](docs/specs/).
6. Inspect `git status` and `git log -3 --oneline`.
7. Run relevant tests; full suite: `py -B -m unittest discover -s tests -v`.
   Python launcher fallback is documented in PROJECT_STATE.

Do not continue undocumented assumptions from chat history. Repository docs
are shared project memory; record current user clarifications there.

At completion, update HANDOFF, PROJECT_STATE if state changed, and NEXT_TASK.
Report files changed and tests. Document uncommitted work and honor no-commit
instructions. Do not duplicate or bypass AGENTS.md.
