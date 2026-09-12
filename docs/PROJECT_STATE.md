# Project state

Updated: 2026-09-12. Owner: Codex.
Chapter: **Ch.1 — Product MVP & UX**.
Status: **Backend Target #1 runtime MCP gate VERIFIED; Ch.1 incomplete.**

The user's explicit [U-MCP-GATE-001] instruction starts Ch.1 in the backend
worktree and prioritizes this narrow gate before the shared API contract.
Python product code → official MCP SDK 2.2.0 → installed ATK MCP 1.4.6 → real
OKX TR ticker/15m candles/orderbook → exact normalized domain facts and a
candle-only snapshot succeeded on 2026-09-12. Protocol: `2025-11-25`.
Evidence, discovered tools and compatibility details:
[runtime-atk-mcp-gate](runtime-atk-mcp-gate.md).
Stop after the target's backend commit; no later implementation is authorized
by this instruction. Integration and UX remain untouched.

## Approved product and rubric

The project continues as an **open-source, self-hosted, agentic market
intelligence / trading copilot** [U-PRODUCT-001]. Preserve the deterministic
core. A shared React/Vite/TypeScript Web/Mini App, thin Telegram bot, FastAPI,
bounded orchestration, actual runtime ATK MCP, SQLite/JSONL and deterministic
explanation are planned. Telegram and LLM enhancement are optional.
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
checkpoint. Its next commit is `feat: add runtime OKX ATK MCP market adapter`;
read the exact hash from Git/final target report. Root integration remains at
`C:/Users/Serdar Arif/Desktop/Agent Trading`; integration and UX branch HEADs
remain at Ch.0. No merge/push/tag/remote creation. Preserve both worktrees.

## Test status and invocation

Last verified baseline: **36 existing tests passing**, 0 failures/errors, on
2026-09-12 at the shared-memory checkpoint.
Fresh Ch.0 closure verification on 2026-09-12: **36 tests passed, zero
failures/errors**, exit 0, with `py -B -m unittest discover -s tests -v`.
Fresh Ch.1 target verification: **79 tests passed**, zero failures/errors,
exit 0: 36 preserved tests + 43 deterministic MCP tests. Normal suite needs no
SDK, ATK, Node, credentials or network. A separate real smoke passed all three
required reads. Infrastructure tests are not empirical validation of DD
strategy behavior; runtime MCP is established by the separate live evidence.

Full suite from the root:

`py -B -m unittest discover -s tests -v`

Use `-B` / `PYTHONDONTWRITEBYTECODE=1` to suppress application bytecode.
If the launcher is unavailable, use the verified local interpreter:

`C:/Users/Serdar Arif/AppData/Local/Programs/Python/Python314/python.exe`

Python 3.11+ remains the project requirement; this path is a host-specific
fallback, not a portable dependency. Linux/macOS can use `python3`.

## Implemented — preserved foundation

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

- FastAPI, agent orchestration or product explanation/report.
- MCP wiring into the existing synchronous SHADOW command or a full MTF
  analysis/report workflow; the CLI SHADOW adapter remains the current default.
- Web/Mini App, Telegram bot, SQLite, Docker Compose or product quickstart.
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

Intended first intelligence: Market Structure → Range → Deviation → LTF
confirmation/context. Range is still the next **strategy source-ingestion**
topic; no confirmed Range source/spec exists. Original longer-term source
priority is retained: Market Structure, Range, Deviation, Manipulation,
Momentum/Distribution, Liquidity/Target, Acceptance, Risk and Microstructure.
Postponed topics are history, not permission to build them during this MVP.

Incoming ecosystem [research](research/agentic-market-intelligence-ecosystem-2026-09-12.md)
from the parallel Kaynak Tarama task is preserved as [R-COPILOT-001]. Its library,
deployment and compatibility proposals remain references, not approved scope,
installed full product stack or new DD semantics. The SDK 2.2.0 / ATK 1.4.6
combination alone is now verified for this narrow public runtime gate.

## Product boundaries and responsibilities

Actual product-runtime MCP is mandatory; desktop Codex/Claude access and CLI
probes are not its proof. The narrow backend gate now verifies application →
MCP client → toolkit → real ticker/15m candles/orderbook → normalized facts and
snapshot. Full 4H/1H/15m report integration remains a later deliverable.

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
**Ch.1 started with explicit approval for Backend Target #1 only; its runtime
MCP gate is verified. Ch.1 is not complete.** [NEXT_TASK](NEXT_TASK.md) describes
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
