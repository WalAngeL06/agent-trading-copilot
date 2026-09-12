"""Exchange-independent data contracts. Scores are not probabilities."""

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def utc_time(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return stamp.astimezone(timezone.utc)


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    closed: bool = True

    def __post_init__(self):
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be nonempty")
        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise ValueError("timeframe must be nonempty")
        if self.closed is not True:
            raise ValueError("only closed candles are supported")
        if self.close_time.tzinfo is None or self.close_time.utcoffset() is None:
            raise ValueError("close_time must include a timezone")
        object.__setattr__(self, "close_time", self.close_time.astimezone(timezone.utc))
        prices = (self.open, self.high, self.low, self.close)
        if any(not isinstance(p, Decimal) or not p.is_finite() or p <= 0 for p in prices):
            raise ValueError("prices must be positive finite Decimals")
        if not isinstance(self.volume, Decimal) or not self.volume.is_finite() or self.volume < 0:
            raise ValueError("volume must be a nonnegative finite Decimal")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("OHLC bounds are inconsistent")

    @classmethod
    def from_dict(cls, row: dict) -> "Candle":
        try:
            if any(isinstance(row[field], float)
                   for field in ("open", "high", "low", "close", "volume")):
                raise ValueError("float inputs are unsafe; use Decimal or decimal strings")
            return cls(symbol=row["symbol"], timeframe=row["timeframe"],
                       close_time=utc_time(row["close_time"]),
                       open=Decimal(str(row["open"])), high=Decimal(str(row["high"])),
                       low=Decimal(str(row["low"])), close=Decimal(str(row["close"])),
                       volume=Decimal(str(row["volume"])), closed=row["closed"])
        except (KeyError, TypeError, AttributeError, InvalidOperation) as exc:
            raise ValueError("invalid candle payload") from exc


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    as_of: datetime
    histories: Mapping[str, tuple[Candle, ...]]

    def __post_init__(self):
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("snapshot symbol must be nonempty")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("snapshot as_of must include a timezone")
        object.__setattr__(self, "as_of", self.as_of.astimezone(timezone.utc))
        if not isinstance(self.histories, Mapping):
            raise ValueError("snapshot histories must be a mapping")
        copied = {}
        for tf, items in sorted(self.histories.items()):
            if not isinstance(tf, str) or not tf.strip():
                raise ValueError("snapshot timeframe must be nonempty")
            history = tuple(items)
            previous = None
            for candle in history:
                if not isinstance(candle, Candle) or candle.closed is not True:
                    raise ValueError("snapshot supports only closed Candle instances")
                if candle.symbol != self.symbol or candle.timeframe != tf:
                    raise ValueError("snapshot symbol/timeframe mismatch")
                if candle.close_time > self.as_of:
                    raise ValueError("snapshot cannot expose future candles")
                if previous is not None and candle.close_time <= previous:
                    raise ValueError("snapshot series must be strictly chronological")
                previous = candle.close_time
            copied[tf] = history
        object.__setattr__(self, "histories", MappingProxyType(copied))


class PatternStatus(str, Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_DETECTED = "NOT_DETECTED"
    DETECTED = "DETECTED"


@dataclass(frozen=True)
class PatternResult:
    name: str
    status: PatternStatus
    detected_at: datetime
    direction: str | None = None
    start_time: datetime | None = None
    window: int | None = None
    evidence: tuple[str, ...] = ()
    relevant_levels: tuple[tuple[str, Decimal], ...] = ()
    invalidation: str | None = None
    source_ids: tuple[str, ...] = ()
    score: Decimal | None = None
    score_method: str | None = None
    timeframe: str | None = None

    def __post_init__(self):
        if not self.name or not isinstance(self.status, PatternStatus):
            raise ValueError("pattern name and status are required")
        if self.detected_at.tzinfo is None or self.detected_at.utcoffset() is None:
            raise ValueError("detected_at must include a timezone")
        if self.start_time is not None:
            if self.start_time.tzinfo is None or self.start_time > self.detected_at:
                raise ValueError("start_time must be aware and no later than detected_at")
        if self.window is not None and (type(self.window) is not int or self.window <= 0):
            raise ValueError("window must be a positive integer")
        if self.timeframe is not None and (not isinstance(self.timeframe, str) or not self.timeframe.strip()):
            raise ValueError("pattern timeframe must be nonempty when supplied")
        if self.score is not None:
            if not isinstance(self.score, Decimal) or not self.score.is_finite() or not self.score_method:
                raise ValueError("score requires a finite Decimal and a named method")


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_jsonable(item) for item in value]
    return value
