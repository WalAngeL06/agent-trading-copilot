# Current project state - 2026-09-24

## Broker trailing fix and the first 30-pair result - 2026-09-24

The multi-pair data came back from the VPS: the top 30 OKX TR USDT pairs,
30/30 complete, no gaps, as_of 2026-09-21T18:13:01Z (`data/okx_tr_usdt_top30`,
gitignored). Its first sweep ended every trade on a stop and never reached a
target. That exposed two broker bugs which had shaped every trade result so
far, including the BTC direction result recorded below.

- Per-trade state leaked. Break-even and the recovery chain were set once per
  broker and never cleared, so after a pair's first break-even every later trade
  trailed from its first bar (164 of 195 trades). The backtest spec claimed a
  reset on `submit` that the code never had.
- Trailing used stale structure. `_trail` accepted any swing since the start of
  the run and took the most extreme one, so a stop could jump far beyond price
  and the next open closed the trade (AVAX-USDT: a long at 9.17 had its stop
  moved to 34.98). All 182 trailing updates were of this kind.
- Fixed with TDD in [broker.py](../agent_trading/strategy_v1/broker.py): the
  state is cleared on every `submit`, a swing must form at or after the fill,
  and a trailed stop must sit strictly on the market side of the bar's close.
  The live PAPER agent runs the same broker. On the rerun a read-only check
  finds no violation of any of the three rules, and the 13 trades that closed
  before any break-even are identical to the old run.
- BTC reference (`runs/eval-direction-fixed`): 1 short, +1.13R, ending equity
  10112.627090374, instead of 2 shorts and 10096.402343948. Its stop now follows
  four fresh lower highs instead of jumping to one from 2026-07-01.
- 30 pairs after the fix (`runs/sweep-okx-tr-fixed`, price scaling, no costs):
  92 trades instead of 195. Groups were fixed before looking: 22 CORE pairs
  with full 1H and 15m history, 7 YOUNG listings, and XAUT apart.

  | Group | Trades | Win rate | Avg R | Median R | Total R | PF |
  |---|---|---|---|---|---|---|
  | CORE | 82 | 0.415 | +0.098 | -0.002 | +8.04 | 1.26 |
  | CORE long | 45 | 0.489 | +0.307 | 0.000 | +13.82 | 1.97 |
  | CORE short | 37 | 0.324 | -0.156 | -0.059 | -5.78 | 0.66 |
  | YOUNG | 10 | 0.200 | -0.046 | -0.007 | -0.46 | 0.85 |
  | XAUT | 0 | - | - | - | - | - |

  12 trades reached the opposite boundary and left a runner. 51 of the 82 CORE
  trades reached break-even, which is why the median sits at zero. With a
  hypothetical fee of 0.05% per side the CORE average falls to +0.037R, and at
  0.1% to -0.023R. Trades cluster in 2026-04 (24) and 2026-07 (26). Under
  multi-setup one manipulation still produced up to 5 trades (22 with the bug).
- This is not a profitability claim: 82 pooled trades that are not independent,
  one window, a survivorship-biased list and no costs. No threshold was changed.
- 761 Python tests pass.

## Multi-pair research set, built and waiting for the VPS - 2026-09-21 [U-MULTI-PAIR-001]

Two trades on one symbol say nothing, so the next step is the same profile on
many pairs. Owner decisions: USDT-quoted pairs only, the top 30 by 24h quote
volume, downloaded on the VPS because OKX is not reachable from this PC (curl
resets, the ATK server reports NetworkError, re-checked 2026-09-21).

- The MCP adapter can read the OKX TR spot instrument and ticker listings
  (public, `instType=SPOT` only, optional at discovery; both gate docs carry a
  dated amendment). An empty candle page after a paging cursor now means the
  end of history.
- `python -m agent_trading.backtest.fetch --universe ...` selects the pairs,
  writes one folder per pair plus `universe.json` and `fetch_manifest.json`,
  paces and retries calls, isolates failing pairs and resumes with `--resume`.
- `python -m agent_trading.backtest.sweep --data ...` runs the unchanged engine
  on every folder, scales the two price-unit knobs per pair
  ([H]-SWEEP-SCALE-001) and writes pooled R statistics, funnels and reasons.
- Verified on the local BTC data: with `--scale none` the sweep reproduces the
  direction result exactly (2 trades, 10096.402343948); it also shows that 7 of
  the 10 risk-blocked setups were `INSUFFICIENT_EQUITY`.
- 751 Python tests, 15 frontend tests and the production build pass. The
  runbook is in [deploy-vps.md](deploy-vps.md), "Çoklu parite verisi ve tarama";
  the design and caveats in [the backtest spec](specs/backtest-v0.1.md), section D.

## Direction follows the guide's HTF context - 2026-09-20 [U-RANGE-GUIDE-002]

The range layer was fixed first (below) and the binding constraint moved to
direction. The guide never defines the 4H "long permission" the engine used; it
defines section 4.3 (a deviation must coincide with a high timeframe zone) and
section 4.4 (no long in premium, no short in discount unless market structure is
broken). Those two rules now decide direction, and the deviation model works on
both sides.

- New `HtfContext` ([context.py](../agent_trading/strategy_v1/context.py)) reads
  the bias timeframe: the current Valid pair is the dealing range, its midpoint
  is the equilibrium, and its boundaries plus unfilled bias-timeframe FVGs are
  the zones a sweep has to touch. Every verdict is emitted as an `HTF_CONTEXT`
  event, so a refusal is auditable.
- Strategy V1 is no longer long-only: `direction` defaults to `BOTH`, targets,
  stops, entries, partials, break-even, trailing and the boundary exit are
  written once and read from the trade's direction. The superseded gate stays
  selectable as `direction_gate='BIAS_LONG_PERMISSION'` (long-only by
  construction) and the shipped acceptance scenario still covers it.
- Measured on the same frozen BTC data (`runs/eval-direction`), old gate -> new
  gate with both directions: trades 0 -> 2, ending equity 10000 -> 10096.40,
  HTF verdicts 30 with 17 allowed (8 refused for no zone, 5 for no frame).
  Premium/discount refused nothing: sweeps already happen on the right side.
  Two trades prove the chain runs end to end; they prove nothing about profit.
- 677 Python tests and 15 frontend tests pass. What the guide still asks for,
  and what was deliberately deferred (symmetric range anchor, CHoCH body
  confirmation, breaker/order block entries, acceptance layer), is listed in the
  [gap report](specs/range-model-gap-2026-09-20.md) sections 8-10.

## Range rules aligned with the source guide - 2026-09-20 [U-RANGE-GUIDE-001]

The missing strategy source turned up as the owner's
`range_trade_learning_guide.md`, now kept in the repository as
[the guide](specs/range-trade-learning-guide.md). Its section 4.1/4.2 defines a
wick beyond a boundary as a liquidity sweep and reserves invalidation for a body
closing past the boundary by more than half of (RangeHigh - EQ); section 3.2
counts a touch only after price returns to EQ. The code did the opposite, so the
owner replaced [U-RANGE-BOUNDARIES-001] with [U-RANGE-GUIDE-001].

- `RangeEngine` now invalidates (and retires) on breakout bodies only, validates
  touches through EQ visits, and exposes `range_deviation_ratio` /
  `range_require_eq_visit` on the profile.
- Measured on one year of BTC (`data/btc_deep`), old -> new: confirmed ranges
  5 -> 7, manipulations 15 -> 30, invalidated candidates 112 (all wicks) -> 67
  (all breakout bodies). Trades stay 0.
- The binding constraint moved to direction: 27 of 30 manipulations are SHORT
  while the strategy is LONG_ONLY, and the 4H long permission blocks more than
  half of the remaining bars. Details and the rule-by-rule comparison:
  [gap report](specs/range-model-gap-2026-09-20.md).
- 630 Python tests pass. Charts of every confirmed and rejected range are
  written next to each run (`runs/<label>/charts`).

Owner: Codex. Branch: `main` (formerly `strategy-v0.1`). Canonical root:
`C:/Users/Serdar Arif/Desktop/Agent Trading`.

## VPS hardening - 2026-09-19 (Claude, owner-requested)

- Market loop reconnects with backoff (5 s up to 5 min, RECONNECTING status) and
  keeps the strategy state; history gaps and rejected data still stop the agent.
- Owner-only API: `API_ACCESS_TOKEN` bearer key or Telegram Mini App initData
  (HMAC per Telegram docs) from `TELEGRAM_ALLOWED_USER_IDS`. A non-local
  `WEBAPP_URL`/`ALLOWED_ORIGINS` without either refuses to start. The Telegram
  bot answers and notifies allowlisted users only. WebApp shows an access gate.
- Durable PAPER session in `runs/product/paper_session.pickle`, resumed on Start
  for the same symbol and strategy profile; a stale session starts fresh with a
  warning. A `.active` marker restarts an owner-started agent after a backend
  restart; Stop clears it.
- Telegram access: the canonical `.env` currently has an empty
  `TELEGRAM_ALLOWED_USER_IDS`, so the bot works but answers `/status` and sends
  notifications to anyone who messages it. Production must set it.
- Telegram `/status` reports `Lira Auto Earn: <local preference>` and
  `API verification: NOT EXPOSED`, like the WebApp; no generic Auto Earn line.
- Tests no longer read the developer's `.env` (they had been polling Telegram and
  reading the OKX account with real credentials): 620 tests in ~15 s. Frontend
  15 tests and the production build pass.
- Draft VPS deployment: `compose.yaml`, `deploy/Dockerfile`, `deploy/Caddyfile`,
  [deploy guide](deploy-vps.md). Not yet run on a real VPS (no Docker here).
- Backtest candles restored to the ignored local `data/` (btc_long, btc_deep).
- Lira Auto Earn (researched 2026-09-19): no read-only status exists. ATK 1.4.6
  has only the write tool `earn_auto_set` (`POST /api/v5/account/set-auto-earn`);
  the 2026-09-12 TR MCP catalog (165 tools) has no auto-earn read tool; balance
  `autoLendStatus`/`autoStakingStatus` are generic per-currency Simple Earn flags
  with no official link to Lira Auto Earn. API verification stays NOT_EXPOSED and
  the UI shows it next to the optional local user preference.
- Network: the application connects to OKX through ATK/MCP whenever network
  access is available; the 2026-09-16 01:13 diagnosis verified every public layer
  end to end. Environment observations, not a product defect: on 2026-09-19 (checks through 14:51 Europe/Istanbul) this
  machine's network reset TLS whenever the SNI was `*.okx.com`, while another SNI
  to the same IP completed normally. Re-check before concluding either way:
  `curl -sS -o /dev/null -w "%{http_code}\n" "https://tr.okx.com/api/v5/market/ticker?instId=BTC-USDT"`

Verified on this machine: browser access gate against a live backend, and
RECONNECTING with the Start/Stop marker lifecycle while OKX was unreachable from
this machine.

## Product consolidation

[U-PRODUCT-CONSOLIDATION-001] supersedes historical Ch.0 stop and isolated
worktree restrictions for this task. The existing product has been consolidated
into this root, without creating/moving/deleting any worktree or sibling folder.

- Canonical existing React/Vite UI: `src/`; Dashboard and Strategy Settings.
- FastAPI → BotService → existing multi-timeframe StrategyV1 → read-only ATK MCP.
- PAPER only. No exchange writes or live execution imported or added.
- GET/PUT `/api/v1/strategy/config`: strict transport fields, Decimal strings,
  engine validation, atomic local persistence, running-state lock.
- Configuration is stored in ignored `config/strategy.json`, never localStorage.
- BotService consumes configured bias/range/entry histories in causal order and
  waits at shared boundaries until delayed higher-timeframe bars arrive.
- Market/account state, timestamps, equity, decisions and activity are backend
  observations. Lira Auto Earn API verification: NOT EXPOSED (see above).
- Optional local Lira Auto Earn preference (GET/PUT
  `/api/v1/account/preferences`, ignored `config/preferences.json`): a user
  declaration only, never sent to or verified by OKX; status stays UNKNOWN.
- Embedded emergency HTML exists only in preserved historical nested sources;
  canonical `/dashboard` is a redirect to `WEBAPP_URL`, not a second UI.
- `run.ps1` starts backend and frontend in separate visible windows.
- Root `.env` was created from empty local defaults; no credential stores copied.

## Verified now

2026-09-19, after committing the Lira preference: 593 Python tests, 11
frontend tests and the production build pass. At consolidation (2026-09-16):
590 Python tests passed; 10 frontend tests passed; production frontend build
passed. Windows launcher and service startup passed. Real browser save/reload,
nondefault persistence across process restart, restore, Start/Stop, and disabled
Save while running passed. Desktop and mobile layouts inspected.

## Current blockers and limits

Fresh diagnosis at 2026-09-16 01:13-01:16 Europe/Istanbul supersedes the
previous connectivity conclusion. Raw REST and venv Python HTTPS pass. The
unchanged product runtime passes MCP subprocess/handshake, ATK initialization,
tools/list, ticker, candles, adapter normalization and configured BotService
4H/1H/15m processing. The actual Dashboard displays CONNECTED while running;
subsequent market observation timestamps advance. No reproducible product
failure was found and no runtime fix was applied. The earlier blanket
"network blocked" conclusion is withdrawn; its original cause is unproven.
Canonical .env has no OKX or Telegram credentials: private AUTH_MISSING is
independent of successful public connectivity. See
[fresh runtime diagnosis](fresh-atk-runtime-diagnosis.md).

PAPER uses simulated equity; since 2026-09-19 its session survives restarts
(see VPS hardening above). Existing strategy hypotheses remain provisional.
No strategy profitability or empirical validation is claimed.

## Git and local data

Consolidation (2026-09-16) source bases: `work/final-demo` 1e4356f for product
runtime/history, `work/backtest-v1` baa77e9 for strategy/backtest/spec/tests and
the `Agent Trading-final-ui/src` visual design; original canonical HEAD 24e1f46.

2026-09-19 branch consolidation (Claude, owner-approved): `strategy-v0.1` was
fast-forwarded into `main` and deleted; `main` is the only development branch.
All 13 `work/*` branches were checked to be contained in `main` (only the
intentionally dropped `src/api/mock.ts` and `validation.ts` differ) and were
replaced by annotated `archive/*` tags. Uncommitted work found in three
worktree folders was first saved, unreviewed, as `wip(archive)` commits:
`archive/final-demo` (experimental LIVE_SMOKE exchange-order path; never merge
without separate review and authorization), `archive/final-ui` (alternate UI
including `BacktestPage.tsx`) and `archive/backtest-v1` (frontend backtest API
draft). Restore a branch with `git switch -c work/<name> archive/<name>`.

The twelve nested `Agent Trading-*` folders, `.worktrees/risk-engine` and
`grep.exe.stackdump` were moved, not deleted, into `_archive/` (excluded in
`.git/info/exclude`, never committed); their stale worktree registrations were
pruned. `_archive/` still holds ignored local data: `.env` files with filled
keys in `-final` and `-auth`, `runs/`, `data/` and virtual environments. The
owner reviews and deletes it. User folders (Yeni klasör, odin-videolar,
öğrenme-dd finance ve odin) are untouched and untracked.

Remote `origin` is the **private** GitHub repository
`WalAngeL06/agent-trading-copilot` (verified 2026-09-19; earlier records that call
it public are outdated). `main` is published by fast-forward only and is the
default branch. PR #1 (`work/final-demo` -> `main`) is stale and must never be
merged. `work/final-demo` and the local `archive/*` tags are kept. The session
worktree
`.claude/worktrees/gracious-meninsky-11af1e` (branch
`claude/worktree-question-1778f7`, no unique commits) remains until the desktop
app removes it.

Run tests with `.venv/Scripts/python.exe -B -m unittest discover -s tests -v`.
The system `py` interpreter lacks FastAPI; use the root virtual environment.
[Detailed evidence](product-consolidation.md), [handoff](HANDOFF.md),
[next task](NEXT_TASK.md), [plan](plans/2026-09-16-product-consolidation.md).

---
## Historical checkpoint records (superseded where stated above)

# Current state — final demo runtime wiring repaired

2026-09-12. Codex; `work/final-demo` in `Agent Trading-final`, based on
`31fded92a018958165b6c28554937fd71b9adc09`. Default FastAPI lifecycle now
constructs BotService and optional Telegram independently of TradingBrain start.
The BotService market loop uses the pinned public read-only ATK MCP runtime, not
the legacy CLI adapter. Private read snapshots map the existing account/Earn
contracts to sanitized auth, equity summary and Auto Earn state. Readiness and
the frontend consume observed market/private timestamps and connectivity.

Fresh verification: 360 Python tests, 11 frontend tests and production frontend
build pass. Default FastAPI startup/liveness and a real public bot-start smoke
passed with `market_source=OKX_ATK_MCP`, PAPER execution and zero exchange writes.
Local `.env` was created with empty values only and remains ignored; tracked
`.env.example` contains placeholders only. No Strategy V1 semantics changed.

---

# Historical state — configurable structure-aware PAPER risk

2026-09-12. Codex; work/risk-engine in
C:/Users/Serdar Arif/Desktop/Agent Trading/.worktrees/risk-engine.
Exact base e9ff346b151587c8deaf903b9ffc40d289659725.
[U-RISK-ENGINE-001] authorizes this isolated feature and requested commit/STOP.
[Spec](specs/risk-engine-v0.1.md), [evidence](risk-engine.md), [ADR013](DECISIONS/013-risk-approved-paper-plans.md).

Implemented RiskEngine, generic SupportingZone/freshness adapter, immutable
evidenced ApprovedTradePlan/RiskDecision, R:R/geometry/size gates with BLOCKED,
STRUCTURE_BE/default configurable favorable excursion1R, FIXED_SL_TP, monotonic
stop updates and approved-plan-only paper broker with actual-fill reapproval.
Offline report trading-brain-paper-v0.2; pending_plan and original approval plus
stop history retained. Production analysis API/UX and Swing/Range semantics unchanged.

Baseline292 and final full323 tests pass, zero failures/errors;31 new risk tests.
Seven CLI smokes pass; existing real/synthetic causal prefixes preserved. Literal
all-default synthetic approval: LONG100000 / FVG invalidation99000 / SL98900 /
TP103000 / size.09090909 / R:R2.72727. Same entry/SL with TP100500 blocks
MIN_REWARD_RISK. Corrected saved synthetic full chain approves with explicit
opposing-boundary target; default EQ/poor-R:R is blocked. Bounded real15m range
stays confirmed, with five risk blocks and zero orders under new defaults.
Exact JSON and limitations are in linked evidence. No empirical validation.

General DD/MTF/zone quality, Breaker/OB detectors, reaction classification,
SWING_TRAIL/ATR_TRAIL, costs, exchange rules, portfolio/durable order state and LIVE
remain gaps. Defaults remain provisional [H], not DD attestations. Independent
read-only review reproduced two defects (skipped first fill and ambient Decimal
rounding); both fixed with regressions, re-review clear. Final323 suite passed in
13.458s and7 CLI smokes passed after fixes. Exact feature hash is in Git/final report.
Commit requested feature then STOP; no merge/push/tag or other-worktree edits.
Inherited records below are historical where this risk change supersedes them.

---

# Historical state — frozen PAPER range boundaries corrected

2026-09-12. Codex; work/trading-brain at Agent Trading-brain.
Correction parent9adfe26ad61ed63d019f70c3f69a4756710c4599;
original baseadbafa485c900164c95ed0e13fce0d267da8b645.
[U-RANGE-BOUNDARIES-001] supersedes symmetric outside-touch semantics.
Every candidate candle wick breach invalidates BEFORE confirmation; inside-only
touches/equality allowed; terminal RANGE_INVALIDATED retains frozen pair and
breach evidence. Raw swings/valid levels continue unchanged; only confirmed
ranges can manipulate. SwingEngine and production API unchanged.

Original full-fixture4H/1H trades are invalid and withdrawn. Four299-candle
BTC default replays now yield zero PAPER orders. A separately labelled249-bar
15m suffix from Sep09 21:15 UTC yields a valid default-config SHORT:
entry77214.6 / SL79996.3 / EQ TP77019.9 / size0.03594923 BTC. This bounded
context changes seeding, not rules;1140 suffixes checked with fixed defaults.
Corrected25-candle synthetic full chain has inside touches80800/119000 and
only a post-confirmation77000 sweep. [Spec](specs/trading-brain-v0.1.md),
[evidence](trading-brain-replay.md), [exact JSON](research/trading-brain-replay-evidence.json).

Full292 tests pass, zero failures/errors (281 before +11 correction methods);
6 CLI smokes;1196 original real +249 bounded real +25 synthetic prefix checks.
Independent read-only correction review found no material defects. No empirical
strategy validation, live writes, merge/push/tag or automatic reseed added.
Commit `fix: enforce frozen range boundaries before confirmation` separately;
read exact final hash/clean status from Git/report. STOP after commit.
Inherited historical records below do not assert current valid PAPER examples.

---

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
