"""DD deviation model 1: the entry-timeframe change of character [U-DD-DEVIATION-001].

After a range deviation the DD school waits for the entry timeframe to break,
with a body close, the last internal swing that carried price to the deviation
extreme. This module only watches for that break; it holds no order, price or
size logic.

[H]-DD-EXTREME-001 The extreme is the most extreme entry candle since the range
bar that swept (earliest on ties), followed until the sweep is reclaimed.
[H]-DD-CHOCH-001 The level is the most recent entry swing on the other side
that formed before that candle.
"""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..models import Candle
from ..trading_brain.models import SwingHigh, SwingLow

SOURCE_IDS = ('[U-DD-DEVIATION-001]', '[H]-DD-CHOCH-001')


@dataclass(frozen=True)
class ChochConfirmation:
    """Auditable evidence that the entry timeframe changed character."""
    direction: str
    level: Decimal
    swing: SwingHigh | SwingLow
    extreme: Decimal
    extreme_at: datetime
    candle: Candle
    confirmed_at: datetime
    source_ids: tuple[str, ...] = SOURCE_IDS


class ChochTracker:
    def __init__(self, window):
        if type(window) is not int or window < 1:
            raise ValueError('window must be a positive number of entry bars')
        self.recent = deque(maxlen=window)
        self._reset()

    def _reset(self):
        self.swept_at = self.direction = None
        self.extreme = self.extreme_at = None
        self.confirmed = None

    def _track(self, candle):
        """Follow the extreme; ties keep the earliest candle."""
        long_ = self.direction == 'LONG'
        price = candle.low if long_ else candle.high
        if self.extreme is None or (price < self.extreme if long_ else price > self.extreme):
            self.extreme, self.extreme_at = price, candle.close_time
            self.confirmed = None            # a new extreme needs a new break

    def process(self, candle, manipulation, swing_highs, swing_lows, range_bar):
        """Consume one closed entry candle; return a new confirmation or None."""
        if manipulation is None or manipulation.direction is None:
            self._reset()
            self.recent.append(candle)
            return None
        if (manipulation.swept_at != self.swept_at
                or manipulation.direction != self.direction):
            self._reset()
            self.swept_at, self.direction = manipulation.swept_at, manipulation.direction
            opened = manipulation.swept_at - range_bar
            for earlier in self.recent:
                if earlier.close_time > opened:
                    self._track(earlier)
        self.recent.append(candle)
        if (manipulation.phase == 'SWEPT'
                and candle.close_time > manipulation.swept_at - range_bar):
            self._track(candle)
        if (self.confirmed is not None or self.extreme_at is None
                or candle.close_time <= self.extreme_at):
            return None
        long_ = self.direction == 'LONG'
        level = None
        # Swings arrive in confirmation order, which is chronological.
        for swing in reversed(swing_highs if long_ else swing_lows):
            if swing.swing_time < self.extreme_at and swing.confirmed_at <= candle.close_time:
                level = swing
                break
        if level is None:
            return None
        if not (candle.close > level.price if long_ else candle.close < level.price):
            return None
        self.confirmed = ChochConfirmation(self.direction, level.price, level, self.extreme,
                                           self.extreme_at, candle, candle.close_time)
        return self.confirmed
