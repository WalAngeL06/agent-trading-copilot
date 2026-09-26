"""Prototype: guide-anchored range detection (owner feedback 2026-09-26).

Guide 3.1: an impulse precedes the range. Guide 3.2: the first peak of the
move is the reference boundary ("Referans Tavan"), each side needs two
touches, and a touch counts only after price reaches EQ. Owner notes: RH/RL
drawn on the wrong swing, levels violated by closes during formation, and
shapes that are not sideways.

Model, per 1H stream, causal (swings are used when confirmed):
  - Impulse: a confirmed swing extreme E whose move from the opposite extreme
    of the previous `window` bars is at least `impulse_atr` ATRs.
    E is the reference boundary (RH after an up-move, RL after a down-move).
  - Reaction: the first confirmed opposite swing after E is the other
    boundary. A close beyond it (more than `tol` of the height) moves it
    (the reaction goes on), unless the move retraces past the impulse origin.
  - A close beyond the reference boundary kills the candidate: the impulse
    resumed.
  - Touches: a confirmed swing within `band` of a boundary (a wick past it
    counts), validated by a later EQ visit. Reference and reaction swings are
    the first touch of their side. Confirmed at 2 + 2 touches and at least
    `min_bars` after the reference.
  - A confirmed range retires on a close beyond the guide 4.1 deviation limit
    (half of RH - EQ).
"""
from dataclasses import dataclass, field
from decimal import Decimal as D
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent_trading.swing import (SwingConfig, SwingEngine, SwingEventType,  # noqa: E402
                                 SwingSide, ConfirmedSwing)


@dataclass
class Params:
    window: int = 48            # bars looked back for the impulse origin
    impulse_atr: D = D('6')     # impulse size in ATRs
    band: D = D('0.15')         # touch band, share of the height
    tol: D = D('0.10')          # close beyond a level tolerated during formation
    min_bars: int = 24          # reference to confirmation, at least
    max_bars: int = 240         # a candidate unconfirmed after this is dropped
    deviation: D = D('0.5')     # guide 4.1, share of (RH - EQ)
    swing_mult: D = D('1.25')


@dataclass
class Candidate:
    direction: str              # UP: reference is RH; DOWN: reference is RL
    ref_price: D
    ref_time: object
    ref_index: int
    origin: D                   # impulse start price
    react_price: D | None = None
    react_time: object = None
    touches_ref: list = field(default_factory=list)     # counted touches (time, price)
    touches_react: list = field(default_factory=list)
    pending: list = field(default_factory=list)         # (side, time, price) awaiting EQ
    confirmed_at: object = None
    confirmed_index: int | None = None
    ended_at: object = None
    end_reason: str | None = None
    born_at: object = None
    atr: D | None = None              # ATR when the reference was found

    @property
    def rh(self):
        return self.ref_price if self.direction == 'UP' else self.react_price

    @property
    def rl(self):
        return self.react_price if self.direction == 'UP' else self.ref_price


class Detector:
    def __init__(self, params=None):
        self.p = params or Params()

    def run(self, candles, symbol):
        p = self.p
        swing = SwingEngine(symbol, '1H', SwingConfig(atr_multiplier=p.swing_mult))
        highs, lows = [], []
        self.index = {}
        cand, done = None, []
        for i, c in enumerate(candles):
            highs.append(c.high)
            lows.append(c.low)
            self.index[c.close_time] = i
            swings = [ConfirmedSwing.from_event(e) for e in swing.process(c)
                      if e.event_type is SwingEventType.SWING_CONFIRMED]
            atr = swing.state.atr
            if cand is not None:
                cand = self._step(cand, c, i, swings, done)
            if cand is None and atr:
                cand = self._seek(swings, candles, highs, lows, i, atr)
        if cand is not None and cand.confirmed_at is not None:
            done.append(cand)
        return done

    # ------------------------------------------------------------ seeking
    def _seek(self, swings, candles, highs, lows, i, atr):
        p = self.p
        best = None
        for s in swings:
            k = self.index[s.swing_time]
            lo = max(0, k - p.window)
            if s.side is SwingSide.HIGH:
                origin = min(lows[lo:k + 1])
                if s.price == max(highs[lo:k + 1]) and s.price - origin >= p.impulse_atr * atr:
                    best = Candidate('UP', s.price, s.swing_time, k, origin, born_at=candles[i].close_time,
                                     atr=atr)
            else:
                origin = max(highs[lo:k + 1])
                if s.price == min(lows[lo:k + 1]) and origin - s.price >= p.impulse_atr * atr:
                    best = Candidate('DOWN', s.price, s.swing_time, k, origin, born_at=candles[i].close_time,
                                     atr=atr)
        return best

    # ----------------------------------------------------------- tracking
    def _step(self, cand, c, i, swings, done):
        p = self.p
        up = cand.direction == 'UP'
        if cand.confirmed_at is not None:
            height = cand.rh - cand.rl
            limit = height / 2 * p.deviation
            if c.close > cand.rh + limit or c.close < cand.rl - limit:
                cand.ended_at, cand.end_reason = c.close_time, 'UP' if c.close > cand.rh else 'DOWN'
                done.append(cand)
                return None
            return cand
        if i - cand.ref_index > p.max_bars:
            return None
        height = (cand.rh - cand.rl) if cand.react_price is not None else None
        tol = height * p.tol if height else D(0)
        # A close beyond the reference: the impulse resumed.
        if (up and c.close > cand.ref_price + tol) or (not up and c.close < cand.ref_price - tol):
            return None
        # A close beyond the reaction level: the reaction goes on.
        if cand.react_price is not None and (
                (up and c.close < cand.react_price - tol) or (not up and c.close > cand.react_price + tol)):
            beyond_origin = (up and c.close < cand.origin) or (not up and c.close > cand.origin)
            if beyond_origin:
                return None
            cand.react_price = cand.react_time = None
            cand.touches_ref, cand.touches_react, cand.pending = [], [], []
        for s in swings:
            if s.swing_time <= cand.ref_time:
                continue
            reaction_side = SwingSide.LOW if up else SwingSide.HIGH
            if cand.react_price is None:
                if s.side is reaction_side:
                    # A reaction past the impulse origin is a reversal, not a range.
                    if (up and s.price < cand.origin) or (not up and s.price > cand.origin):
                        return None
                    cand.react_price, cand.react_time = s.price, s.swing_time
                    cand.touches_ref = [(cand.ref_time, cand.ref_price)]
                    cand.pending = [('react', s.swing_time, s.price)]
                continue
            if s.swing_time <= cand.react_time:
                continue
            height = cand.rh - cand.rl
            band = height * p.band
            if s.side is SwingSide.HIGH and s.price >= cand.rh - band:
                cand.pending.append(('ref' if up else 'react', s.swing_time, s.price))
            elif s.side is SwingSide.LOW and s.price <= cand.rl + band:
                cand.pending.append(('react' if up else 'ref', s.swing_time, s.price))
        if cand.react_price is None:
            return cand
        eq = (cand.rh + cand.rl) / 2
        if c.low <= eq <= c.high:
            # Guide 3.2: one EQ visit validates at most one touch per side.
            for side in ('ref', 'react'):
                waiting = [x for x in cand.pending if x[0] == side and x[1] < c.close_time]
                if waiting:
                    (cand.touches_ref if side == 'ref' else cand.touches_react).append(waiting[0][1:])
            cand.pending = [x for x in cand.pending if x[1] >= c.close_time]
        if (len(cand.touches_ref) >= 2 and len(cand.touches_react) >= 2
                and i - cand.ref_index >= p.min_bars):
            cand.confirmed_at, cand.confirmed_index = c.close_time, i
        return cand
