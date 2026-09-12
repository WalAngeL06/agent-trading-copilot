# Source registry

Updated: 2026-09-12. **Source and validation are separate concepts.** A source
ID identifies provenance; its confirmation status is not proof of performance.
Agent-authored summaries and external libraries do not become DD strategy truth.

| Source ID | Type | Topic | Status | Empirical Validation | Notes |
|---|---|---|---|---|---|
| [U-RANGE-BOUNDARIES-001] | [U] Exact semantic correction | Frozen candidate boundaries | CONFIRMED PROJECT RULE | PENDING — no DD attestation | 2026-09-12 direct correction: any wick below/above frozen bounds BEFORE confirmation invalidates candidate; low/high proximity is inside-only; preserve raw swings; only AFTER confirmation may sweep/reclaim be manipulation. Separate correction/tests/replay/commit then STOP. [Corrected spec](specs/trading-brain-v0.1.md). |
| [E-RANGE-BOUNDARIES-001] | [E] Corrected offline replay evidence | Invalidation and causal PAPER flow | VERIFIED DETERMINISTIC CORRECTION | NO EMPIRICAL STRATEGY VALIDATION | Full292 tests; original4H/1H examples withdrawn; full saved BTC replays have0 orders; explicit bounded249-bar15m and corrected25-bar synthetic chains demonstrated. [Evidence](trading-brain-replay.md) records fixed-default1140 suffix search/graphs/limits. |
| [U-TRADING-BRAIN-001] | [U] Explicit urgent user implementation | Causal low-first range sweep PAPER strategy | CONFIRMED TASK REQUIREMENT | PENDING — not a DD attestation | 2026-09-12 direct instruction: exact adbafa4 base/isolated brain worktree, preserve SwingEngine; valid levels by body-close breaks, frozen ordered near-boundary traversal, sweep/reclaim then FVG/iFVG, plan/risk/PAPER, historical replay/full tests/commit then STOP. [Spec](specs/trading-brain-v0.1.md). |
| [H]-STRUCTURE-001 / [H]-RANGE-001 / [H]-MANIPULATION-001 / [H]-GAP-001 / [H]-PLAN-001 / [H]-RISK-001 / [H]-PAPER-001 | [H] Project hypotheses | Runnable provisional definitions | PROVISIONAL — NOT DD RULES | NOT VALIDATED | Latest prior target/raw candidate, low-first pair selection/ordered timing/no-reseed, strict-inside reclaim, basic wick gaps/one-time inversions, next-open plan, explicit paper sizing and conservative fills/exits. Exact definitions/config in [spec](specs/trading-brain-v0.1.md). Preserved ATR raw confirmation remains [H]-SWING-ATR-CLOSE-001. |
| [E-TRADING-BRAIN-001] | [E] Offline code/replay evidence | Real saved BTC + synthetic causal PAPER chains | VERIFIED DETERMINISTIC ENGINEERING FLOW | NO EMPIRICAL STRATEGY VALIDATION | [Evidence](trading-brain-replay.md), public fixture hashes/transitive graphs; full281 tests pass,1196 real prefixes and22 synthetic prefixes; Initial9adfe26 replay produced real1H FVG SHORT and4H iFVG LONG; both valid-trade claims are WITHDRAWN by U-RANGE-BOUNDARIES-001. Current evidence is E-RANGE-BOUNDARIES-001. Gross simulated PnL excludes costs; no new DD attestations or profit claim. |
| [D-DD-MSB-001] | [D] DD Finance | Market Structure | SOURCE CONFIRMED | PENDING | User-attested 21 DD rules captured in [market-structure-v0.1](specs/market-structure-v0.1.md). Original DD recording/transcript is not in this repository; no independent source verification or own-data/backtest validation. N-1–N-7 unresolved. |
| [U-PD-001] | [U] User clarification | Premium / Discount | CONFIRMED PROJECT RULE | PENDING | Premium/Discount is context/confirmation, not an independent entry trigger. EQ reaction/reclaim is not mandatory unless a specific approved setup requires it. Separate from DD's ordinary side blocks; see [ADR 003](DECISIONS/003-premium-discount-context.md). |
| [R-OSS-001] | [R] External research | Open-source ecosystem review | RESEARCH REFERENCE | N/A | smart-money-concepts, Freqtrade, NautilusTrader, Backtesting.py, Lightweight Charts, Optuna, etc. Actionable summary: [open-source-notes](research/open-source-notes.md). Earlier broader [review](research/open-source-kaynak-taramasi-2026-09-12.md) is retained. Libraries are references, not strategy truth; no dependencies were added or framework compatibility/performance validated. |
| [U-PRODUCT-001] | [U] Approved user product requirement | Ch.0 copilot scope and architecture | CONFIRMED PROJECT REQUIREMENT | N/A — product decision; implementation unverified | Formal Ch.0 closure instruction, 2026-09-12, attachment cb5f98e2-1801-400a-aab8-b92e83f729dc/pasted-text.txt. Requirements captured in [product-mvp-v0.1](specs/product-mvp-v0.1.md): preserve core; open-source/self-hosted; shared Web/Mini App and optional Telegram; FastAPI; actual product-runtime ATK MCP; template-first optional LLM with no price/state/strategy/risk/execution authority; READ-ONLY/SHADOW and no LIVE; P0.5 honest pre-demo intelligence; separate agents/worktrees and explicit Ch.1 approval. New ADRs 006–009 record these decisions, not completed features or trading semantics. |
| [U-RUBRIC-001] | [U] Confirmed user event requirement | Revised hackathon rubric | CONFIRMED PROJECT REQUIREMENT | N/A — judging weights | Same formal Ch.0 instruction, 2026-09-12. Utility 30%, UX 30%, ATK MCP depth 20%, Reliability/Safety 10%, Innovation 10%. Recorded in [product-mvp-v0.1](specs/product-mvp-v0.1.md), AGENTS and PROJECT_STATE. User-supplied scoring, not independent public-rule verification or guaranteed points. |
| [R-COPILOT-001] | [R] External engineering research | Agentic Market Intelligence ecosystem | RESEARCH REFERENCE | N/A | Incoming [ecosystem report](research/agentic-market-intelligence-ecosystem-2026-09-12.md), 2026-09-12, parallel Kaynak Tarama task. Preserved without editing during closure. Proposed package versions, framework/deployment choices and compatibility claims are not an installed/tested product stack, approved scope or DD semantics. |
| [U-MCP-GATE-001] | [U] Explicit user implementation authorization | Ch.1 Backend Target #1: runtime ATK MCP integration gate | CONFIRMED PROJECT REQUIREMENT | N/A — runtime requirement, not a trading rule | User instruction, 2026-09-12, attachment 5365fd21-41b2-46b0-99df-7cbaee5d1a85/pasted-text-1.txt. Start Ch.1 only in backend worktree; prove official Python MCP client → installed ATK 1.4.6 → TR market-only/read-only public reads before API work. Preserve CLI/core; exact normalization/provenance, deterministic tests, explicit real smoke; commit coherent target then stop without merge/push/tag. [Target spec](specs/runtime-atk-mcp-gate.md). |
| [E-MCP-GATE-001] | [E] Local runtime interoperability evidence | Public product-runtime MCP data gate | VERIFIED NARROW RUNTIME GATE | N/A — no strategy/performance validation | [Smoke evidence](runtime-atk-mcp-gate.md): official mcp 2.2.0 + ATK MCP 1.4.6, protocol 2025-11-25, 21 discovered tools; actual BTC-USDT ticker, ten 15m rows (nine closed retained), depth-five book and candle snapshot. 36 baseline + 43 new deterministic tests passed. This evidence supports U-MCP-GATE-001, does not alter original rule provenance, and proves no API/UX/intelligence/PnL or full MTF delivery. |
| [U-ANALYSIS-API-001] | [U] Explicit user implementation authorization | Ch.1 Backend Target #2 product service/API/persistence | CONFIRMED PROJECT REQUIREMENT | N/A — engineering scope | User attachment dcb7efe6-17be-4d50-bcca-1acf3dd92c6f/pasted-text-1.txt, 2026-09-12. Backend worktree only, parent cd686755; frozen report, real MCP MTF/core, thin FastAPI, stdlib SQLite/JSONL, deterministic explanation, neutral failures, offline tests and separate real product smoke; commit then stop with no merge/push/tag. [Contract](specs/analysis-api-v0.1.md). |
| [E-ANALYSIS-API-001] | [E] Local public product interoperability evidence | Real MTF/core/report/SQLite/API flow | VERIFIED BOUNDED PRODUCT FLOW | N/A — no strategy/performance validation | [Real product smoke](product-analysis-smoke.md): analysis580b88e9-a183-4889-8cc7-b861fef405a4, five real public MCP reads, 100 closed candles per TF, causal core NO_TRADE/STRATEGY_NOT_CONFIGURED, exact string/UTC report, core audit, ten events, DELETE journal and identical fresh SQLite/API retrieval. 79 old +71 new =150 offline tests passed. No intelligence/order/private/deployment/UX claim; original trading-rule provenance unchanged. |
| [U-AUTONOMOUS-CONTRACT-001] | [U] Explicit user direction/scope correction | Autonomous agent / analysis contract v0.2 | CONFIRMED PROJECT REQUIREMENT | N/A — no trading algorithm approval | Attachment 44378832-b6a3-4dfb-bd1f-b9cb4af8ab46/pasted-text-1.txt, 2026-09-12. Backend only from 6c1af4b; dynamic strategy-required timeframes, display separation, causal knowledge meaning, future autonomous runtime/modes/outcomes only; preserve default/history/core; Swing R&D/spec next; no loop/intelligence/exchange writes; exact commit then stop. [v0.2](specs/analysis-api-v0.2.md), [ADR011](DECISIONS/011-autonomous-runtime-contract.md). |
| [E-AUTONOMOUS-CONTRACT-001] | [E] Local contract/baseline compatibility evidence | Dynamic collection and original history | VERIFIED BOUNDED COMPATIBILITY | N/A — no strategy/autonomous/profitability validation | [Handoff](HANDOFF.md): 150 preserved +20 focused =170 offline tests; configured 1H/5m causal core/SQLite/HTTP, unchanged default real smoke 517c6e4d-265b-4a9b-9860-cf7f8aa7e4a2 v0.2, 100 closed candles per baseline TF, 5 public reads, NO_TRADE/STRATEGY_NOT_CONFIGURED/order_sent=false; real original v0.1/v0.2 GET/history matched SQLite. |

Tag vocabulary: [D] DD Finance; [U] user hypothesis/clarification; [G] ChatGPT;
[C] Claude; [R] external research; [E] empirical validation evidence.

For future records, keep topic, source artifact/locator, confirmation status,
unresolved definitions and validation evidence distinct. A user hypothesis
stays a hypothesis until explicitly clarified/confirmed; do not automatically
give every [U] record CONFIRMED PROJECT RULE status. Record a supporting [E]
artifact and its methodology/limitations before asserting empirical validation.

No confirmed Range source is registered yet; no placeholder source ID asserts
that unreceived DD material was reviewed. Historical Range intake and chart/history
extension are deferred. Target #1/#2 runtime/backend remain verified; the user's
subsequent correction makes SWING ENGINE R&D / SPEC the next intelligence task.
Its opposing-movement/causal definitions are pending, not new DD attestations.
See [NEXT_TASK](NEXT_TASK.md).

Product approval does not resolve MarketStructureEngine N-1–N-7 or approve a
Range/Deviation algorithm. P0.5 requires its own narrow, causal intelligence
specification and fixtures; relabeling STRATEGY_NOT_CONFIGURED as WAIT is not
validation. Preserve [D-DD-MSB-001] and [U-PD-001], including Premium/Discount
context, no universal EQ reaction/reclaim and separate DD ordinary side blocks.

Ch.0 froze scope/memory and prepared Git worktrees without implementation.
Ch.1 Backend Targets #1/#2 and the contract correction are verified; subsequent implementation remains gated
by its next user instruction and Ch.1 is not complete.
Chapter sequence: Ch.0 Base Setup / Product Re-Scope; Ch.1 Product MVP & UX;
Ch.2 Trading Intelligence; Ch.3 Agent Workflows; Ch.4 Validation & Demo.

## [U-WEBAPP-SHELL-001] — isolated trading control frontend

User instruction, 2026-09-12: React/Vite/TypeScript Dashboard and Strategy Settings
in Agent Trading-webapp / work/webapp, with typed mock/local data and optional
Telegram WebApp detection. Authorizes local preset/timeframe/module/risk/mode
controls and confirmed LIVE preview without execution. Explicitly excludes
Swing/strategy/market logic, exchange writes, bot, backend persistence and charts.
Demo defaults and switch availability are UI configuration, not source-confirmed
strategy predicates or empirical trading validation. Details: [shell spec](specs/webapp-shell-v0.1.md)
and [handoff](webapp-shell.md). Requested commit only; no merge/push/tag.

## OKX capability research — 2026-09-12

| ID | Tag | Record | Status / limits |
|---|---|---|---|
| [U-OKX-CAP-001] | [U] | User authorized an isolated work/okx-capabilities audit from 9d842077581f51b8264344fb331d1123665955e7; read-only capability checks, coherent commit and stop | No trades, transfers, Earn toggles, LIVE, Swing/frontend/strategy, merge/push/tag |
| [E-OKX-CAP-001] | [E] | [OKX TR report](research/okx-tr-capabilities-2026-09-12.md) and [sanitized runtime evidence](research/okx-tr-capabilities-2026-09-12.json): connected 1.5.0 and isolated 1.4.6 discovery, 13 successful read tools, Auto Earn flags and Earn demo error 50038 | Capability/connectivity evidence only; remote grants not exposed, local private AUTH_MISSING, writes untested; no strategy or yield validation |
