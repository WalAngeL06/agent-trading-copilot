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

Evolve the preserved deterministic foundation into an **open-source,
self-hosted, agentic market intelligence / trading copilot**. Telegram is an
optional interface: shared Web/Mini App, REST API and future agent interfaces
use the same core. Keep pattern detection, context, decisions, acceptance, risk,
execution and position management separated. READ-ONLY / SHADOW first;
**LIVE execution is outside the current hackathon MVP**. A functioning data
pipeline is not strategy or profitability proof. Approved scope:
[product-mvp-v0.1](docs/specs/product-mvp-v0.1.md), [U-PRODUCT-001].

## Approved product priorities and chapter boundary

| Hackathon criterion | Weight |
|---|---|
| Functional Utility & Value | 30% |
| User Experience & Interaction | 30% |
| ATK MCP Integration Depth | 20% |
| System Reliability & Safety | 10% |
| Innovation & Uniqueness | 10% |

These are user-confirmed weights [U-RUBRIC-001]. Prioritize a usable BTC
report/API and shared mobile/web UX, with early **actual product-runtime MCP**
validation. Development-tool MCP connections and current CLI success do not
count as product-runtime integration. Target one easy self-hosting start
command with Docker Compose; it need not mean one container. Telegram and an
LLM must remain optional.

Preferred explanation boundary: deterministic report → deterministic/template
explanation → optional LLM enhancement. LLMs may orchestrate validated reads
and explain but never determine/override prices, structural state, deterministic
strategy results, risk approval or execution authorization. See ADRs
[006](docs/DECISIONS/006-open-source-self-hosting-first.md),
[007](docs/DECISIONS/007-runtime-atk-mcp.md),
[008](docs/DECISIONS/008-llm-decision-boundary.md),
[009](docs/DECISIONS/009-telegram-as-interface.md).

P0.5 before the final demo requires at least one approved, narrow, meaningful
deterministic intelligence slice; no fake signals or relabelled placeholders.
The current strategy is not completed. First intended intelligence is Market
Structure → Range → Deviation → LTF confirmation/context, with existing spec
gates preserved. Advanced models/theories and portfolio management are deferred.

Chapter model: Ch.0 — Base Setup / Product Re-Scope; Ch.1 — Product MVP & UX;
Ch.2 — Trading Intelligence; Ch.3 — Agent Workflows; Ch.4 — Validation & Demo.
Ch.0 closed at `24e1f465a886e2941a8ce2fce8fb51d53b643405`, with the frozen scope,
architecture, responsibilities, 36 passing tests and two clean sibling worktrees.
The user explicitly started Ch.1 with [U-MCP-GATE-001], approving **Backend
Target #1: runtime MCP gate only**, before the shared API contract. That narrow
gate is verified; see [evidence](docs/runtime-atk-mcp-gate.md). Ch.1 is not complete.
Stop after the requested backend commit; subsequent implementation needs its
next user instruction. No API/UX/intelligence scope is implied by this gate.

## Architecture: current vs intended

| Component | Current state |
|---|---|
| Data Engine | JSONL replay, preserved public-market-only OKX CLI adapter, and separate async MCP market adapter |
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
| Product-runtime ATK MCP | Verified narrow Python SDK 2.2.0 → ATK 1.4.6 TR market-only/read-only smoke; full report/MTF integration pending |
| FastAPI / agent orchestration / product explanation | Planned; not implemented |
| Shared React/Vite/TypeScript Web/Mini App and Telegram bot | Planned; not implemented; Telegram optional |
| SQLite / Docker Compose / self-hosting quickstart | Planned; not implemented |

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
  not authorize application live trading. LIVE remains outside this MVP;
  no usable live toggle or exchange write path may be added as an MVP feature.
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
- Next product work is the shared API contract, with Claude review, after the
  user's next instruction. The narrow runtime MCP proof is verified. Range remains the next strategy-source
  ingestion topic; the Market Structure draft stays blocked by N-1–N-7.
  A product scope approval does not fill missing trading algorithms.

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
`strategy-v0.1` remains the integration branch. Ch.0 created
`work/copilot-backend` and `work/copilot-ux` in sibling worktrees from its exact
documentation checkpoint. Only the backend worktree is authorized for this
target; integration and UX remain at the checkpoint. Preserve/report existing
branches/worktrees instead of recreating or destroying them. No merge, tag,
push or remote creation is authorized by this target.

Codex owns backend, runtime MCP adapter, FastAPI, core integration, persistence,
backend tests and Compose/integration. Claude owns React/Vite/TypeScript,
Telegram Mini App UX, bot/interface and frontend tests. Codex owns shared API,
root integration and shared-memory files, with Claude review. Freeze the shared
API contract before parallel implementation; **one owner at a time** edits
trading-intelligence core files. Worktree availability is not Ch.1 permission.
