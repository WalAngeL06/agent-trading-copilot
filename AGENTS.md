# Shared project constitution

This is the primary project instruction file for Codex and Claude. Current
user instructions take precedence; persist new clarifications in repository
docs rather than continuing undocumented assumptions from chat history.

## Start here

Read the current state first: [PROJECT_STATE](docs/PROJECT_STATE.md), then
[HANDOFF](docs/HANDOFF.md), [NEXT_TASK](docs/NEXT_TASK.md), and the relevant
[spec](docs/specs/). Inspect Git status/log before editing. `CLAUDE.md` and
`CODEX.md` are short bootstrap guides; this file holds the shared rules.

## Project goal

Build a deterministic, explainable agent for the Agentic Trading Hackathon
using OKX Agent Trade Kit and multi-timeframe market structure. Keep pattern
detection, context, decisions, acceptance, risk, execution and position
management separated. Validate in SHADOW before explicitly authorized live
execution. A functioning data pipeline is not strategy or profitability proof.

## Architecture: current vs intended

| Component | Current state |
|---|---|
| Data Engine | JSONL replay and public-market-only OKX CLI adapter |
| MarketSnapshot / MTF histories | Immutable causal snapshot; bounded histories separated by symbol/timeframe |
| Market Structure | Spec draft only; MarketStructureEngine blocked by N-1–N-7 |
| Pattern Engine | Unconfigured range/deviation/manipulation/momentum/distribution detectors |
| Context | Generic snapshot exists; strategy-specific HTF/Premium/Discount context not implemented |
| Decision Router | Placeholder: NO_TRADE / STRATEGY_NOT_CONFIGURED |
| Acceptance | Placeholder; cannot approve a candidate |
| Risk | Placeholder; production policy/sizing not implemented |
| Execution | Replay disabled; SHADOW records intent only, with no exchange order client |
| Position Management | Not implemented |
| Logging | Structured JSONL, schema_version=2; new file for each run |

The intended chain is data → snapshot/state/patterns → context → decision →
acceptance → risk → execution → position management, with logging throughout.
Do not silently rewrite the architecture or represent planned modules as done.

## Non-negotiable rules

- Never silently invent missing trading rules. Write **ALGORITHMIC DEFINITION
  PENDING** for unresolved deterministic definitions; specs precede strategy code.
- SOURCE-CONFIRMED RULE is not EMPIRICALLY VALIDATED RULE. Keep provenance and
  validation status separate in specs and [SOURCE_REGISTRY](docs/SOURCE_REGISTRY.md).
- Preserve source IDs for strategy rules. Do not substitute generic textbook
  SMC or a library's defaults for DD semantics.
- Keep trading logic, risk logic and execution separate. No live execution
  without explicit user authorization; external CLI/MCP trade permissions do
  not authorize application live trading.
- No look-ahead: only closed candles unless partial-candle semantics are
  explicitly specified. Keep `swing_time` and `confirmed_at` distinct and
  expose evidence only when knowable at `as_of`.
- Preserve Decimal precision and UTC timestamps. Never route price/quantity
  JSON through float. No magic strategy numbers; operational config is not
  permission to choose missing pivot, ATR, volume or retracement thresholds.
- Never expose secrets/API keys in docs, logs or Git. Keep runtime logs in
  ignored `runs/`; do not copy user credential/config stores into the repo.
- Premium/Discount is context/confirmation, **not an independent entry
  trigger**. EQ reaction/reclaim is not mandatory unless a specific approved
  setup requires it. Preserve DD's ordinary HTF side blocks separately.
  Source: [U-PD-001]; DD context: [D-DD-MSB-001].

## Development discipline

- Read the relevant spec before coding; do not implement unresolved assumptions.
- Run relevant tests before and after meaningful code/contract changes. For
  docs-only work, verify references/state and run the suite when feasible.
- Full suite from the project root: `py -B -m unittest discover -s tests -v`
  (use `python3` outside Windows). If the launcher is unavailable, use the
  configured Python path documented in PROJECT_STATE; do not change source
  or install dependencies just to repair the invocation.
- Keep commits small and task-scoped. Honor an explicit no-commit instruction.
  No push or remote creation is currently authorized.
- Document major decisions in [DECISIONS](docs/DECISIONS/), and update HANDOFF,
  PROJECT_STATE when state changes, and NEXT_TASK at each safe completion.
- Source ingestion is the current strategy work; Range is next. The Market
  Structure draft remains blocked. This does not authorize implementation.

## Source tagging

| Tag | Provenance |
|---|---|
| [D] | DD Finance |
| [U] | User hypothesis or clarification |
| [G] | ChatGPT |
| [C] | Claude |
| [R] | External research |
| [E] | Empirical validation evidence |

Use stable IDs such as [D-DD-MSB-001] and [U-PD-001]. An [E] record is validation
evidence; it does not overwrite a rule's original source. Agent-written drafts
are not new DD attestations. Record evidence and limitations before claiming
empirical validation; a green infrastructure suite does not establish it.

## Handoff workflow

When switching Codex ↔ Claude:

1. Finish or stop at a safe boundary and run relevant tests.
2. Commit completed work when authorized; never override a task's no-commit rule.
3. Ensure the working tree is clean **or explicitly list uncommitted files in
   HANDOFF**, including pre-existing work and any remaining limitations.
4. Update PROJECT_STATE, HANDOFF and NEXT_TASK before handing off.
5. The next agent reads those files and the relevant spec before continuing.

If agents work simultaneously, use separate Git worktrees **and branches**;
never the same working directory. Merge/cherry-pick only reviewed commits.
No extra worktree is requested for the current documentation task. Preserve
the current branch and existing checkpoint tags.
