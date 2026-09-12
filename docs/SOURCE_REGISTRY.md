# Source registry

Updated: 2026-09-12. **Source and validation are separate concepts.** A source
ID identifies provenance; its confirmation status is not proof of performance.
Agent-authored summaries and external libraries do not become DD strategy truth.

| Source ID | Type | Topic | Status | Empirical Validation | Notes |
|---|---|---|---|---|---|
| [D-DD-MSB-001] | [D] DD Finance | Market Structure | SOURCE CONFIRMED | PENDING | User-attested 21 DD rules captured in [market-structure-v0.1](specs/market-structure-v0.1.md). Original DD recording/transcript is not in this repository; no independent source verification or own-data/backtest validation. N-1–N-7 unresolved. |
| [U-PD-001] | [U] User clarification | Premium / Discount | CONFIRMED PROJECT RULE | PENDING | Premium/Discount is context/confirmation, not an independent entry trigger. EQ reaction/reclaim is not mandatory unless a specific approved setup requires it. Separate from DD's ordinary side blocks; see [ADR 003](DECISIONS/003-premium-discount-context.md). |
| [R-OSS-001] | [R] External research | Open-source ecosystem review | RESEARCH REFERENCE | N/A | smart-money-concepts, Freqtrade, NautilusTrader, Backtesting.py, Lightweight Charts, Optuna, etc. Actionable summary: [open-source-notes](research/open-source-notes.md). Earlier broader [review](research/open-source-kaynak-taramasi-2026-09-12.md) is retained. Libraries are references, not strategy truth; no dependencies were added or framework compatibility/performance validated. |
| [U-PRODUCT-001] | [U] Approved user product requirement | Ch.0 copilot scope and architecture | CONFIRMED PROJECT REQUIREMENT | N/A — product decision; implementation unverified | Formal Ch.0 closure instruction, 2026-09-12, attachment cb5f98e2-1801-400a-aab8-b92e83f729dc/pasted-text.txt. Requirements captured in [product-mvp-v0.1](specs/product-mvp-v0.1.md): preserve core; open-source/self-hosted; shared Web/Mini App and optional Telegram; FastAPI; actual product-runtime ATK MCP; template-first optional LLM with no price/state/strategy/risk/execution authority; READ-ONLY/SHADOW and no LIVE; P0.5 honest pre-demo intelligence; separate agents/worktrees and explicit Ch.1 approval. New ADRs 006–009 record these decisions, not completed features or trading semantics. |
| [U-RUBRIC-001] | [U] Confirmed user event requirement | Revised hackathon rubric | CONFIRMED PROJECT REQUIREMENT | N/A — judging weights | Same formal Ch.0 instruction, 2026-09-12. Utility 30%, UX 30%, ATK MCP depth 20%, Reliability/Safety 10%, Innovation 10%. Recorded in [product-mvp-v0.1](specs/product-mvp-v0.1.md), AGENTS and PROJECT_STATE. User-supplied scoring, not independent public-rule verification or guaranteed points. |
| [R-COPILOT-001] | [R] External engineering research | Agentic Market Intelligence ecosystem | RESEARCH REFERENCE | N/A | Incoming [ecosystem report](research/agentic-market-intelligence-ecosystem-2026-09-12.md), 2026-09-12, parallel Kaynak Tarama task. Preserved without editing during closure. Proposed package versions, framework/deployment choices and compatibility claims are not an installed/tested product stack, approved scope or DD semantics. |
| [U-MCP-GATE-001] | [U] Explicit user implementation authorization | Ch.1 Backend Target #1: runtime ATK MCP integration gate | CONFIRMED PROJECT REQUIREMENT | N/A — runtime requirement, not a trading rule | User instruction, 2026-09-12, attachment 5365fd21-41b2-46b0-99df-7cbaee5d1a85/pasted-text-1.txt. Start Ch.1 only in backend worktree; prove official Python MCP client → installed ATK 1.4.6 → TR market-only/read-only public reads before API work. Preserve CLI/core; exact normalization/provenance, deterministic tests, explicit real smoke; commit coherent target then stop without merge/push/tag. [Target spec](specs/runtime-atk-mcp-gate.md). |
| [E-MCP-GATE-001] | [E] Local runtime interoperability evidence | Public product-runtime MCP data gate | VERIFIED NARROW RUNTIME GATE | N/A — no strategy/performance validation | [Smoke evidence](runtime-atk-mcp-gate.md): official mcp 2.2.0 + ATK MCP 1.4.6, protocol 2025-11-25, 21 discovered tools; actual BTC-USDT ticker, ten 15m rows (nine closed retained), depth-five book and candle snapshot. 36 baseline + 43 new deterministic tests passed. This evidence supports U-MCP-GATE-001, does not alter original rule provenance, and proves no API/UX/intelligence/PnL or full MTF delivery. |

Tag vocabulary: [D] DD Finance; [U] user hypothesis/clarification; [G] ChatGPT;
[C] Claude; [R] external research; [E] empirical validation evidence.

For future records, keep topic, source artifact/locator, confirmation status,
unresolved definitions and validation evidence distinct. A user hypothesis
stays a hypothesis until explicitly clarified/confirmed; do not automatically
give every [U] record CONFIRMED PROJECT RULE status. Record a supporting [E]
artifact and its methodology/limitations before asserting empirical validation.

No confirmed Range source is registered yet; no placeholder source ID asserts
that unreceived DD material was reviewed. Range remains the next strategy-source
ingestion topic. The narrow runtime MCP gate is verified under explicit Ch.1
authorization; the next product task is the shared API contract after the user's
next instruction. See [NEXT_TASK](NEXT_TASK.md).

Product approval does not resolve MarketStructureEngine N-1–N-7 or approve a
Range/Deviation algorithm. P0.5 requires its own narrow, causal intelligence
specification and fixtures; relabeling STRATEGY_NOT_CONFIGURED as WAIT is not
validation. Preserve [D-DD-MSB-001] and [U-PD-001], including Premium/Discount
context, no universal EQ reaction/reclaim and separate DD ordinary side blocks.

Ch.0 froze scope/memory and prepared Git worktrees without implementation.
Ch.1 Backend Target #1 is now verified; subsequent implementation remains gated
by its next user instruction and Ch.1 is not complete.
Chapter sequence: Ch.0 Base Setup / Product Re-Scope; Ch.1 Product MVP & UX;
Ch.2 Trading Intelligence; Ch.3 Agent Workflows; Ch.4 Validation & Demo.
