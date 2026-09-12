# Backend Target #2 — real product analysis evidence

Date: 2026-09-12. Source: [U-ANALYSIS-API-001].
Evidence: [E-ANALYSIS-API-001]. Result: **REAL PRODUCT FLOW VERIFIED**.
Ch.1 and the trading strategy remain incomplete.

## Actual path and immutable result

Explicit command from Agent Trading-backend, work/copilot-backend:

```powershell
./.venv/Scripts/python.exe -B -m agent_trading.product_smoke --node-path 'C:/Program Files/nodejs/node.exe' --server-path 'C:/Users/Serdar Arif/AppData/Roaming/npm/node_modules/@okx_ai/okx-trade-mcp/dist/index.js'
```

AnalysisService -> official Python MCP SDK2.2.0 -> installed pinned ATK MCP1.4.6
stdio child -> OKX TR public market tools -> existing exact normalization ->
300 retained closed candles in causal MTF snapshot -> preserved core ->
AnalysisReport -> core JSONL audit + SQLite final report/10 timeline events.
No desktop MCP connector, CLI fallback, credentials or trade calls.
Same credential-free launch/version/cleanup gates as the
[verified runtime gate](runtime-atk-mcp-gate.md).

| Fact | Observed result |
|---|---|
| Smoke exit | 0, COMPLETED |
| analysis_id | 580b88e9-a183-4889-8cc7-b861fef405a4 |
| symbol/site | BTC-USDT / tr |
| requested_at = started_at/candle cutoff | 2026-09-12T09:07:02.744844Z |
| completed_at | 2026-09-12T09:07:06.432714Z |
| decision_as_of | 2026-09-12T09:00:00Z |
| decision/reason | NO_TRADE / STRATEGY_NOT_CONFIGURED |
| ticker exchange_time | 2026-09-12T09:06:57.270000Z |
| ticker observed_at | 2026-09-12T09:07:04.543121Z |
| book exchange_time | 2026-09-12T09:06:59.459000Z |
| book observed_at | 2026-09-12T09:07:06.399493Z |
| book spread JSON | string "0.1" |
| order_sent | false |
| SQLite | user_version1, DELETE rollback journal, 10 ordered events |
| Core audit | BOOTSTRAP_COMPLETE + DECISION, existing schema_version2 |
| MCP market reads | 5, all succeeded |
| Fresh repository/API retrieval | identical original report verified |

## Actual public calls

tools/list succeeded at09:07:03.824127Z ->09:07:03.827012Z (2ms).

| Tool / timeframe | Request UTC | Response UTC | Latency | Closed result |
|---|---|---|---|---|
| market_get_ticker | 09:07:03.831033 | 09:07:04.543121 | 712ms | Separate live observation |
| market_get_candles /4H | 09:07:04.547562 | 09:07:05.029690 | 483ms | 100, latest08:00Z, FRESH |
| market_get_candles /1H | 09:07:05.034512 | 09:07:05.396457 | 363ms | 100, latest09:00Z, FRESH |
| market_get_candles /15m | 09:07:05.401591 | 09:07:05.931959 | 531ms | 100, latest09:00Z, FRESH |
| market_get_orderbook /depth5 | 09:07:05.937046 | 09:07:06.399493 | 462ms | Separate descriptive book |

Each timeframe received101 rows, excluded one open row, retained100 closed,
zero future/duplicate rows. All dates/times are 2026-09-12 UTC.
Ticker/book times exceed candle decision_as_of and are explicitly excluded
from decision inputs. Independent initial-cutoff freshness passed per TF;
a normally older4H close is not judged by ticker age.
Only three exact public tool names were called; discovery itself is separate.

## Verification and reproduction

```powershell
./.venv/Scripts/python.exe -B -m pip install -e '.[product,test-product]'
./.venv/Scripts/python.exe -B -m unittest discover -s tests -v
./.venv/Scripts/python.exe -B -m agent_trading.product_smoke
./.venv/Scripts/python.exe -B -m pip check
```

Operator paths above are host-specific; automatic installed Node/ATK discovery
works in a configured user environment. --db-path and --audit-dir configure
operator storage. Defaults are ignored runs/product/analyses.sqlite3 and
runs/analyses/{analysis_id}.jsonl. The repository and API read-only retrieval
were verified from fresh connections; strict OpenAPI response models accepted
the real stored report, every financial value remained a string, no JSON float
was present, and all timeframes had AVAILABLE/FRESH data.
API restart preserved this completed report; readiness503 before a new
validation request was confirmed, per the request-driven policy.
No matching smoke process or temporary public home remained. pip check passed.

**79 old +71 new =150 offline tests passed**, zero failures/errors.
12 repository,37 service,18 API,4 product smoke additions. Tests also
demonstrated stale/missing/malformed/MCP/storage/core failures, immutable
history/recovery, exact subsecond sorting, racing reservations, causality,
no order and health/readiness. Normal suite does not use live network.

## Limits

This is a public-market infrastructure/product interoperability test, not
empirical validation of strategy semantics, market forecasts or profitability.
Market Structure/Range/Deviation/Premium-Discount are NOT_IMPLEMENTED.
Acceptance/risk are NOT_EVALUATED. No live/order/private tool path exists.
Original core, CLI and all original79 tests stayed untouched.
Only the tested Windows combination is established; Linux/container,
transitive lock, shared UX/Telegram/deployment/LLM/agent workflows and full
chart-history extension remain outside this target.
