# Shared project constitution

This is the primary project instruction file for Codex and Claude. Current
user instructions take precedence; persist new clarifications in repository
docs rather than continuing undocumented assumptions from chat history.

## Current product consolidation and project-root policy - 2026-09-16

Canonical project root: `C:\Users\Serdar Arif\Desktop\Agent Trading`.
Do not create sibling `Agent Trading-*` directories or new Git worktrees unless
the user explicitly requests it. Use the canonical project directory for all
normal development. Integration branch: `main` (2026-09-19 owner-approved
branch consolidation). Retired `work/*` branches survive as `archive/*` tags;
their former worktree folders sit in the locally excluded `_archive/`
directory. Do not develop in, delete or re-register those folders. Start new
work on a short-lived branch from `main`, merge it after review, then delete it.

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

## Current RiskEngine exception — 2026-09-12

[U-RISK-ENGINE-001] explicitly authorizes the modular PAPER-only RiskEngine
from corrected e9ff346b151587c8deaf903b9ffc40d289659725 in work/risk-engine.
[Risk spec](docs/specs/risk-engine-v0.1.md), [evidence](docs/risk-engine.md) and
[ADR013](docs/DECISIONS/013-risk-approved-paper-plans.md) supersede older risk
and STOP records only within this task. Preserve SwingEngine and Range semantics.
STRUCTURE_BE default, generic validated fresh support, sweep fallback [H],
configurable1R break-even [H], quality gates and approved-plan-only paper fills.
Production API/UX, LIVE and other worktrees remain outside this change.
Commit `feat: add configurable structure-aware risk engine`, then STOP.
No merge/push/tag. Historical range/swing/source approvals remain preserved.

## Frozen candidate boundary correction — 2026-09-12

[U-RANGE-BOUNDARIES-001] confirms: ANY wick outside frozen rangeLow/rangeHigh
while forming a candidate invalidates it before any confirmation. Low/high
proximity must be inside-only, equality allowed. Preserve raw swing/valid-level
histories. Only AFTER RANGE_CONFIRMED may outside sweep/reclaim be manipulation.
[Current evidence](docs/trading-brain-replay.md) withdraws original4H/1H trades;
bounded15m and corrected synthetic examples are labelled explicitly. No reseed
policy is newly approved. Commit correction separately then STOP; no merge/push/tag.

## Current isolated PAPER exception — 2026-09-12

[U-TRADING-BRAIN-001] explicitly authorizes only the causal historical PAPER
slice in work/trading-brain from adbafa485c900164c95ed0e13fce0d267da8b645.
[Spec](docs/specs/trading-brain-v0.1.md) defines all provisional [H] rules;
[evidence](docs/trading-brain-replay.md) records real/synthetic results. Preserve
SwingEngine. PAPER is now implemented only in this opt-in offline runtime;
LIVE, autonomous loop and strategy wiring into API/UX remain unimplemented.
The architecture/scope statements below are inherited baseline context where
superseded by this narrow task. General DD N-1–N-7 gates remain unresolved.
Commit requested message then STOP. No merge/push/tag or other-worktree edits.

## Start here

Read the current state first: [PROJECT_STATE](docs/PROJECT_STATE.md), then
[HANDOFF](docs/HANDOFF.md), [NEXT_TASK](docs/NEXT_TASK.md), and the relevant
[spec](docs/specs/). Inspect Git status/log before editing. `CLAUDE.md` and
`CODEX.md` are short bootstrap guides; this file holds the shared rules.

## Project goal

Evolve the preserved deterministic foundation into an **open-source,
self-hosted autonomous trading agent** [U-AUTONOMOUS-CONTRACT-001].
Future START BOT maintains strategy-required market state and evaluates
approved strategy/candidate, Acceptance, Trade Plan, Risk and authorized
execution, with logging/notification. Users configure permissions/risk/symbol
scope; approved profiles own required timeframes. DISPLAY / INSPECTION TIMEFRAME
never changes STRATEGY REQUIRED TIMEFRAME. Current symbol-only manual/debug
analysis remains useful and does not start an autonomous loop.
Telegram is optional; interfaces use the same core. Preserve separate pattern,
context, decision, acceptance, risk, execution and position-management layers.
Conceptual ANALYZE/PAPER/LIVE are defined in
[ADR011](docs/DECISIONS/011-autonomous-runtime-contract.md); PAPER/LIVE and the
autonomous runtime are unimplemented. READ-ONLY/intent-only SHADOW first;
**LIVE remains disabled and outside the current hackathon execution scope**.
A functioning pipeline is not strategy/profitability proof. Historical scope:
[product-mvp-v0.1](docs/specs/product-mvp-v0.1.md), [U-PRODUCT-001]; current
[analysis v0.2](docs/specs/analysis-api-v0.2.md) records the user's direction correction.

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
The current strategy is not completed. Next foundation: Causal Swing Engine
R&D/spec, followed by Swing → Market Structure → Range → Premium/Discount →
Deviation → Acceptance → Trade Plan → Risk → Execution dependencies.
Existing source/spec gates remain; no Swing algorithm is approved or implemented
by this contract correction. Advanced models/theories/portfolio are deferred.

Chapter model: Ch.0 — Base Setup / Product Re-Scope; Ch.1 — Product MVP & UX;
Ch.2 — Trading Intelligence; Ch.3 — Agent Workflows; Ch.4 — Validation & Demo.
Ch.0 closed at `24e1f465a886e2941a8ce2fce8fb51d53b643405`, with the frozen scope,
architecture, responsibilities, 36 passing tests and two clean sibling worktrees.
The user explicitly started Ch.1 with [U-MCP-GATE-001]; Target #1 passed and
committed at cd686755cc1a01d032510806331ccf79267ed5af. Then
[U-ANALYSIS-API-001] authorized **Backend Target #2: analysis service/API/SQLite**.
Target #2 completed at 6c1af4b6f6cd8c22986b8436dd26d61f64de469d; its
[v0.1 contract](docs/specs/analysis-api-v0.1.md) and [smoke](docs/product-analysis-smoke.md)
remain preserved. The user then authorized [U-AUTONOMOUS-CONTRACT-001]:
v0.2 product/configurability correction only. New reports expose actual required
timeframes/absent profile, with original v0.1 history retained; default real
analysis and170 tests pass. Stop after
`chore: generalize analysis contract for autonomous trading`.
No Swing/strategy/monitoring/UX/deployment work follows automatically; Ch.1 incomplete.

## Architecture: current vs intended

| Component | Current state |
|---|---|
| Data Engine | JSONL replay, preserved public-market-only OKX CLI adapter, and separate async MCP market adapter |
| MarketSnapshot / MTF histories | Immutable causal snapshot; bounded independent symbol/timeframe histories; product requirements collection configurable, default verified4H/1H/15m |
| Market Structure | Spec draft only; MarketStructureEngine blocked by N-1–N-7 |
| Pattern Engine | Unconfigured range/deviation/manipulation/momentum/distribution detectors |
| Context | Generic snapshot exists; strategy-specific HTF/Premium/Discount context not implemented |
| Decision Router | Placeholder: NO_TRADE / STRATEGY_NOT_CONFIGURED |
| Acceptance | Placeholder; cannot approve a candidate |
| Risk | Placeholder; production policy/sizing not implemented |
| Execution | Replay disabled; SHADOW records intent only, with no exchange order client |
| Position Management | Not implemented |
| Logging | Structured JSONL, schema_version=2; new file for each run |
| Product-runtime ATK MCP | Verified SDK 2.2.0 → ATK 1.4.6 TR public ticker/4H/1H/15m/book → causal core/report/SQLite; CLI remains separate |
| FastAPI / analysis service / explanation | Same five routes; bounded manual service with required collection, v0.2 context/original v0.1 history and deterministic template; strategy profile/agent/LLM implementation pending |
| AutonomousTradingRuntime / modes | Future responsibilities/outcomes and ANALYZE/PAPER/LIVE specified only; no new monitoring loop, PAPER simulator or LIVE capability |
| Shared React/Vite/TypeScript Web/Mini App and Telegram bot | Planned; not implemented; Telegram optional |
| SQLite / product history | Implemented stdlib DELETE rollback history/real events, atomic finalization/idempotency and startup interruption recovery; core JSONL preserved |
| Docker Compose / deployment quickstart | Planned; local backend API setup exists, deployment not implemented |

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
- Full suite from backend root: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -v`
  (use .venv/bin/python outside Windows), with optional test-product dependencies
  installed once. The suite is offline; base CLI/replay remain dependency-free.
  Launcher/interpreter fallback is documented in PROJECT_STATE; do not change
  source or install global dependencies merely to repair invocation.
- Keep commits small and task-scoped. Honor an explicit no-commit instruction.
  No push or remote creation is currently authorized.
- Document major decisions in [DECISIONS](docs/DECISIONS/), and update HANDOFF,
  PROJECT_STATE when state changes, and NEXT_TASK at each safe completion.
- Next task: **SWING ENGINE R&D / SPEC**, with source-labelled causal definitions/
  fixtures under the next explicit instruction. No engine implementation while
  definitions remain pending. Market Structure stays blocked by N-1–N-7.
  Chart-history extension and later Range source intake are deferred. Product
  approval does not fill missing trading algorithms or authorize LIVE.

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
`main` is the integration branch. On 2026-09-19 `strategy-v0.1` was
fast-forwarded into `main` and deleted; the Ch.0-era `work/*` branches survive
only as `archive/*` tags. Push, tag or remote changes still need explicit
user authorization.

Codex owns backend, runtime MCP adapter, FastAPI, core integration, persistence,
backend tests and Compose/integration. Claude owns React/Vite/TypeScript,
Telegram Mini App UX, bot/interface and frontend tests. Codex owns shared API,
root integration and shared-memory files, with Claude review. Freeze the shared
API contract before parallel implementation; **one owner at a time** edits
trading-intelligence core files. Worktree availability is not Ch.1 permission.

## Authorized isolated frontend shell [U-WEBAPP-SHELL-001]

The 2026-09-12 explicit user instruction authorizes Codex frontend work only in
Agent Trading-webapp / work/webapp from 9d842077581f51b8264344fb331d1123665955e7.
Dashboard/Strategy Settings, mock/local config and optional Telegram init are
implemented; this overrides the earlier automatic-stop/frontend-owner boundary
for this shell only. LIVE warning/confirmation is a local preview, with startup
blocked and no execution path. Do not confuse demo presets/risk/modules with
approved trading rules. See docs/webapp-shell.md. After the requested commit,
stop; no merge/push/tag or other-worktree edits.

## Authorized isolated private read adapter [U-OKX-AUTH-001]

2026-09-12 owner instruction/design approval authorizes only work/okx-auth in
Agent Trading-auth from adbafa485c900164c95ed0e13fce0d267da8b645. Separate
product-owned TR authentication via owner-local ignored `.env`, fixed private
reads for balance/funding/config/savings, normalized Decimal/UTC account/Earn
snapshots and CONNECTED/AUTH_MISSING/ERROR. Auto Earn is balance-derived flags,
not an enablement tool. See docs/specs/okx-private-read-v0.1.md and ADR012.
Never inherit desktop/CLI/OAuth sessions, log secrets/auth headers/raw private
payloads, expose unauthenticated private HTTP data, place orders or perform any
exchange write (earn_auto_set, transfer, redeem, purchase included). LIVE stays
disabled. Test and commit only this task, then STOP; no merge/push/tag.
