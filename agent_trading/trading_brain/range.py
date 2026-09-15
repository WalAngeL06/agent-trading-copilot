"""Frozen valid pair plus ordered boundary extrema; no swing-count rule [H]."""
from dataclasses import replace
from ..swing import SwingSide
from .models import ValidLow, ValidHigh, SwingLow, SwingHigh, RangeState

class RangeEngine:
    def __init__(self, proximity, allow_reseek=False, allow_retire=False):
        self.proximity = proximity
        self.allow_reseek = allow_reseek
        self.allow_retire = allow_retire
        self.first_low = None
        self.state = None
        self.reseeks = 0

    def process(self, candle, valid=(), swings=()):
        # [U-RANGE-RESEEK-001] With re-seek enabled an invalidated candidate no
        # longer ends the stream: the engine drops it and waits for a fresh Valid
        # pair. A CONFIRMED range still stays terminal. Default off, so existing
        # callers keep the original one-range behaviour untouched.
        if (self.allow_reseek and self.state is not None
                and self.state.phase in ('RANGE_INVALIDATED', 'RANGE_RETIRED')):
            self.state = None
            self.first_low = None
            self.reseeks += 1
        result = []
        for level in valid:
            if self.state is not None:
                break
            if isinstance(level, ValidLow) and self.first_low is None:
                self.first_low = level
            elif (isinstance(level, ValidHigh) and self.first_low is not None
                  and level.confirmed_at > self.first_low.confirmed_at
                  and level.swing.swing_time > self.first_low.swing.swing_time
                  and level.price > self.first_low.price):
                self.state = RangeState(self.first_low, level)
                result.append(self.state)
        # [U-RANGE-RETIRE-001] A confirmed range retires once a closed BODY leaves
        # it by more than the configured boundary tolerance. Wicks never retire it,
        # and the tolerance is what separates a manipulation sweep -- which pokes
        # just past the edge and reclaims -- from price genuinely leaving the band.
        if (self.allow_retire and self.state is not None
                and self.state.phase == 'RANGE_CONFIRMED'
                and candle.close_time > self.state.confirmed_at
                and not (self.state.range_low - self.proximity <= candle.close
                         <= self.state.range_high + self.proximity)):
            side = ('BODY_CLOSE_BELOW_RANGE_LOW' if candle.close < self.state.range_low
                    else 'BODY_CLOSE_ABOVE_RANGE_HIGH')
            self.state = replace(self.state, phase='RANGE_RETIRED',
                                 invalidated_at=candle.close_time,
                                 invalidation_candle=candle,
                                 invalidation_reasons=(side,))
            result.append(self.state)
            return tuple(result)
        if self.state is None or self.state.phase in ('RANGE_CONFIRMED',
                                                     'RANGE_INVALIDATED', 'RANGE_RETIRED'):
            return tuple(result)
        # Check EVERY candidate candle, including the forming/confirming bar.
        # Invalidation wins over a swing newly published on the same close.
        # Keep raw/valid identities and frozen prices; only the range is invalid.
        reasons = []
        if candle.low < self.state.range_low:
            reasons.append('WICK_BELOW_RANGE_LOW')
        if candle.high > self.state.range_high:
            reasons.append('WICK_ABOVE_RANGE_HIGH')
        if reasons:
            self.state = replace(self.state, phase='RANGE_INVALIDATED',
                                 invalidated_at=candle.close_time,
                                 invalidation_candle=candle,
                                 invalidation_reasons=tuple(reasons))
            result.append(self.state)
            return tuple(result)
        for raw in swings:
            if (self.state.phase == 'WAIT_LOW_TOUCH' and raw.side is SwingSide.LOW
                    and raw.swing_time > self.state.high.confirmed_at
                    and self.state.range_low <= raw.price <= min(
                        self.state.range_low + self.proximity, self.state.range_high)):
                self.state = replace(self.state, phase='WAIT_HIGH_TOUCH', low_touch=SwingLow(raw))
                result.append(self.state)
            elif (self.state.phase == 'WAIT_HIGH_TOUCH' and raw.side is SwingSide.HIGH
                  and raw.swing_time > self.state.low_touch.confirmed_at
                  and max(self.state.range_high - self.proximity,
                          self.state.range_low) <= raw.price <= self.state.range_high):
                self.state = replace(self.state, phase='RANGE_CONFIRMED',
                                     high_touch=SwingHigh(raw), confirmed_at=candle.close_time)
                result.append(self.state)
        return tuple(result)
