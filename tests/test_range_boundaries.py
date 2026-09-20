"""Guide boundary rules [U-RANGE-GUIDE-001]: sweeps keep a candidate, breakout bodies end it.

Supersedes the wick-breach invalidation of [U-RANGE-BOUNDARIES-001]. The frozen
candidate is 80 .. 120, so EQ is 100 and the deviation limit is 10: bodies may
close down to 70 and up to 130 while the structure survives.
"""
from decimal import Decimal as D
import unittest
from test_trading_brain import bar, raw, pair
from agent_trading.swing import SwingSide
from agent_trading.trading_brain import RangeEngine, ManipulationEngine


def candidate(phase='WAIT_LOW_TOUCH'):
    engine=RangeEngine(D('2'))
    low,high=pair()
    engine.process(bar(4),(low,),())
    engine.process(bar(7),(high,),())
    if phase=='WAIT_HIGH_TOUCH':
        engine.process(bar(9),(),(raw(SwingSide.LOW,'81',8,9),))
    return engine

class FrozenBoundaryTests(unittest.TestCase):
    def test_bodies_beyond_the_deviation_limit_invalidate_in_both_pending_phases(self):
        cases=(
            (bar(10,'100','105','69','69.9'),('BODY_CLOSE_BELOW_DEVIATION_LIMIT',)),
            (bar(10,'100','131','95','130.1'),('BODY_CLOSE_ABOVE_DEVIATION_LIMIT',)),
        )
        for phase in ('WAIT_LOW_TOUCH','WAIT_HIGH_TOUCH'):
            for candle,reasons in cases:
                with self.subTest(phase=phase,reasons=reasons):
                    engine=candidate(phase)
                    previous=engine.state
                    invalidated,=engine.process(candle)
                    self.assertEqual(invalidated.phase,'RANGE_INVALIDATED')
                    self.assertEqual(invalidated.invalidated_at,candle.close_time)
                    self.assertEqual(invalidated.invalidation_candle,candle)
                    self.assertEqual(invalidated.invalidation_reasons,reasons)
                    self.assertEqual((invalidated.low,invalidated.high),(previous.low,previous.high))
                    self.assertIsNone(invalidated.confirmed_at)
                    self.assertEqual(ManipulationEngine().process(candle,invalidated),())

    def test_sweeps_of_either_boundary_keep_the_candidate_alive(self):
        for label,candle in (('wick below',bar(10,'100','105','70.1','100')),
                             ('wick above',bar(10,'100','129.9','95','100')),
                             ('body inside the band',bar(10,'100','131','69','129.9'))):
            with self.subTest(case=label):
                engine=candidate()
                self.assertEqual(engine.process(candle),())
                self.assertEqual(engine.state.phase,'WAIT_LOW_TOUCH')

    def test_breakout_wins_over_a_high_touch_confirmed_on_the_same_bar(self):
        engine=candidate('WAIT_HIGH_TOUCH')
        result=engine.process(bar(11,'100','119','69','69.5'),(),
                              (raw(SwingSide.HIGH,'119',10,11),))
        self.assertEqual([s.phase for s in result],['RANGE_INVALIDATED'])
        self.assertIsNone(engine.state.high_touch)

    def test_forming_bar_is_checked_and_invalidated_candidate_cannot_be_revived(self):
        engine=RangeEngine(D('2'))
        low,high=pair()
        engine.process(bar(4),(low,),())
        result=engine.process(bar(7,'100','105','69','69.5'),(high,),())
        self.assertEqual([s.phase for s in result],['WAIT_LOW_TOUCH','RANGE_INVALIDATED'])
        invalidated=engine.state
        engine.process(bar(9),(),(raw(SwingSide.LOW,'81',8,9),))
        engine.process(bar(11),(),(raw(SwingSide.HIGH,'119',10,11),))
        self.assertEqual(engine.state,invalidated)
        self.assertEqual(engine.process(bar(12),(low,high),()),())

    def test_proximity_accepts_only_inside_boundary_swings(self):
        engine=candidate()
        self.assertEqual(engine.process(bar(9),(),(raw(SwingSide.LOW,'79',8,9),)),())
        self.assertEqual(engine.state.phase,'WAIT_LOW_TOUCH')
        engine.process(bar(11),(),(raw(SwingSide.LOW,'81',10,11),))
        self.assertEqual(engine.process(bar(13),(),(raw(SwingSide.HIGH,'121',12,13),)),())
        self.assertEqual(engine.state.phase,'WAIT_HIGH_TOUCH')
        result=engine.process(bar(15),(),(raw(SwingSide.HIGH,'119',14,15),))
        self.assertEqual(result[0].phase,'RANGE_CONFIRMED')

    def test_large_tolerance_still_cannot_accept_a_swing_outside_the_opposing_boundary(self):
        engine=candidate()
        engine.proximity=D('100')
        self.assertEqual(engine.process(bar(9),(),(raw(SwingSide.LOW,'121',8,9),)),())
        engine.process(bar(11),(),(raw(SwingSide.LOW,'81',10,11),))
        self.assertEqual(engine.process(bar(13),(),(raw(SwingSide.HIGH,'79',12,13),)),())
        self.assertEqual(engine.state.phase,'WAIT_HIGH_TOUCH')

    def test_exact_boundary_wicks_and_zero_tolerance_touches_remain_valid(self):
        engine=candidate()
        engine.proximity=D('0')
        engine.process(bar(9,'100','120','80','100'),(),(raw(SwingSide.LOW,'80',8,9),))
        result=engine.process(bar(11,'100','120','80','100'),(),(raw(SwingSide.HIGH,'120',10,11),))
        self.assertEqual(result[0].phase,'RANGE_CONFIRMED')

    def test_a_sweep_and_reclaim_bar_is_a_manipulation_only_after_confirmation(self):
        for prices,direction in ((('100','105','79','100'),'LONG'),
                                  (('100','121','95','100'),'SHORT')):
            with self.subTest(direction=direction):
                before=candidate('WAIT_HIGH_TOUCH')
                self.assertEqual(before.process(bar(10,*prices)),())
                self.assertEqual(before.state.phase,'WAIT_HIGH_TOUCH')
                self.assertEqual(ManipulationEngine().process(bar(12,*prices),before.state),())
                after=candidate('WAIT_HIGH_TOUCH')
                after.process(bar(11),(),(raw(SwingSide.HIGH,'119',10,11),))
                confirmed=after.state
                self.assertEqual(confirmed.phase,'RANGE_CONFIRMED')
                self.assertEqual(after.process(bar(12,*prices)),())
                self.assertEqual(after.state,confirmed)
                sweep,reclaim=ManipulationEngine().process(bar(12,*prices),after.state)
                self.assertEqual((sweep.phase,reclaim.phase,reclaim.direction),
                                 ('SWEPT','RECLAIMED',direction))

if __name__=='__main__':
    unittest.main()
