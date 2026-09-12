# Trading control Web App shell

User-authorized frontend shell [U-WEBAPP-SHELL-001], isolated on work/webapp.
Base: 9d842077581f51b8264344fb331d1123665955e7.
Final commit message: feat: add Telegram trading control web app shell.
Read the exact resulting commit from Git or the completion report.

## Start

From Agent Trading-webapp, with Node 22.12+ (verified on Node 24.15.0):

```sh
npm install
npm run dev
```

Open http://127.0.0.1:5173. No backend, Telegram account, credentials or Python
environment is required. Build with npm run build; check with npm test.
npm run preview serves the production build locally. dist is ignored.

## Implemented

Dashboard: local RUNNING/STOPPED status, BTC-USDT, active strategy, sample
NO SETUP decision, intended OKX ATK MCP source shown disconnected, UNKNOWN
Auto Earn, recent session activity, Start Bot/Stop Bot/Open Strategy.

Strategy Settings: Sweep Reversal/Custom; context/structure/setup/confirmation
timeframes; three editable local module switches and three unavailable modules;
risk per trade %, max daily loss %, max open positions; trailing stop preference;
ANALYZE/PAPER/LIVE preview; validated Save Strategy; unsaved-navigation warning.
All edit controls lock while the local bot runs, so drafts cannot become trapped.
LIVE requires checkbox confirmation, a visible warning and remains blocked at
both the Dashboard Start button and mock API start method.

Market Structure/Liquidity Sweep/Body Close Reclaim switches are demo configuration
only, with no module evaluation. Manipulation and Range are COMING SOON;
Premium/Discount is NOT IMPLEMENTED and disabled. Premium/Discount is context,
never an independent entry trigger. Swing/ATR trailing is configuration only.
Risk values/defaults/bounds are UI preferences, not approved sizing/strategy rules.

## Mock and real boundaries

| Field or action | Current source |
|---|---|
| Bot status/start/stop/mode | In-memory local UI state; resets on reload |
| Strategy, timeframes, conditions, risk, trailing | Validated localStorage config; session-only fallback if storage is blocked |
| BTC-USDT | Fixed configured demo symbol |
| Latest decision | Explicit NO SETUP sample; no backend decision mapping |
| Market price/observation time | null; no market reads |
| Market data source | Intended OKX ATK MCP, disconnected |
| Auto Earn | UNKNOWN placeholder; no account reads |
| Activity/history | Actual local UI actions, capped at 8; resets on reload |
| Telegram ready/expand/environment | Official optional SDK when present in a real WebView |
| PAPER/LIVE execution | Unimplemented; no simulator, fills, orders or exchange writes |

A storage write failure leaves the saved profile unchanged and shows an error.
Corrupt saved profiles fall back to ANALYZE demo defaults. Financial/risk values
stay strings; no price/quantity is parsed into float.

The SDK script loads asynchronously. React renders in browser mode independently
and initializes Telegram when the SDK arrives. No initData authentication, bot,
production identity/session handling or deployment is implemented. A deployed
Telegram launch still needs a reachable HTTPS URL and separate launcher setup.

## Adapter boundary

src/api/control.ts defines TradingControlApi:
kind = MOCK | BACKEND; strategyStorage = BROWSER | SESSION | BACKEND;
getDashboard(), getStrategy(), saveStrategy(profile), startBot(), stopBot().
Methods return promises of the typed models in src/types/control.ts.
Replace the factory in src/api/index.ts with an HTTP adapter and inject it into
App. Networking and wire-to-view mapping belong in that adapter, not components.
The current frontend model is a local projection, not a frozen backend schema.

## Exact backend contracts still needed

The following HTTP routes are **proposals for a later integration task**, not
existing endpoints or implementation authorization. Backend ownership/review
must settle wire naming, capability validation, concurrency, access and errors.

| Needed contract | Proposed route and payload |
|---|---|
| Authoritative bot state | GET /api/v1/bot -> status RUNNING/STOPPED, mode, started_at nullable UTC, updated_at UTC, profile_id, profile_version, execution_available=false |
| Start/stop acknowledgment | POST /api/v1/bot/start with profile_id/profile_version/mode; POST /api/v1/bot/stop with {}; both return authoritative bot state, with defined idempotency and conflict/busy errors |
| Current strategy read/write | GET /api/v1/strategy-profiles/current -> profile_id/version/profile; PUT same route with expected_version/profile -> validated saved profile/version; stale edits must return 409 |
| Presets and capabilities | GET /api/v1/strategy-capabilities -> preset IDs/versions, supported timeframe roles/values, per-module availability/reasons, trailing capabilities and enabled execution modes |
| Real activity/history | GET /api/v1/agent-events?limit=8&cursor=... -> items of id/at/title/detail/tone/origin=BACKEND and next_cursor; define ordering and retention |
| Market and decision projection | Reuse GET /api/v1/analyses and GET /api/v1/analyses/{id}; preserve schema-version discrimination, ticker strings/times, provider provenance, freshness, report lifecycle and real reason codes |
| Auto Earn read-only placeholder replacement | GET /api/v1/account/auto-earn -> status ON/OFF/UNKNOWN, observed_at nullable UTC and reason_code; account authorization remains future work |

Current real API accepts strict symbol-only POST /api/v1/analyses. It does not
accept strategy, risk, timeframes or mode, and does not start a bot.
Current NO_TRADE / STRATEGY_NOT_CONFIGURED must project to unavailable decision
with its actual reason, never NO SETUP/WAIT. FAILED analysis remains a data error.
The five future outcome labels need approved outcome/reason/evidence contracts
before any real outcome can appear. EXECUTED requires actual PAPER/LIVE evidence.
No write endpoint or LIVE authorization/credentials is added here.

A future HTTP adapter also needs a same-origin deployment or explicit backend
CORS/access policy, cancellation/timeouts and sanitized error envelopes. Its
capability response must govern allowed settings; local switches are not proof
of backend support. Bot startup must reject unsupported PAPER/LIVE server-side.

## Verification

npm install: exit 0; 25 packages audited, zero vulnerabilities reported.
npm run build: exit 0; TypeScript and Vite 8.3.0 production build.
npm test: 10 passing lightweight Node checks, including corrupt enum arrays,
storage failure, local transitions and LIVE block.

Built-page browser verification at 390x844 and 1280x900: both screens inspected,
no horizontal overflow, no console errors/warnings; start/stop, preset/timeframe/
risk/trailing/module edits, invalid risk feedback, canceling dirty navigation,
save/reload persistence, LIVE checkbox confirmation/start block and running
settings lock exercised. Telegram SDK detection tested with a small wrapper
fixture; an actual Telegram device/authentication flow was not tested.

No Python backend/core changes, algorithms, market reads, real execution,
Telegram bot, backend persistence, charting, merge, push or tag.
