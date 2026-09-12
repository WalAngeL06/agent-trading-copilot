"""Causal swing detectors. Every rule here is a project hypothesis [H].

None of these is a DD-confirmed swing definition. DD states only that genuine
opposing movement is required and that no fixed 2/3/5-bar pivot rule is approved
(market-structure-v0.1 E-3, M, N-1; DD-18, DD-19). The thresholds below are
research parameters for comparison, not approved trading constants.

Look-ahead is prevented structurally: `process` accepts exactly one candle and
detectors hold no reference to any future series.
"""

from collections import deque
from decimal import Decimal
from typing import Protocol

from ...models import Candle
from .events import SwingEvent, SwingEventType, SwingSide, SwingStatus


class CausalSwingDetector(Protocol):
    name: str
    params: dict

    def process(self, candle: Candle) -> tuple[SwingEvent, ...]: ...


class _BaseDetector:
    """Shared candle validation, bar indexing and event sequencing."""

    name = "base"
    source_ids: tuple[str, ...] = ()

    def __init__(self):
        self._symbol = None
        self._timeframe = None
        self._index = -1
        self._sequence = 0
        self._last_close = None

    @property
    def params(self) -> dict:
        return {}

    def process(self, candle: Candle) -> tuple[SwingEvent, ...]:
        if not isinstance(candle, Candle) or candle.closed is not True:
            raise ValueError("swing detection requires closed Candle instances")
        if self._symbol is None:
            self._symbol, self._timeframe = candle.symbol, candle.timeframe
        elif candle.symbol != self._symbol or candle.timeframe != self._timeframe:
            raise ValueError("detector state is per symbol and timeframe")
        if self._last_close is not None and candle.close_time <= self._last_close:
            raise ValueError("duplicate or out-of-order candle for this timeframe")
        self._last_close = candle.close_time
        self._index += 1
        return tuple(self._on_candle(candle, self._index))

    def _on_candle(self, candle, index):
        return ()

    def _emit(self, candle, event_type, side, price, swing_time, *, evidence=(),
              confirmed=False, delay=None):
        self._sequence += 1
        return SwingEvent(
            symbol=self._symbol, timeframe=self._timeframe, detector=self.name,
            event_type=event_type, side=side,
            status=SwingStatus.CONFIRMED if confirmed else SwingStatus.CANDIDATE,
            price=price, swing_time=swing_time, observed_at=candle.close_time,
            confirmed_at=candle.close_time if confirmed else None,
            confirmation_delay_bars=delay if confirmed else None,
            evidence=tuple(evidence), source_ids=self.source_ids,
            sequence=self._sequence)


class FractalSwingDetector(_BaseDetector):
    """[H] Symmetric n-bar fractal. Benchmark reference only.

    A candle is a swing high when its high strictly exceeds the highs of the
    `width` candles on each side. Confirmation therefore always costs exactly
    `width` bars of delay. Strict comparison means equal highs produce no
    fractal; that tie policy is a hypothesis, not a DD rule.

    Note that this detector does not alternate: it can publish two highs with
    no intervening low, because it classifies each candle independently.
    """

    source_ids = ("[H]-SWING-FRACTAL-001",)

    def __init__(self, width: int = 2):
        super().__init__()
        if type(width) is not int or width < 1:
            raise ValueError("fractal width must be a positive integer")
        self.width = width
        self.name = "fractal_w%d" % width
        self._left = deque(maxlen=width)
        self._pending = []

    @property
    def params(self):
        return {"width": self.width}

    def _on_candle(self, candle, index):
        events = []
        surviving = []
        for item in self._pending:
            side = item["side"]
            price = candle.high if side is SwingSide.HIGH else candle.low
            beaten = price >= item["price"] if side is SwingSide.HIGH else price <= item["price"]
            age = index - item["index"]
            if beaten:
                events.append(self._emit(
                    candle, SwingEventType.CANDIDATE_DISCARDED, side, item["price"],
                    item["time"], evidence=("right_window_breach_at_bar_%d" % age,)))
            elif age >= self.width:
                events.append(self._emit(
                    candle, SwingEventType.SWING_CONFIRMED, side, item["price"],
                    item["time"], confirmed=True, delay=age,
                    evidence=("strict_fractal_width_%d" % self.width,)))
            else:
                surviving.append(item)
        self._pending = surviving
        if len(self._left) == self.width:
            for side in (SwingSide.HIGH, SwingSide.LOW):
                price = candle.high if side is SwingSide.HIGH else candle.low
                if side is SwingSide.HIGH:
                    strict = price > max(c.high for c in self._left)
                else:
                    strict = price < min(c.low for c in self._left)
                if strict:
                    self._pending.append({"side": side, "price": price,
                                          "time": candle.close_time, "index": index})
                    events.append(self._emit(
                        candle, SwingEventType.CANDIDATE_CREATED, side, price,
                        candle.close_time,
                        evidence=("left_window_strict_extreme_%d" % self.width,)))
        self._left.append(candle)
        return events


class _ReversalCore(_BaseDetector):
    """Shared causal candidate-extreme + opposing-reversal machinery.

    Tracks the running extreme since the last confirmation (the candidate) and
    the best opposing extreme reached since that candidate last improved. The
    candidate is confirmed at the first candle whose opposing excursion from it
    reaches the detector's reversal distance.

    Two intrabar rules keep this honest, both following from the fact that an
    OHLC candle records no path between its high and its low
    (market-structure-v0.1 section O, "one candle confirms a swing and appears
    to break it", and N-7; DD-4, DD-18):

    * A swing is never confirmed from its own candle. The opposing excursion
      must come from a strictly later candle, so confirmation delay is >= 1.
    * The next candidate never reuses the confirmed swing's candle. If the only
      opposing extreme available sits on that same candle, the candidate is
      dropped and re-established from the following candle.

    Together these guarantee at most one confirmed swing per candle and
    strictly increasing confirmed swing_time, which is what stops a single bar
    from being republished as an endless alternating sequence of swings.
    """

    uses_wicks = True

    def __init__(self):
        super().__init__()
        self._side = None
        self._cand_price = None
        self._cand_time = None
        self._cand_index = None
        self._opp_price = None
        self._opp_time = None
        self._opp_index = None
        self._seed_low = None
        self._seed_low_time = None
        self._seed_low_index = None
        self._seed_high_opp = None
        self._seed_high_opp_time = None
        self._seed_high_opp_index = None
        self._last_confirmed_time = None

    def _reversal_distance(self, extreme_price, candle):
        """Absolute price distance that counts as genuine opposing movement."""
        raise NotImplementedError

    def _up_down(self, candle):
        if self.uses_wicks:
            return candle.high, candle.low
        return candle.close, candle.close

    def provisional_candidate(self):
        """The current unconfirmed candidate, or None.

        This is genuinely useful to a live consumer, but it is NOT a swing: it
        has met no opposing-movement evidence and it will move whenever a new
        extreme prints. Anything that persists or acts on it is repainting.
        """
        if self._side is None or self._cand_price is None:
            return None
        return {"symbol": self._symbol, "timeframe": self._timeframe,
                "side": self._side, "price": self._cand_price,
                "swing_time": self._cand_time, "status": SwingStatus.CANDIDATE}

    def _on_candle(self, candle, index):
        up, down = self._up_down(candle)
        if self._side is None:
            return self._seed(candle, index, up, down)
        if self._cand_price is None:
            return self._establish(candle, index, up, down)
        events = []
        if self._side is SwingSide.HIGH:
            improving = up > self._cand_price
        else:
            improving = down < self._cand_price
        if improving:
            self._cand_price = up if self._side is SwingSide.HIGH else down
            self._cand_time, self._cand_index = candle.close_time, index
            self._opp_price = down if self._side is SwingSide.HIGH else up
            self._opp_time, self._opp_index = candle.close_time, index
            events.append(self._emit(candle, SwingEventType.CANDIDATE_UPDATED, self._side,
                                     self._cand_price, self._cand_time,
                                     evidence=("candidate_extreme_improved",)))
        else:
            opposing = down if self._side is SwingSide.HIGH else up
            if self._side is SwingSide.HIGH:
                better = opposing < self._opp_price
            else:
                better = opposing > self._opp_price
            if better:
                self._opp_price, self._opp_time = opposing, candle.close_time
                self._opp_index = index
        if index > self._cand_index:
            distance = self._reversal_distance(self._cand_price, candle)
            if distance is not None:
                if self._side is SwingSide.HIGH:
                    excursion = self._cand_price - down
                else:
                    excursion = up - self._cand_price
                if excursion >= distance:
                    events.append(self._flip(candle, index, self._side, self._cand_price,
                                             self._cand_time, self._cand_index,
                                             self._opp_price, self._opp_time,
                                             self._opp_index))
        return events

    def _establish(self, candle, index, up, down):
        """Re-open a candidate after a same-candle refusal. Cannot confirm here."""
        self._cand_price = up if self._side is SwingSide.HIGH else down
        self._cand_time, self._cand_index = candle.close_time, index
        self._opp_price = down if self._side is SwingSide.HIGH else up
        self._opp_time, self._opp_index = candle.close_time, index
        return (self._emit(candle, SwingEventType.CANDIDATE_CREATED, self._side,
                           self._cand_price, self._cand_time,
                           evidence=("candidate_reopened_after_same_candle_refusal",)),)

    def _seed(self, candle, index, up, down):
        """Undetermined start: track both extremes until one side reverses."""
        events = []
        if self._cand_price is None:
            self._cand_price, self._cand_time, self._cand_index = up, candle.close_time, index
            self._opp_price, self._opp_time, self._opp_index = down, candle.close_time, index
            self._seed_low, self._seed_low_time, self._seed_low_index = down, candle.close_time, index
            self._seed_high_opp, self._seed_high_opp_time = up, candle.close_time
            self._seed_high_opp_index = index
            return events
        if up > self._cand_price:
            self._cand_price, self._cand_time, self._cand_index = up, candle.close_time, index
            self._opp_price, self._opp_time, self._opp_index = down, candle.close_time, index
        elif down < self._opp_price:
            self._opp_price, self._opp_time, self._opp_index = down, candle.close_time, index
        if down < self._seed_low:
            self._seed_low, self._seed_low_time, self._seed_low_index = down, candle.close_time, index
            self._seed_high_opp, self._seed_high_opp_time = up, candle.close_time
            self._seed_high_opp_index = index
        elif up > self._seed_high_opp:
            self._seed_high_opp, self._seed_high_opp_time = up, candle.close_time
            self._seed_high_opp_index = index
        high_rev = self._reversal_distance(self._cand_price, candle)
        low_rev = self._reversal_distance(self._seed_low, candle)
        down_hit = (high_rev is not None and index > self._cand_index
                    and self._cand_price - down >= high_rev)
        up_hit = (low_rev is not None and index > self._seed_low_index
                  and up - self._seed_low >= low_rev)
        if down_hit and up_hit:
            # Deterministic tie-break [H]: the earlier extreme is the one being
            # reversed away from; identical times resolve to HIGH.
            down_hit = self._cand_time <= self._seed_low_time
            up_hit = not down_hit
        if down_hit:
            events.append(self._flip(candle, index, SwingSide.HIGH, self._cand_price,
                                     self._cand_time, self._cand_index,
                                     self._opp_price, self._opp_time, self._opp_index))
        elif up_hit:
            events.append(self._flip(candle, index, SwingSide.LOW, self._seed_low,
                                     self._seed_low_time, self._seed_low_index,
                                     self._seed_high_opp, self._seed_high_opp_time,
                                     self._seed_high_opp_index))
        return events

    def _flip(self, candle, index, side, price, swing_time, swing_index,
              next_price, next_time, next_index):
        """Freeze the confirmed swing and open the opposite candidate."""
        if self._last_confirmed_time is not None and swing_time <= self._last_confirmed_time:
            raise ValueError("confirmed swing times must strictly increase")
        event = self._emit(candle, SwingEventType.SWING_CONFIRMED, side, price, swing_time,
                           confirmed=True, delay=index - swing_index,
                           evidence=("opposing_reversal_" + self.name,))
        self._last_confirmed_time = swing_time
        self._side = SwingSide.LOW if side is SwingSide.HIGH else SwingSide.HIGH
        if next_index is not None and next_index > swing_index:
            self._cand_price, self._cand_time, self._cand_index = next_price, next_time, next_index
            up, down = self._up_down(candle)
            self._opp_price = up if side is SwingSide.HIGH else down
            self._opp_time, self._opp_index = candle.close_time, index
        else:
            # The opposing extreme shares the confirmed swing's candle. Using it
            # would assume an intrabar order OHLC does not record, so drop it.
            self._cand_price = self._cand_time = self._cand_index = None
            self._opp_price = self._opp_time = self._opp_index = None
        return event


class ZigZagSwingDetector(_ReversalCore):
    """[H] Percentage reversal on wick extremes.

    Confirms the running wick extreme once price retraces `reversal_pct` of it.
    Unlike a charting ZigZag, a confirmed swing is frozen and never relocated.
    """

    source_ids = ("[H]-SWING-ZIGZAG-001",)
    uses_wicks = True

    def __init__(self, reversal_pct="0.005"):
        super().__init__()
        pct = Decimal(str(reversal_pct))
        if not pct.is_finite() or pct <= 0 or pct >= 1:
            raise ValueError("reversal_pct must be a fraction in (0, 1)")
        self.reversal_pct = pct
        self.name = "zigzag_" + str(pct)

    @property
    def params(self):
        return {"reversal_pct": str(self.reversal_pct)}

    def _reversal_distance(self, extreme_price, candle):
        return extreme_price * self.reversal_pct


class DirectionalChangeDetector(_ReversalCore):
    """[H] Classic Directional Change on the close series only.

    Identical reversal logic to ZigZag but observes one price per candle, so
    intrabar wick excursions cannot trigger or extend a swing. Included to
    separate "wick extreme" semantics from "threshold crossing" semantics.
    """

    source_ids = ("[H]-SWING-DC-001",)
    uses_wicks = False

    def __init__(self, theta="0.005"):
        super().__init__()
        value = Decimal(str(theta))
        if not value.is_finite() or value <= 0 or value >= 1:
            raise ValueError("theta must be a fraction in (0, 1)")
        self.theta = value
        self.name = "dc_" + str(value)

    @property
    def params(self):
        return {"theta": str(self.theta)}

    def _reversal_distance(self, extreme_price, candle):
        return extreme_price * self.theta


class AtrReversalDetector(_ReversalCore):
    """[H] Volatility-adaptive reversal: threshold = multiplier * ATR(period).

    ATR is a simple mean of True Range over closed candles only, so the
    threshold applied at a candle uses volatility knowable at that candle.
    No confirmation is possible before the ATR warmup completes.
    """

    source_ids = ("[H]-SWING-ATR-001",)
    uses_wicks = True

    def __init__(self, period=14, multiplier="1.5"):
        super().__init__()
        if type(period) is not int or period < 1:
            raise ValueError("ATR period must be a positive integer")
        mult = Decimal(str(multiplier))
        if not mult.is_finite() or mult <= 0:
            raise ValueError("ATR multiplier must be positive")
        self.period, self.multiplier = period, mult
        self.name = "atr_p%d_x%s" % (period, mult)
        self._tr = deque(maxlen=period)
        self._prev_close = None

    @property
    def params(self):
        return {"period": self.period, "multiplier": str(self.multiplier)}

    def _on_candle(self, candle, index):
        true_range = candle.high - candle.low
        if self._prev_close is not None:
            true_range = max(true_range, abs(candle.high - self._prev_close),
                             abs(candle.low - self._prev_close))
        self._tr.append(true_range)
        self._prev_close = candle.close
        return super()._on_candle(candle, index)

    def _reversal_distance(self, extreme_price, candle):
        if len(self._tr) < self.period:
            return None
        return (sum(self._tr, Decimal(0)) / Decimal(len(self._tr))) * self.multiplier


_DEFAULT_SPECS = (
    (FractalSwingDetector, {"width": 2}),
    (FractalSwingDetector, {"width": 3}),
    (ZigZagSwingDetector, {"reversal_pct": "0.005"}),
    (ZigZagSwingDetector, {"reversal_pct": "0.015"}),
    (DirectionalChangeDetector, {"theta": "0.005"}),
    (DirectionalChangeDetector, {"theta": "0.015"}),
    (AtrReversalDetector, {"period": 14, "multiplier": "1.5"}),
)


def default_detectors():
    """The comparison set for this R&D target. Parameters are research values."""
    return tuple(cls(**kwargs) for cls, kwargs in _DEFAULT_SPECS)


def default_detector_factories():
    """(name, factory) pairs. Detectors are stateful, so every run needs a new one."""
    return tuple((cls(**kwargs).name, _factory(cls, kwargs))
                 for cls, kwargs in _DEFAULT_SPECS)


def _factory(cls, kwargs):
    return lambda: cls(**kwargs)
