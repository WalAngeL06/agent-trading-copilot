"""Frozen valid pair plus ordered boundary extrema; no swing-count rule [H]."""
from dataclasses import replace
from ..swing import SwingSide
from .models import ValidLow, ValidHigh, SwingLow, SwingHigh, RangeState

class RangeEngine:
    def __init__(self, proximity):
        self.proximity = proximity
        self.first_low = None
        self.state = None

    def process(self, candle, valid=(), swings=()):
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
        if self.state is None or self.state.phase == 'RANGE_CONFIRMED':
            return tuple(result)
        for raw in swings:
            if (self.state.phase == 'WAIT_LOW_TOUCH' and raw.side is SwingSide.LOW
                    and raw.swing_time > self.state.high.confirmed_at
                    and abs(raw.price - self.state.range_low) <= self.proximity):
                self.state = replace(self.state, phase='WAIT_HIGH_TOUCH', low_touch=SwingLow(raw))
                result.append(self.state)
            elif (self.state.phase == 'WAIT_HIGH_TOUCH' and raw.side is SwingSide.HIGH
                  and raw.swing_time > self.state.low_touch.confirmed_at
                  and abs(raw.price - self.state.range_high) <= self.proximity):
                self.state = replace(self.state, phase='RANGE_CONFIRMED',
                                     high_touch=SwingHigh(raw), confirmed_at=candle.close_time)
                result.append(self.state)
        return tuple(result)
