"""Raw swings become valid levels only on strict body-close breaks [H]."""
from ..swing import ConfirmedSwing, SwingSide
from .models import SwingHigh, SwingLow, ValidHigh, ValidLow

class StructureEngine:
    def __init__(self, symbol, timeframe):
        self.symbol, self.timeframe = symbol, timeframe
        self.high = self.low = None
        self.pending_high = self.pending_low = None
        self.valid = ()

    def process(self, candle, swings=()):
        swings = tuple(swings)
        for raw in swings:
            if (not isinstance(raw, ConfirmedSwing) or raw.symbol != self.symbol
                    or raw.timeframe != self.timeframe
                    or raw.confirmed_at != candle.close_time
                    or raw.swing_time >= raw.confirmed_at):
                raise ValueError('raw swing must belong to this current knowledge time')
        for raw in swings:
            if raw.side is SwingSide.HIGH:
                self.high = SwingHigh(raw)
                if self.low is not None and self.low.swing_time < raw.swing_time:
                    self.pending_high = (self.high, self.low)
            else:
                self.low = SwingLow(raw)
                if self.high is not None and self.high.swing_time < raw.swing_time:
                    self.pending_low = (self.low, self.high)
        result = []
        if self.pending_low is not None:
            swing, target = self.pending_low
            if candle.close_time > swing.swing_time and candle.close > target.price:
                result.append(ValidLow(swing, target, candle.close_time))
                self.pending_low = None
        if self.pending_high is not None:
            swing, target = self.pending_high
            if candle.close_time > swing.swing_time and candle.close < target.price:
                result.append(ValidHigh(swing, target, candle.close_time))
                self.pending_high = None
        self.valid += tuple(result)
        return tuple(result)
