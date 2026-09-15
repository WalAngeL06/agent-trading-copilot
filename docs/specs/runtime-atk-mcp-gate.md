# Runtime ATK MCP market gate

Date: 2026-09-12. Status: **APPROVED TARGET; implementation evidence recorded separately**.
Source: [U-MCP-GATE-001], the user's Ch.1 Backend Target #1 instruction.
This instruction explicitly starts Ch.1 in the backend worktree and prioritizes
the runtime MCP gate before the shared API contract. Ch.1 is not complete.

## Scope and contracts

Python product code uses the official `mcp==2.2.0` v2 `Client` and stdio
transport to launch the installed `@okx_ai/okx-trade-mcp@1.4.6` through absolute
Node/JavaScript paths. Require the package identity/version and negotiated
server version. Arguments are fixed: `--site tr --modules market --read-only
--no-log`. Force `https://tr.okx.com`, disable update checks, and use an empty
temporary home under ignored `runs/`; do not inherit credentials or account
configuration. Use bounded initialization/discovery/call timeouts and SDK-owned
process cleanup. Do not install/upgrade ATK automatically.

`tools/list` is authoritative: discover every page, require the exact
`market_get_ticker`, `market_get_candles`, `market_get_orderbook` names, verify
their input schema against the permitted requests, and fail on drift. Only
these three tools can be invoked by the adapter. Account/write tools are outside
scope. Discovery may include other market reads and ATK's capability tool.

Decode ATK's text JSON with `parse_float=Decimal` to avoid the SDK's generic
structured-JSON float representation. A structured-only response is supported
only if its numeric inputs meet the same strict domain rules. Require a matching
tool, `ok=true`, public/read-only/non-demo capabilities, and the actual ATK
market envelope `data = {endpoint, requestTime, data: [...]}`. Unwrap only the
inner data array; endpoint/requestTime are transport metadata, never domain facts.
Errors expose fixed categories and, when available, numeric JSON-RPC codes;
raw provider/SDK error text, headers, environment values and payloads stay out
of provenance and smoke output. Never fall back to CLI silently.

Reuse `normalize_candles` and the existing `Candle`, `MarketSnapshot` and
`HistoryStore` contracts without altering them. Candles carry their closing UTC
time, retain Decimal OHLCV, are chronological/deduplicated, and exclude
unconfirmed or future closes. The requested decision `as_of` cannot exceed the
request observation time. Record received/open/future/duplicate/retained counts.
Ticker and book use small immutable domain observation contracts with Decimal
prices/quantities and separate exchange and response observation times. They
are never inserted into candle snapshots or represented as known earlier.

Return normalized values with immutable sanitized MCP provenance: provider,
transport, site, tool, symbol/timeframe, request/response UTC times, integer
latency milliseconds, success/error category, and candle filtering summary.
Keep a bounded in-memory provenance history; persistence/report APIs are later
work. Malformed/missing data fails closed.

## Verification and stopping boundary

Normal `unittest` runs use fake sessions/process contexts and need neither the
SDK nor Node, credentials, ATK, or network access. Cover discovery/pagination,
schema/name drift, normalization, precision, causal filtering/isolation,
malformed/error replies, unavailability/timeouts, launch restrictions and cleanup.
Preserve the 36-test baseline and existing CLI implementation.

An explicit `python -B -m agent_trading.mcp_smoke` starts a real public MCP
session, discovers tools, calls BTC-USDT ticker, ten 15m candles and depth-five
book, builds a candle-only snapshot, prints sanitized JSON, and exits cleanly.
Record versions, discovered names, protocol, output counts/times, and outcome
in `docs/runtime-atk-mcp-gate.md`. Success proves this narrow data gate, not a
strategy, product report/API, MTF workflow, Ch.1 completion or profitability.
Otherwise document a precise reproducible interoperability blocker.

No FastAPI, SQLite, frontend/Telegram/LLM, intelligence, PnL, private reads,
LIVE path, merge, push or tag. After checks/docs, make the single requested
backend commit and stop.
