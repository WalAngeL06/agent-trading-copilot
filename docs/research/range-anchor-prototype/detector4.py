"""Prototype v4: v3 plus the round-3 finding. Before confirmation no candle may
close outside [RL, RH]; wicks may pass by up to `over` (owner labels 2026-09-27)."""
import detector3 as d3


class Detector4(d3.Detector3):
    def _formation_bar(self, cand, c, up):
        if c.close > cand.rh or c.close < cand.rl:
            return False
        return super()._formation_bar(cand, c, up)
