"""[U-DD-DEVIATION-001] DD model 1: the entry-timeframe CHoCH and the gap it leaves."""
import unittest
from dataclasses import replace
from decimal import Decimal as D

from agent_trading.market import bar_duration
from agent_trading.swing import ConfirmedSwing, SwingSide
from agent_trading.trading_brain.models import FVG, ManipulationEvent, SwingHigh, SwingLow
from agent_trading.strategy_v1.choch import ChochConfirmation, ChochTracker
from agent_trading.strategy_v1.entry import FvgBook

from strategy_v1_fixtures import ENTRY_START, SYMBOL, candle, scenario_profile

STEP, HOUR = bar_duration('15m'), bar_duration('1H')
AXIS = D('256')


def at(index):
    return ENTRY_START + index * STEP


def bar(index, open_, high, low, close):
    return candle('15m', at(index), open_, high, low, close)


def swing(side, price, index):
    raw = ConfirmedSwing(SYMBOL, '15m', side, D(str(price)), at(index), at(index + 1), 1,
                         D('1'), D('1'))
    return SwingHigh(raw) if side is SwingSide.HIGH else SwingLow(raw)


def swept(direction, index, extreme, phase='SWEPT'):
    """The range bar that swept closes together with entry bar `index`."""
    return ManipulationEvent(direction, phase, D(str(extreme)), at(index), at(index),
                             at(index + 4) if phase == 'RECLAIMED' else None)


def mirror(c):
    return replace(c, open=AXIS - c.open, high=AXIS - c.low, low=AXIS - c.high,
                   close=AXIS - c.close)


PRE = [bar(1, 127, 129, 126, 127), bar(2, 127, 129, 126, 128),
       bar(3, 128, 128, 125, 126), bar(4, 126, 126, 124, 125)]
IN_SWEEP_BAR = [bar(5, 125, 125, 120, 121), bar(6, 121, 121, 116, 117),
                bar(7, 117, 118, 113, 114)]
EXTREME = bar(8, 114, 115, 112, 113)
RISE = [bar(9, 113, 117, 112, 116), bar(10, 116, 121, 116, 120),
        bar(11, 120, 126, 120, 125)]
BREAK = bar(12, 125, 131, 125, 130)                  # closes above the 129 swing high
LEVEL = swing(SwingSide.HIGH, 129, 2)


def run(tracker, candles, manipulation, highs=(LEVEL,), lows=()):
    found = []
    for item in candles:
        result = tracker.process(item, manipulation, highs, lows, HOUR)
        if result is not None:
            found.append(result)
    return found


def primed():
    """The sweep's range bar is only known once it closes, with bar 8."""
    tracker = ChochTracker(4)
    run(tracker, PRE + IN_SWEEP_BAR, None)
    return tracker


class ChochTrackerTests(unittest.TestCase):
    def test_the_extreme_includes_bars_seen_before_the_sweep_was_known(self):
        tracker = primed()
        run(tracker, [EXTREME, RISE[0]], swept('LONG', 8, 112))
        self.assertEqual((tracker.extreme, tracker.extreme_at), (D('112'), at(8)))

    def test_a_body_close_above_the_last_swing_high_before_the_extreme_confirms(self):
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [BREAK], swept('LONG', 8, 112))
        self.assertEqual(len(found), 1)
        choch = found[0]
        self.assertIsInstance(choch, ChochConfirmation)
        self.assertEqual((choch.direction, choch.level, choch.extreme, choch.extreme_at,
                          choch.confirmed_at), ('LONG', D('129'), D('112'), at(8), at(12)))
        self.assertIs(choch.swing, LEVEL)
        self.assertEqual(choch.candle, BREAK)

    def test_a_wick_through_the_level_is_not_a_change_of_character(self):
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [bar(12, 125, 131, 125, 128.5)],
                    swept('LONG', 8, 112))
        self.assertEqual(found, [])

    def test_the_level_is_the_most_recent_swing_high_before_the_extreme(self):
        highs = (swing(SwingSide.HIGH, 135, 1), swing(SwingSide.HIGH, 129, 2),
                 swing(SwingSide.HIGH, 140, 10))
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [BREAK], swept('LONG', 8, 112), highs)
        self.assertEqual(found[0].level, D('129'))

    def test_no_swing_before_the_extreme_means_no_change_of_character(self):
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [BREAK], swept('LONG', 8, 112),
                    (swing(SwingSide.HIGH, 125, 10),))
        self.assertEqual(found, [])

    def test_a_new_extreme_while_still_swept_restarts_the_watch(self):
        tracker = primed()
        self.assertEqual(len(run(tracker, [EXTREME, bar(9, 113, 131, 113, 130)],
                                 swept('LONG', 8, 112))), 1)
        run(tracker, [bar(10, 130, 130, 108, 109)], swept('LONG', 8, 108))
        self.assertIsNone(tracker.confirmed)
        self.assertEqual((tracker.extreme, tracker.extreme_at), (D('108'), at(10)))

    def test_after_the_reclaim_the_extreme_is_frozen(self):
        tracker = primed()
        run(tracker, [EXTREME], swept('LONG', 8, 112))
        run(tracker, [bar(9, 113, 114, 111, 113)], swept('LONG', 8, 112, 'RECLAIMED'))
        self.assertEqual((tracker.extreme, tracker.extreme_at), (D('112'), at(8)))

    def test_a_lost_or_new_manipulation_resets_the_watch(self):
        tracker = primed()
        run(tracker, [EXTREME] + RISE + [BREAK], swept('LONG', 8, 112))
        run(tracker, [bar(13, 130, 131, 129, 130)], None)
        self.assertIsNone(tracker.confirmed)
        self.assertIsNone(tracker.extreme)
        run(tracker, [bar(14, 130, 131, 110, 111)], swept('LONG', 14, 110))
        self.assertEqual((tracker.extreme, tracker.extreme_at), (D('110'), at(14)))

    def test_a_confirmation_is_reported_once(self):
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [BREAK, bar(13, 130, 133, 129, 132)],
                    swept('LONG', 8, 112))
        self.assertEqual(len(found), 1)

    def test_a_short_mirrors_it(self):
        tracker = ChochTracker(4)
        run(tracker, [mirror(c) for c in PRE + IN_SWEEP_BAR], None, lows=())
        found = run(tracker, [mirror(c) for c in [EXTREME] + RISE + [BREAK]],
                    swept('SHORT', 8, 144), highs=(), lows=(swing(SwingSide.LOW, 127, 2),))
        self.assertEqual((found[0].direction, found[0].level, found[0].extreme),
                         ('SHORT', D('127'), D('144')))


class ChochGapTests(unittest.TestCase):
    def setUp(self):
        self.book = FvgBook(True)
        self.profile = scenario_profile()
        self.choch = ChochConfirmation('LONG', D('129'), LEVEL, D('112'), at(8), BREAK, at(12))

    def gap(self, gap_id, lower, upper, first, direction='LONG', kind='FVG'):
        formed = (at(first), at(first + 1), at(first + 2))
        return self.book.publish(FVG(direction, D(str(lower)), D(str(upper)), formed,
                                     at(first + 2), kind=kind), gap_id)

    def test_the_gap_whose_candles_include_the_break_is_chosen(self):
        self.gap('before', 117, 122, 8)            # published at bar 10
        self.gap('left', 126, 130, 11)             # bars 11..13 include bar 12
        self.gap('later', 131, 133, 12)            # also includes it, published later
        self.assertEqual(self.book.choch_gap('LONG', self.profile, self.choch, at(14)).gap_id,
                         'left')

    def test_a_gap_not_yet_published_is_not_chosen(self):
        self.gap('left', 126, 130, 11)
        self.assertIsNone(self.book.choch_gap('LONG', self.profile, self.choch, at(12)))

    def test_a_touched_gap_gives_way_to_the_next_one(self):
        # A long gap below a trading bar stays fresh; one the bar wicks into
        # is only TOUCHED, so the other containing gap is chosen.
        self.gap('left', 128, 130, 11)
        self.gap('later', 124, 126, 12)
        self.book.process(bar(15, 129.5, 129.5, 128.5, 129))
        self.assertEqual(self.book.choch_gap('LONG', self.profile, self.choch, at(15)).gap_id,
                         'later')

    def test_only_fresh_gaps_of_the_setup_side_and_kind_count(self):
        self.gap('short', 126, 130, 11, direction='SHORT')
        self.gap('inverse', 126, 130, 11, kind='iFVG')
        self.assertIsNone(self.book.choch_gap('LONG', self.profile, self.choch, at(14)))
        allowed = scenario_profile(allow_ifvg_entry=True)
        self.assertEqual(self.book.choch_gap('LONG', allowed, self.choch, at(14)).gap_id,
                         'inverse')


if __name__ == '__main__':
    unittest.main()
