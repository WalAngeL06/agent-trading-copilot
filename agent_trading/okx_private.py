"""Four explicit private reads; no generic tool dispatch, logging or write API."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
import re

from .account_snapshots import (
    AccountConfiguration, AccountSnapshot, AutoEarnState, CurrencyBalance,
    EarnSnapshot, PrivateSnapshotRead, SavingsBalance,
)
from .market_observations import observation_time, okx_milliseconds
from .okx_mcp import McpMarketError, validate_timeout


PRIVATE_READ_ALLOWLIST = (
    "account_get_balance", "account_get_asset_balance", "account_get_config",
    "earn_get_savings_balance",
)
_ENDPOINTS = dict(zip(PRIVATE_READ_ALLOWLIST, (
    "/api/v5/account/balance", "/api/v5/asset/balances", "/api/v5/account/config",
    "/api/v5/finance/savings/balance",
)))
_SCHEMAS = {
    "account_get_balance": {"ccy": "string"},
    "account_get_asset_balance": {"ccy": "string", "showValuation": "boolean", "valuationCcy": "string"},
    "account_get_config": {}, "earn_get_savings_balance": {"ccy": "string"},
}
_SAFE_ERRORS = frozenset({
    "AUTH_MISSING", "AUTH_FAILED", "CONFIG_INVALID", "ENV_UNREADABLE", "MCP_TIMEOUT",
    "MCP_UNAVAILABLE", "MCP_PROTOCOL_ERROR", "MCP_SCHEMA_ERROR", "OKX_READ_FAILED",
    "PRIVATE_SCOPE_MISMATCH", "MALFORMED_RESPONSE", "MALFORMED_DISCOVERY",
    "TOOLS_NOT_DISCOVERED", "TOOL_NOT_ALLOWED", "TOOL_SCHEMA_DRIFT", "REQUIRED_TOOLS_MISSING",
    "ATK_NOT_INSTALLED", "ATK_PACKAGE_MISMATCH", "ATK_VERSION_MISMATCH",
    "MCP_SDK_UNAVAILABLE", "MCP_SDK_VERSION_MISMATCH",
})


class PrivateReadError(RuntimeError):
    def __init__(self, code):
        self.code = code if code in _SAFE_ERRORS else "MCP_PROTOCOL_ERROR"
        super().__init__(f"OKX private read failed: {self.code}")


def private_failure(exc):
    if isinstance(exc, PrivateReadError):
        return exc
    if isinstance(exc, McpMarketError):
        return PrivateReadError(exc.code)
    if isinstance(exc, TimeoutError):
        return PrivateReadError("MCP_TIMEOUT")
    if isinstance(exc, OSError):
        return PrivateReadError("MCP_UNAVAILABLE")
    if isinstance(exc, ExceptionGroup):
        failures = [private_failure(item) for item in exc.exceptions]
        return next((item for item in failures if item.code != "MCP_PROTOCOL_ERROR"), failures[0])
    return PrivateReadError("MCP_PROTOCOL_ERROR")


def failed_read(exc, *, account=None):
    error = private_failure(exc)
    return PrivateSnapshotRead("AUTH_MISSING" if error.code == "AUTH_MISSING" else "ERROR",
                               error.code, account=account)


def _reject_constant(_):
    raise ValueError


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _business_failure(code):
    if code == "AUTH_MISSING":
        raise PrivateReadError("AUTH_MISSING")
    if code in {"50103", "50104", "50105", "50110", "50111", "50112", "50113", "50114", "50119", "401"}:
        raise PrivateReadError("AUTH_FAILED")
    raise PrivateReadError("OKX_READ_FAILED")


def _payload(response, name):
    if response.content:
        if len(response.content) != 1 or response.content[0].type != "text":
            raise ValueError
        payload = json.loads(response.content[0].text, parse_float=Decimal,
                             parse_constant=_reject_constant, object_pairs_hook=_object)
    else:
        payload = response.structured_content
    if not isinstance(payload, dict) or payload.get("tool") != name:
        raise ValueError
    caps = payload.get("capabilities")
    if (not isinstance(caps, dict) or caps.get("readOnly") is not True
            or caps.get("hasAuth") is not True or caps.get("demo") is not False):
        raise PrivateReadError("PRIVATE_SCOPE_MISMATCH")
    if response.is_error is not False or payload.get("ok") is not True:
        error = payload.get("error")
        code = error.get("code") if isinstance(error, dict) else payload.get("code")
        # Pinned ATK 1.4.6 serializes AuthenticationError at top level and
        # intentionally drops its original numeric OKX code. Use only fixed
        # type identifiers, never the raw message/suggestion/traceId.
        if payload.get("type") == "AuthenticationError":
            raise PrivateReadError("AUTH_FAILED")
        if payload.get("type") == "NetworkError":
            raise PrivateReadError("MCP_UNAVAILABLE")
        _business_failure(code if isinstance(code, str) else None)
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("endpoint") != _ENDPOINTS[name]:
        raise ValueError
    # Pinned ATK handlers normally consume the REST code; if it is present it
    # must be zero regardless of MCP is_error/ok. Never inspect/echo messages.
    if "code" in data and data["code"] != "0":
        _business_failure(data["code"] if isinstance(data["code"], str) else None)
    rows = data.get("data")
    if not isinstance(rows, list) or len(rows) > 1000 or any(not isinstance(row, dict) for row in rows):
        raise ValueError
    return rows


def _schema(tool, name):
    schema = tool.input_schema
    annotations = tool.annotations
    if (getattr(annotations, "read_only_hint", None) is not True
            or getattr(annotations, "destructive_hint", None) is True):
        raise PrivateReadError("PRIVATE_SCOPE_MISMATCH")
    if (not isinstance(schema, dict) or schema.get("type") != "object"
            or not isinstance(schema.get("properties"), dict) or schema.get("required", []) != []):
        raise PrivateReadError("TOOL_SCHEMA_DRIFT")
    # No arguments are passed, ever. Optional fields may only be the pinned
    # known schema fields; simulatedTrading/write inputs are not accepted.
    props = schema["properties"]
    if name == "account_get_config" and props:
        raise PrivateReadError("TOOL_SCHEMA_DRIFT")
    if name != "account_get_config" and "ccy" not in props:
        raise PrivateReadError("TOOL_SCHEMA_DRIFT")
    for field, definition in props.items():
        if field not in _SCHEMAS[name] or not isinstance(definition, dict) or definition.get("type") != _SCHEMAS[name][field]:
            raise PrivateReadError("TOOL_SCHEMA_DRIFT")


def _amount(value, *, nullable=False):
    if nullable and value in ("", None):
        return None
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise ValueError
    amount = Decimal(value)
    if not amount.is_finite():
        raise ValueError
    return amount


def _currency(row):
    value = row.get("ccy")
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9]{1,20}", value):
        raise ValueError
    return value


def _unique(rows):
    currencies = [_currency(row) for row in rows]
    if len(set(currencies)) != len(currencies):
        raise ValueError


def _time(value, observed):
    result = okx_milliseconds(value)
    if result > observed:
        raise ValueError
    return result


def _flag(value):
    return value if value in ("unsupported", "off", "pending", "active") else "UNKNOWN"


def _optional_bool(row, field):
    value = row.get(field)
    if value is not None and type(value) is not bool:
        raise ValueError
    return value


def normalize_account(balance, funding, config, observed):
    if len(balance) != 1 or len(config) != 1:
        raise ValueError
    head, settings = balance[0], config[0]
    rows = head["details"]
    if not isinstance(rows, list) or len(rows) > 1000 or any(not isinstance(row, dict) for row in rows):
        raise ValueError
    _unique(rows)
    _unique(funding)
    if settings.get("acctLv") not in ("1", "2", "3", "4") or settings.get("posMode") not in ("net_mode", "long_short_mode"):
        raise ValueError
    configuration = AccountConfiguration(settings["acctLv"], settings["posMode"],
        _optional_bool(settings, "autoLoan"), _optional_bool(settings, "enableSpotBorrow"))
    trading = tuple(CurrencyBalance(_currency(row), _amount(row["cashBal"], nullable=True),
        _amount(row["availBal"], nullable=True), _amount(row["frozenBal"], nullable=True),
        _amount(row["eq"], nullable=True), _time(row["uTime"], observed)) for row in rows)
    assets = tuple(CurrencyBalance(_currency(row), _amount(row["bal"]), _amount(row["availBal"]),
        _amount(row["frozenBal"])) for row in funding)
    flags = tuple(AutoEarnState(_currency(row), _flag(row.get("autoLendStatus")),
        _flag(row.get("autoStakingStatus"))) for row in rows)
    return AccountSnapshot(observed, _time(head["uTime"], observed), trading, assets,
                           _amount(head["totalEq"], nullable=True), configuration, flags)


def normalize_earn(rows, account, observed):
    _unique(rows)
    savings = tuple(SavingsBalance(_currency(row), _amount(row["amt"]),
        _amount(row.get("loanAmt"), nullable=True), _amount(row.get("rate"), nullable=True),
        _amount(row.get("earnings"), nullable=True)) for row in rows)
    return EarnSnapshot(observed, savings, account.auto_earn, account.observed_at)


class OkxPrivateReadAdapter:
    def __init__(self, session, timeout=30, clock=None):
        validate_timeout(timeout)
        self._session = session
        self.timeout = timeout
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._tools = {}

    async def discover(self):
        self._tools = {}
        tools, cursor, seen = {}, None, set()
        try:
            async with asyncio.timeout(self.timeout):
                for _ in range(100):
                    page = await self._session.list_tools(cursor=cursor)
                    if not isinstance(page.tools, list):
                        raise PrivateReadError("MALFORMED_DISCOVERY")
                    for tool in page.tools:
                        name = tool.name
                        if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,95}", name)
                                or name in tools or len(tools) >= 1000):
                            raise PrivateReadError("MALFORMED_DISCOVERY")
                        if (getattr(tool.annotations, "read_only_hint", None) is not True
                                or getattr(tool.annotations, "destructive_hint", None) is True):
                            raise PrivateReadError("PRIVATE_SCOPE_MISMATCH")
                        tools[name] = tool
                    cursor = page.next_cursor
                    if cursor is None:
                        break
                    if not isinstance(cursor, str) or not cursor or cursor in seen:
                        raise PrivateReadError("MALFORMED_DISCOVERY")
                    seen.add(cursor)
                else:
                    raise PrivateReadError("MALFORMED_DISCOVERY")
            if any(name not in tools for name in PRIVATE_READ_ALLOWLIST):
                raise PrivateReadError("REQUIRED_TOOLS_MISSING")
            for name in PRIVATE_READ_ALLOWLIST:
                _schema(tools[name], name)
            # Store only the exact four approved tools, even if the server
            # discovers additional read tools. Never call capability metadata.
            self._tools = {name: tools[name] for name in PRIVATE_READ_ALLOWLIST}
        except Exception as exc:
            raise private_failure(exc) from None

    async def _read(self, name):
        if name not in PRIVATE_READ_ALLOWLIST:
            raise PrivateReadError("TOOL_NOT_ALLOWED")
        if name not in self._tools:
            raise PrivateReadError("TOOLS_NOT_DISCOVERED")
        try:
            _schema(self._tools[name], name)
            async with asyncio.timeout(self.timeout):
                response = await self._session.call_tool(name, {})
            return _payload(response, name)
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            raise PrivateReadError("MALFORMED_RESPONSE") from None
        except Exception as exc:
            raise private_failure(exc) from None

    async def snapshot(self):
        account = None
        try:
            balance = await self._read("account_get_balance")
            funding = await self._read("account_get_asset_balance")
            settings = await self._read("account_get_config")
            observed = observation_time(self.clock())
            account = normalize_account(balance, funding, settings, observed)
            savings = await self._read("earn_get_savings_balance")
            earn = normalize_earn(savings, account, observation_time(self.clock()))
            return PrivateSnapshotRead("CONNECTED", account=account, earn=earn)
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            return failed_read(PrivateReadError("MALFORMED_RESPONSE"), account=account)
        except Exception as exc:
            return failed_read(exc, account=account)
