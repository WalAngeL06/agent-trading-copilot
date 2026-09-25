"""Internal-structure pivots on the entry timeframe [U-RR-TRAIL-001].

Guide section 2 step 1 (docs/specs/range-trade-learning-guide.md): a pivot low
is a bar whose low is strictly below the lows of the N bars before it and the
N bars after it; a pivot high mirrors it. A pivot is only knowable once bar
i+N has closed, so it is confirmed then and never earlier. No ATR or R
multiplier is involved. [H]-PIVOT-N-001 N is configuration.
"""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

SOURCE_IDS = ('[U-RR-TRAIL-001]', '[H]-PIVOT-N-001')


@dataclass(frozen=True)
class Pivot:
    side: str                   # LOW | HIGH
    price: Decimal
    swing_time: datetime        # close time of the pivot bar
    confirmed_at: datetime      # close time of bar i+N
    bars: int
    source_ids: tuple[str, ...] = SOURCE_IDS


class PivotTracker:
    def __init__(self, bars):
        if type(bars) is not int or not 1 <= bars <= 10:
            raise ValueError('pivot bars must be an integer between 1 and 10')
        self.bars = bars
        self.window = deque(maxlen=2 * bars + 1)

    def process(self, candle):
        """Consume one closed candle; return the pivots it confirms."""
        self.window.append(candle)
        if len(self.window) < self.window.maxlen:
            return ()
        middle = self.window[self.bars]
        others = [bar for index, bar in enumerate(self.window) if index != self.bars]
        found = []
        if all(middle.low < bar.low for bar in others):
            found.append(Pivot('LOW', middle.low, middle.close_time, candle.close_time, self.bars))
        if all(middle.high > bar.high for bar in others):
            found.append(Pivot('HIGH', middle.high, middle.close_time, candle.close_time,
                               self.bars))
        return tuple(found)
