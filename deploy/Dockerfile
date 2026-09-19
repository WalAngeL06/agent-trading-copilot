# syntax=docker/dockerfile:1
# Build context is the repository root; see compose.yaml.
# Draft: not yet exercised on a real VPS (see docs/deploy-vps.md).

# ---- WebApp: static React build served by Caddy on the API's origin
FROM node:22-bookworm-slim AS webapp-build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
ARG PUBLIC_URL
RUN test -n "$PUBLIC_URL" || (echo "PUBLIC_URL build argument is required" >&2 && exit 1)
RUN VITE_BACKEND_URL="$PUBLIC_URL" npm run build

FROM caddy:2 AS web
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=webapp-build /src/dist /srv

# ---- Pinned OKX Agent Trade Kit; the backend starts it as a Node child process
FROM node:22-bookworm-slim AS atk
RUN npm install --global @okx_ai/okx-trade-mcp@1.4.6

# ---- Backend: FastAPI + BotService
FROM python:3.14-slim AS app
RUN apt-get update \
 && apt-get install -y --no-install-recommends libstdc++6 ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=atk /usr/local/bin/node /usr/local/bin/node
COPY --from=atk /usr/local/lib/node_modules/@okx_ai /usr/local/lib/node_modules/@okx_ai
RUN ln -s /usr/local/lib/node_modules/@okx_ai/okx-trade-mcp/dist/index.js /usr/local/bin/okx-trade-mcp
WORKDIR /app
COPY pyproject.toml ./
COPY agent_trading ./agent_trading
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir ".[product]"
RUN useradd --create-home --uid 10001 agent \
 && mkdir -p /app/config /app/runs \
 && chown -R agent:agent /app/config /app/runs
USER agent
EXPOSE 8000
CMD ["/opt/venv/bin/python", "-m", "uvicorn", "agent_trading.api:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
