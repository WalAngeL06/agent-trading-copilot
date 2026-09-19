# Agent Trading

A self-hosted market intelligence and PAPER trading copilot. The React WebApp
shows real runtime, market and account states, configures the multi-timeframe
strategy, and starts or stops the agent. Telegram is optional.

## Architecture

React/Vite WebApp → FastAPI → BotService → trading engine → OKX Agent Trade Kit / MCP

The WebApp lives in `src/`. The backend lives in `agent_trading/`. Both run from
the repository root. `/dashboard` redirects to the WebApp; there is one UI.

## Features

- Real OKX closed-candle market data through read-only ATK/MCP.
- Multi-timeframe strategy: bias, range/manipulation, FVG entry; LONG-only.
- Structural risk management, configurable break-even trigger and higher-low trailing.
- Configurable R-based partial take profits and runner management.
- Optional read-only account equity/status and Telegram integration.
- Local strategy configuration that survives backend restarts.
- Durable PAPER session: positions and strategy state survive backend restarts.
- Automatic reconnect to OKX market data with backoff (RECONNECTING status).
- Owner-only API: an access key or allowlisted Telegram users.
- PAPER execution only. No LIVE switch, exchange order submission or ANALYZE execution mode.
- Existing analysis/history API and offline backtest CLI remain available.

Strategy rules include documented provisional hypotheses; infrastructure and
replay tests do not establish profitability. PAPER uses configured simulated
equity (default 10,000), not the connected account balance. The PAPER session
(positions, trades, strategy state) is saved in `runs/product/` after every
processed candle. Start resumes it while the symbol and strategy settings are
unchanged; changing settings starts a fresh session with a new bootstrap. After a
backend restart the agent starts again by itself if the owner left it running;
Stop keeps it stopped. Prices on the Dashboard are the latest closed entry-candle
price, with an observation time.

## Quick Start

Requirements: Windows PowerShell, Python 3.11+, Node.js 22.12+ and Git.

```powershell
git clone https://github.com/WalAngeL06/agent-trading-copilot.git "Agent Trading"
cd "Agent Trading"
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Then fill `.env` for optional private account access or Telegram. Leave those
credentials empty to use public market data and the local browser.

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Open [the WebApp](http://localhost:5173). The backend runs at
[localhost:8000](http://localhost:8000/docs). The launcher opens two visible
service windows. The agent starts STOPPED; use **Start Agent** in the Dashboard.
Close the service windows to shut down. Existing occupied ports are reported,
not silently replaced. Run one backend worker for this local product.

`setup.ps1` installs the locked frontend packages, Python product dependencies
and pinned OKX MCP package. It creates `.env` only if absent.
To launch separately:

```powershell
.\.venv\Scripts\python.exe -B -m uvicorn agent_trading.api:create_app --factory --host 127.0.0.1 --port 8000
npm run dev
```

## Configure Strategy

Open **Dashboard → Strategy**. Users can configure:

- Bias, range and entry timeframes (strictly descending).
- FVG LOW / EQ / HIGH entry level and secondary FVG support.
- Risk per trade percentage and minimum reward/risk.
- Break-even trigger in R (break-even is always enabled by the current engine).
- Structural trailing and its absolute price buffer (blank uses the engine stop buffer).
- Partial take profits, for example 1R → 20%, 2R → 30%, and runner percentage.

Stop the agent before saving strategy changes. Save validates through the
trading engine and re-fetches the persisted settings. Duplicate R levels,
invalid timeframes, impossible allocations and unsupported fields are rejected.
Maximum daily loss and maximum position settings are not exposed because the
current runtime does not enforce those configurable policies.

`GET /api/v1/strategy/config` returns the active configuration.
`PUT /api/v1/strategy/config` saves atomically to `config/strategy.json`.
This ignored file contains no secrets. First-run defaults come from the engine;
partial exits are initially empty and the runner is 10%. Corrupt existing
configuration stops backend startup instead of silently replacing it.

## Environment Variables

Names only; put your own values in the ignored `.env`:

- `OKX_API_KEY`
- `OKX_SECRET_KEY`
- `OKX_PASSPHRASE`
- `TELEGRAM_BOT_TOKEN`
- `VITE_BACKEND_URL`
- `WEBAPP_URL`
- `ALLOWED_ORIGINS`
- `API_ACCESS_TOKEN`: browser access key (at least 24 characters)
- `TELEGRAM_ALLOWED_USER_IDS`: Telegram users allowed to use the bot and Mini App
- `DOMAIN`: server DNS name, used only by `compose.yaml`

Local URL defaults are provided in `.env.example`. Restart the relevant service
after changing environment configuration. Public market reads do not require
private credentials. Missing credentials show AUTH_MISSING. The account API's
generic auto-lend flag is not OKX TR Lira Auto Earn: the UI shows
**Lira Auto Earn — Status unavailable via API**.

## Safety

- Secrets remain local; `.env` and runtime files are ignored by Git.
- Grant read-only API permissions. Withdrawal permission should never be granted.
- PAPER is the safe default and the only supported execution mode.
- Every `/api/` route requires the owner access key (`Authorization: Bearer`)
  or Telegram Mini App data signed for an allowlisted user. Without either
  setting the API stays open for local use only: the backend refuses to start
  when `WEBAPP_URL` or `ALLOWED_ORIGINS` points beyond this machine.
- Start/stop and settings saves use confirmed backend state. Failed market reads
  reconnect with backoff (5 s up to 5 min) and keep the PAPER session; data the
  strategy rejects, such as a history gap, stops the agent with ERROR.

## Telegram

Telegram is not required for local browser use. For optional Telegram setup,
create a bot using BotFather, set its token and point `WEBAPP_URL` to the HTTPS
address of this same React WebApp. Set `VITE_BACKEND_URL` to a backend address
reachable from that device and include the frontend origin in `ALLOWED_ORIGINS`.
Set `TELEGRAM_ALLOWED_USER_IDS` so only you can use the bot and the Mini App; the
bot's `/start` reply shows your user ID. Telegram `/start` launches the WebApp
and `/status` reports runtime state. Existing
`/dashboard` links redirect to `WEBAPP_URL`; update old links to the frontend.

## Deploy to a VPS

`compose.yaml` runs the backend and a Caddy web server with automatic HTTPS:
`docker compose up -d --build` after setting `DOMAIN` and an access setting in
`.env`. Step-by-step guide (Turkish): [docs/deploy-vps.md](docs/deploy-vps.md).
The deployment files have not yet been exercised on a real VPS.

## Verification and technical history

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
npm test
npm run build
```

See [project state](docs/PROJECT_STATE.md), [strategy spec](docs/specs/strategy-v1.md)
and [consolidation evidence](docs/product-consolidation.md). Earlier technical
research and decisions remain in `docs/`; historical scope limits describe
those checkpoints and do not imply that planned work was implemented then.
