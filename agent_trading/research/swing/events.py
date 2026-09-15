"""Causal swing event/state contract.

Timestamp convention [H]: a swing's `swing_time` is the close time of the candle
whose wick holds the extreme. OHLC supplies no intrabar instant, so no finer
precision is invented (market-structure-v0.1 N-7, DD-4).

Causal invariant: swing_time <= confirmed_at == observed_at for a confirmation.
A confirmation is published at the first candle whose close makes the detector's
opposing-movement evidence knowable, never backdated onto the extreme candle
(market-structure-v0.1 L-1, L-2; DD-18).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum


class SwingSide(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


class SwingStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"


class SwingEventType(str, Enum):
    CANDIDATE_CREATED = "CANDIDATE_CREATED"
    CANDIDATE_UPDATED = "CANDIDATE_UPDATED"
    CANDIDATE_DISCARDED = "CANDIDATE_DISCARDED"
    SWING_CONFIRMED = "SWING_CONFIRMED"


_CONFIRMING = (SwingEventType.SWING_CONFIRMED,)


@dataclass(frozen=True)
class SwingEvent:
    """One immutable, then-knowable observation about a swing.

    `observed_at` is the close time of the candle being processed when this
    event was emitted: the knowledge time. `swing_time` may be much earlier.
    """

    symbol: str
    timeframe: str
    detector: str
    event_type: SwingEventType
    side: SwingSide
    status: SwingStatus
    price: Decimal
    swing_time: datetime
    observed_at: datetime
    confirmed_at: datetime | None = None
    confirmation_delay_bars: int | None = None
    evidence: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    sequence: int = 0

    def __post_init__(self):
        for name in ("symbol", "timeframe", "detector"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if not isinstance(self.event_type, SwingEventType):
            raise ValueError("event_type must be a SwingEventType")
        if not isinstance(self.side, SwingSide):
            raise ValueError("side must be a SwingSide")
        if not isinstance(self.status, SwingStatus):
            raise ValueError("status must be a SwingStatus")
        if not isinstance(self.price, Decimal) or not self.price.is_finite() or self.price <= 0:
            raise ValueError("price must be a positive finite Decimal")
        for name in ("swing_time", "observed_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must include a timezone")
            object.__setattr__(self, name, value.astimezone(timezone.utc))
        if self.swing_time > self.observed_at:
            raise ValueError("swing_time cannot be later than observed_at")
        confirming = self.event_type in _CONFIRMING
        if confirming != (self.status is SwingStatus.CONFIRMED):
            raise ValueError("only SWING_CONFIRMED may carry CONFIRMED status")
        if confirming:
            if self.confirmed_at is None:
                raise ValueError("a confirmation requires confirmed_at")
            if self.confirmed_at.tzinfo is None or self.confirmed_at.utcoffset() is None:
                raise ValueError("confirmed_at must include a timezone")
            object.__setattr__(self, "confirmed_at",
                               self.confirmed_at.astimezone(timezone.utc))
            if self.confirmed_at != self.observed_at:
                raise ValueError("confirmation must be published at its knowledge time")
            if self.swing_time > self.confirmed_at:
                raise ValueError("swing_time cannot be later than confirmed_at")
            if type(self.confirmation_delay_bars) is not int or self.confirmation_delay_bars < 0:
                raise ValueError("confirmation_delay_bars must be a nonnegative integer")
        else:
            if self.confirmed_at is not None or self.confirmation_delay_bars is not None:
                raise ValueError("an unconfirmed event cannot carry confirmation fields")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative integer")
        for name in ("evidence", "source_ids"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(not isinstance(item, str) or not item
                                                   for item in value):
                raise ValueError(f"{name} must be a tuple of nonempty strings")


@dataclass(frozen=True)
class ConfirmedSwing:
    """The immutable identity of a confirmed swing.

    Equality of this record across replays is the anti-repaint contract:
    once published it must never move, reprice, retime or disappear.
    """

    symbol: str
    timeframe: str
    side: SwingSide
    price: Decimal
    swing_time: datetime
    confirmed_at: datetime

    @classmethod
    def from_event(cls, event: SwingEvent) -> "ConfirmedSwing":
        if event.status is not SwingStatus.CONFIRMED:
            raise ValueError("only a confirmed event has a confirmed identity")
        return cls(event.symbol, event.timeframe, event.side, event.price,
                   event.swing_time, event.confirmed_at)
