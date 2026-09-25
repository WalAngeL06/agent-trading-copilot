"""[U-RR-TRAIL-001] Guide section 2 step 1 pivots on the entry timeframe [H]-PIVOT-N-001."""
from decimal import Decimal as D
import unittest

from agent_trading.market import bar_duration
from agent_trading.strategy_v1.pivots import Pivot, PivotTracker
from strategy_v1_fixtures import ENTRY_START, candle

STEP = bar_duration('15m')


def run(tracker, rows):
    """`rows` are (high, low); open and close sit on the low so each bar is valid."""
    found = []
    for i, (high, low) in enumerate(rows, 1):
        found.extend(tracker.process(candle('15m', ENTRY_START + i * STEP, low, high, low, low)))
    return found


class PivotTests(unittest.TestCase):
    def test_a_low_below_n_bars_on_each_side_is_confirmed_n_bars_later(self):
        found = run(PivotTracker(2), [(12, 10), (11, 9), (10, 7), (11, 8), (12, 9)])
        self.assertEqual(found, [Pivot('LOW', D('7'), ENTRY_START + 3 * STEP,
                                       ENTRY_START + 5 * STEP, 2)])

    def test_an_equal_neighbour_is_not_a_pivot(self):
        found = run(PivotTracker(2), [(12, 10), (11, 7), (10, 7), (11, 8), (12, 9)])
        self.assertEqual([p for p in found if p.side == 'LOW'], [])

    def test_highs_mirror_lows(self):
        found = run(PivotTracker(1), [(10, 5), (13, 6), (11, 5)])
        self.assertEqual([(p.side, p.price) for p in found], [('HIGH', D('13'))])

    def test_nothing_is_known_before_the_window_fills(self):
        self.assertEqual(run(PivotTracker(3), [(12, 10), (11, 9), (10, 7), (11, 8), (12, 9)]), [])

    def test_n_is_validated(self):
        for bad in (0, 11, 2.0, '3'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                PivotTracker(bad)


if __name__ == '__main__':
    unittest.main()
