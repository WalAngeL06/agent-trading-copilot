# Codex bootstrap

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
