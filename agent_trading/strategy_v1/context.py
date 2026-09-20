"""High timeframe context for the guide's direction rules [U-RANGE-GUIDE-002].

`docs/specs/range-trade-learning-guide.md` 4.3: a range deviation found on the
lower timeframe is not a reason to trade on its own; it has to coincide with a
high timeframe zone -- an unfilled FVG or a major support/resistance level.
Guide 4.4: the same movement is only tradable on the correct side of the high
timeframe equilibrium, the midpoint between the current Valid High and Valid
Low. Longs are not taken in premium; shorts are not taken in discount unless
market structure is already broken.

This engine consumes the bias timeframe alone and answers one question:
"does the high timeframe allow this direction here?". It never places, sizes or
prices an order, and it holds no strategy state.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from ..trading_brain.gaps import GapEngine
from ..trading_brain.models import ValidHigh

DIRECTIONS = ('LONG', 'SHORT')
REGIONS = ('PREMIUM', 'DISCOUNT', 'EQUILIBRIUM')
SOURCE_IDS = ('[U-RANGE-GUIDE-002]', '[H]-HTF-CONTEXT-001')


@dataclass(frozen=True)
class HtfZone:
    """One high timeframe price band a deviation may coincide with."""
    kind: str                       # HTF_FVG | HTF_VALID_HIGH | HTF_VALID_LOW
    lower: Decimal
    upper: Decimal
    observed_at: datetime
    timeframe: str | None = None
    source_ids: tuple[str, ...] = SOURCE_IDS


@dataclass(frozen=True)
class HtfVerdict:
    """Auditable answer of the guide's 4.3/4.4 gate for one direction."""
    direction: str
    allowed: bool
    reason: str                     # HTF_CONTEXT_OK | NO_HTF_FRAME | ...
    price: Decimal
    region: str | None = None
    eq: Decimal | None = None
    frame_low: Decimal | None = None
    frame_high: Decimal | None = None
    zones: tuple[HtfZone, ...] = ()
    source_ids: tuple[str, ...] = SOURCE_IDS


class HtfContext:
    def __init__(self, timeframe, tolerance=Decimal('0'), require_zone=True):
        if not isinstance(tolerance, Decimal) or not tolerance.is_finite() or tolerance < 0:
            raise ValueError('tolerance must be a nonnegative finite Decimal')
        self.timeframe = timeframe
        self.tolerance = tolerance
        self.require_zone = require_zone
        self.gaps = GapEngine()
        self.open_gaps = ()
        self.valid_high = self.valid_low = None
        self.as_of = None

    # ------------------------------------------------------------------ input
    def process(self, candle, valid=()):
        """Consume one closed bias-timeframe candle and its new Valid levels."""
        if candle.timeframe != self.timeframe:
            raise ValueError('HTF context consumes its own timeframe only')
        # A gap published earlier stops being a zone once price trades through
        # the far edge of the imbalance: it has been mitigated.
        surviving = [gap for gap in self.open_gaps
                     if gap.observed_at >= candle.close_time or not self._filled(gap, candle)]
        for gap in self.gaps.process(candle):
            if gap.kind == 'FVG':          # an inversion re-labels a gap, never adds one
                surviving.append(gap)
        self.open_gaps = tuple(surviving)
        for level in valid:
            if isinstance(level, ValidHigh):
                self.valid_high = level
            else:
                self.valid_low = level
        self.as_of = candle.close_time

    @staticmethod
    def _filled(gap, candle):
        return (candle.low < gap.lower if gap.direction == 'LONG'
                else candle.high > gap.upper)

    # ----------------------------------------------------------------- frame
    @property
    def frame(self):
        """(low, high, eq) of the current Valid pair, or None while incomplete."""
        high, low = self.valid_high, self.valid_low
        if high is None or low is None or high.price <= low.price:
            return None
        return low.price, high.price, (low.price + high.price) / Decimal(2)

    def region(self, price):
        frame = self.frame
        if frame is None:
            return None
        eq = frame[2]
        return 'PREMIUM' if price > eq else 'DISCOUNT' if price < eq else 'EQUILIBRIUM'

    # ----------------------------------------------------------------- zones
    def zones_touching(self, lower, upper):
        """Every high timeframe zone the closed span [lower, upper] intersects."""
        found = []
        for gap in self.open_gaps:
            if gap.lower <= upper and gap.upper >= lower:
                found.append(HtfZone('HTF_FVG', gap.lower, gap.upper, gap.observed_at,
                                     self.timeframe))
        for level, kind in ((self.valid_high, 'HTF_VALID_HIGH'), (self.valid_low, 'HTF_VALID_LOW')):
            if level is None:
                continue
            band = (level.price - self.tolerance, level.price + self.tolerance)
            if band[0] <= upper and band[1] >= lower:
                found.append(HtfZone(kind, band[0], band[1], level.confirmed_at, self.timeframe))
        return tuple(found)

    # --------------------------------------------------------------- verdict
    def evaluate(self, direction, price, span=None, structure_bearish=False):
        """Guide 4.3 + 4.4 for one direction at `price`, over the swept `span`."""
        if direction not in DIRECTIONS:
            raise ValueError('direction must be LONG or SHORT')
        frame = self.frame
        if frame is None:
            return HtfVerdict(direction, False, 'NO_HTF_FRAME', price)
        low, high, eq = frame
        region = self.region(price)
        reason = None
        if direction == 'LONG' and region == 'PREMIUM':
            reason = 'PREMIUM_BLOCKS_LONG'
        elif direction == 'SHORT' and region == 'DISCOUNT' and not structure_bearish:
            reason = 'DISCOUNT_BLOCKS_SHORT'
        lower, upper = span if span is not None else (price, price)
        zones = self.zones_touching(min(lower, upper), max(lower, upper))
        if reason is None and self.require_zone and not zones:
            reason = 'NO_HTF_ZONE'
        return HtfVerdict(direction, reason is None, reason or 'HTF_CONTEXT_OK', price,
                          region, eq, low, high, zones)
