# Next task - calibrate the guide-anchored range detector from round-2 labels

Updated 2026-09-25. Do not create new worktrees or sibling Agent Trading folders.
Normal work stays in `C:/Users/Serdar Arif/Desktop/Agent Trading` on `main`.

1. Strategy, highest value. The DD models, the R ladder and three trailing
   methods are built [U-DD-DEVIATION-001] [U-RR-TRAIL-001]. The comparison is
   in [PROJECT_STATE](PROJECT_STATE.md) (2026-09-25). Review it with the
   owner before changing any threshold.
   (00) [U-RANGE-ANCHOR-001] Round 1 labels rejected the engine's ranges (3
        of 50 real). A guide-anchored prototype is under review; see
        [range-anchor-2026-09-26.md](specs/range-anchor-2026-09-26.md).
        - Read `labels_v2` from [Range Kontrolü](https://claude.ai/artifact/PUkS2Mwvv2qLuBsc2oJvce).
        - Calibrate its thresholds.
        - Implement it as a `RangeEngine` mode with TDD, keeping the `RANGE_*`
          events.
        - Rerun the 30-pair sweep.
        This supersedes choosing a touch rule in (0).
   (0) [U-FUNNEL-001] The 2026-09-26 audit found why so few trades were
       taken; see [PROJECT_STATE](PROJECT_STATE.md) (2026-09-26).
       - Read the labels from the review page ([Range Kontrolü](https://claude.ai/artifact/PUkS2Mwvv2qLuBsc2oJvce),
         collections `labels` and `pairnotes`).
       - Score each touch rule against them. The rules are: current, A =
         overshoot to the deviation limit, B = band 20% of the height, AB,
         and E = the old drifting tolerance.
       - Implement the chosen rule with TDD as a profile option, then make
         it the default.
       - Then ask the owner about the inverted HTF frame (re-anchor on the
         fresher level and the extreme since it) and a pending-entry expiry.
       - The what-if harness is in the scratchpad (`whatif_sweep.py`).
   (a) The owner chooses the default trailing method:
       - `CONFIRMED_HIGHER_LOW`, the current default;
       - `INTERNAL_PIVOT`, with N=2 or N=3;
       - `ATR_TIERS`.
       Then regenerate the trade report for that run.
   (b) The touch tolerance. At a correctly measured 0.5% of price, a year of
   30 pairs gives 60 ranges and 11-15 trades. Ask the owner whether a
   volatility-aware tolerance (a share of the range height or of ATR) matches
   their chart reading better.
   (c) Shorts still lose (S1: 5 trades, -1.78R).
   (d) Measure with OKX TR's real fees (limit entries, stop exits).
   (e) The panel settings screen does not show the DD and ladder knobs (entry
   models, EQ share, break-even trigger, trailing method). Add them. Until
   then, panel partials above 50% are rejected.
   (f) Then:
       - breaker/S-R flip entries (DD model 1's second option);
       - DXY for model 3, if a feed appears;
       - the symmetric range anchor (gap report section 10).
   Rerun: `python -m agent_trading.backtest.sweep --data data/okx_tr_usdt_top30
   --output runs/<name>`, about 15 minutes.
       - For the DD-as-shipped exits, add `--partial-tp ''
         --break-even-trigger RANGE_EQ`.
       - For the pre-DD engine, add the legacy flags from the backtest spec.
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
