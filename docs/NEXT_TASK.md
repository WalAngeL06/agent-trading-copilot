# Next task — Ch.1 pending explicit approval

Updated: 2026-09-12.
Current chapter: **Ch.0 — Base Setup / Product Re-Scope**.
**Do not begin this task automatically.** The user must review and explicitly
approve the formal Ch.0 closure before Ch.1 starts.

## Required reading and verified starting point

Read AGENTS.md, PROJECT_STATE, HANDOFF, [product-mvp-v0.1](specs/product-mvp-v0.1.md),
[SOURCE_REGISTRY](SOURCE_REGISTRY.md) and ADRs 006–009. Read the Market Structure
spec before any intelligence work; N-1–N-7 remain unresolved.

Integration stays `strategy-v0.1`. The checkpoint is the Ch.0 documentation
commit with message `chore: freeze hackathon product scope and ch0 plan`;
take its exact hash from Git/final closure report. Verify both prepared
worktrees start at that exact commit and are clean:
- Backend `work/copilot-backend`: `C:/Users/Serdar Arif/Desktop/Agent Trading-backend`.
- UX `work/copilot-ux`: `C:/Users/Serdar Arif/Desktop/Agent Trading-ux`.

The preserved baseline has 36 existing tests. No product implementation has
started. No additional tag, remote or push is authorized.

## First Ch.1 deliverable — shared product API contract

Codex defines, Claude reviews, before parallel feature implementation.
Specify routes/request lifecycle, schema version, exact Decimal string fields,
symbol/timeframe limits, analysis identity, candle `as_of`, live observation
times, freshness/error/loading states, facts/evidence references, module
availability, deterministic result/reasons, template explanation, history and
sanitized MCP provenance. Keep future intelligence state labels separate from
operational status and the current NO_TRADE/STRATEGY_NOT_CONFIGURED placeholder.

Freeze request/response examples and expected contract behavior before the
frontend and backend independently implement against them. This closure does
not create an API schema, OpenAPI file or application code.

## Highest early technical risk — prove actual runtime ATK MCP

Application runtime → MCP client → official OKX Agent Trade Kit → real
BTC-USDT ticker, candles 4H/1H/15m and orderbook → exact normalization →
causal MarketSnapshot/core input.

Use market-only/read-only TR public reads and bounded timeouts. Desktop
Codex/Claude MCP, OAuth completion and CLI probes are not product-runtime
proof. Preserve existing CLI foundation; label any fallback honestly.
Record useful call provenance without secrets, floats in prices or future/open
candles. Keep separately observed ticker/book data out of past candle decisions.

Acceptance: real calls run inside the backend service/runtime and their actual
results feed the report and normalized core inputs. Add meaningful MCP/contract
checks alongside the preserved baseline. Do not send exchange orders.

## Parallel responsibilities after contract review

Codex: backend, runtime MCP adapter, FastAPI, core integration, persistence,
backend tests, root configuration/Compose/integration and shared-memory files.
Claude: React/Vite/TypeScript shared Web/Mini App, Analysis/History UX,
Telegram bot/interface and frontend tests.
Do not overlap file ownership. Trading-intelligence core files have one owner
at a time. Integration receives reviewed commits and relevant verification.

## P0 continuation

Build BTC report/API, live market facts, one Lightweight Charts chart and
timeframe selector, evidence/results, template explanation, SQLite History,
shared browser/Mini App, thin Telegram launcher and easy Docker Compose setup.
Include loading/errors/staleness/missing-module states. Telegram and optional
LLM must not be required for useful normal web/API output. No usable LIVE switch.

## P0.5 — required before the final demo

Deliver at least one narrow, approved, deterministic market-intelligence slice
with source-labelled causal fixtures and meaningful WAIT, NO_VALID_SETUP or
supported candidate behavior. Do not satisfy this by renaming the unconfigured
placeholder or presenting only data quality as a completed strategy.

First intended intelligence: Market Structure → Range → Deviation → LTF
confirmation/context. Product approval does not resolve missing algorithms.
Resolve/approve the required definitions before coding; no full
MarketStructureEngine while N-1–N-7 are open. If the slice is not approved or
complete, record the unmet gate and seek the needed specific source/decision.

## Preserved next strategy-source task — Range

No confirmed DD Range source is registered. When source ingestion is authorized,
obtain DD material or explicitly confirmed rules, preserve provenance and create
`docs/research/range-source-notes.md` and `docs/specs/range-v0.1.md`.
Specify boundaries, lifecycle, availability, edge cases and future tests;
mark unresolved behavior **ALGORITHMIC DEFINITION PENDING**.
Do not invent touch counts, windows, ATR, retracement, volume or tolerances.

Existing longer-term source priorities and DD history are in PROJECT_STATE.
P1/P2 and excluded features remain governed by the product spec, not these
historical research topics. Premium/Discount is context, not an entry trigger;
EQ reaction/reclaim is not globally mandatory.

## Current stopping boundary

This formal closure prepares documentation, a checkpoint commit and untouched
worktrees only. Stop and wait. Ch.1 begins only after user review and explicit
approval; no package install, features, Python behavior changes, LIVE, tags,
remote or push during this closure.
