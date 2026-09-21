# Ch.1 Backend Target #1 — runtime MCP evidence

Date: 2026-09-12. Owner: Codex. Source: [U-MCP-GATE-001].
Result: **VERIFIED NARROW PRODUCT-RUNTIME MCP GATE** [E-MCP-GATE-001].
**Ch.1 is not complete.** No strategy or profitability validation is claimed.

> **Amendment 2026-09-21 [U-MULTI-PAIR-001].** The adapter can now also call
> `market_get_instruments` and `market_get_tickers` (public, `instType=SPOT`
> only, optional at discovery), so five public read tools are callable. The
> "exactly three public read tool names" statement below records the 2026-09-12
> state. Contract: [the gate spec](specs/runtime-atk-mcp-gate.md).

## Verified context and path

Only `C:/Users/Serdar Arif/Desktop/Agent Trading-backend`, branch
`work/copilot-backend`, changed. It started clean at the exact Ch.0 checkpoint
`24e1f465a886e2941a8ce2fce8fb51d53b643405`, with 36 baseline tests passing.
Integration and UX remain at that checkpoint; neither worktree was edited.

Demonstrated path:

`agent_trading.mcp_smoke → open_atk_mcp → official Python MCP Client/stdio →
installed ATK MCP child → real public OKX TR → normalized domain facts/Candle →
existing HistoryStore/MarketSnapshot`

This does not use Codex/Claude's MCP connector, the CLI adapter, or a fabricated
tool trace. All three required calls ran through the product's SDK session.

| Component | Actual version / configuration |
|---|---|
| Python | Host CPython 3.14.6; project requirement remains >=3.11 |
| Official Python SDK | `mcp==2.2.0`, `mcp-types==2.2.0`, in ignored backend `.venv` |
| ATK MCP package | Installed `@okx_ai/okx-trade-mcp@1.4.6`; package identity/version and negotiated server version checked |
| MCP protocol | `2025-11-25`, negotiated by v2's automatic legacy handshake support |
| Site / endpoint | `tr` / forced `https://tr.okx.com` |
| Launch arguments | `--site tr --modules market --read-only --no-log` |
| Credentials | None; SDK inherits OS essentials only, all home/app-data locations overridden to a new empty public home |
| Bounds | 30s for startup, complete discovery, and each individual call; finite pagination/provenance history |

Official references: [v2 client lifecycle/negotiation](https://py.sdk.modelcontextprotocol.io/client/),
[pinned SDK manifest](https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/v2.2.0/pyproject.toml),
[ATK source](https://github.com/okx/agent-trade-kit).
Actual versions/shapes above were checked in the installed packages and real
session, rather than inferred from moving documentation.

## Discovery and real reads

`tools/list` returned **21 tools**. Only the required three were invoked:

| Tool | Request | Normalized outcome | Request UTC | Response UTC | Latency |
|---|---|---|---|---|---|
| `market_get_ticker` | BTC-USDT | last `77323.3`, bid `77326.3`, ask `77326.4`; Decimal domain fields | 08:22:20.224301 | 08:22:21.165923 | 941ms |
| `market_get_candles` | BTC-USDT, 15m, limit 10 | 10 received; 1 open excluded; 0 future; 0 duplicates; 9 closed retained | 08:22:21.166116 | 08:22:21.671535 | 505ms |
| `market_get_orderbook` | BTC-USDT, depth 5 | 5 bids / 5 asks; Decimal prices/quantities | 08:22:21.671745 | 08:22:22.142569 | 470ms |

All times in this table are on 2026-09-12 UTC. Smoke exit: **0**.
Snapshot `as_of`: `2026-09-12T08:22:20.224211Z`; latest closed 15m candle:
`2026-09-12T08:15:00Z`, close `77303.5`, volume `16.5122811`.
Ticker/book response observation times are later and remain outside the
snapshot. Exchange timestamps are retained separately. No candle close exceeds
the snapshot boundary. Each normalized result includes sanitized MCP provenance.

Complete discovered tool list:

```text
market_filter
market_filter_oi_change
market_get_candles
market_get_funding_rate
market_get_index_candles
market_get_index_ticker
market_get_indicator
market_get_instruments
market_get_instruments_by_category
market_get_mark_price
market_get_oi_history
market_get_open_interest
market_get_orderbook
market_get_pair_spread
market_get_price_limit
market_get_stock_tokens
market_get_ticker
market_get_tickers
market_get_trades
market_list_indicators
system_get_capabilities
```

Discovery does not prove TR availability of other instruments/derivatives or
validate the uncalled tools. No required-tool name drift occurred. Their input
schemas verified `instId`, candles `bar`/`limit`, and book `sz`.

## Compatibility finding and resolution

The first real ticker call initialized/discovered/called successfully but
failed normalization with `MALFORMED_RESPONSE`. Investigation found the actual
ATK market handler returns a nested normalized response, not a direct array:

```text
{tool, ok, data: {endpoint, requestTime, data: [...]}, capabilities, timestamp}
```

This matches installed ATK `normalizeResponse` and `successResult` code.
The deterministic fixture and a regression test now use this actual shape;
the adapter unwraps only the inner rows. Real smokes then passed all three
reads, including a repeat after the final failure-provenance changes. This
was an adapter normalization assumption, **not an unresolved SDK/ATK blocker**.

Text JSON is decoded with `parse_float=Decimal`. The SDK's generic parsed
structured JSON may contain floats, so text is authoritative for exact numeric
tokens. Structured-only replies must pass strict string/int/Decimal domain
validation; float prices/quantities fail. Provider metadata never becomes
strategy input. Time conversion and closed-candle normalization reuse the
existing CLI/domain rules without changing that code.

## Reproduction and automated checks

The documented setup was installed successfully through the optional extra:

```powershell
py -B -m venv .venv
.\.venv\Scripts\python.exe -B -m pip install -e '.[runtime-mcp]'
.\.venv\Scripts\python.exe -B -m agent_trading.mcp_smoke
py -B -m unittest discover -s tests -v
```

Prerequisite: installed Node and `@okx_ai/okx-trade-mcp@1.4.6`; the application
does not auto-install or upgrade ATK. `--node-path` / `--server-path` configure
operator runtime paths when auto-discovery is unavailable. These are shell-free
SDK process arguments, not product request fields. No credentials are needed.

Automated result: **36 old + 43 new = 79 tests passed**, zero failures/errors.
The normal suite passed using host Python without MCP installed. New tests use
fake sessions/SDK/process contexts; no network/live connection is required.
Coverage includes discovery/pagination, exact names/schema drift, ticker/book
normalization, Decimal JSON/float rejection, UTC/causality/isolation, open/future/
duplicate filtering, malformed replies, timeout/unavailability, truthful
bounded provenance, package/server pinning, public-only launch, cleanup and
sanitized smoke output. Dependency check: no broken requirements.

The repeat smoke's full sanitized JSON is host-local and ignored:
`runs/runtime-atk-mcp-20260912.json`. The permanent evidence is this summary;
the host-local file and `.venv` are not committed. After smoke, the temporary
public home was removed and no matching MCP child process remained.

## Remaining work and limits

No interoperability blocker remains for this tested Windows combination.
Linux/container smoke and a complete transitive dependency lock remain future
validation. The optional SDK is pinned; ATK is checked at 1.4.6, not bundled.
Full 4H/1H/15m bootstrap/polling/report integration, freshness/recovery and
persistence are future work. The existing synchronous CLI SHADOW flow remains
the default; the MCP adapter is independently usable through its async context.
Provenance is bounded in memory, not a new persisted product event store.

The contract review was performed inline within the single authorized backend
worktree; an independent peer review has not been performed. Shared API contract
review by Claude is still a separate next deliverable.

No trading write/client/toggle was added. Exactly three public read tool names
are callable by this adapter. Core/CLI/original tests are unchanged. No FastAPI,
SQLite, Telegram/frontend/LLM, MarketStructure/Range/Deviation, PnL or LIVE
feature was introduced. Stop after the requested backend commit; no merge,
push or tag, and no Ch.1 completion claim.
