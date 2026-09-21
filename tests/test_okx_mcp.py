import asyncio
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import json
from types import SimpleNamespace
import unittest

from agent_trading.market import HistoryStore
from agent_trading.models import to_jsonable, utc_time
from agent_trading.okx_mcp import McpMarketError, OkxMcpMarketAdapter, REQUIRED_TOOLS


AS_OF = utc_time("2026-01-01T10:15:00Z")
OBSERVED = AS_OF + timedelta(minutes=1)
MS = "1767262500000"


LISTING = ("market_get_instruments", "market_get_tickers")
INST_TYPES = ["SPOT", "SWAP", "FUTURES", "OPTION", "MARGIN", "EVENTS"]


def tool(name):
    if name in LISTING:
        properties = {"instType": {"type": "string", "enum": list(INST_TYPES)},
                      "instFamily": {"type": "string"}, "demo": {"type": "boolean"}}
        return SimpleNamespace(name=name, input_schema={"type": "object",
                               "properties": properties, "required": ["instType"]})
    properties = {"instId": {"type": "string"}}
    if name == "market_get_candles":
        properties.update(bar={"type": "string", "enum": ["15m", "1H", "4H"]},
                          limit={"type": "number"}, after={"type": "string"})
    if name == "market_get_orderbook":
        properties["sz"] = {"type": "number"}
    return SimpleNamespace(name=name, input_schema={"type": "object",
                           "properties": properties, "required": ["instId"]})


def reply(name, data):
    endpoint = {"market_get_ticker": "/api/v5/market/ticker",
                "market_get_candles": "/api/v5/market/candles",
                "market_get_orderbook": "/api/v5/market/books",
                "market_get_instruments": "/api/v5/public/instruments",
                "market_get_tickers": "/api/v5/market/tickers"}[name]
    payload = {"tool": name, "ok": True,
               "data": {"endpoint": endpoint, "requestTime": AS_OF.isoformat(), "data": data},
               "capabilities": {"readOnly": True, "hasAuth": False, "demo": False}}
    return SimpleNamespace(is_error=False, structured_content=payload,
                           content=[SimpleNamespace(type="text", text=json.dumps(payload))])


def candle(open_time="2026-01-01T10:00:00Z", confirm="1", close="101.1234567890123456789"):
    ms = (utc_time(open_time) - utc_time("1970-01-01T00:00:00Z")) // timedelta(milliseconds=1)
    return [str(ms), "100", "102", "99", close, "0.1234567890123456789", "0", "0", confirm]


def ticker(symbol="BTC-USDT"):
    return [{"instId": symbol, "ts": MS, "last": "101.1234567890123456789",
             "bidPx": "101", "askPx": "102"}]


def book():
    return [{"ts": MS, "bids": [["101", "0.1234567890123456789", "0", "2"],
                                 ["100", "2", "0", "1"]],
             "asks": [["102", "3", "0", "1"], ["103", "4", "0", "1"]]}]


class FakeSession:
    def __init__(self):
        self.tools = [tool(name) for name in REQUIRED_TOOLS]
        self.responses = {"market_get_ticker": reply("market_get_ticker", ticker()),
                          "market_get_candles": reply("market_get_candles", [candle()]),
                          "market_get_orderbook": reply("market_get_orderbook", book())}
        self.calls = []
        self.pages = None
        self.error = None
        self.delay = 0

    async def list_tools(self, *, cursor=None):
        if self.error:
            raise self.error
        await asyncio.sleep(self.delay)
        if self.pages:
            return self.pages[cursor]
        return SimpleNamespace(tools=self.tools, next_cursor=None)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.error:
            raise self.error
        await asyncio.sleep(self.delay)
        return self.responses[name]


class McpAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = FakeSession()
        self.adapter = OkxMcpMarketAdapter(self.session, clock=lambda: OBSERVED)
        await self.adapter.discover()

    async def test_discovery_records_authoritative_tools(self):
        self.assertEqual(set(self.adapter.discovered_tools), set(REQUIRED_TOOLS))
        self.assertEqual(self.session.calls, [])
        self.assertEqual(self.adapter.provenance[0].tool, "tools/list")
        self.assertTrue(self.adapter.provenance[0].success)

    async def test_discovery_handles_pagination(self):
        self.session.pages = {
            None: SimpleNamespace(tools=[tool(REQUIRED_TOOLS[0])], next_cursor="page2"),
            "page2": SimpleNamespace(tools=[tool(n) for n in REQUIRED_TOOLS[1:]], next_cursor=None)}
        self.assertEqual(set(await self.adapter.discover()), set(REQUIRED_TOOLS))

    async def test_repeated_cursor_fails_closed(self):
        page = SimpleNamespace(tools=[tool(REQUIRED_TOOLS[0])], next_cursor="repeat")
        self.session.pages = {None: page, "repeat": page}
        with self.assertRaises(McpMarketError):
            await self.adapter.discover()
        with self.assertRaises(McpMarketError):
            await self.adapter.ticker("BTC-USDT")

    async def test_missing_or_renamed_required_tool_stops_calls(self):
        self.session.tools[-1] = tool("market_get_book")
        with self.assertRaises(McpMarketError) as error:
            await self.adapter.discover()
        self.assertEqual(error.exception.code, "REQUIRED_TOOLS_MISSING")
        self.assertEqual(error.exception.missing_tools, (REQUIRED_TOOLS[-1],))
        with self.assertRaises(McpMarketError):
            await self.adapter.ticker("BTC-USDT")
        self.assertEqual(self.session.calls, [])

    async def test_schema_drift_fails_before_call(self):
        self.session.tools[0].input_schema["properties"] = {"symbol": {"type": "string"}}
        with self.assertRaises(McpMarketError) as error:
            await self.adapter.discover()
        self.assertEqual(error.exception.code, "TOOL_SCHEMA_DRIFT")
        self.assertEqual(self.session.calls, [])

    async def test_private_tool_discovery_fails(self):
        self.session.tools.append(tool("spot_place_order"))
        with self.assertRaises(McpMarketError):
            await self.adapter.discover()
        self.assertEqual(self.session.calls, [])

    async def test_ticker_normalizes_decimal_and_observation_times(self):
        read = await self.adapter.ticker("BTC-USDT")
        self.assertEqual(read.value.symbol, "BTC-USDT")
        self.assertEqual(read.value.last, Decimal("101.1234567890123456789"))
        self.assertEqual(read.value.exchange_time, AS_OF)
        self.assertEqual(read.value.observed_at, OBSERVED)
        self.assertGreater(read.value.observed_at, AS_OF)
        self.assertEqual(self.session.calls[-1], ("market_get_ticker", {"instId": "BTC-USDT"}))

    async def test_candles_reuse_closed_domain_contracts(self):
        read = await self.adapter.candles("BTC-USDT", "15m", 10, as_of=AS_OF)
        self.assertEqual(len(read.value), 1)
        self.assertEqual(read.value[0].close_time, AS_OF)
        self.assertEqual(read.value[0].close, Decimal("101.1234567890123456789"))
        self.assertEqual(read.value[0].volume, Decimal("0.1234567890123456789"))
        self.assertTrue(read.value[0].closed)
        self.assertEqual(self.session.calls[-1][1], {"instId": "BTC-USDT", "bar": "15m", "limit": 10})

    async def test_open_future_and_duplicate_candles_are_counted_and_filtered(self):
        rows = [candle(), candle(), candle("2026-01-01T10:15:00Z", "0"),
                candle("2026-01-01T10:15:00Z"), candle("2026-01-01T09:45:00Z")]
        self.session.responses["market_get_candles"] = reply("market_get_candles", rows)
        read = await self.adapter.candles("BTC-USDT", "15m", 10, as_of=AS_OF)
        self.assertEqual([c.close_time for c in read.value], [AS_OF-timedelta(minutes=15), AS_OF])
        self.assertEqual(to_jsonable(read.provenance.filtering), {
            "received_rows": 5, "open_rows": 1, "future_rows": 1,
            "duplicate_rows": 1, "retained_rows": 2})

    async def test_candle_symbol_timeframe_isolation_reaches_existing_snapshot(self):
        store = HistoryStore(10)
        for symbol, tf in [("BTC-USDT", "15m"), ("ETH-USDT", "15m"), ("BTC-USDT", "1H")]:
            self.session.responses["market_get_candles"] = reply(
                "market_get_candles", [candle("2026-01-01T09:00:00Z")])
            read = await self.adapter.candles(symbol, tf, 10, as_of=AS_OF)
            for value in read.value:
                store.append(value)
        snapshot = store.snapshot("BTC-USDT", AS_OF)
        self.assertEqual(set(snapshot.histories), {"15m", "1H"})
        self.assertTrue(all(c.symbol == "BTC-USDT" and c.timeframe == tf and c.close_time <= AS_OF
                            for tf, rows in snapshot.histories.items() for c in rows))

    async def test_future_decision_as_of_is_rejected_before_call(self):
        with self.assertRaises(McpMarketError):
            await self.adapter.candles("BTC-USDT", "15m", 10, as_of=OBSERVED+timedelta(seconds=1))
        self.assertEqual(self.session.calls, [])

    async def test_orderbook_normalizes_prices_quantities_and_times(self):
        read = await self.adapter.orderbook("BTC-USDT", 5)
        self.assertEqual(read.value.bids[0].price, Decimal("101"))
        self.assertEqual(read.value.bids[0].quantity, Decimal("0.1234567890123456789"))
        self.assertEqual(read.value.asks[0].price, Decimal("102"))
        self.assertEqual(read.value.exchange_time, AS_OF)
        self.assertEqual(read.value.observed_at, OBSERVED)
        self.assertEqual(self.session.calls[-1], ("market_get_orderbook", {"instId": "BTC-USDT", "sz": 5}))

    async def test_numeric_text_json_is_parsed_without_float_rounding(self):
        response = reply("market_get_ticker", ticker())
        response.content[0].text = response.content[0].text.replace(
            '"101.1234567890123456789"', '101.1234567890123456789')
        response.structured_content["data"]["data"][0]["last"] = 101.12345678901235
        self.session.responses["market_get_ticker"] = response
        read = await self.adapter.ticker("BTC-USDT")
        self.assertEqual(read.value.last, Decimal("101.1234567890123456789"))

    async def test_structured_only_float_prices_are_rejected(self):
        for name, rows in [("market_get_ticker", ticker()), ("market_get_candles", [candle()]),
                           ("market_get_orderbook", book())]:
            if name.endswith("ticker"):
                rows[0]["last"] = 101.1
            elif name.endswith("candles"):
                rows[0][4] = 101.1
            else:
                rows[0]["bids"][0][1] = 0.1
            response = reply(name, [])
            response.content = []
            response.structured_content["data"]["data"] = rows
            self.session.responses[name] = response
            with self.subTest(name=name), self.assertRaises(McpMarketError):
                if name.endswith("ticker"):
                    await self.adapter.ticker("BTC-USDT")
                elif name.endswith("candles"):
                    await self.adapter.candles("BTC-USDT", "15m", 10, as_of=AS_OF)
                else:
                    await self.adapter.orderbook("BTC-USDT")

    async def test_malformed_response_fails_with_sanitized_provenance(self):
        for data in [[], ["secret"], ticker("ETH-USDT"), [{"instId": "BTC-USDT"}],
                     [dict(ticker()[0], last="NaN")], [dict(ticker()[0], ts="secret")]]:
            self.session.responses["market_get_ticker"] = reply("market_get_ticker", data)
            with self.subTest(data=data), self.assertRaises(McpMarketError) as error:
                await self.adapter.ticker("BTC-USDT")
            self.assertEqual(error.exception.code, "MALFORMED_RESPONSE")
            self.assertFalse(self.adapter.provenance[-1].success)
            self.assertNotIn("secret", json.dumps(to_jsonable(self.adapter.provenance)))

    async def test_invalid_json_or_wrong_envelope_cannot_pass(self):
        for payload in ["secret", "[]", '{"ok":true,"data":[]}',
                        json.dumps({"tool": "market_get_candles", "ok": True, "data": ticker()})]:
            response = reply("market_get_ticker", ticker())
            response.content[0].text = payload
            self.session.responses["market_get_ticker"] = response
            with self.subTest(payload=payload), self.assertRaises(McpMarketError):
                await self.adapter.ticker("BTC-USDT")

    async def test_atk_nested_envelope_is_unwrapped_before_domain_normalization(self):
        response = reply("market_get_ticker", ticker())
        self.assertEqual(set(response.structured_content["data"]), {"endpoint", "requestTime", "data"})
        self.session.responses["market_get_ticker"] = response
        read = await self.adapter.ticker("BTC-USDT")
        self.assertEqual(read.value.last, Decimal("101.1234567890123456789"))
        self.assertNotIn("endpoint", to_jsonable(read.value))

    async def test_tool_errors_and_nonpublic_capabilities_are_rejected(self):
        for change in [{"ok": False}, {"capabilities": {"readOnly": False, "hasAuth": False, "demo": False}},
                       {"capabilities": {"readOnly": True, "hasAuth": True, "demo": False}},
                       {"capabilities": {"readOnly": True, "hasAuth": False, "demo": True}}]:
            response = reply("market_get_ticker", ticker())
            response.structured_content.update(change)
            response.content[0].text = json.dumps(response.structured_content)
            self.session.responses["market_get_ticker"] = response
            with self.subTest(change=change), self.assertRaises(McpMarketError):
                await self.adapter.ticker("BTC-USDT")
        response.is_error = True
        response.content[0].text = "secret authorization token"
        with self.assertRaises(McpMarketError) as error:
            await self.adapter.ticker("BTC-USDT")
        self.assertNotIn("secret", str(error.exception))

    async def test_discovery_and_call_unavailability_suppress_raw_errors(self):
        self.session.error = OSError("secret token private environment")
        for operation in [self.adapter.ticker("BTC-USDT"), self.adapter.discover()]:
            with self.assertRaises(McpMarketError) as error:
                await operation
            self.assertEqual(error.exception.code, "MCP_UNAVAILABLE")
            self.assertNotIn("secret", str(error.exception))
            self.assertFalse(error.exception.provenance.success)

    async def test_discovery_and_call_timeouts_are_bounded(self):
        self.adapter.timeout = 0.01
        self.session.delay = 0.1
        for operation in [self.adapter.ticker("BTC-USDT"), self.adapter.discover()]:
            with self.assertRaises(McpMarketError) as error:
                await operation
            self.assertEqual(error.exception.code, "MCP_TIMEOUT")

    async def test_provenance_truthfully_identifies_mcp_and_is_serializable(self):
        read = await self.adapter.ticker("BTC-USDT")
        event = to_jsonable(read.provenance)
        self.assertEqual((event["transport"], event["provider"], event["site"]),
                         ("MCP", "OKX Agent Trade Kit", "tr"))
        self.assertEqual(event["tool"], "market_get_ticker")
        self.assertEqual(event["symbol"], "BTC-USDT")
        self.assertEqual(read.provenance.request_observed_at, OBSERVED)
        self.assertEqual(read.provenance.response_observed_at, OBSERVED)
        self.assertIsInstance(event["latency_ms"], int)
        self.assertTrue(event["success"])
        self.assertEqual(to_jsonable(read.value)["last"], "101.1234567890123456789")

    async def test_invalid_requests_never_invoke_mcp(self):
        for operation in [self.adapter.ticker("--help"), self.adapter.orderbook("BTC-USDT", True),
                          self.adapter.candles("BTC-USDT", "1D", 10, as_of=AS_OF),
                          self.adapter.candles("BTC-USDT", "15m", 301, as_of=AS_OF),
                          self.adapter.candles("BTC-USDT", "15m", 10, as_of=AS_OF, after=-1)]:
            with self.assertRaises(ValueError):
                await operation
        self.assertEqual(self.session.calls, [])

    async def test_conflicting_closed_candles_are_rejected(self):
        self.session.responses["market_get_candles"] = reply(
            "market_get_candles", [candle(), candle(close="100")])
        with self.assertRaises(McpMarketError):
            await self.adapter.candles("BTC-USDT", "15m", 10, as_of=AS_OF)

    async def test_an_empty_candle_page_without_a_cursor_stays_malformed(self):
        # Live callers never page, so for them an empty answer is a broken one.
        self.session.responses["market_get_candles"] = reply("market_get_candles", [])
        with self.assertRaises(McpMarketError) as error:
            await self.adapter.candles("BTC-USDT", "15m", 10, as_of=AS_OF)
        self.assertEqual(error.exception.code, "MALFORMED_RESPONSE")

    async def test_an_empty_page_after_a_cursor_means_no_older_history(self):
        # [U-MULTI-PAIR-001] Paging past a pair's listing date returns nothing.
        self.session.responses["market_get_candles"] = reply("market_get_candles", [])
        read = await self.adapter.candles("BTC-USDT", "15m", 10, as_of=AS_OF,
                                          after=1767262500000)
        self.assertEqual(read.value, ())
        self.assertEqual(to_jsonable(read.provenance.filtering), {
            "received_rows": 0, "open_rows": 0, "future_rows": 0,
            "duplicate_rows": 0, "retained_rows": 0})
        self.assertEqual(self.session.calls[-1][1]["after"], "1767262500000")

    async def test_too_many_rows_still_fail_with_a_cursor(self):
        rows = [candle("2026-01-01T09:00:00Z"), candle("2026-01-01T09:15:00Z")]
        self.session.responses["market_get_candles"] = reply("market_get_candles", rows)
        with self.assertRaises(McpMarketError) as error:
            await self.adapter.candles("BTC-USDT", "15m", 1, as_of=AS_OF, after=1767262500000)
        self.assertEqual(error.exception.code, "MALFORMED_RESPONSE")

    async def test_bad_book_sort_crossing_empty_or_future_time_fails(self):
        variants = []
        for change in ["reversed", "crossed", "empty", "future"]:
            rows = deepcopy(book())
            if change == "reversed":
                rows[0]["bids"].reverse()
            if change == "crossed":
                rows[0]["asks"][0][0] = "100"
            if change == "empty":
                rows[0]["asks"] = []
            if change == "future":
                rows[0]["ts"] = "1767270000000"
            variants.append(rows)
        for rows in variants:
            self.session.responses["market_get_orderbook"] = reply("market_get_orderbook", rows)
            with self.subTest(rows=rows), self.assertRaises(McpMarketError):
                await self.adapter.orderbook("BTC-USDT")

    async def test_response_arrival_time_is_conservative(self):
        times = iter([OBSERVED, OBSERVED+timedelta(seconds=2)])
        self.adapter.clock = lambda: next(times)
        read = await self.adapter.ticker("BTC-USDT")
        self.assertEqual(read.provenance.request_observed_at, OBSERVED)
        self.assertEqual(read.value.observed_at, OBSERVED+timedelta(seconds=2))

    async def test_malformed_response_provenance_keeps_its_arrival_time(self):
        times = iter([OBSERVED, OBSERVED+timedelta(seconds=2)])
        self.adapter.clock = lambda: next(times)
        self.session.responses["market_get_ticker"] = reply("market_get_ticker", [])
        with self.assertRaises(McpMarketError) as error:
            await self.adapter.ticker("BTC-USDT")
        self.assertEqual(error.exception.code, "MALFORMED_RESPONSE")
        self.assertEqual(error.exception.provenance.response_observed_at, OBSERVED+timedelta(seconds=2))

    async def test_structured_only_exact_decimals_are_preserved(self):
        response = reply("market_get_ticker", ticker())
        response.content = []
        response.structured_content["data"]["data"][0]["last"] = Decimal("101.1234567890123456789")
        self.session.responses["market_get_ticker"] = response
        self.assertEqual((await self.adapter.ticker("BTC-USDT")).value.last,
                         Decimal("101.1234567890123456789"))

    async def test_provenance_history_is_bounded(self):
        for _ in range(105):
            await self.adapter.ticker("BTC-USDT")
        self.assertLessEqual(len(self.adapter.provenance), 100)


def spot_instrument(inst_id="ETH-USDT"):
    base, quote = inst_id.split("-")
    return {"instType": "SPOT", "instId": inst_id, "baseCcy": base, "quoteCcy": quote,
            "state": "live", "listTime": "1548133413000"}


def spot_ticker(inst_id="ETH-USDT", volume="1000.5"):
    return {"instType": "SPOT", "instId": inst_id, "last": "2500", "volCcy24h": volume,
            "ts": MS}


class SpotListingAdapterTests(unittest.IsolatedAsyncioTestCase):
    """[U-MULTI-PAIR-001] Two public listing reads; still no private or write tool."""

    async def asyncSetUp(self):
        self.session = FakeSession()
        self.session.tools += [tool(name) for name in LISTING]
        self.session.responses["market_get_instruments"] = reply(
            "market_get_instruments", [spot_instrument(), spot_instrument("BTC-USDT")])
        self.session.responses["market_get_tickers"] = reply(
            "market_get_tickers", [spot_ticker(), spot_ticker("BTC-USDT", "9000")])
        self.adapter = OkxMcpMarketAdapter(self.session, clock=lambda: OBSERVED)
        await self.adapter.discover()

    async def test_the_callable_tools_are_the_three_required_plus_two_listings(self):
        from agent_trading import okx_mcp
        self.assertEqual(okx_mcp.REQUIRED_TOOLS,
                         ("market_get_ticker", "market_get_candles", "market_get_orderbook"))
        self.assertEqual(okx_mcp.LISTING_TOOLS, LISTING)

    async def test_spot_instruments_are_read_with_inst_type_spot_only(self):
        read = await self.adapter.spot_instruments()
        self.assertEqual([record.symbol for record in read.value], ["ETH-USDT", "BTC-USDT"])
        self.assertEqual(self.session.calls[-1], ("market_get_instruments", {"instType": "SPOT"}))
        self.assertEqual((read.provenance.tool, read.provenance.symbol, read.provenance.timeframe),
                         ("market_get_instruments", None, None))
        self.assertTrue(read.provenance.success)

    async def test_spot_tickers_carry_the_quote_volume(self):
        read = await self.adapter.spot_tickers()
        self.assertEqual({record.symbol: record.quote_volume_24h for record in read.value},
                         {"ETH-USDT": Decimal("1000.5"), "BTC-USDT": Decimal("9000")})
        self.assertEqual(self.session.calls[-1], ("market_get_tickers", {"instType": "SPOT"}))

    async def test_discovery_does_not_require_the_listing_tools(self):
        session = FakeSession()                       # only the three required tools
        adapter = OkxMcpMarketAdapter(session, clock=lambda: OBSERVED)
        await adapter.discover()
        for operation in (adapter.spot_instruments(), adapter.spot_tickers()):
            with self.assertRaises(McpMarketError) as error:
                await operation
            self.assertEqual(error.exception.code, "TOOLS_NOT_DISCOVERED")
        self.assertEqual(session.calls, [])

    async def test_listing_schema_drift_is_caught_when_called_not_at_discovery(self):
        drifted = tool("market_get_instruments")
        drifted.input_schema["required"] = ["instId"]
        self.session.tools[-2] = drifted
        await self.adapter.discover()                 # the live contract stays intact
        with self.assertRaises(McpMarketError) as error:
            await self.adapter.spot_instruments()
        self.assertEqual(error.exception.code, "TOOL_SCHEMA_DRIFT")
        self.assertEqual(self.session.calls, [])

    async def test_an_inst_type_enum_without_spot_is_drift(self):
        self.session.tools[-1].input_schema["properties"]["instType"]["enum"] = ["SWAP"]
        await self.adapter.discover()
        with self.assertRaises(McpMarketError) as error:
            await self.adapter.spot_tickers()
        self.assertEqual(error.exception.code, "TOOL_SCHEMA_DRIFT")
        self.assertEqual(self.session.calls, [])

    async def test_other_market_tools_stay_uncallable_even_when_discovered(self):
        self.session.tools.append(tool("market_get_trades"))
        await self.adapter.discover()
        with self.assertRaises(McpMarketError) as error:
            await self.adapter._read("market_get_trades", "BTC-USDT", {"instId": "BTC-USDT"},
                                     lambda rows, observed: (rows, None))
        self.assertEqual(error.exception.code, "TOOLS_NOT_DISCOVERED")
        self.assertEqual(self.session.calls, [])

    async def test_a_malformed_listing_fails_without_leaking_the_payload(self):
        self.session.responses["market_get_tickers"] = reply(
            "market_get_tickers", [spot_ticker(volume="secret")])
        with self.assertRaises(McpMarketError) as error:
            await self.adapter.spot_tickers()
        self.assertEqual(error.exception.code, "MALFORMED_RESPONSE")
        self.assertNotIn("secret", json.dumps(to_jsonable(self.adapter.provenance)))
