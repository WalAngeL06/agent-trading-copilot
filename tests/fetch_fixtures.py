"""Offline OKX venue for fetcher tests: the real adapter over a fake MCP session.

The session serves the two spot listings and candle pages keyed by (instId,
bar), honouring OKX's `after` cursor: rows open strictly before it, newest
first, at most `limit` (and at most `cap`). Faults can be scripted per symbol.
"""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace

from agent_trading.backtest.fetch import open_ms
from agent_trading.okx_mcp import OkxMcpMarketAdapter, REQUIRED_TOOLS
from test_okx_mcp import LISTING, reply, tool


def okx_row(candle):
    return [str(open_ms(candle)), str(candle.open), str(candle.high), str(candle.low),
            str(candle.close), str(candle.volume), '0', '0', '1']


class FakeVenue:
    def __init__(self, series, volumes, as_of, *, states=None, cap=300):
        """series: {(symbol, timeframe): candles}; volumes: {symbol: quote volume}."""
        self.series = {key: sorted(candles, key=lambda c: c.close_time, reverse=True)
                       for key, candles in series.items()}
        self.volumes = dict(volumes)
        self.states = dict(states or {})
        self.clock = as_of + timedelta(minutes=1)
        self.cap = cap
        self.tools = [tool(name) for name in REQUIRED_TOOLS + LISTING]
        self.opens = 0
        self.open_error = None
        self.unavailable = {}          # symbol -> OSError raises left
        self.tool_errors = {}          # symbol -> is_error replies left
        self.calls = []

    def instrument_rows(self):
        rows = []
        for symbol in sorted({symbol for symbol, _ in self.series} | set(self.volumes)):
            base, quote = symbol.split('-')
            rows.append({'instType': 'SPOT', 'instId': symbol, 'baseCcy': base,
                         'quoteCcy': quote, 'state': self.states.get(symbol, 'live'),
                         'listTime': '1548133413000'})
        return rows

    def ticker_rows(self):
        return [{'instType': 'SPOT', 'instId': symbol, 'last': '1', 'volCcy24h': str(volume),
                 'ts': '1767262500000'} for symbol, volume in sorted(self.volumes.items())]

    def factory(self, *, timeout=30):
        return self._runtime(timeout)

    @asynccontextmanager
    async def _runtime(self, timeout):
        self.opens += 1
        if self.open_error is not None:
            raise self.open_error
        adapter = OkxMcpMarketAdapter(_Session(self), timeout, clock=lambda: self.clock)
        await adapter.discover()
        yield adapter

    def candle_calls(self, symbol=None):
        return [arguments for name, arguments in self.calls
                if name == 'market_get_candles'
                and (symbol is None or arguments['instId'] == symbol)]


class _Session:
    def __init__(self, venue):
        self.venue = venue

    async def list_tools(self, *, cursor=None):
        return SimpleNamespace(tools=self.venue.tools, next_cursor=None)

    async def call_tool(self, name, arguments):
        venue = self.venue
        venue.calls.append((name, dict(arguments)))
        if name == 'market_get_instruments':
            return reply(name, venue.instrument_rows())
        if name == 'market_get_tickers':
            return reply(name, venue.ticker_rows())
        symbol = arguments['instId']
        if venue.unavailable.get(symbol, 0) > 0:
            venue.unavailable[symbol] -= 1
            raise OSError('secret transport detail')
        if venue.tool_errors.get(symbol, 0) > 0:
            venue.tool_errors[symbol] -= 1
            response = reply(name, [])
            response.is_error = True
            return response
        after = int(arguments.get('after', 10 ** 16))
        rows = [okx_row(candle) for candle in venue.series.get((symbol, arguments['bar']), ())
                if open_ms(candle) < after]
        return reply(name, rows[:min(int(arguments['limit']), venue.cap)])
