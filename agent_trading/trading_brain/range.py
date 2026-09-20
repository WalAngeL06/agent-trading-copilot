"""Frozen valid pair with guide range rules [U-RANGE-GUIDE-001].

`docs/specs/range-trade-learning-guide.md` 4.1/4.2: a wick beyond a boundary is
a liquidity sweep, never invalidation. Only a body closing past the boundary by
more than the deviation tolerance -- a share of the half-range -- ends the
structure, because that is a breakout rather than a trap. Guide 3.2: a boundary
touch counts only once price has returned to EQ afterwards.

This supersedes [U-RANGE-BOUNDARIES-001], whose wick-breach invalidation
removed 112 of 117 candidates in the 2026-09-20 one-year BTC measurement
(docs/specs/range-model-gap-2026-09-20.md).
"""
from dataclasses import replace
from decimal import Decimal
from ..swing import SwingSide
from .models import ValidLow, ValidHigh, SwingLow, SwingHigh, RangeState

class RangeEngine:
    def __init__(self, proximity, allow_reseek=False, allow_retire=False,
                 deviation_ratio=Decimal('0.5'), require_eq_visit=True):
        if (not isinstance(deviation_ratio, Decimal) or not deviation_ratio.is_finite()
                or deviation_ratio < 0):
            raise ValueError('deviation_ratio must be a nonnegative finite Decimal')
        self.proximity = proximity
        self.allow_reseek = allow_reseek
        self.allow_retire = allow_retire
        self.deviation_ratio = deviation_ratio
        self.require_eq_visit = require_eq_visit
        self.first_low = None
        self.state = None
        self.reseeks = 0
        self.pending_touch = None
        self.last_eq_visit = None

    def breakout_reason(self, candle, state):
        """Guide 4.1: tolerated overshoot is `deviation_ratio` of (RH - EQ)."""
        limit = (state.range_high - state.eq) * self.deviation_ratio
        if candle.close < state.range_low - limit:
            return 'BODY_CLOSE_BELOW_DEVIATION_LIMIT'
        if candle.close > state.range_high + limit:
            return 'BODY_CLOSE_ABOVE_DEVIATION_LIMIT'
        return None

    def _register_touch(self, raw):
        """A boundary swing becomes a pending touch; EQ decides whether it counts."""
        state = self.state
        if (state.phase == 'WAIT_LOW_TOUCH' and raw.side is SwingSide.LOW
                and raw.swing_time > state.high.confirmed_at
                and state.range_low <= raw.price <= min(state.range_low + self.proximity,
                                                        state.range_high)):
            self.pending_touch = raw
            return True
        if (state.phase == 'WAIT_HIGH_TOUCH' and raw.side is SwingSide.HIGH
                and raw.swing_time > state.low_touch.confirmed_at
                and max(state.range_high - self.proximity,
                        state.range_low) <= raw.price <= state.range_high):
            self.pending_touch = raw
            return True
        return False

    def _eq_seen_after(self, raw):
        """Guide 3.2 counts the EQ visit that follows the touch itself."""
        return self.last_eq_visit is not None and self.last_eq_visit > raw.swing_time

    def _count_touch(self, candle):
        raw, self.pending_touch = self.pending_touch, None
        if self.state.phase == 'WAIT_LOW_TOUCH':
            self.state = replace(self.state, phase='WAIT_HIGH_TOUCH', low_touch=SwingLow(raw))
        else:
            self.state = replace(self.state, phase='RANGE_CONFIRMED', high_touch=SwingHigh(raw),
                                 confirmed_at=candle.close_time)
        return self.state

    def process(self, candle, valid=(), swings=()):
        # [U-RANGE-RESEEK-001] With re-seek enabled an invalidated candidate no
        # longer ends the stream: the engine drops it and waits for a fresh Valid
        # pair. A CONFIRMED range still stays terminal. Default off, so existing
        # callers keep the original one-range behaviour untouched.
        if (self.allow_reseek and self.state is not None
                and self.state.phase in ('RANGE_INVALIDATED', 'RANGE_RETIRED')):
            self.state = None
            self.first_low = None
            self.pending_touch = None
            self.last_eq_visit = None
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
                self.last_eq_visit = None
                result.append(self.state)
        # [U-RANGE-RETIRE-001] A confirmed range retires on a breakout body, the
        # same rule that invalidates a candidate. Sweeps keep it alive.
        if (self.allow_retire and self.state is not None
                and self.state.phase == 'RANGE_CONFIRMED'
                and candle.close_time > self.state.confirmed_at):
            reason = self.breakout_reason(candle, self.state)
            if reason is not None:
                self.state = replace(self.state, phase='RANGE_RETIRED',
                                     invalidated_at=candle.close_time,
                                     invalidation_candle=candle,
                                     invalidation_reasons=(reason,))
                result.append(self.state)
                return tuple(result)
        if self.state is None or self.state.phase in ('RANGE_CONFIRMED',
                                                     'RANGE_INVALIDATED', 'RANGE_RETIRED'):
            return tuple(result)
        # Check EVERY candidate candle, including the forming/confirming bar.
        # Keep raw/valid identities and frozen prices; only the range is invalid.
        reason = self.breakout_reason(candle, self.state)
        if reason is not None:
            self.pending_touch = None
            self.state = replace(self.state, phase='RANGE_INVALIDATED',
                                 invalidated_at=candle.close_time,
                                 invalidation_candle=candle,
                                 invalidation_reasons=(reason,))
            result.append(self.state)
            return tuple(result)
        # Guide 3.2: the EQ visit that follows a touch is what validates it.
        if candle.low <= self.state.eq <= candle.high:
            self.last_eq_visit = candle.close_time
        if self.pending_touch is not None and self._eq_seen_after(self.pending_touch):
            result.append(self._count_touch(candle))
        for raw in swings:
            if self._register_touch(raw) and (not self.require_eq_visit
                                              or self._eq_seen_after(raw)):
                result.append(self._count_touch(candle))
        return tuple(result)
