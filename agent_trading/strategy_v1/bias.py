"""Bias timeframe structure. Breaks are body-close only and known immediately."""
from ..swing import SwingEngine, SwingEventType, SwingSide, ConfirmedSwing
from ..trading_brain.models import SwingHigh, SwingLow, ValidHigh, ValidLow
from ..trading_brain.structure import StructureEngine
from .models import BiasBreak, BiasSnapshot


class BiasEngine:
    """Tracks Valid High/Low history on the bias timeframe and derives bias.

    A break is recognised on the closing candle that breaks the level; no future
    Valid level has to confirm first. Wicks never break structure.
    """

    def __init__(self, symbol, timeframe, swing_config=None):
        self.symbol, self.timeframe = symbol, timeframe
        self.swing = SwingEngine(symbol, timeframe, swing_config)
        self.structure = StructureEngine(symbol, timeframe)
        self.state = 'NEUTRAL'
        self.current_valid_high = self.current_valid_low = None
        self.past_valid_high = self.past_valid_low = None
        # Unbroken levels are the only ones a break may consume.
        self._unbroken_high = self._unbroken_low = None
        self._level_ids = {}
        self.last_break = None
        self.breaks = ()

    def register_level_id(self, level, event_id):
        self._level_ids[id(level)] = event_id

    def process(self, candle):
        """Returns (raw_swings, valid_levels, breaks) for this closed candle."""
        raw_swings = []
        for event in self.swing.process(candle):
            if event.event_type is SwingEventType.SWING_CONFIRMED:
                raw_swings.append(ConfirmedSwing.from_event(event))
        valid = self.structure.process(candle, raw_swings)
        for level in valid:
            if isinstance(level, ValidHigh):
                self.past_valid_high = self.current_valid_high
                self.current_valid_high = level
                self._unbroken_high = level
            else:
                self.past_valid_low = self.current_valid_low
                self.current_valid_low = level
                self._unbroken_low = level
        breaks = tuple(self._detect(candle))
        return tuple(raw_swings), tuple(valid), breaks

    def _detect(self, candle):
        # A single closed candle may only resolve one side; bullish is evaluated
        # first because Strategy V1 only ever acts on bullish permission.
        high = self._unbroken_high
        if high is not None and candle.close_time > high.confirmed_at and candle.close > high.price:
            previous, new = self.state, ('BULLISH_REVERSAL' if self.state == 'LONG_DISABLED'
                                         else 'BULLISH_CONTINUATION')
            self._unbroken_high = None
            self.state = new
            event = BiasBreak('BULLISH', previous, new, self._level_ids.get(id(high)),
                              high.price, candle, candle.close, candle.close_time)
            self.last_break = event
            self.breaks += (event,)
            yield event
            return
        low = self._unbroken_low
        if low is not None and candle.close_time > low.confirmed_at and candle.close < low.price:
            previous = self.state
            self._unbroken_low = None
            self.state = 'LONG_DISABLED'
            # Bearish structure only removes long permission. It never creates a
            # SHORT setup, candidate, plan or PAPER order anywhere in Strategy V1.
            event = BiasBreak('BEARISH', previous, 'LONG_DISABLED', self._level_ids.get(id(low)),
                              low.price, candle, candle.close, candle.close_time)
            self.last_break = event
            self.breaks += (event,)
            yield event

    @property
    def unbroken_valid_high(self):
        """The Valid High a bullish body close would consume next."""
        return self._unbroken_high

    @property
    def unbroken_valid_low(self):
        return self._unbroken_low

    @property
    def long_permission(self):
        return self.state in ('BULLISH_CONTINUATION', 'BULLISH_REVERSAL')

    def snapshot(self):
        return BiasSnapshot(self.state, self.long_permission, self.current_valid_high,
                            self.current_valid_low, self.past_valid_high,
                            self.past_valid_low, self.last_break)
