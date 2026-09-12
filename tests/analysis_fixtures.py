"""Real-shaped public ATK fixtures. Only the external SDK transport is fake."""

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from types import SimpleNamespace

from agent_trading.models import utc_time
from agent_trading.okx_mcp import OkxMcpMarketAdapter, REQUIRED_TOOLS


NOW = utc_time("2026-01-01T10:31:00Z")
PRICE = "101.123456789012345678901234567890"
ASK = "102.123456789012345678901234567893"
QUANTITY = "0.12345678901234567890123456789012345"


class Clock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now


def milliseconds(stamp):
    return str((stamp - utc_time("1970-01-01T00:00:00Z")) // timedelta(milliseconds=1))


def candle(open_time, confirm="1", close=PRICE):
    return [milliseconds(utc_time(open_time)), "100", "103", "99", close, QUANTITY, "0", "0", confirm]


def tool(name):
    fields = {"instId": {"type": "string"}}
    if name == "market_get_candles":
        fields.update(bar={"type": "string", "enum": ["4H", "1H", "15m"]},
                      limit={"type": "number"}, after={"type": "string"})
    if name == "market_get_orderbook":
        fields["sz"] = {"type": "number"}
    return SimpleNamespace(name=name, input_schema={"type": "object", "properties": fields,
                                                   "required": ["instId"]})


def reply(name, rows, stamp):
    endpoint = {"market_get_ticker": "/api/v5/market/ticker",
                "market_get_candles": "/api/v5/market/candles",
                "market_get_orderbook": "/api/v5/market/books"}[name]
    payload = {"tool": name, "ok": True,
               "data": {"endpoint": endpoint, "requestTime": stamp.isoformat(), "data": rows},
               "capabilities": {"readOnly": True, "hasAuth": False, "demo": False},
               "timestamp": stamp.isoformat()}
    return SimpleNamespace(is_error=False, content=[SimpleNamespace(type="text", text=json.dumps(payload))],
                           structured_content=deepcopy(payload))


class Session:
    def __init__(self, clock):
        self.clock = clock
        self.tools = [tool(n) for n in REQUIRED_TOOLS]
        self.rows = {
            "4H": [candle(t) for t in ("2026-01-01T04:00:00Z", "2026-01-01T00:00:00Z",
                                      "2025-12-31T20:00:00Z")] +
                   [candle("2026-01-01T08:00:00Z", "0")],
            "1H": [candle(t) for t in ("2026-01-01T09:00:00Z", "2026-01-01T08:00:00Z",
                                      "2026-01-01T07:00:00Z")] +
                   [candle("2026-01-01T10:00:00Z", "0")],
            "15m": [candle(t) for t in ("2026-01-01T10:15:00Z", "2026-01-01T10:00:00Z",
                                       "2026-01-01T09:45:00Z")] +
                    [candle("2026-01-01T10:30:00Z", "0")],
        }
        self.calls = []
        self.errors = {}
        self.delay = 0
        self.gate = None
        self.entered = asyncio.Event()
        self.old_observation = False
        self.bad_book = False

    async def list_tools(self, *, cursor=None):
        self.clock.now += timedelta(seconds=1)
        return SimpleNamespace(tools=self.tools, next_cursor=None)

    async def call_tool(self, name, arguments):
        self.calls.append((name, deepcopy(arguments)))
        if self.gate and name == "market_get_ticker":
            self.entered.set()
            await self.gate.wait()
        await asyncio.sleep(self.delay)
        error = self.errors.get((name, arguments.get("bar")), self.errors.get(name))
        if error:
            raise error
        self.clock.now += timedelta(seconds=1)
        exchange = self.clock.now - timedelta(seconds=120 if self.old_observation else 1)
        if name == "market_get_ticker":
            rows = [{"instId": arguments["instId"], "ts": milliseconds(exchange), "last": PRICE,
                     "bidPx": PRICE, "askPx": ASK}]
        elif name == "market_get_candles":
            rows = self.rows[arguments["bar"]]
        elif name == "market_get_orderbook":
            rows = [{"ts": milliseconds(exchange), "bids": [[PRICE, QUANTITY, "0", "1"]],
                     "asks": [[ASK, QUANTITY, "0", "1"]]}]
            if self.bad_book:
                rows[0]["bids"][0][0] = "999"
        else:
            raise AssertionError("A non-public or undocumented tool was called")
        return reply(name, rows, self.clock.now)


class Runtime:
    def __init__(self, clock):
        self.clock = clock
        self.session = Session(clock)
        self.closed = False
        self.connections = 0
        self.entry_error = None
        self.exit_error = None

    @asynccontextmanager
    async def __call__(self, **kwargs):
        self.connections += 1
        if self.entry_error:
            raise self.entry_error
        adapter = OkxMcpMarketAdapter(self.session, timeout=kwargs["timeout"], clock=self.clock)
        adapter.runtime_info = {"mcp_sdk_version": "2.2.0", "atk_version": "1.4.6",
                                "protocol_version": "2025-11-25"}
        try:
            await adapter.discover()
            yield adapter
            if self.exit_error:
                raise self.exit_error
        finally:
            self.closed = True
