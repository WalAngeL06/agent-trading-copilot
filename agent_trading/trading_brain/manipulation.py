"""Strict boundary sweeps and body-close reclaims, after range confirmation [H]."""
from dataclasses import replace
from .models import ManipulationEvent

class ManipulationEngine:
    def __init__(self):
        self.active = None

    def process(self, candle, state):
        if (state is None or state.confirmed_at is None
                or candle.close_time <= state.confirmed_at):
            return ()
        down, up = candle.low < state.range_low, candle.high > state.range_high
        if down and up:
            self.active = None
            return (ManipulationEvent(None, 'AMBIGUOUS', None, candle.close_time, candle.close_time),)
        result = []
        if self.active is None or self.active.phase == 'RECLAIMED':
            if not (down or up):
                return ()
            self.active = ManipulationEvent('LONG' if down else 'SHORT', 'SWEPT',
                                            candle.low if down else candle.high,
                                            candle.close_time, candle.close_time)
            result.append(self.active)
        elif ((self.active.direction == 'LONG' and up)
              or (self.active.direction == 'SHORT' and down)):
            self.active = ManipulationEvent('SHORT' if up else 'LONG', 'SWEPT',
                                            candle.high if up else candle.low,
                                            candle.close_time, candle.close_time)
            result.append(self.active)
        else:
            extreme = (min(self.active.extreme, candle.low) if self.active.direction == 'LONG'
                       else max(self.active.extreme, candle.high))
            self.active = replace(self.active, extreme=extreme, observed_at=candle.close_time)
        reclaim = state.range_low < candle.close < state.range_high
        if reclaim:
            self.active = replace(self.active, phase='RECLAIMED', observed_at=candle.close_time,
                                  reclaimed_at=candle.close_time)
            # One-bar sweep/reclaim still emits separate observations.
            result.append(self.active)
        return tuple(result)
