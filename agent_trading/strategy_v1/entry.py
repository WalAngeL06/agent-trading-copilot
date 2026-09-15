"""Entry-timeframe gap lifecycle and configurable FVG entry pricing."""
from dataclasses import replace
from decimal import Decimal

from ..trading_brain.risk import exact_difference, exact_product
from .models import TrackedFvg


def entry_price(gap, level, ratio):
    """LOW/EQ/HIGH pricing. EQ is `lower + (upper - lower) * ratio`, exact.

    The 0.5 midpoint lives in configuration, never in this expression.
    """
    if level == 'FVG_LOW':
        return gap.lower
    if level == 'FVG_HIGH':
        return gap.upper
    if level != 'FVG_EQ':
        raise ValueError('unknown entry level')
    span = exact_difference(gap.upper, gap.lower)
    return exact_difference(gap.lower, exact_product(span, ratio).copy_negate())


class FvgBook:
    """Causal gap states on the entry timeframe.

    Freshness reuses the shipped supporting-zone rule ([H]-RISK-ZONE-001): a
    later candle whose wick intersects the gap removes freshness, and a close
    past the protective edge invalidates it. The only addition here is that the
    two outcomes are named separately (TOUCHED vs INVALIDATED) instead of being
    collapsed into one boolean. Tagged [H]-SV1-FRESH-001.
    """

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.tracked = ()

    def publish(self, gap, gap_id):
        entry = TrackedFvg(gap_id, gap)
        self.tracked += (entry,)
        return entry

    def process(self, candle):
        """Age every gap published strictly before this candle."""
        if not self.enabled:
            return
        updated = []
        for item in self.tracked:
            if item.state == 'INVALIDATED' or candle.close_time <= item.observed_at:
                updated.append(item)
                continue
            invalidated = (candle.low < item.lower if item.direction == 'LONG'
                           else candle.high > item.upper)
            if invalidated:
                updated.append(replace(item, state='INVALIDATED',
                                       invalidated_at=candle.close_time,
                                       touched_at=item.touched_at or candle.close_time))
            elif item.state == 'FRESH' and candle.low <= item.upper and candle.high >= item.lower:
                updated.append(replace(item, state='TOUCHED', touched_at=candle.close_time))
            else:
                updated.append(item)
        self.tracked = tuple(updated)

    def current(self, gap_id):
        for item in self.tracked:
            if item.gap_id == gap_id:
                return item
        return None

    def _kinds(self, profile):
        return ('FVG', 'iFVG') if profile.allow_ifvg_entry else ('FVG',)

    def eligible_long(self, profile, manipulation, now):
        """Fresh bullish gaps belonging to the current post-sweep setup only."""
        kinds = self._kinds(profile)
        result = []
        for item in self.tracked:
            if (item.direction != 'LONG' or item.gap.kind not in kinds
                    or item.observed_at > now):
                continue
            if profile.fvg_freshness_enabled and not item.fresh:
                continue
            # Belongs to this setup: published after the reclaim and built from
            # candles at or after the sweep that created the setup.
            if item.observed_at <= manipulation.reclaimed_at:
                continue
            if item.formed_at < manipulation.swept_at:
                continue
            result.append(item)
        return tuple(result)

    def secondary_below(self, profile, primary, manipulation, now):
        """Closest eligible fresh bullish gap strictly below PRIMARY_FVG."""
        if not profile.secondary_fvg_support_enabled:
            return None
        kinds = self._kinds(profile)
        candidates = []
        for item in self.tracked:
            if (item.direction != 'LONG' or item.gap.kind not in kinds
                    or item.gap_id == primary.gap_id or item.observed_at > now):
                continue
            if profile.fvg_freshness_enabled and not item.fresh:
                continue
            if item.upper >= primary.lower:
                continue
            if item.formed_at < manipulation.swept_at:
                continue
            candidates.append(item)
        if not candidates:
            return None
        # Closest below primary, then newest, then stable id order.
        candidates.sort(key=lambda z: z.gap_id)
        candidates.sort(key=lambda z: z.observed_at, reverse=True)
        candidates.sort(key=lambda z: z.upper, reverse=True)
        return candidates[0]


def protecting_swing_low(swing_lows, level, now):
    """Most recent confirmed swing low at or below `level`, known by `now`."""
    eligible = [s for s in swing_lows
                if s.confirmed_at <= now and s.price <= level]
    if not eligible:
        return None
    eligible.sort(key=lambda s: s.price)
    eligible.sort(key=lambda s: s.swing_time, reverse=True)
    return eligible[0]
