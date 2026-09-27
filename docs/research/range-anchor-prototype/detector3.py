"""Prototype v3: the owner's touch rules (answers of 2026-09-27).

Impulse and reference are found as in detector.py. Formation changes:
  - The levels are the wick tips of the reference and reaction swings.
  - A touch is a candle whose wick reaches a level, within `eps` of the
    height. A wick that stops short is not a touch.
  - Before confirmation, a wick beyond either level (more than `eps`) ends
    the candidate: that level was drawn wrong.
  - A touch counts once a later candle's wick reaches EQ. Touches of one side
    with no EQ visit between them are one touch.
  - Confirmed at two counted touches per side (the reference and reaction
    swings are the first), at least `min_bars` after the reference.
After confirmation nothing changes: deviations are allowed, and a close
beyond the guide 4.1 limit retires the range.
"""
from dataclasses import dataclass, field
from decimal import Decimal as D

import detector as v1

Params3 = v1.Params


@dataclass
class Side:
    count: int = 0
    state: str = 'await_touch'          # or 'await_eq'
    pending: tuple | None = None        # (close_time, price) of the touch awaiting EQ
    touches: list = field(default_factory=list)


class Detector3(v1.Detector):
    under = D('0.05')    # a wick that stops short of the level by more than this is no touch
    over = D('0.15')     # a wick past the level by more than this breaks the candidate

    def run(self, candles, symbol):
        self.candles = candles
        return super().run(candles, symbol)

    def _step(self, cand, c, i, swings, done):
        p = self.p
        up = cand.direction == 'UP'
        if cand.confirmed_at is not None:
            return super()._step(cand, c, i, swings, done)
        if i - cand.ref_index > p.max_bars:
            return None
        if cand.react_price is None:
            # The impulse is still running: a new extreme ends this reference.
            if (up and c.high > cand.ref_price) or (not up and c.low < cand.ref_price):
                return None
            reaction_side = v1.SwingSide.LOW if up else v1.SwingSide.HIGH
            for s in swings:
                if s.side is reaction_side and s.swing_time > cand.ref_time:
                    if (up and s.price < cand.origin) or (not up and s.price > cand.origin):
                        return None      # a reversal, not a range
                    cand.react_price, cand.react_time = s.price, s.swing_time
                    cand.sides = {'ref': Side(1, 'await_touch', None, [(cand.ref_time, cand.ref_price)]),
                                  'react': Side(0, 'await_eq', (s.swing_time, s.price), [])}
                    # Bars between the reaction swing and its confirmation.
                    k = self.index[s.swing_time]
                    for j in range(k + 1, i):
                        if not self._formation_bar(cand, self.candles[j], up):
                            return None
                    break
            if cand.react_price is None:
                return cand
        if not self._formation_bar(cand, c, up):
            return None
        cand.touches_ref = cand.sides['ref'].touches
        cand.touches_react = cand.sides['react'].touches
        if (cand.sides['ref'].count >= 2 and cand.sides['react'].count >= 2
                and i - cand.ref_index >= p.min_bars):
            cand.confirmed_at, cand.confirmed_index = c.close_time, i
        return cand

    def _formation_bar(self, cand, c, up):
        """Apply one bar to an unconfirmed candidate; False ends it."""
        rh, rl = cand.rh, cand.rl
        under, over = (rh - rl) * self.under, (rh - rl) * self.over
        if c.high > rh + over or c.low < rl - over:
            return False
        high_side, low_side = ('ref', 'react') if up else ('react', 'ref')
        for name, reached, price in ((high_side, c.high >= rh - under, c.high),
                                     (low_side, c.low <= rl + under, c.low)):
            side = cand.sides[name]
            if reached and side.state == 'await_touch':
                side.state, side.pending = 'await_eq', (c.close_time, price)
        eq = (rh + rl) / 2
        if c.low <= eq <= c.high:
            for side in cand.sides.values():
                if side.state == 'await_eq' and side.pending[0] < c.close_time:
                    side.count += 1
                    side.touches.append(side.pending)
                    side.state, side.pending = 'await_touch', None
        return True
