"""Three-candle wick gaps and one-time far-edge body-close inversions [H]."""
from collections import deque
from dataclasses import replace
from .models import FVG

class GapEngine:
    def __init__(self):
        self.bars = deque(maxlen=3)
        self.gaps = []
        self.inverted = set()

    def process(self, candle):
        result = []
        previous = self.bars[-1] if self.bars else None
        if previous is not None:
            for index, gap in enumerate(self.gaps):
                if index in self.inverted:
                    continue
                crossing = (previous.close <= gap.upper and candle.close > gap.upper
                            if gap.direction == 'SHORT' else
                            previous.close >= gap.lower and candle.close < gap.lower)
                if crossing:
                    result.append(replace(gap, kind='iFVG',
                                          direction='LONG' if gap.direction == 'SHORT' else 'SHORT',
                                          observed_at=candle.close_time, origin_at=gap.observed_at))
                    self.inverted.add(index)
        self.bars.append(candle)
        if len(self.bars) == 3:
            first, middle, last = self.bars
            gap = None
            times = (first.close_time, middle.close_time, last.close_time)
            if first.high < last.low:
                gap = FVG('LONG', first.high, last.low, times, last.close_time)
            elif first.low > last.high:
                gap = FVG('SHORT', last.high, first.low, times, last.close_time)
            if gap is not None:
                self.gaps.append(gap)
                result.append(gap)
        return tuple(result)
