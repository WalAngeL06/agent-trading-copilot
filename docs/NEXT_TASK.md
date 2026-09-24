# Next task - review the DD deviation models with the owner

Updated 2026-09-25. Do not create new worktrees or sibling Agent Trading folders.
Normal work stays in `C:/Users/Serdar Arif/Desktop/Agent Trading` on `main`.

1. Strategy, highest value. The DD deviation models are the default
   [U-DD-DEVIATION-001]; the first 30-pair result is in
   [PROJECT_STATE](PROJECT_STATE.md) (2026-09-25). Review it with the owner
   before changing any threshold.
   (a) Shorts still lose on the CORE pairs under both models (24 trades,
   -3.86R) while longs win (19, +16.07R).
   (b) Measure with OKX TR's real fees (limit entries, stop exits).
   (c) The panel settings screen does not show the DD knobs (entry models, EQ
   share, break-even trigger). Add them; until then, panel partials above 50%
   are rejected.
   (d) Then: breaker/S-R flip entries (DD model 1's second option), DXY for
   model 3 if a feed appears, and the symmetric range anchor (gap report
   section 10).
   Rerun: `python -m agent_trading.backtest.sweep --data data/okx_tr_usdt_top30
   --output runs/<name>`, about 15 minutes. Add the legacy flags from the
   backtest spec to compare with the pre-DD engine.
2. VPS, together with the owner: the DigitalOcean VPS runs, tr.okx.com is
   reachable there, and the multi-pair download was done on 2026-09-21. The
   product deployment still needs a domain pointing at it; then run the draft
   deployment from [deploy-vps.md](deploy-vps.md) and fix what the first real
   run reveals.
3. Network: the application connects to OKX through ATK/MCP whenever network
   access is available; the 2026-09-16
   [diagnosis](fresh-atk-runtime-diagnosis.md) verified every public layer. This
   is environment-specific, not a product defect: on
   2026-09-19 (latest check 14:51 Europe/Istanbul) TLS to `*.okx.com` was reset
   while other HTTPS worked. Before concluding either way run
   `curl -sS -o /dev/null -w "%{http_code}\n" "https://tr.okx.com/api/v5/market/ticker?instId=BTC-USDT"`.
   While it fails the agent shows RECONNECTING and recovers on its own.
4. GitHub: `WalAngeL06/agent-trading-copilot` is private. Publish `main` by
   fast-forward only and keep it the default branch. Never merge stale PR #1
   (`work/final-demo` -> `main`). Keep `work/final-demo` and the local
   `archive/*` tags until the owner decides otherwise.
5. The canonical `.env` already holds OKX read-only keys and a Telegram token
   (values not displayed); account reads could not be verified locally because
   of the network. On the VPS prefer a new read-only key restricted to its IP,
   and set `API_ACCESS_TOKEN` and `TELEGRAM_ALLOWED_USER_IDS`. The allowlist is
   empty today, so the bot answers anyone who messages it; do not guess the ID,
   the owner reads it from the bot's `/start` reply.
6. Owner: review `_archive/` (it holds `.env` files with filled keys and local
   run data) and delete it when satisfied. Pushing the local `archive/*` tags
   to GitHub is optional.
7. Archived, unreviewed candidates: the BacktestPage UI in `archive/final-ui`.
   The LIVE_SMOKE path in `archive/final-demo` stays out of scope unless the
   owner explicitly authorizes live execution work.

Current deliverable and tests: [PROJECT_STATE](PROJECT_STATE.md),
[consolidation evidence](product-consolidation.md). No automatic push or LIVE
execution. Old chapter/worktree entries below are historical reference only.

---
## Historical next-task notes (superseded)

# Current boundary — STOP after public publish

2026-09-12. The owner then explicitly authorized the README and a public push,
superseding the earlier no-README / no-push boundary. Published to
`https://github.com/WalAngeL06/agent-trading-copilot` (public, default branch
`work/final-demo`, only that branch pushed). Credential sweep over all 22
published commits found no secrets, no `.env` and no tunnel URLs.

STOP. Do not redesign the UI, add a second dashboard, touch strategy or backtest,
add charts, enable real-money execution, push other branches or merge to main.

Open owner-device step: send `/start` to `@agentiic_trading_bot`, tap Open Dashboard
and confirm the Mini App shows real state. Tunnel URLs are ephemeral; regenerate
them and rewrite `.env` plus restart both services before any later demo.
Decide separately whether the concurrent `/dashboard` endpoint in
`agent_trading/api.py` is kept or discarded; it is currently uncommitted.

---

# Current boundary — STOP after final demo runtime repair

2026-09-12. Commit the verified tracked repair as
`fix: repair final demo runtime wiring`, report the requested evidence, then STOP.
Do not merge, push, tag, fill credentials, start LIVE execution or modify Strategy
V1 semantics. The ignored local `.env` remains for the owner to fill manually.

---

# Historical boundary — STOP after RiskEngine feature commit

2026-09-12. [U-RISK-ENGINE-001] authorizes only this isolated RiskEngine from
e9ff346b151587c8deaf903b9ffc40d289659725 in work/risk-engine.
Finish full verification/review and commit
`feat: add configurable structure-aware risk engine`, report hash/tests/approved
and blocked examples/exact [H] defaults/gaps, then STOP. No merge/push/tag.
Do not auto-start trailing, zone detectors, strategy semantics, API/UX integration,
LIVE or another feature. [Spec](specs/risk-engine-v0.1.md), [evidence](risk-engine.md).
SwingEngine and frozen Range semantics remain unchanged. Further work needs a
new explicit instruction; historical task descriptions below are not authorization.

---

# Historical boundary — STOP after separate range correction

2026-09-12. [U-RANGE-BOUNDARIES-001] authorized boundary diagnosis/fix,
raw preservation, tests and real replay, separate correction commit then STOP.
Do not merge/push/tag or begin another feature. Worktree remains work/trading-brain.
Read [corrected spec](specs/trading-brain-v0.1.md) and [evidence](trading-brain-replay.md).
Original4H/1H trades are withdrawn; full fixtures have no orders; explicit bounded
15m/synthetic chains remain. No new reseed/expiry policy or missing DD rules approved.
Historical task descriptions below do not override this STOP boundary.

---

# Current next task — STOP after integration verification

2026-09-12. Only the requested three-commit integration and verification are
authorized on `work/hackathon-integration`. Run full Python tests, frontend
`npm install`, `npm run build`, `npm test`, and verify clean Git status. Report
HEAD, source/included commits and results, then STOP. No new features, push/tag
or automatic continuation of the historical source-branch plans below.

---

# Next task — Web App shell complete; awaiting instruction

Updated: 2026-09-12. Worktree/branch: Agent Trading-webapp / work/webapp.
Current frontend authority: [U-WEBAPP-SHELL-001].

Stop after the requested frontend checkpoint. Do not auto-start integration,
strategy algorithms, Swing, execution, bot, authentication or deployment.

When explicitly authorized later, read [shell handoff](webapp-shell.md), the
local spec and current analysis v0.2 contract. Review/freeze bot lifecycle,
strategy capabilities/versioned save and event contracts with the backend owner.
Replace src/api/index.ts's mock factory with a typed adapter. Preserve Decimal
strings/UTC, original report versions, actual errors/unconfigured outcomes,
unavailable modules and disabled LIVE execution.

Swing work is independent and is not a prerequisite for this shell.
The prior backend intelligence next-task record is retained below as history;
it is not the next instruction for this worktree.

---

---

# Next task — STOP after OKX capability audit

## Current branch boundary [U-OKX-CAP-001]

2026-09-12. `work/okx-capabilities` in Agent Trading-okx was created from
`9d842077581f51b8264344fb331d1123665955e7` for capability research only.
[Results](research/okx-tr-capabilities-2026-09-12.md);
[exact runtime names and evidence](research/okx-tr-capabilities-2026-09-12.json).

Commit `research: verify OKX account earn and execution capabilities`, then
STOP. No merge/push/tag or automatic integration. No Swing, strategy, frontend,
trades, fund movement, Earn enablement or LIVE work is authorized here.

A possible separately approved next integration is an owner-only read contract
for trading/funding balance, savings balance and balance-derived Auto Earn
flags. Independent TR authentication is required: connected desktop reads work,
local CLI and fresh self-hosted MCP have no private auth. Read-only server mode,
an explicit client allowlist, schema discovery, exact Decimal/UTC handling,
private-log sanitization and nonzero OKX-code gates precede a real-account read
proof. Earn simulation returned 50038; do not promise simulated Earn or tested
write support.

## Preserved backend next-task context

The historical checkpoint plan below is preserved as context and must not
auto-start from this capability branch.

# Next task — SWING ENGINE R&D / SPEC

Updated: 2026-09-12. Ch.1 remains incomplete.
Current contract correction: [U-AUTONOMOUS-CONTRACT-001].
**Await the next explicit user instruction; do not auto-start implementation.**

## Starting point

Read AGENTS -> PROJECT_STATE -> HANDOFF -> this file, then
[analysis v0.2](specs/analysis-api-v0.2.md),
[autonomous runtime ADR011](DECISIONS/011-autonomous-runtime-contract.md),
[Market Structure draft](specs/market-structure-v0.1.md) and
[SOURCE_REGISTRY](SOURCE_REGISTRY.md).
Preserve historical [v0.1](specs/analysis-api-v0.1.md) and smoke evidence.

Backend worktree/branch: Agent Trading-backend / work/copilot-backend.
Correction parent:6c1af4b6f6cd8c22986b8436dd26d61f64de469d.
Obtain correction hash from Git/final report; verified baseline170 tests.
Integration/UX remain at Ch.0. No merge/push/tag/remote creation.

## Exact next trading-intelligence task

**SWING ENGINE R&D / SPEC — Causal Swing Engine**, before strategy-engine code.

Study the existing source-confirmed DD rules [D-DD-MSB-001] and explicitly
separate their qualitative meaning from unresolved algorithmic definitions.
The repository lacks the original DD recording/transcript; request missing
source/clarifications when needed rather than creating an attestation.
Do not silently substitute generic SMC, a library pivot or a 2/3/5-bar rule.

The separately authorized R&D/spec should resolve or explicitly leave pending:

- Observable opposing movement that confirms a swing, and its first knowable
  closed-candle evaluation (N-1).
- Candidate identity/replacement/ties, meaningful-versus-incidental extremes
  and any responsibility linkage needed downstream (necessary N-2).
- Causal initialization, insufficient/truncated history, retention and
  immutable evidence identity (necessary N-3).
- swing_time versus confirmed_at/recognition time, no intrabar precision
  invented from OHLC, equal-time per-symbol/TF ordering (necessary N-7).
- Prefix-invariant replay/bootstrap and future-suffix tests, independent state
  by symbol/timeframe and safe missing/stale/revised-data behavior.

Document inputs/state/events/statuses and source-labelled hand-checked causal
fixtures. Any numerical threshold or confirmation predicate is
**ALGORITHMIC DEFINITION PENDING** until approved. No SwingEngine or downstream
implementation is authorized by the present correction. Full
MarketStructureEngine still needs N-1–N-7, not merely a Swing spec.

Dependency sequence:
Swing -> Market Structure -> Range -> Premium/Discount -> Deviation ->
Acceptance -> Trade Plan -> Risk -> Execution.
This does not authorize entries, sizing, acceptance or real execution.
Premium/Discount stays context, no universal EQ reclaim; DD HTF side blocks
and [U-PD-001] remain separate/preserved.

## Preserved product boundaries and deferred work

The intended product is an autonomous trading agent. Approved future profiles
own required timeframes; user display selection cannot choose trading inputs.
Current manual/debug analysis is bounded, default4H/1H/15m, honest
NO_TRADE / STRATEGY_NOT_CONFIGURED, Decimal/UTC and real MCP -> core ->
v0.2/SQLite/API. Original v0.1 records remain unchanged.

AutonomousRuntime, continuous monitoring/deduplication, PAPER simulator and
LIVE authorization/execution remain specs/future work. LIVE is disabled and
unimplemented. No private/account/order path or usable live switch exists.
P0.5 still needs a separately approved meaningful deterministic intelligence
slice; the unconfigured placeholder does not satisfy it.

Bounded full-chart-history persistence/API is a deferred product extension,
not the next intelligence foundation. UX/Telegram/LLM/deployment and later
Range/Deviation/source intake stay outside this next R&D/spec until authorized.
