# Current handoff - VPS hardening, 2026-09-19

Claude; branch `main`. The owner asked to make the system robust before moving
it to a VPS, then to continue together. Read "VPS hardening" in
[PROJECT_STATE](PROJECT_STATE.md) and [NEXT_TASK](NEXT_TASK.md).

Commits: reconnect with backoff, owner-only API access, test isolation from the
developer's `.env`, durable PAPER session, restart-after-restart marker, plus
this documentation and the draft deployment files. Each feature was built test
first; 620 Python tests, 15 frontend tests and the build passed then. No LIVE
path. GitHub publishing follows the fast-forward rule in NEXT_TASK. The
deployment files are unverified until the first real VPS run.

---

# Previous handoff - branch consolidation, 2026-09-19

Claude; canonical root `C:/Users/Serdar Arif/Desktop/Agent Trading`, branch
`main`. The Git layout changed; read "Git and local data" in
[PROJECT_STATE](PROJECT_STATE.md) first.

- Reviewed, fixed and committed the previously uncommitted Lira Auto Earn local
  preference and Telegram HTTPS-only Open Dashboard button (`98c75ab`). Review
  fix: the first preference save returned 503 on a fresh clone because
  `config/` did not exist; a regression test covers it.
- Committed the pending 2026-09-16 fresh runtime diagnosis documentation.
- `main` is the only development branch; old `work/*` branches are `archive/*`
  tags; former worktree folders are in the locally excluded `_archive/`.
- Verified: 593 Python tests, 11 frontend tests and the production build pass.
- Not done: no push or remote change and no files deleted. The owner decides on
  `_archive/` and on publishing `main` to GitHub.

---

# Previous handoff - product consolidation, 2026-09-16

Codex; canonical root `C:/Users/Serdar Arif/Desktop/Agent Trading`,
branch `strategy-v0.1`. See [PROJECT_STATE](PROJECT_STATE.md) and
[verification evidence](product-consolidation.md) before reading older entries.

## Delivered

Existing designed React/Vite UI preserved in src, connected to the real API.
Local strategy GET/PUT and atomic persistence use the real engine's validators.
BotService now runs configured multi-timeframe strategy through read-only MCP.
Embedded emergency UI removed from the canonical backend; /dashboard redirects.
Windows startup, README and canonical-root policy updated. PAPER only.

## Verification and unfinished external checks

590 Python tests, 10 frontend tests, build and desktop/mobile browser checks pass.
Browser save/reload and nondefault process-restart persistence pass; verification
risk restored to 1%. Real browser Start/Stop and running settings lock pass.
Fresh follow-up diagnosis now passes public MCP initialization, tools/list,
ticker/candles, normalization, real multi-timeframe BotService processing and
Dashboard CONNECTED. Repeated observation timestamps confirm polling. No runtime
code changed. Previous network-blocked attribution is withdrawn; old failure is
not reproduced. Account AUTH_MISSING and Telegram disabled remain honest states.
See [fresh diagnosis](fresh-atk-runtime-diagnosis.md).
No private credentials copied. Agent left STOPPED. Local services may remain open
in their visible windows for review; close them or use existing services before
running run.ps1 again.

## Commit / uncommitted data

Requested commit: `refactor: consolidate production webapp and local configuration`.
Read its exact hash from git log/final report; no push. Root commit includes the
imported existing product/strategy plus consolidation, because root HEAD lacked
those modules. No edits were made in nested source folders. The following were
untracked before this task and remain untracked outside the commit:

- Nested projects: Agent Trading-auth, -backend, -backtest, -brain, -final-ui,
  -final, -integration, -okx, -strategy-v1, -swing, -ux, -webapp.
- User folders: Yeni klasör, odin-videolar, öğrenme-dd finance ve odin.
- grep.exe.stackdump.

No new worktree, sibling directory, branch, tag or remote was created. Existing
stale registrations are preserved. Runtime config/.env/logs/screenshots are
ignored. Consolidation implementation is committed at e826277. The fresh diagnosis
updates only this handoff, PROJECT_STATE, NEXT_TASK, product-consolidation and the
new fresh-atk-runtime-diagnosis report; these documentation changes were
committed on 2026-09-19 together with the branch-consolidation records. The
ignored fresh diagnostic probes and screenshot remain local. For current state, inspect git status to distinguish preserved untracked data.

---
## Historical handoffs (not current status)

# Current handoff — WebApp runtime operational

2026-09-12. Worktree `Agent Trading-final`, branch `work/final-demo`, parent
`60c8474`. The existing React/Vite frontend already lived in this worktree and was
reused unchanged in design; only runtime wiring was repaired.

Three runtime defects fixed. `BackendApi` stored native `fetch` as an instance
member and invoked it as `this.request(...)`, so every dashboard load threw
`TypeError: Illegal invocation` and the shell showed "Control center could not
load"; the constructor now wraps it, preserving test injection. `App` had no
refresh at all, so a running agent never updated; a silent 5s poll now refreshes
the snapshot and pauses while a bot action is busy or a strategy form is dirty.
`vite.config.ts` allows `.trycloudflare.com` so the dev server answers tunnelled
Host headers. No UI redesign, strategy, backtest or execution change.

Verified live: `npm install`, `npm run build`, 11 frontend tests, 360 Python tests.
Local and public HTTPS flows both load real state — bot STOPPED/RUNNING, PAPER,
`market_source=OKX_ATK_MCP`, `market_connected=true` after start with real 15m
candle updates, `account_auth=CONNECTED` with a real balance, live activity feed,
STOP returning to stopped with Telegram still RUNNING. No mock states.

Two cloudflared quick tunnels (frontend 5173, backend 8000) are ephemeral; `.env`
holds their URLs in `WEBAPP_URL` / `VITE_BACKEND_URL` / `ALLOWED_ORIGINS` and stays
ignored. Restart the frontend after changing `VITE_BACKEND_URL` and the backend
after `WEBAPP_URL` / `ALLOWED_ORIGINS`. Telegram bot `@agentiic_trading_bot`
answers `getMe` and polls with the HTTPS WebApp URL; sending `/start` and tapping
Open Dashboard inside Telegram remains an owner-device step, not machine-verified.

The existing market card intentionally shows source, connection and decision but
no price, so `last_price` is fetched and unused; unchanged by request. An
uncommitted `/dashboard` HTML endpoint in `agent_trading/api.py` arrived from a
concurrent session, duplicates this frontend and is deliberately not committed.
Then, under a later explicit owner instruction, the README was rewritten with a
self-hosting and Telegram Mini App guide and the branch was published to the new
public repository `WalAngeL06/agent-trading-copilot` with `work/final-demo` as its
default branch. Only that branch was pushed; no merge and no tag. A scan of all 22
published commits for the live credential values, `.env` additions and tunnel URLs
came back clean.

---

# Current handoff — final demo runtime repair

2026-09-12. Worktree `Agent Trading-final`, branch `work/final-demo`, starting
HEAD `31fded92a018958165b6c28554937fd71b9adc09`. The requested repair is complete
under commit message `fix: repair final demo runtime wiring`; read the exact hash
from Git after commit.

BotService is created by the default FastAPI factory and starts Telegram polling
at application lifecycle startup while the trading engine remains STOPPED.
Starting the bot opens the existing pinned read-only public ATK MCP session and
feeds normalized real 15m candles to the unchanged TradingBrain. Private reads
retain the four-tool allowlist and expose sanitized auth/equity/Auto Earn state.
Readiness, bot APIs and the frontend use observed state and timestamps. CORS uses
`ALLOWED_ORIGINS`; mobile Telegram requires public HTTPS frontend and backend
URLs because the browser calls `VITE_BACKEND_URL` directly.

Fresh checks: 360 Python tests pass; 11 frontend tests pass; frontend build passes;
default backend startup/liveness passes; real public MCP bot-start smoke reports
connected OKX data, PAPER and zero trades. `.env` exists locally with empty values
only and is ignored. No merge/push/tag and no Strategy V1 semantic edits.

---

# Historical handoff — modular structure-aware RiskEngine

2026-09-12. Codex; work/risk-engine in
C:/Users/Serdar Arif/Desktop/Agent Trading/.worktrees/risk-engine.
Parent e9ff346b151587c8deaf903b9ffc40d289659725. No pre-existing uncommitted work.
[U-RISK-ENGINE-001] explicitly supersedes the earlier STOP for this risk task only.
[Spec](specs/risk-engine-v0.1.md), [report](risk-engine.md), [exact examples](research/risk-engine-evidence.json).

Risk models/engine and zone-support adapter are new. Broker requires an
engine-issued plan; next-open fill reapproves geometry/R:R/size before opening.
BLOCKED evidence has primary machine reason. Stop management retains original
plan and monotonic updates, with configurable1R default [H] and fixed profile.
Runtime/config/CLI compose these modules; exports and offline v0.2 report updated.
Existing paper/replay tests now use approved plans and revised risk expectations.
Raw Swing, Range boundaries/selection, manipulation and gap detector files and
dependencies are preserved. Production API/frontend unchanged.

Verified baseline292 and final full323 tests pass;31 new focused risk methods;
seven CLI smokes. Evidence examples are synthetic and do not prove profitability.
Exact [H] defaults and remaining gaps are in the spec/report. Runtime logs stay
ignored in runs. Completed source/tests/docs belong to the requested feature
commit; obtain final hash and clean status from Git/final report. No external writes.
Independent review found skipped-first-fill/exact-Decimal defects; regressions
and exact next-open/arithmetic fixes verified. Re-review clear; full323 pass
in13.458s,7 post-fix CLI smokes pass. Full command from this checkout:
`C:/Users/Serdar Arif/Desktop/Agent Trading-backend/.venv/Scripts/python.exe -B -m unittest discover -s tests -v`.
Commit/Git status verification follows this documentation freeze; no other files
remain uncommitted after successful requested checkpoint. Read exact state from Git.
No merge/push/tag. NEXT: STOP after requested commit; no trailing/strategy feature.
Older handoff examples/counts are retained below as history, superseded for risk.

---

# Historical handoff — frozen range boundary correction

2026-09-12. Codex; work/trading-brain / Agent Trading-brain.
Parent9adfe26ad61ed63d019f70c3f69a4756710c4599. Explicit user correction
[U-RANGE-BOUNDARIES-001]: any pending-candidate wick breach invalidates;
inside-only low/high tolerance; after-confirmation sweeps remain manipulation.

Changed range/models/runtime,11 additional regressions, corrected synthetic
fixture, exact real15m bounded suffix fixture, spec/source/evidence/memory.
Raw SwingEngine, valid-level selection, gap/risk/broker and dependencies unchanged.
RANGE_INVALIDATED retains causal breach candle/reasons, blocks revival and
manipulation, and preserves every raw event. Original4H and1H examples withdrawn;
full BTC replays yield no orders. New15m249-row suffix from source index50:
SHORT77214.6 / SL79996.3 / TP77019.9 / size0.03594923 BTC, with unchanged defaults.
Corrected synthetic25-bar full chain retained. [Evidence](trading-brain-replay.md).

Full292 tests pass;6 CLI smokes;1470 real/synthetic prefixes checked.
Independent read-only correction review clear. No pre-existing uncommitted work
before correction. Separate requested commit includes only this correction;
verify exact hash and clean status from Git/final report. Ignored local runs only.
Original valid-trade assertions are superseded, with prior records in Git history.
One-range/no-reseed and other [H]/DD/MTF/risk/cost/validation blockers remain.
No exchange writes, merge/push/tag. NEXT: STOP; no additional work authorized.
Inherited records below are historical, not current valid examples/permissions.

---

# Current handoff — hackathon integration

2026-09-12. User-authorized integration only in `work/hackathon-integration`
at `C:/Users/Serdar Arif/Desktop/Agent Trading-integration`, based on
`50146110f727048677b7d6c6643221f00d77cf22`. Apply `75d1200`, `d6933cf`,
and `8322fab` in that order. Documentation conflicts preserve both source
records below as historical context; their branch-specific permissions do not
authorize new work here. No new feature or behavior change. Run the full Python
suite, frontend install/build/tests and verify clean Git status; exact HEAD and
fresh results belong in the final integration report. STOP afterward. No push/tag.

---

# Handoff — trading control Web App shell

Updated: 2026-09-12. Last agent: Codex.
Work only in Agent Trading-webapp / work/webapp.
Base: 9d842077581f51b8264344fb331d1123665955e7.

Completed user-authorized Dashboard + Strategy Settings, minimal typed mock API,
validated browser-local config, optional nonblocking Telegram environment init,
mobile/desktop styles and lightweight checks. LIVE preview has confirmation
and warning, and cannot start. No backend/strategy/market/exchange/bot code changed.

Files: package/config/lock/index, src/api, src/types, src/components, src/pages,
App/main/styles, src/telegram, shell spec/plan/handoff and worktree-local memory.
Tests/build: npm install and npm run build exit 0, 10 npm test checks pass.
Browser: both pages and critical controls verified at 390x844/1280x900.
Important independent review issues fixed and re-reviewed.
Actual Telegram device launch/authentication remains unverified/unimplemented.

Exact backend gaps and proposals: [webapp-shell](webapp-shell.md).
Local profiles are UI drafts, not approved strategy definitions or executable risk.
Real manual analysis already exists at the base but is not wired into this shell.
Do not map the current backend unconfigured result to the sample NO SETUP label.

Final commit follows this documentation freeze and has message
feat: add Telegram trading control web app shell. Read its hash/clean status
from Git/final completion report. No pre-existing uncommitted work was present.
All completed scoped files are included in that commit; ignored node_modules
and dist are local build artifacts. No merge, push or tag.

Stop. Await a new integration instruction. Keep other worktrees untouched.
The prior shared backend checkpoint handoff is retained below as historical context.

---

---

# Handoff — OKX TR capability audit

## Current handoff — 2026-09-12

Last agent: Codex. User authorization [U-OKX-CAP-001].
Only `work/okx-capabilities` / `C:/Users/Serdar Arif/Desktop/Agent Trading-okx`.
Clean starting checkpoint: `9d842077581f51b8264344fb331d1123665955e7`.
Target commit: `research: verify OKX account earn and execution capabilities`;
read its actual hash from Git/final report.

[Capability matrix](research/okx-tr-capabilities-2026-09-12.md) and
[exact discovery/evidence](research/okx-tr-capabilities-2026-09-12.json) record
165 connected TR tools, 31 fresh local read-only tools, auth requirements,
schema differences and 13 successful real-account/catalog read tools.
USDT Auto Lend off / Auto Staking unsupported; Earn holdings/orders empty.
Simulated Earn is unavailable (50038). Spot order/fill/trailing reads succeed;
write support is exposed and untested. Remote auth works for reads, but grant
scope/method is not exposed; CLI is unauthenticated and local private MCP reports
AUTH_MISSING. Product account integration is still absent.

Changed files are research report + sanitized JSON, PROJECT_STATE, HANDOFF,
NEXT_TASK and SOURCE_REGISTRY. No pre-existing dirty files; no product code,
tests, dependencies, Swing, frontend, strategy or runtime configuration changes.
No other worktree was edited. Temporary local probe home was cleaned up.
Zero trades/order writes/transfers/Earn toggles. LIVE stays disabled.

Full offline suite: 170 tests passed, zero failures/errors, exit 0. Executed
from the OKX checkout with bytecode disabled and
`C:/Users/Serdar Arif/Desktop/Agent Trading-backend/.venv/Scripts/python.exe`;
the package import resolved to Agent Trading-okx. No dependencies were installed.
Documentation/evidence references and JSON counts/statuses were checked.

STOP after the coherent research commit. No merge, push, tag or integration.
Safe next task, only if separately approved: owner-only balance/Earn read
contract and independent TR read authentication, pinned/discovered MCP schemas,
client allowlist, nonzero exchange-code failure gates and sanitized exact values.

## Preserved backend checkpoint handoff

The remainder is inherited backend history, not this task's current permission.

# Handoff — autonomous analysis contract v0.2 correction

Updated: 2026-09-12. Last agent: Codex.
Status: **Contract/configurability correction verified; Ch.1 incomplete.**
Authorization: [U-AUTONOMOUS-CONTRACT-001]. Stop after the requested commit.

## Branch and scope

Only Agent Trading-backend / work/copilot-backend, initially clean at
`6c1af4b6f6cd8c22986b8436dd26d61f64de469d` with150 passing tests.
Target commit: `chore: generalize analysis contract for autonomous trading`;
obtain its exact hash from Git/final report, not this containing document.
Integration strategy-v0.1 and UX work/copilot-ux remain at
`24e1f465a886e2941a8ce2fce8fb51d53b643405`. No merge/push/tag/remote creation.

## Product correction and current behavior

The intended product is a self-hosted autonomous trading agent. Future START BOT
maintains required market state and evaluates approved strategies, Acceptance,
Trade Plan, Risk and authorized execution, with notification/audit.
Users configure permissions/risk/symbol scope; strategy profiles own required
timeframes. Display/inspection timeframe never changes strategy requirements.

Current POST /api/v1/analyses remains bounded manual/debug/test/audit/demo and
inspection. It does not start monitoring or execute a strategy. No full bot
loop, scheduler, queue, WebSocket, profile engine, Swing/strategy, frontend,
Telegram, LLM, PAPER execution, account/private path or LIVE switch was added.
[Future runtime/modes/outcomes ADR](DECISIONS/011-autonomous-runtime-contract.md).

## Exact v0.2 correction and compatibility

[Current contract](specs/analysis-api-v0.2.md).
[Historical v0.1](specs/analysis-api-v0.1.md) is byte-for-byte preserved.

- New reports use analysis-report-v0.2 and strategy_context with profile_id=null
  and actual required_timeframes. Null identifies absent strategy, not a fake profile.
- Timeframes is a bounded dynamic map matching that unique collection, not a
  forever-fixed4H/1H/15m schema. Per-timeframe status/freshness/evidence remain honest.
- AnalysisConfig.required_timeframes is immutable operator configuration, default
  4H/1H/15m, with ANALYSIS_REQUIRED_TIMEFRAMES environment support. Current runtime
  accepts the existing10 fixed intervals; wire can represent future calendar labels
  without claiming runtime calendar support. Bound1..16; no request-side selection.
- decision_as_of means the causal deterministic knowledge cutoff. Current manual
  compatibility policy uses the latest closed candle of the shortest required
  fixed interval, after independent initial-cutoff freshness validation; trim
  every history to that cutoff. Default remains the same latest closed15m.
  A future strategy must specify its own causal trigger/ordering, not inherit a
  universal shortest-timeframe synchronization rule.
- Existing v0.1 SQLite JSON remains original. GET/history/key replay use strict
  schema-version discrimination for both versions; no synthetic context is
  inserted into old reports. Default key fingerprint stays compatible; differing
  required input sets conflict rather than silently replay another context.
- Five routes, strict symbol-only body, lifecycle/status/error/null rules,
  Decimal strings/UTC, deterministic wording, JSONL2 and SQLite1 remain.
- Current decision remains NO_TRADE / STRATEGY_NOT_CONFIGURED, no fake NO_SETUP,
  WAIT, TRADE_CANDIDATE, BLOCKED or EXECUTED. Those outcomes and ANALYZE/PAPER/LIVE
  are documented future concepts; PAPER/LIVE are unimplemented and LIVE disabled.

| Endpoint | Retained contract |
|---|---|
| GET /health/live | 200 ALIVE |
| GET /health/ready | Request-driven local probe/cached complete market validation; no network GET |
| POST /api/v1/analyses | Symbol-only, terminal resource201 including FAILED; idempotent replay200 |
| GET /api/v1/analyses/{analysis_id} | Original versioned report, invalid UUID422/unknown404 |
| GET /api/v1/analyses | Bounded limit1..50/offset0..10000, mixed original reports newest first |

Market Structure, Range, Deviation and Premium/Discount remain NOT_IMPLEMENTED;
Acceptance/Risk remain real placeholders NOT_EVALUATED. No fabricated prices,
levels, strategy signals, risk approval, simulated fills or PnL.

## Verification and real compatibility evidence

Initial150 passed. After correction: **150 preserved +20 focused =170 passed**,
zero failures/errors, exit0. New:3 collection,6 wire,8 configured service,
3 versioned HTTP tests. Existing150 test files unchanged.
Normal suite uses complete fake external SDK transport and real normalization,
Decimal/UTC domain, causal core, audit, SQLite and HTTP; no live network needed.

`./.venv/Scripts/python.exe -B -m unittest discover -s tests -v`

Focused tests verify non-baseline1H/5m and1m/1H/5m states, latest closed cutoff,
publication-lag trimming, future filtering, required collection validation,
provider enum drift/no fallback, original/mixed v0.1/v0.2 history/key replay,
context conflicts, honest absent profile and forbidden user/display timeframe
or mode input. Wire rejects mismatched map/candle identities and future evidence.
Two additional regressions preserve v0.1 nested candle/error timeframe enums;
the full legacy report JSON schema matches the Target #2 checkpoint exactly.

The existing unchanged **real product smoke command passed again**:

`./.venv/Scripts/python.exe -B -m agent_trading.product_smoke --node-path 'C:/Program Files/nodejs/node.exe' --server-path 'C:/Users/Serdar Arif/AppData/Roaming/npm/node_modules/@okx_ai/okx-trade-mcp/dist/index.js'`

| Fact | Actual new result |
|---|---|
| analysis_id / version | 517c6e4d-265b-4a9b-9860-cf7f8aa7e4a2 / analysis-report-v0.2 |
| symbol/site/status | BTC-USDT / tr / COMPLETED |
| requested_at | 2026-09-12T09:46:45.857565Z |
| completed_at | 2026-09-12T09:46:50.329515Z |
| decision_as_of | 2026-09-12T09:45:00Z |
| latest close4H /1H /15m | 08:00Z /09:00Z /09:45Z |
| retained candles | 100 per required baseline timeframe |
| profile_id / required_timeframes | null /4H,1H,15m |
| decision/reason | NO_TRADE / STRATEGY_NOT_CONFIGURED |
| spread / order_sent | string0.1 / false |
| reads/runtime | 5 public MCP reads; SDK2.2.0/ATK1.4.6, no CLI fallback |
| storage/audit | SQLite original report +10 real events; unchanged JSONL audit |

Fresh typed HTTP GET/history returned this report and the prior real
v0.1 report580b88e9-a183-4889-8cc7-b861fef405a4 identically to SQLite.
Old v0.1 received no strategy_context. No smoke-created market child remained;
pre-existing desktop MCP processes are unrelated to this product proof.
Original [Target #2 smoke record](product-analysis-smoke.md) remains unchanged.
An additional unchanged direct MCP-adapter smoke passed at 10:04 UTC:21 discovered
tools, all3 required public reads,10 received15m candles/1 open excluded/9 retained,
depth5 on both book sides, SDK2.2.0/ATK1.4.6/TR and order_sent=false.
This verifies baseline/runtime/contract compatibility, not autonomous operation,
strategy correctness or profitability.

## Files changed

No pre-existing uncommitted work; this correction changes16 files.

| File | Responsibility |
|---|---|
| agent_trading/analysis_config.py | Immutable required collection/operator environment |
| agent_trading/analysis_report.py | v0.2 context and collection-driven report |
| agent_trading/analysis_service.py | Collection-driven reads/state/cutoff/readiness and context-safe manual idempotency |
| agent_trading/analysis_api_models.py | Dynamic v0.2 validation and retained v0.1 schema discriminator |
| agent_trading/api.py | Same routes with versioned response types/OpenAPI metadata |
| tests/test_analysis_contract_v2.py | 20 focused real-boundary regression tests |
| docs/specs/analysis-api-v0.2.md | Current wire/product correction |
| docs/DECISIONS/011-autonomous-runtime-contract.md | Future runtime/modes/outcomes/dependency responsibilities only |
| docs/superpowers/plans/2026-09-12-autonomous-analysis-contract.md | Implementation/completion checklist |
| AGENTS.md | Persisted user direction/current boundary |
| README.md | Current product intent/API/configuration/compatibility |
| docs/PROJECT_STATE.md | Actual state/counts/evidence/debt |
| docs/HANDOFF.md | This handoff |
| docs/NEXT_TASK.md | SWING ENGINE R&D / SPEC, pending next instruction |
| docs/SOURCE_REGISTRY.md | Separate user correction and compatibility evidence |
| docs/specs/product-mvp-v0.1.md | Current direction amendment and historical baseline annotations |

Original trading core, CLI/MCP adapters/runtime, SQLite repository, JSONL journal,
product_smoke.py, dependency configuration, all150 prior tests and v0.1 analysis
spec/ADR010/original smoke evidence are unchanged. Ignored .venv/runs/SQLite/audit
and credential stores never enter the commit. No exchange write path exists.

## Next task and limitations

**SWING ENGINE R&D / SPEC — Causal Swing Engine** is the next intelligence task,
only under the next explicit user instruction. Resolve source-labelled swing
confirmation, swing_time/confirmed_at, candidate initialization/ties/retention,
causal prefix invariance and necessary equal-time ordering before any engine code.
Full MarketStructure N-1–N-7 stay blocked; [D-DD-MSB-001]/[U-PD-001] preserved.
Dependency: Swing -> Market Structure -> Range -> Premium/Discount -> Deviation
-> Acceptance -> Trade Plan -> Risk -> Execution.

Chart-history extension is deferred; reports still retain latest/counts rather
than persistent full candle arrays. Future autonomous trigger/durable evaluation
identity, approved profiles, calendar bars, PAPER accounting, authorization,
continuous recovery/refresh, multi-instance leases, UX review, auth/CORS,
transitive locks and Linux/deployment validation remain unimplemented.
ANALYZE/PAPER/LIVE are contract concepts; current SHADOW is intent logging only.
Do not auto-start Swing, chart/UX or bot work after this commit. Ch.1 incomplete.
