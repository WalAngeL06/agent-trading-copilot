"""Exact, immutable live facts kept outside closed-candle decision snapshots."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .okx import _decimal, _symbol


def observation_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observation time must include a timezone")
    return value.astimezone(timezone.utc)


def okx_milliseconds(value) -> datetime:
    stamp = _decimal(value)
    if not stamp.is_finite() or stamp < 0 or stamp != stamp.to_integral_value():
        raise ValueError("invalid OKX millisecond timestamp")
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(stamp))


def _exact(value: Decimal, *, quantity=False):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("market values must be finite Decimals")
    if (value < 0 if quantity else value <= 0):
        raise ValueError("invalid market price or quantity")


def _times(value):
    observed = observation_time(value.observed_at)
    exchange = observation_time(value.exchange_time)
    if exchange > observed:
        raise ValueError("exchange observation cannot be in the future")
    object.__setattr__(value, "observed_at", observed)
    object.__setattr__(value, "exchange_time", exchange)


@dataclass(frozen=True)
class TickerObservation:
    symbol: str
    last: Decimal
    bid: Decimal
    ask: Decimal
    exchange_time: datetime
    observed_at: datetime

    def __post_init__(self):
        _symbol(self.symbol)
        _times(self)
        for value in (self.last, self.bid, self.ask):
            _exact(value)
        if self.bid > self.ask:
            raise ValueError("crossed ticker quotes")


@dataclass(frozen=True)
class BookLevel:
    price: Decimal
    quantity: Decimal

    def __post_init__(self):
        _exact(self.price)
        _exact(self.quantity, quantity=True)


@dataclass(frozen=True)
class OrderBookObservation:
    symbol: str
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    exchange_time: datetime
    observed_at: datetime

    def __post_init__(self):
        _symbol(self.symbol)
        _times(self)
        for name in ("bids", "asks"):
            levels = tuple(getattr(self, name))
            if not levels or any(not isinstance(level, BookLevel) for level in levels):
                raise ValueError("order book requires nonempty domain levels")
            prices = [level.price for level in levels]
            if len(set(prices)) != len(prices) or prices != sorted(prices, reverse=name == "bids"):
                raise ValueError("order book levels must be strictly sorted")
            object.__setattr__(self, name, levels)
        if self.bids[0].price > self.asks[0].price:
            raise ValueError("crossed order book")


def normalize_ticker(rows: list, symbol: str, observed_at: datetime) -> TickerObservation:
    if len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get("instId") != symbol:
        raise ValueError("ticker instrument or row shape mismatch")
    row = rows[0]
    return TickerObservation(symbol, _decimal(row["last"]), _decimal(row["bidPx"]),
                             _decimal(row["askPx"]), okx_milliseconds(row["ts"]), observed_at)


def normalize_orderbook(rows: list, symbol: str, observed_at: datetime,
                        depth: int) -> OrderBookObservation:
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("unexpected order book row shape")
    row = rows[0]
    if "instId" in row and row["instId"] != symbol:
        raise ValueError("order book instrument mismatch")
    sides = []
    for name in ("bids", "asks"):
        levels = row[name]
        if not isinstance(levels, list) or not 1 <= len(levels) <= depth:
            raise ValueError("unexpected order book depth")
        if any(not isinstance(level, (list, tuple)) or len(level) != 4 for level in levels):
            raise ValueError("order book level must have four fields")
        sides.append(tuple(BookLevel(_decimal(level[0]), _decimal(level[1])) for level in levels))
    return OrderBookObservation(symbol, *sides, okx_milliseconds(row["ts"]), observed_at)
