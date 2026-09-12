# Current state — isolated hackathon integration

2026-09-12. Integration branch: `work/hackathon-integration`; worktree:
`C:/Users/Serdar Arif/Desktop/Agent Trading-integration`. Exact base:
`50146110f727048677b7d6c6643221f00d77cf22`. User requested cherry-picks
`75d1200898185b22cb582230f1891a81630b0e3d`, `d6933cf`, `8322fab`, followed
by full Python and frontend install/build/test verification and clean Git status.
Documentation conflicts preserve the source records as historical context.
No new features or behavior changes are authorized. Fresh verification and exact
HEAD are recorded in the final integration report; inherited counts below are
historical. STOP after verification; no push/tag. Other worktrees are preserved.

---

# Project state — isolated Web App shell

Updated: 2026-09-12. Owner: Codex. Worktree: Agent Trading-webapp.
Branch: work/webapp. Base: 9d842077581f51b8264344fb331d1123665955e7.
Authority: [U-WEBAPP-SHELL-001], explicit two-screen frontend instruction.

Dashboard and Strategy Settings are implemented with React/Vite/TypeScript.
All trading controls/data are local/mock; the optional Telegram SDK initializes
the WebView shell. No real execution, backend/core edit, bot or chart was added.
LIVE is a confirmed local preference and is blocked at startup.
Config is browser-local; bot state/activity reset on reload.

Verified: npm install/build exit 0; 10 Node checks pass; browser checks at
390x844 and 1280x900 with no horizontal overflow/console errors. Independent
read-only review findings were fixed and re-reviewed with no important issues.
See [shell handoff](webapp-shell.md) for files, limits and backend gaps.
Final checkpoint is the commit containing this record, using the requested
message; obtain its exact hash/status from Git/final report. No merge/push/tag.

Stop after this shell checkpoint. This worktree's frontend scope does not
authorize Swing or backend implementation. The backend checkpoint record below
is preserved as history; frontend/planned claims there are superseded locally.

---

# Project state

## Current isolated task — OKX capabilities [U-OKX-CAP-001]

2026-09-12, Codex. Capability research completed only on
`work/okx-capabilities` in `C:/Users/Serdar Arif/Desktop/Agent Trading-okx`,
from `9d842077581f51b8264344fb331d1123665955e7`.
[Report](research/okx-tr-capabilities-2026-09-12.md);
[sanitized discovery/evidence](research/okx-tr-capabilities-2026-09-12.json).

Connected TR MCP 1.5.0 exposes 165 tools; 13 distinct read tools succeeded.
Trading/funding reads and Earn status are verified on the real connected
account. USDT Auto Lend is supported but off; Auto Staking is unsupported for
that observed currency. Flexible/fixed/on-chain holdings lists are empty.
Spot orders/fills and pending trailing listing succeed. Spot/trailing and Earn
writes are discovered only, never executed. Simulated Earn read returns 50038.
Local CLI has no key profiles and no OAuth login; fresh read-only ATK 1.4.6
SDK discovery returns 31 tools but private modules require auth (AUTH_MISSING).

170 existing tests pass in this worktree, zero failures/errors. The existing
backend interpreter was reused without installing dependencies, and imports
were verified to resolve to this OKX checkout. Product source/tests/dependencies
are unchanged. No account adapter/private endpoint, Swing, strategy, frontend
or LIVE integration was added. Zero exchange writes/transfers/settings changes.
Commit only this coherent research; no merge/push/tag. STOP after the commit.
A future owner-only balance/Earn read contract needs separate approval and
independent TR read authentication. Connected desktop auth is not product proof.

## Preserved backend checkpoint context

The remainder records the inherited 9d84207 backend state and its prior task;
it does not authorize that historical next task or any additional work here.


Updated: 2026-09-12. Owner: Codex.
Chapter: **Ch.1 — Product MVP & Backend Foundation**.
Status: **Autonomous analysis contract v0.2 correction VERIFIED; Ch.1 incomplete.**

Target #1: cd686755cc1a01d032510806331ccf79267ed5af.
Target #2: 6c1af4b6f6cd8c22986b8436dd26d61f64de469d; historical
[real product evidence](product-analysis-smoke.md) preserved.
[U-AUTONOMOUS-CONTRACT-001] then authorized the current backend-only correction:
[analysis v0.2](specs/analysis-api-v0.2.md) uses configured required-timeframe maps
and honest null profile context; HTTP retains original v0.1 records.
170 tests passed, default real MCP 4H/1H/15m/core/SQLite smoke passed again,
and real mixed-version API retrieval matched original JSON. The complete legacy
v0.1 report schema also matches its checkpoint. [Handoff](HANDOFF.md).
The intended product is an autonomous trading agent; current POST remains a
bounded manual/debug/inspection path. Future runtime/modes/outcomes are
[specification only](DECISIONS/011-autonomous-runtime-contract.md).
No autonomous loop, Swing/strategy, PAPER/LIVE, UX or deployment implemented.
Stop after `chore: generalize analysis contract for autonomous trading`.
Next intelligence task is SWING ENGINE R&D / SPEC, pending explicit instruction.
Integration/UX stay untouched at Ch.0.

## Approved product and rubric

The project is an **open-source, self-hosted autonomous trading agent**
[U-AUTONOMOUS-CONTRACT-001], correcting historical copilot/manual framing
[U-PRODUCT-001]. Approved profiles determine required timeframes; display choices
do not change decisions. Preserve the deterministic core and layer separation.
Public MCP/manual-analysis/FastAPI/SQLite/JSONL/template backend now exists;
shared React/Vite/TypeScript Web/Mini App, thin optional Telegram, agent workflows,
LLM enhancement and Compose delivery remain planned.
Authoritative scope: [product-mvp-v0.1](specs/product-mvp-v0.1.md).

| User-confirmed hackathon criterion [U-RUBRIC-001] | Weight |
|---|---|
| Functional Utility & Value | 30% |
| User Experience & Interaction | 30% |
| ATK MCP Integration Depth | 20% |
| System Reliability & Safety | 10% |
| Innovation & Uniqueness | 10% |

P0 delivers usable BTC analysis/API, actual runtime MCP, chart/shared UI,
history, template explanation, Telegram launcher and easy Compose installation.
P0.5 before the final demo requires one approved, meaningful deterministic
intelligence slice; simply renaming STRATEGY_NOT_CONFIGURED to WAIT does not count.
P1 adds ETH, specified watches/notifications and approved Range/Deviation.
P2 may add authenticated balance, replay UI, proper shadow positions and our
own MCP server. LIVE, full portfolio management, SMT/SSMT, Quarterly Theory,
Momentum/Distribution and framework migration are outside the current MVP.

## Git / safe checkpoints

Integration branch: **strategy-v0.1**.
Base of this closure: `364a3a7d50024520065e74a9c9e9da899d4e3897`.
The Ch.0 closure checkpoint is the documentation commit containing this state
record, with message `chore: freeze hackathon product scope and ch0 plan`.
Read its exact hash from Git and the final closure report; do not mistake the
base hash above for the new current HEAD.

| Historical checkpoint | Commit |
|---|---|
| foundation-v0.1 — annotated tag | `e4f2fdf6b4bb7dc2be1fd4912a342814c7c8f283` |
| shadow-foundation-v0.2 — annotated tag | `667135804a30d8e998d3fc49f0fb2dce236f4a20` |
| Shared project-memory checkpoint — commit, no new tag | `364a3a7d50024520065e74a9c9e9da899d4e3897` |

The shared-memory files and Market Structure draft were committed at 364a3a7;
the older "uncommitted docs" state is historical and superseded. Existing tags
remain preserved. No push/remote exists. This closure creates no tag.

Ch.0 commit/worktree creation is verified complete. Exact checkpoint:
`24e1f465a886e2941a8ce2fce8fb51d53b643405`. Both branches were clean at that
checkpoint before this target:
- Backend: `C:/Users/Serdar Arif/Desktop/Agent Trading-backend`.
- UX: `C:/Users/Serdar Arif/Desktop/Agent Trading-ux`.

Current work is exclusively on `work/copilot-backend`, descended from that
checkpoint. Targets #1/#2 committed at cd686755 and 6c1af4b respectively.
The correction commit is `chore: generalize analysis contract for autonomous trading`.
Read its exact hash from Git/final correction report. Root integration remains at
`C:/Users/Serdar Arif/Desktop/Agent Trading`; integration and UX branch HEADs
remain at Ch.0. No merge/push/tag/remote creation. Preserve both worktrees.

## Test status and invocation

Historical Ch.0 baseline36 and Target #1 baseline79 remain preserved.
Historical Target #2: 79 old +71 new =150 tests, preserved unchanged.
Fresh correction: **150 preserved +20 focused =170 passing**, zero failures/errors,
exit0. New: 3 collection +6 wire +8 configured service +3 versioned API.
Tests keep normalization/domain/core/audit/SQLite/HTTP real and fake only
external SDK transport. They need no Node, ATK, credentials, internet or live MCP.
The complete product suite uses optional FastAPI/HTTPX test dependencies installed
once in ignored .venv; host/global Python remains unchanged. Base CLI/replay
still need no Python dependencies. No empirical strategy validation is claimed.

Full suite from backend root, after `pip install -e '.[product,test-product]'`:

`./.venv/Scripts/python.exe -B -m unittest discover -s tests -v`

Linux/macOS: .venv/bin/python (real platform smoke pending).
Suppress application bytecode with -B. py launcher is currently unavailable in
the sandbox profile; verified host fallback to create/use a virtual environment:

`C:/Users/Serdar Arif/AppData/Local/Programs/Python/Python314/python.exe`

Python >=3.11 remains portable requirement; fallback path is host-specific.
Dependency check passed. Real smoke completed separately with exact public
provenance and no orders; normal offline tests do not establish real connectivity.

## Implemented — product backend and preserved foundation

- Current analysis-report-v0.2/context/dynamic timeframe API; historical v0.1
  spec/original SQLite JSON preserved with strict version discrimination.
- Operator-owned immutable required_timeframes, default verified 4H/1H/15m;
  existing fixed intervals supported, future calendar representation only.
- Serialized/bounded public manual AnalysisService with independent initial-cutoff
  freshness, shortest-required-interval closed cutoff and causal trimming;
  default behavior remains the same latest closed15m, not a universal strategy rule.
- Five FastAPI analysis/history/health endpoints, typed errors, neutral failed
  decision and no raw MCP payload/request echo.
- Stdlib SQLite DELETE history/events, atomic idempotency/reservation/finalization,
  startup interruption recovery, exact subsecond ordering and unique core audit.
- Honest unavailable intelligence, actual acceptance/risk/current core reasons,
  entirely report-derived deterministic explanation.
- Same unchanged real smoke verified again for v0.2 (517c6e4d-265b-4a9b-9860-cf7f8aa7e4a2); original real v0.1/v0.2 API/history retrieval matched SQLite.
- Request-driven readiness with local storage probe, no network GET, expiry and
  failure invalidation; explicit POST validates initial/recovery prerequisites.

- Deterministic incremental replay; Decimal prices/quantities and UTC times.
- Immutable MarketSnapshot; bounded symbol/timeframe-separated histories.
- Official ATK public-market **CLI** adapter: ticker, candles and orderbook,
  exact normalization, closed filtering and allowlisted reads.
- Separate async runtime **MCP** market adapter with authoritative discovery,
  schema/name gates, sanitized provenance, bounded failures and the existing
  candle normalizer. New immutable ticker/book observations remain outside
  candle snapshots. Explicit public-network smoke builds an existing snapshot.
- Optional `runtime-mcp` dependency: official `mcp==2.2.0` (mcp-types 2.2.0).
  Installed/verified in the ignored backend `.venv`; host Python stays unchanged.
  The pinned ATK MCP 1.4.6 child uses an isolated empty home, fixed TR URL,
  market/read-only arguments, disabled toolkit logs/update checks and cleanup.
- Real BTC-USDT bootstrap, configurable 4H / 1H / 15m snapshots; bootstrap does
  not call the decision chain.
- SHADOW bounded/continuous polling; intent-only execution, zero real-order path.
- Unconfigured detectors/router/acceptance/risk; default
  `NO_TRADE / STRATEGY_NOT_CONFIGURED → NO_ACTION`.
- Structured JSONL explainability/error logs, schema_version=2, ignored in `runs/`.

## Not implemented

- AutonomousTradingRuntime/continuous bot loop, approved strategy-profile implementation, Causal Swing Engine, PAPER simulation/accounting, agent workflows or LLM enhancement.
- MCP wiring into the existing synchronous CLI SHADOW command; product MTF/API
  uses real MCP separately and preserves the CLI default.
- Web/Mini App, Telegram bot, full chart-history extension, Docker Compose or
  deployment quickstart. Local backend API setup is documented in README.
- Real strategy, MarketStructureEngine, Range/Deviation/Manipulation detectors.
- Momentum/Distribution, strategy HTF/Premium/Discount context, real Acceptance
  rules, production Risk/sizing, Position Manager, fill/PnL accounting or LIVE.
- Full backtest, adaptive WindowScanner, comprehensive freshness/recovery,
  automatic retry/backfill, WebSocket ingestion or calendar/session bars.

## Strategy/source history and preserved gates

[market-structure-v0.1](specs/market-structure-v0.1.md) is a committed formal
draft with 21 user-attested DD rules [D-DD-MSB-001]. They are **source-confirmed**,
not empirically validated. N-1–N-7 remain open: swing confirmation, meaningful/
responsible swings, causal initialization/retention, protection/transitions,
scale/boundaries, EQ inputs/lifecycle and event/time representation.
N-8 is setup-integration work; N-9/N-10 are deferred quality/rejection work.
Product scope approval does not resolve these algorithms.

[U-PD-001]: Premium/Discount is context/confirmation, not an entry trigger.
EQ reaction/reclaim is not universally mandatory. Preserve DD ordinary HTF
side blocks; context alone cannot create an entry, acceptance or risk approval.

Market Structure remains planned persistent derived state, not just a boolean
pattern; the current PatternResult API has not been replaced. Separate
BreakQuality, Deviation and Manipulation specifications remain future work.
See [SOURCE_REGISTRY](SOURCE_REGISTRY.md) and ADRs 001–005 under [DECISIONS](DECISIONS/).

Next intelligence task is **SWING ENGINE R&D / SPEC — Causal Swing Engine**.
Dependencies now begin Swing → Market Structure → Range → Premium/Discount →
Deviation → Acceptance → Trade Plan → Risk → Execution. Required source-labelled
swing confirmation/causality definitions remain pending; no algorithm invented.
Historical longer-term Range/Deviation/Manipulation and other source intake is
preserved as deferred work; no confirmed Range source/spec exists.
Postponed topics are history, not permission to build them during this MVP.

Incoming ecosystem [research](research/agentic-market-intelligence-ecosystem-2026-09-12.md)
from the parallel Kaynak Tarama task is preserved as [R-COPILOT-001]. Its library,
deployment and compatibility proposals remain references, not approved scope,
installed full product stack or new DD semantics. The SDK 2.2.0 / ATK 1.4.6
combination alone is now verified for this narrow public runtime gate.

## Product boundaries and responsibilities

Actual product-runtime MCP is mandatory; desktop Codex/Claude access and CLI
probes are not its proof. The narrow backend gate now verifies application →
MCP client → toolkit → real ticker/4H/1H/15m/orderbook → normalized causal core
→ report/SQLite/API. A functioning pipeline is not strategy validation.

Preferred explanation: deterministic report → template explanation → optional
LLM enhancement. LLMs cannot determine/override prices, structural state,
deterministic strategy results, risk approval or execution authorization.
READ-ONLY/SHADOW defaults; no usable LIVE toggle. Self-hosting targets one easy
start command, not necessarily one container; Telegram stays optional.
See new ADRs [006](DECISIONS/006-open-source-self-hosting-first.md),
[007](DECISIONS/007-runtime-atk-mcp.md), [008](DECISIONS/008-llm-decision-boundary.md)
and [009](DECISIONS/009-telegram-as-interface.md).

Codex: backend, runtime MCP adapter, FastAPI, core integration, persistence,
backend tests and Compose/integration/shared-memory ownership.
Claude: React/Vite/TypeScript frontend, Mini App UX, Telegram bot/interface and
frontend tests. Shared API contract precedes parallel implementation.
Trading-intelligence core files have one owner at a time.

## Ch.0 exit / chapter model

Ch.0 historical exit checklist, now verified through Git metadata and baseline:

- [x] Deterministic foundation checkpoint.
- [x] Real OKX shadow-data pipeline.
- [x] Shared Codex/Claude memory system.
- [x] Product direction approved.
- [x] Hackathon MVP scope frozen.
- [x] Product architecture documented.
- [x] Agent responsibilities defined.
- [x] Final Ch.0 checkpoint commit.
- [x] Clean worktrees created from that checkpoint.

Ch.0 — Base Setup / Product Re-Scope; Ch.1 — Product MVP & UX;
Ch.2 — Trading Intelligence; Ch.3 — Agent Workflows; Ch.4 — Validation & Demo.
**Ch.1 Backend Targets #1/#2 and this separately authorized contract correction
are verified. Ch.1 is not complete.** [NEXT_TASK](NEXT_TASK.md) describes
future work, not permission to auto-start after the requested commit.

## Historical runtime evidence / limits

Phase 1 ticker, three-timeframe candle and orderbook CLI probes succeeded;
account read lacked CLI credentials. OAuth MCP login is separate from CLI
authentication. These are historical results, not a fresh product-runtime MCP
or account-session verification. Do not read credential stores for handoff.

[Phase 1 report](shadow-phase1.md) records the evidence. Ignored local
`runs/shadow-phase1-20260912.jsonl` and `runs/shadow-poll-20260912.jsonl`
show bootstrap with 100 closed candles/timeframe and NO_TRADE/NO_ACTION.
They are host-local, not available in a new worktree, and provide no PnL proof.
Polling stops on malformed/missing required series, gaps or conflicting retained
closed candles. There is no automatic recovery or partial-candle strategy.
