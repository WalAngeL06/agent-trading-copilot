"""Shared bounded closed-candle histories for replay and market bootstrap."""

from collections import deque
from datetime import datetime, timedelta

from .models import Candle, MarketSnapshot


# Fixed intervals only: calendar bars need explicit exchange session semantics.
BAR_DURATIONS = {
    "1m": timedelta(minutes=1), "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5), "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30), "1H": timedelta(hours=1),
    "2H": timedelta(hours=2), "4H": timedelta(hours=4),
    "6H": timedelta(hours=6), "12H": timedelta(hours=12),
}


def bar_duration(timeframe: str) -> timedelta:
    if timeframe not in BAR_DURATIONS:
        raise ValueError("unsupported fixed candle timeframe")
    return BAR_DURATIONS[timeframe]


class HistoryStore:
    def __init__(self, limit: int):
        if type(limit) is not int or limit <= 0:
            raise ValueError("history limit must be a positive integer")
        self._limit = limit
        self._series: dict[tuple[str, str], deque[Candle]] = {}

    def append(self, candle: Candle) -> None:
        if not isinstance(candle, Candle) or candle.closed is not True:
            raise ValueError("history requires closed Candle instances")
        history = self._series.setdefault((candle.symbol, candle.timeframe),
                                          deque(maxlen=self._limit))
        if history and candle.close_time <= history[-1].close_time:
            raise ValueError("duplicate or old candle for this symbol/timeframe")
        history.append(candle)

    def snapshot(self, symbol: str, as_of: datetime) -> MarketSnapshot:
        return MarketSnapshot(symbol, as_of, {
            tf: tuple(c for c in history if c.close_time <= as_of)
            for (stored_symbol, tf), history in self._series.items()
            if stored_symbol == symbol
        })


def snapshot_summary(snapshot: MarketSnapshot) -> dict:
    return {
        "as_of": snapshot.as_of,
        "counts": {tf: len(history) for tf, history in snapshot.histories.items()},
        "latest_closed": {tf: history[-1].close_time if history else None
                          for tf, history in snapshot.histories.items()},
    }
