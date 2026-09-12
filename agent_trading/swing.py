"""Causal volatility-adaptive swing detection.

Detects raw turning points only. **Raw swing != structural swing** (DD-1): this
module never decides protected levels, responsible swings, BOS, external or
internal scale, dealing range, premium/discount, direction or anything a
strategy would act on. Those belong to MarketStructureEngine and below.

Confirmation model — **PROJECT HYPOTHESIS [H], not a DD rule**:

* a candidate extreme is a **wick** high/low (DD-4 prices swings from wicks)
* it is confirmed when a **later candle's close** is at least
  `ATR(length) * multiplier` beyond it
* never from its own candle, so confirmation delay is always >= 1

DD confirms only that genuine opposing movement is required and that no fixed
2/3/5-bar pivot rule is approved (DD-18, DD-19). What exactly qualifies as that
movement remains **ALGORITHMIC DEFINITION PENDING** (market-structure-v0.1 N-1).
The ATR predicate below is a provisional stand-in isolated in one method so it
can be replaced without touching the state machine.

One engine instance owns one symbol and one timeframe. Nothing here assumes a
particular timeframe set: an approved strategy profile decides what it needs.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from .market import bar_duration
from .models import Candle


class SwingSide(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


class SwingStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"


class SwingEventType(str, Enum):
    CANDIDATE_CREATED = "CANDIDATE_CREATED"
    CANDIDATE_UPDATED = "CANDIDATE_UPDATED"
    SWING_CONFIRMED = "SWING_CONFIRMED"


def _opposite(side: SwingSide) -> SwingSide:
    return SwingSide.LOW if side is SwingSide.HIGH else SwingSide.HIGH


@dataclass(frozen=True)
class SwingConfig:
    """Operator/profile-owned detection settings. No strategy rules here.

    `atr_multiplier` is **provisional [H]**. The benchmark in
    docs/specs/swing-engine-v0.1.md does not single out an optimum: 1.25 was
    chosen because it holds swing density near 15-18 per 100 bars with mean
    confirmation delay under ~3 bars across 5m/15m/1H/4H BTC-USDT. It is a
    density/latency judgement, not a validated constant, and every caller can
    override it. `bootstrap_candles` is replay context length, not a trading rule.
    """

    atr_length: int = 14
    atr_multiplier: Decimal = Decimal("1.25")
    bootstrap_candles: int = 200

    def __post_init__(self):
        if type(self.atr_length) is not int or not 2 <= self.atr_length <= 500:
            raise ValueError("atr_length must be an integer between 2 and 500")
        multiplier = self.atr_multiplier
        if isinstance(multiplier, (str, int)):
            multiplier = Decimal(str(multiplier))
            object.__setattr__(self, "atr_multiplier", multiplier)
        if (not isinstance(multiplier, Decimal) or not multiplier.is_finite()
                or not Decimal("0.05") <= multiplier <= Decimal("20")):
            raise ValueError("atr_multiplier must be a Decimal between 0.05 and 20")
        if (type(self.bootstrap_candles) is not int
                or not 1 <= self.bootstrap_candles <= 5000):
            raise ValueError("bootstrap_candles must be an integer between 1 and 5000")
        if self.bootstrap_candles <= self.atr_length:
            raise ValueError("bootstrap_candles must exceed atr_length for a usable warmup")


@dataclass(frozen=True)
class SwingEvent:
    """One immutable, then-knowable observation about a swing.

    `observed_at` is the close time of the candle being processed: the
    knowledge time. `swing_time` is the close time of the candle whose wick
    holds the extreme and may be much earlier. OHLC records no intrabar
    instant, so no finer precision is invented (N-7, DD-4).
    """

    symbol: str
    timeframe: str
    event_type: SwingEventType
    side: SwingSide
    status: SwingStatus
    price: Decimal
    swing_time: datetime
    observed_at: datetime
    confirmed_at: datetime | None = None
    confirmation_delay_bars: int | None = None
    atr: Decimal | None = None
    threshold: Decimal | None = None
    evidence: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ("[H]-SWING-ATR-CLOSE-001",)
    sequence: int = 0

    def __post_init__(self):
        for name in ("symbol", "timeframe"):
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
        confirming = self.event_type is SwingEventType.SWING_CONFIRMED
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
            if self.swing_time >= self.confirmed_at:
                raise ValueError("a swing cannot be confirmed by its own candle")
            if type(self.confirmation_delay_bars) is not int or self.confirmation_delay_bars < 1:
                raise ValueError("confirmation_delay_bars must be a positive integer")
            for name in ("atr", "threshold"):
                value = getattr(self, name)
                if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                    raise ValueError(f"{name} must be a positive finite Decimal")
        else:
            if self.confirmed_at is not None or self.confirmation_delay_bars is not None:
                raise ValueError("an unconfirmed event cannot carry confirmation fields")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative integer")


@dataclass(frozen=True)
class ConfirmedSwing:
    """The immutable identity of a confirmed swing.

    Equality of this record across replays is the anti-repaint contract: once
    published it must never move, reprice, retime or disappear.
    """

    symbol: str
    timeframe: str
    side: SwingSide
    price: Decimal
    swing_time: datetime
    confirmed_at: datetime
    confirmation_delay_bars: int
    atr: Decimal
    threshold: Decimal

    @classmethod
    def from_event(cls, event: SwingEvent) -> "ConfirmedSwing":
        if event.status is not SwingStatus.CONFIRMED:
            raise ValueError("only a confirmed event has a confirmed identity")
        return cls(event.symbol, event.timeframe, event.side, event.price,
                   event.swing_time, event.confirmed_at,
                   event.confirmation_delay_bars, event.atr, event.threshold)


@dataclass(frozen=True)
class SwingState:
    """Immutable view of what the engine knows at its current knowledge time."""

    symbol: str
    timeframe: str
    bars_processed: int
    warmup_complete: bool
    as_of: datetime | None = None
    atr: Decimal | None = None
    threshold: Decimal | None = None
    candidate_side: SwingSide | None = None
    candidate_price: Decimal | None = None
    candidate_swing_time: datetime | None = None
    pending_high_price: Decimal | None = None
    pending_low_price: Decimal | None = None
    last_confirmed: ConfirmedSwing | None = None
    confirmed_count: int = 0

    @property
    def seeding(self) -> bool:
        """True while no side is established yet and both extremes are provisional.

        Before the first confirmation the engine does not know which side it is
        tracking, so `candidate_side` is None and the two provisional extremes
        are reported separately.
        """
        return self.warmup_complete and self.candidate_side is None


class SwingEngine:
    """Causal swing detection for exactly one symbol and timeframe.

    Live incremental processing and historical replay are the same code path:
    `process` accepts one closed candle and the engine holds no future series,
    so look-ahead is prevented by the interface rather than by discipline.
    """

    def __init__(self, symbol: str, timeframe: str, config: SwingConfig | None = None):
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("swing engine requires a nonempty symbol")
        if not isinstance(timeframe, str) or not timeframe.strip():
            raise ValueError("swing engine requires a nonempty timeframe")
        bar_duration(timeframe)          # reject unsupported/calendar bars early
        if config is not None and not isinstance(config, SwingConfig):
            raise ValueError("config must be a SwingConfig")
        self.symbol = symbol
        self.timeframe = timeframe
        self.config = config or SwingConfig()
        self._index = -1
        self._sequence = 0
        self._last_close_time = None
        self._true_ranges = deque(maxlen=self.config.atr_length)
        self._previous_close = None
        self._side = None
        self._cand = None                # (price, time, index)
        self._anti = None                # opposing extreme strictly after _cand
        self._seed_high = None
        self._seed_high_anti = None
        self._seed_low = None
        self._seed_low_anti = None
        self._confirmed = []

    # ---------------------------------------------------------------- public

    @property
    def confirmed(self) -> tuple[ConfirmedSwing, ...]:
        """Append-only confirmed history. Never rewritten."""
        return tuple(self._confirmed)

    @property
    def warmup_complete(self) -> bool:
        return len(self._true_ranges) >= self.config.atr_length

    @property
    def state(self) -> SwingState:
        candidate = self._cand
        if self._side is None:
            candidate = None
        return SwingState(
            symbol=self.symbol, timeframe=self.timeframe,
            bars_processed=self._index + 1, warmup_complete=self.warmup_complete,
            as_of=self._last_close_time, atr=self._atr(), threshold=self._threshold(),
            candidate_side=self._side,
            candidate_price=candidate[0] if candidate else None,
            candidate_swing_time=candidate[1] if candidate else None,
            pending_high_price=self._seed_high[0] if self._seed_high else None,
            pending_low_price=self._seed_low[0] if self._seed_low else None,
            last_confirmed=self._confirmed[-1] if self._confirmed else None,
            confirmed_count=len(self._confirmed))

    def bootstrap(self, candles) -> tuple[SwingEvent, ...]:
        """Replay a chronological context batch oldest -> newest.

        Identical to feeding the same candles through `process` one at a time;
        it exists so a starting bot has one obvious call. Requires a fresh
        engine so a bootstrap can never be mistaken for a mid-run refill.
        """
        if self._index >= 0:
            raise ValueError("bootstrap requires a fresh engine")
        events = []
        for candle in candles:
            events.extend(self.process(candle))
        return tuple(events)

    def process(self, candle: Candle) -> tuple[SwingEvent, ...]:
        """Reveal exactly one closed candle and return the events it makes knowable."""
        if not isinstance(candle, Candle) or candle.closed is not True:
            raise ValueError("swing detection requires closed Candle instances")
        if candle.symbol != self.symbol or candle.timeframe != self.timeframe:
            raise ValueError("candle does not belong to this swing engine")
        if self._last_close_time is not None and candle.close_time <= self._last_close_time:
            raise ValueError("duplicate or out-of-order candle for this timeframe")
        self._last_close_time = candle.close_time
        self._index += 1
        self._absorb_volatility(candle)
        if not self.warmup_complete:
            # Explicit warmup. Candidate tracking starts only once a threshold
            # exists, otherwise the first candidate would be seeded by wherever
            # the bootstrap window happens to begin and its confirmation delay
            # would measure the warmup rather than the market.
            return ()
        if self._side is None:
            return tuple(self._seed(candle, self._index))
        return tuple(self._track(candle, self._index))

    # --------------------------------------------------------------- internal

    def _absorb_volatility(self, candle):
        """True Range over closed candles only; the threshold stays causal."""
        true_range = candle.high - candle.low
        if self._previous_close is not None:
            true_range = max(true_range, abs(candle.high - self._previous_close),
                             abs(candle.low - self._previous_close))
        self._true_ranges.append(true_range)
        self._previous_close = candle.close

    def _atr(self):
        """Simple mean of True Range [H]; not Wilder smoothing.

        A rolling window is reproducible from the last `atr_length` candles
        alone, so a bootstrapped engine and a streamed engine hold the same
        volatility state with no seeding convention to agree on.
        """
        if len(self._true_ranges) < self.config.atr_length:
            return None
        return sum(self._true_ranges, Decimal(0)) / Decimal(len(self._true_ranges))

    def _threshold(self):
        atr = self._atr()
        return None if atr is None else atr * self.config.atr_multiplier

    def _emit(self, candle, event_type, side, price, swing_time, *, evidence=(),
              confirmed=False, delay=None, atr=None, threshold=None):
        self._sequence += 1
        return SwingEvent(
            symbol=self.symbol, timeframe=self.timeframe, event_type=event_type,
            side=side,
            status=SwingStatus.CONFIRMED if confirmed else SwingStatus.CANDIDATE,
            price=price, swing_time=swing_time, observed_at=candle.close_time,
            confirmed_at=candle.close_time if confirmed else None,
            confirmation_delay_bars=delay if confirmed else None,
            atr=atr, threshold=threshold, evidence=tuple(evidence),
            sequence=self._sequence)

    def _extreme(self, candle, side):
        return candle.high if side is SwingSide.HIGH else candle.low

    def _beyond(self, close, price, side, threshold):
        """Has a later close moved far enough against the candidate extreme?"""
        if side is SwingSide.HIGH:
            return close <= price - threshold
        return close >= price + threshold

    def _improves(self, value, price, side):
        return value > price if side is SwingSide.HIGH else value < price

    def _seed(self, candle, index):
        """Undetermined start: track both extremes until one side confirms."""
        events = []
        if self._seed_high is None:
            self._seed_high = (candle.high, candle.close_time, index)
            self._seed_low = (candle.low, candle.close_time, index)
            self._seed_high_anti = self._seed_low_anti = None
            for side, price in ((SwingSide.HIGH, candle.high), (SwingSide.LOW, candle.low)):
                events.append(self._emit(candle, SwingEventType.CANDIDATE_CREATED, side,
                                         price, candle.close_time,
                                         evidence=("initial_candidate",)))
            return events
        if candle.high > self._seed_high[0]:
            self._seed_high = (candle.high, candle.close_time, index)
            self._seed_high_anti = None
            events.append(self._emit(candle, SwingEventType.CANDIDATE_UPDATED,
                                     SwingSide.HIGH, candle.high, candle.close_time,
                                     evidence=("candidate_extreme_improved",)))
        else:
            self._seed_high_anti = self._better_anti(self._seed_high_anti, candle,
                                                     SwingSide.HIGH, index)
        if candle.low < self._seed_low[0]:
            self._seed_low = (candle.low, candle.close_time, index)
            self._seed_low_anti = None
            events.append(self._emit(candle, SwingEventType.CANDIDATE_UPDATED,
                                     SwingSide.LOW, candle.low, candle.close_time,
                                     evidence=("candidate_extreme_improved",)))
        else:
            self._seed_low_anti = self._better_anti(self._seed_low_anti, candle,
                                                    SwingSide.LOW, index)
        threshold = self._threshold()
        if threshold is None:
            return events
        high_hit = (index > self._seed_high[2]
                    and self._beyond(candle.close, self._seed_high[0], SwingSide.HIGH, threshold))
        low_hit = (index > self._seed_low[2]
                   and self._beyond(candle.close, self._seed_low[0], SwingSide.LOW, threshold))
        if high_hit and low_hit:
            # Deterministic tie-break [H]: the earlier extreme is the one being
            # reversed away from; identical times resolve to HIGH.
            high_hit = self._seed_high[1] <= self._seed_low[1]
            low_hit = not high_hit
        if high_hit:
            self._side, self._cand, self._anti = SwingSide.HIGH, self._seed_high, self._seed_high_anti
        elif low_hit:
            self._side, self._cand, self._anti = SwingSide.LOW, self._seed_low, self._seed_low_anti
        else:
            return events
        events.append(self._confirm(candle, index, threshold))
        return events

    def _better_anti(self, current, candle, side, index):
        """Best opposing extreme seen strictly after the candidate's candle."""
        value = self._extreme(candle, _opposite(side))
        if current is None or self._improves(value, current[0], _opposite(side)):
            return (value, candle.close_time, index)
        return current

    def _track(self, candle, index):
        events = []
        value = self._extreme(candle, self._side)
        if self._improves(value, self._cand[0], self._side):
            self._cand = (value, candle.close_time, index)
            self._anti = None
            events.append(self._emit(candle, SwingEventType.CANDIDATE_UPDATED, self._side,
                                     value, candle.close_time,
                                     evidence=("candidate_extreme_improved",)))
            return events          # a candidate is never confirmed by its own candle
        self._anti = self._better_anti(self._anti, candle, self._side, index)
        threshold = self._threshold()
        if threshold is None:
            return events
        if self._beyond(candle.close, self._cand[0], self._side, threshold):
            events.append(self._confirm(candle, index, threshold))
        return events

    def _confirm(self, candle, index, threshold):
        """Freeze the candidate and open the opposite one."""
        side, (price, swing_time, swing_index) = self._side, self._cand
        event = self._emit(
            candle, SwingEventType.SWING_CONFIRMED, side, price, swing_time,
            confirmed=True, delay=index - swing_index, atr=self._atr(),
            threshold=threshold,
            evidence=("close_beyond_extreme_by_atr_multiple",
                      "atr_length_%d" % self.config.atr_length,
                      "atr_multiplier_%s" % self.config.atr_multiplier))
        self._confirmed.append(ConfirmedSwing.from_event(event))
        self._side = _opposite(side)
        # The opposing extreme was only ever tracked after the confirmed swing's
        # candle, so the next candidate cannot reuse that candle. Reusing it
        # would assume an intrabar order OHLC does not record. Confirmation
        # requires a later candle, so such an extreme always exists.
        if self._anti is None:
            raise ValueError("confirmation without an opposing extreme is impossible")
        self._cand = self._anti
        self._anti = None
        if self._cand[2] < index:
            self._anti = self._better_anti(None, candle, self._side, index)
        self._seed_high = self._seed_low = None
        self._seed_high_anti = self._seed_low_anti = None
        return event
