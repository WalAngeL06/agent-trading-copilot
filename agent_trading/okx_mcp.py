"""Read-only MCP data adapter. SDK/provider JSON never reaches strategy logic."""

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
import re
from time import monotonic_ns
from typing import Generic, TypeVar

from .market import bar_duration
from .market_observations import (
    normalize_orderbook, normalize_spot_instruments, normalize_spot_tickers, normalize_ticker,
    observation_time, okx_milliseconds,
)
from .okx import _symbol, normalize_candles


REQUIRED_TOOLS = ("market_get_ticker", "market_get_candles", "market_get_orderbook")
# [U-MULTI-PAIR-001] Public spot listings for the offline universe selection.
# Callable once discovered but never required, so the live contract is unchanged.
LISTING_TOOLS = ("market_get_instruments", "market_get_tickers")
_REQUEST_FIELDS = {
    REQUIRED_TOOLS[0]: {"instId": "string"},
    REQUIRED_TOOLS[1]: {"instId": "string", "bar": "string", "limit": "number"},
    REQUIRED_TOOLS[2]: {"instId": "string", "sz": "number"},
    LISTING_TOOLS[0]: {"instType": "string"},
    LISTING_TOOLS[1]: {"instType": "string"},
}
T = TypeVar("T")


@dataclass(frozen=True)
class CandleFiltering:
    received_rows: int
    open_rows: int
    future_rows: int
    duplicate_rows: int
    retained_rows: int


@dataclass(frozen=True)
class McpProvenance:
    tool: str
    symbol: str | None
    timeframe: str | None
    request_observed_at: datetime
    response_observed_at: datetime
    latency_ms: int
    success: bool
    error_code: str | None = None
    filtering: CandleFiltering | None = None
    rpc_error_code: int | None = None
    transport: str = "MCP"
    provider: str = "OKX Agent Trade Kit"
    site: str = "tr"


@dataclass(frozen=True)
class McpMarketRead(Generic[T]):
    value: T
    provenance: McpProvenance


class McpMarketError(RuntimeError):
    """Fixed public categories; never include raw SDK/provider error messages."""

    def __init__(self, code: str, *, provenance=None, missing_tools=(), rpc_error_code=None):
        super().__init__(f"OKX public MCP failed: {code}")
        self.code = code
        self.provenance = provenance
        self.missing_tools = tuple(missing_tools)
        self.rpc_error_code = rpc_error_code


def validate_timeout(timeout):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("MCP timeout must be a positive finite number")


def sanitized_failure(exc: Exception) -> McpMarketError:
    if isinstance(exc, McpMarketError):
        return exc
    if isinstance(exc, TimeoutError):
        return McpMarketError("MCP_TIMEOUT")
    if isinstance(exc, OSError):
        return McpMarketError("MCP_UNAVAILABLE")
    # Python SDK request failures can be grouped by its transport task groups.
    if isinstance(exc, ExceptionGroup):
        failures = [sanitized_failure(item) for item in exc.exceptions]
        return next((item for item in failures if item.code != "MCP_PROTOCOL_ERROR"), failures[0])
    code = getattr(getattr(exc, "error", None), "code", None)
    if type(code) is not int:
        code = None
    category = "MCP_SCHEMA_ERROR" if type(exc).__name__ == "ValidationError" else "MCP_PROTOCOL_ERROR"
    return McpMarketError(category, rpc_error_code=code)


def _reject_constant(value):
    raise ValueError("nonfinite JSON number")


def _payload(response, tool_name: str) -> list:
    if response.is_error is not False:
        raise McpMarketError("MCP_TOOL_ERROR")
    # ATK emits identical text and structured envelopes. Text retains numeric
    # token precision even if the SDK parsed structured_content through float.
    if response.content:
        if len(response.content) != 1 or response.content[0].type != "text":
            raise ValueError("unexpected MCP content")
        payload = json.loads(response.content[0].text, parse_float=Decimal,
                             parse_constant=_reject_constant)
    else:
        payload = response.structured_content
    if not isinstance(payload, dict) or payload.get("tool") != tool_name:
        raise ValueError("unexpected ATK envelope")
    if payload.get("ok") is not True:
        raise McpMarketError("MCP_TOOL_ERROR")
    caps = payload.get("capabilities")
    if (not isinstance(caps, dict) or caps.get("readOnly") is not True
            or caps.get("hasAuth") is not False or caps.get("demo") is not False):
        raise McpMarketError("PUBLIC_SCOPE_MISMATCH")
    market_response = payload.get("data")
    if not isinstance(market_response, dict) or not isinstance(market_response.get("data"), list):
        raise ValueError("ATK market envelope must contain a data array")
    rows = market_response["data"]
    return rows


def _schema(tool, fields, key="instId"):
    schema = tool.input_schema
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise McpMarketError("TOOL_SCHEMA_DRIFT")
    properties, required = schema.get("properties"), schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise McpMarketError("TOOL_SCHEMA_DRIFT")
    if key not in required or any(name not in fields for name in required):
        raise McpMarketError("TOOL_SCHEMA_DRIFT")
    for name, expected in fields.items():
        field = properties.get(name)
        accepted = ("number", "integer") if expected == "number" else (expected,)
        if not isinstance(field, dict) or field.get("type") not in accepted:
            raise McpMarketError("TOOL_SCHEMA_DRIFT")


class OkxMcpMarketAdapter:
    def __init__(self, session, timeout=30, clock=None):
        validate_timeout(timeout)
        self._session = session
        self.timeout = timeout
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._tools = {}
        self.discovered_tools = ()
        self._provenance = deque(maxlen=100)
        self.runtime_info = None

    @property
    def provenance(self) -> tuple[McpProvenance, ...]:
        return tuple(self._provenance)

    def _event(self, tool, symbol, timeframe, start, started_ns, *, error=None, filtering=None,
               response_observed_at=None):
        end = observation_time(response_observed_at if response_observed_at is not None else self.clock())
        event = McpProvenance(tool, symbol, timeframe, start, end,
                              max(0, (monotonic_ns()-started_ns)//1_000_000),
                              error is None, error.code if error else None, filtering,
                              error.rpc_error_code if error else None)
        self._provenance.append(event)
        return event

    async def discover(self) -> tuple[str, ...]:
        self._tools = {}
        self.discovered_tools = ()
        start, started_ns = observation_time(self.clock()), monotonic_ns()
        try:
            tools, cursor, seen = {}, None, set()
            # Bound both the whole discovery and pagination, not each page only.
            async with asyncio.timeout(self.timeout):
                for _ in range(100):
                    page = await self._session.list_tools(cursor=cursor)
                    if not isinstance(page.tools, list):
                        raise McpMarketError("MALFORMED_DISCOVERY")
                    for tool in page.tools:
                        name = tool.name
                        if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,95}", name)
                                or name in tools):
                            raise McpMarketError("MALFORMED_DISCOVERY")
                        if not name.startswith("market_") and name != "system_get_capabilities":
                            raise McpMarketError("PUBLIC_SCOPE_MISMATCH")
                        tools[name] = tool
                    cursor = page.next_cursor
                    if cursor is None:
                        break
                    if not isinstance(cursor, str) or not cursor or cursor in seen:
                        raise McpMarketError("MALFORMED_DISCOVERY")
                    seen.add(cursor)
                else:
                    raise McpMarketError("MALFORMED_DISCOVERY")
            missing = tuple(name for name in REQUIRED_TOOLS if name not in tools)
            if missing:
                raise McpMarketError("REQUIRED_TOOLS_MISSING", missing_tools=missing)
            for name in REQUIRED_TOOLS:
                _schema(tools[name], _REQUEST_FIELDS[name])
            self._tools = tools
            self.discovered_tools = tuple(sorted(tools))
        except Exception as exc:
            error = sanitized_failure(exc)
            error.provenance = self._event("tools/list", None, None, start, started_ns, error=error)
            raise error from None
        self._event("tools/list", None, None, start, started_ns)
        return self.discovered_tools

    async def _read(self, name, symbol, arguments, normalize, *, timeframe=None, as_of=None):
        if name not in REQUIRED_TOOLS + LISTING_TOOLS or name not in self._tools:
            raise McpMarketError("TOOLS_NOT_DISCOVERED")
        start, started_ns = observation_time(self.clock()), monotonic_ns()
        observed_at = None
        try:
            if as_of is not None and as_of > start:
                raise McpMarketError("INVALID_AS_OF")
            fields = dict(_REQUEST_FIELDS[name])
            if "after" in arguments:
                fields["after"] = "string"
            _schema(self._tools[name], fields,
                    "instType" if name in LISTING_TOOLS else "instId")
            for field, value in arguments.items():
                enum = self._tools[name].input_schema["properties"][field].get("enum")
                if enum is not None and value not in enum:
                    raise McpMarketError("TOOL_SCHEMA_DRIFT")
            async with asyncio.timeout(self.timeout):
                response = await self._session.call_tool(name, arguments)
            observed_at = observation_time(self.clock())
            if observed_at < start:
                raise McpMarketError("CLOCK_MOVED_BACKWARD")
            try:
                value, filtering = normalize(_payload(response, name), observed_at)
            except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
                raise McpMarketError("MALFORMED_RESPONSE") from None
        except Exception as exc:
            error = sanitized_failure(exc)
            error.provenance = self._event(name, symbol, timeframe, start, started_ns, error=error,
                                           response_observed_at=observed_at)
            raise error from None
        # Reuse arrival time; normalized facts must never precede this event.
        event = McpProvenance(name, symbol, timeframe, start, observed_at,
                              max(0, (monotonic_ns()-started_ns)//1_000_000), True, filtering=filtering)
        self._provenance.append(event)
        return McpMarketRead(value, event)

    async def ticker(self, symbol: str) -> McpMarketRead:
        _symbol(symbol)
        return await self._read(REQUIRED_TOOLS[0], symbol, {"instId": symbol},
                                lambda rows, observed: (normalize_ticker(rows, symbol, observed), None))

    async def candles(self, symbol: str, timeframe: str, limit: int, *, as_of: datetime,
                      after: int | None = None) -> McpMarketRead:
        _symbol(symbol)
        duration = bar_duration(timeframe)
        boundary = observation_time(as_of)
        if type(limit) is not int or not 1 <= limit <= 300:
            raise ValueError("candle request limit must be between 1 and 300")
        arguments = {"instId": symbol, "bar": timeframe, "limit": limit}
        if after is not None:
            if type(after) is not int or after < 0:
                raise ValueError("after must be a nonnegative millisecond timestamp")
            arguments["after"] = str(after)

        def normalize(rows, observed):
            # [U-MULTI-PAIR-001] An empty page that answers a paging cursor is
            # the end of the venue's history; without a cursor it is malformed.
            if len(rows) > limit or (not rows and after is None):
                raise ValueError("unexpected candle response count")
            candles = normalize_candles(rows, symbol, timeframe, boundary)
            open_rows = sum(str(row[8]) == "0" for row in rows)
            future_rows = sum(str(row[8]) == "1" and okx_milliseconds(row[0])+duration > boundary
                              for row in rows)
            filtering = CandleFiltering(len(rows), open_rows, future_rows,
                                         len(rows)-open_rows-future_rows-len(candles), len(candles))
            return candles, filtering

        return await self._read(REQUIRED_TOOLS[1], symbol, arguments, normalize,
                                timeframe=timeframe, as_of=boundary)

    async def orderbook(self, symbol: str, depth: int = 5) -> McpMarketRead:
        _symbol(symbol)
        if type(depth) is not int or not 1 <= depth <= 400:
            raise ValueError("order book depth must be between 1 and 400")
        return await self._read(REQUIRED_TOOLS[2], symbol, {"instId": symbol, "sz": depth},
                                lambda rows, observed: (normalize_orderbook(rows, symbol, observed, depth), None))

    async def spot_instruments(self) -> McpMarketRead:
        """Every OKX TR spot listing. Only `instType=SPOT` is ever sent."""
        return await self._read(LISTING_TOOLS[0], None, {"instType": "SPOT"},
                                lambda rows, observed: (normalize_spot_instruments(rows), None))

    async def spot_tickers(self) -> McpMarketRead:
        """24h activity of every OKX TR spot pair, for volume ranking."""
        return await self._read(LISTING_TOOLS[1], None, {"instType": "SPOT"},
                                lambda rows, observed: (normalize_spot_tickers(rows), None))
