# Fresh ATK/MCP product-runtime diagnosis

2026-09-16 01:13-01:16 Europe/Istanbul (2026-09-15 22:13-22:16 UTC).
Canonical root: C:/Users/Serdar Arif/Desktop/Agent Trading. Base e826277.
No additional project folder/worktree. No runtime source changes, no commit/push.

## Results

| Layer | Fresh result |
|---|---|
| RAW REST | PASS: curl exit 0, OKX code 0, BTC-USDT |
| PYTHON HTTPS | PASS: root venv httpx, HTTP 200, OKX code 0 |
| MCP START | PASS: real stdio child launched by open_atk_mcp |
| MCP HANDSHAKE | PASS: protocol 2025-11-25 |
| ATK INIT | PASS: installed/runtime ATK 1.4.6, Python MCP SDK 2.2.0 |
| ATK TOOL LIST | PASS: 21 tools, required names/schema accepted |
| ATK TICKER | PASS: real market_get_ticker, is_error=false, ok=true |
| ATK CANDLES | PASS: real market_get_candles, BTC-USDT/4H/101 rows requested |
| ADAPTER NORMALIZATION | PASS: ticker observation and closed Decimal candle tuples |
| BOTSERVICE MARKET LOOP | PASS: configured 4H/1H/15m, normalized data, CONNECTED |
| DASHBOARD MARKET STATE | PASS: actual React UI and API show CONNECTED |
| PRIVATE AUTH | AUTH_MISSING, separate from public market success |

## Presence only: canonical .env

- OKX_API_KEY: MISSING
- OKX_SECRET_KEY: MISSING
- OKX_PASSPHRASE: MISSING
- TELEGRAM_BOT_TOKEN: MISSING

Parsed only the canonical file; no secret values printed. No private account
success is claimed. The BotService private read returned AUTH_MISSING because
its required credentials are absent. Public MCP runs credential-free by design.

## Product path evidence

The probe imported the actual open_atk_mcp and OkxMcpMarketAdapter, used the
installed pinned ATK subprocess, called real tools, then invoked the actual
normalization paths. A fresh BotService using the persisted configuration
received all three configured timeframes and exposed CONNECTED. Its captured
exception wrapper did not see an exception in this run.

The already running canonical backend (port 8000) and WebApp (port 5173) were
then tested through the actual Start Agent button. Browser-visible market state
became CONNECTED and the real strategy reported WAITING_FOR_BIAS, PAPER mode.
The Dashboard showed BTC-USDT last closed entry-candle price 75448.9 and a real
market observation timestamp. No fixture or fallback provider was used.
Repeated REST observations of the same running BotService verify that the
market update advances during polling. The independent polling evidence, not
an initial browser wait, is the basis for the polling PASS.

Local ignored evidence:
- runs/fresh_runtime_diagnosis.jsonl: per-layer results and normalization times.
- runs/fresh_polling_evidence.jsonl: consecutive successful observation times.
- runs/fresh_runtime_diagnosis.py: public-only layer probe and private status.
- output/playwright/fresh-mcp-connected.png: actual connected Dashboard.

## Root-cause conclusion

No current product-runtime failure was reproduced. All requested public layers
pass without changing runtime code, Node/SDK/ATK versions, endpoints or launch
configuration. The previously captured MCP_TOOL_ERROR/ATK NetworkError is a
historical observation, not a proven root cause. Its underlying cause cannot
be established from the available old evidence. The blanket "network blocked"
conclusion is withdrawn; no WARP/DNS/TLS/HTTP cause is asserted.

Before this test, the Dashboard was STOPPED/WAITING because its agent was
stopped. Starting it established CONNECTED. Missing private credentials explain
AUTH_MISSING only, and do not explain public market connectivity.

After verification, Stop Agent restored the initial STOPPED state. Services
remain available; no live exchange orders or Telegram messages were sent.
