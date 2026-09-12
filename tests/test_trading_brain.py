"""Behavior tests: literal expectations catch wick breaks, repaint and unsafe fills."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest

from agent_trading.models import Candle
from agent_trading.swing import ConfirmedSwing, SwingSide
from agent_trading.trading_brain import (
    StructureEngine, RangeEngine, ManipulationEngine, GapEngine,
    BrainConfig, RiskPolicy, PaperBroker, SwingHigh, SwingLow,
    ValidLow, ValidHigh, RangeState, TradeCandidate,
)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)

def bar(i, o='100', h='105', l='95', c='100'):
    return Candle('BTC-USDT', '15m', START + timedelta(minutes=15*i),
                  D(o), D(h), D(l), D(c), D('1'))

def raw(side, price, i, known):
    return ConfirmedSwing('BTC-USDT', '15m', side, D(price),
                          bar(i).close_time, bar(known).close_time, known-i,
                          D('2'), D('2'))

def pair():
    low = ValidLow(SwingLow(raw(SwingSide.LOW, '80', 2, 3)),
                   SwingHigh(raw(SwingSide.HIGH, '100', 0, 1)), bar(4).close_time)
    high = ValidHigh(SwingHigh(raw(SwingSide.HIGH, '120', 5, 6)),
                     low.swing, bar(7).close_time)
    return low, high

def confirmed_range():
    low, high = pair()
    return RangeState(low, high, 'RANGE_CONFIRMED',
                      SwingLow(raw(SwingSide.LOW, '81', 8, 9)),
                      SwingHigh(raw(SwingSide.HIGH, '119', 10, 11)),
                      bar(11).close_time)

class StructureTests(unittest.TestCase):
    def test_wick_and_equal_close_do_not_validate_responsible_low(self):
        engine = StructureEngine('BTC-USDT', '15m')
        engine.process(bar(1), (raw(SwingSide.HIGH, '110', 0, 1),))
        engine.process(bar(3), (raw(SwingSide.LOW, '90', 2, 3),))
        self.assertEqual(engine.process(bar(4, '100', '115', '99', '109')), ())
        self.assertEqual(engine.process(bar(5, '109', '115', '100', '110')), ())
        values = engine.process(bar(6, '110', '115', '108', '111'))
        self.assertEqual(len(values), 1)
        self.assertIsInstance(values[0], ValidLow)
        self.assertEqual(values[0].price, D('90'))
        self.assertEqual(values[0].target.price, D('110'))
        self.assertEqual(values[0].confirmed_at, bar(6).close_time)
        self.assertEqual(engine.process(bar(7, '111', '120', '110', '119')), ())

    def test_high_requires_strict_close_below_previous_low(self):
        engine = StructureEngine('BTC-USDT', '15m')
        engine.process(bar(1), (raw(SwingSide.LOW, '90', 0, 1),))
        engine.process(bar(3), (raw(SwingSide.HIGH, '120', 2, 3),))
        self.assertEqual(engine.process(bar(4, '100', '105', '85', '90')), ())
        value, = engine.process(bar(5, '90', '100', '85', '89'))
        self.assertIsInstance(value, ValidHigh)
        self.assertEqual(value.price, D('120'))

    def test_new_low_replaces_unvalidated_candidate_but_not_its_prior_high_target(self):
        engine = StructureEngine('BTC-USDT','15m')
        engine.process(bar(1),(raw(SwingSide.HIGH,'110',0,1),))
        engine.process(bar(3),(raw(SwingSide.LOW,'90',2,3),))
        engine.process(bar(5),(raw(SwingSide.LOW,'85',4,5),))
        level, = engine.process(bar(6,'110','115','108','111'))
        self.assertEqual((level.price,level.target.price),(D('85'),D('110')))

    def test_future_or_foreign_raw_is_rejected_before_mutation(self):
        engine = StructureEngine('BTC-USDT', '15m')
        with self.assertRaises(ValueError):
            engine.process(bar(1), (raw(SwingSide.LOW, '90', 0, 2),))
        self.assertEqual(engine.process(bar(1)), ())

class RangeTests(unittest.TestCase):
    def test_frozen_pair_ordered_touches_and_unlimited_internal_swings(self):
        engine = RangeEngine(D('2'))
        low, high = pair()
        self.assertEqual(engine.process(bar(4), (low,), ()), ())
        state, = engine.process(bar(7), (high,), ())
        self.assertEqual((state.range_low, state.range_high, state.eq),
                         (D('80'), D('120'), D('100')))
        # Upper touch before lower touch cannot confirm the range.
        self.assertEqual(engine.process(bar(9), (), (raw(SwingSide.HIGH, '120', 8, 9),)), ())
        for i in range(10, 20):
            engine.process(bar(i), (), (raw(SwingSide.LOW if i%2 else SwingSide.HIGH,
                                             '100', i-1, i),))
        state, = engine.process(bar(21), (), (raw(SwingSide.LOW, '81', 20, 21),))
        self.assertEqual(state.phase, 'WAIT_HIGH_TOUCH')
        state, = engine.process(bar(23), (high,), (raw(SwingSide.HIGH, '119', 22, 23),))
        self.assertEqual(state.phase, 'RANGE_CONFIRMED')
        self.assertEqual((state.range_low, state.range_high), (D('80'), D('120')))

    def test_proximity_is_configurable_and_new_valid_pairs_cannot_move_boundaries(self):
        low,high=pair()
        engine=RangeEngine(D('0'))
        engine.process(bar(4),(low,),())
        engine.process(bar(7),(high,),())
        self.assertEqual(engine.process(bar(9),(),(raw(SwingSide.LOW,'81',8,9),)),())
        changed_low=ValidLow(SwingLow(raw(SwingSide.LOW,'95',10,11)),low.target,bar(12).close_time)
        changed_high=ValidHigh(SwingHigh(raw(SwingSide.HIGH,'105',13,14)),changed_low.swing,bar(15).close_time)
        engine.process(bar(15),(changed_low,changed_high),())
        self.assertEqual((engine.state.range_low,engine.state.range_high),(D('80'),D('120')))

    def test_touch_occurring_before_pair_publication_is_not_used(self):
        engine = RangeEngine(D('2'))
        low, high = pair()
        engine.process(bar(4), (low,), ())
        engine.process(bar(7), (high,), ())
        self.assertEqual(engine.process(bar(8), (), (raw(SwingSide.LOW, '80', 6, 8),)), ())

class ManipulationTests(unittest.TestCase):
    def test_long_tracks_wick_extreme_until_strict_reclaim(self):
        engine = ManipulationEngine()
        state = confirmed_range()
        sweep, = engine.process(bar(12, '85', '90', '78', '79'), state)
        self.assertEqual(sweep.phase, 'SWEPT')
        self.assertEqual(engine.process(bar(13, '79', '85', '77', '80'), state), ())
        reclaim, = engine.process(bar(14, '80', '88', '79', '86'), state)
        self.assertEqual((reclaim.direction, reclaim.extreme), ('LONG', D('77')))
        self.assertEqual(reclaim.swept_at, bar(12).close_time)
        self.assertEqual(reclaim.reclaimed_at, bar(14).close_time)

    def test_short_and_same_bar_reclaim_are_symmetric(self):
        sweep, value = ManipulationEngine().process(bar(12, '118', '123', '112', '116'), confirmed_range())
        self.assertEqual(sweep.phase, 'SWEPT')
        self.assertEqual((value.direction, value.phase, value.extreme), ('SHORT', 'RECLAIMED', D('123')))

    def test_opposing_boundary_equal_close_is_not_reclaim_in_either_direction(self):
        for candle in (bar(12,'100','120','78','120'),bar(12,'100','122','80','80')):
            engine=ManipulationEngine()
            result=engine.process(candle,confirmed_range())
            self.assertEqual([e.phase for e in result],['SWEPT'])
            self.assertEqual(engine.active.phase,'SWEPT')
            reclaimed, = engine.process(bar(13,'100','115','85','100'),confirmed_range())
            self.assertEqual(reclaimed.phase,'RECLAIMED')
            self.assertEqual(reclaimed.reclaimed_at,bar(13).close_time)

    def test_sweep_is_ineligible_on_or_before_range_confirmation(self):
        engine=ManipulationEngine()
        state=confirmed_range()
        self.assertEqual(engine.process(bar(11,'80','90','77','85'),state),())
        self.assertIsNone(engine.active)

    def test_dual_boundary_sweep_is_ambiguous_and_cannot_reclaim(self):
        engine = ManipulationEngine()
        value, = engine.process(bar(12, '100', '125', '75', '100'), confirmed_range())
        self.assertEqual(value.phase, 'AMBIGUOUS')
        self.assertIsNone(engine.active)

class GapTests(unittest.TestCase):
    def test_fvg_is_known_only_on_third_closed_candle(self):
        engine = GapEngine()
        self.assertEqual(engine.process(bar(1, '95', '100', '90', '98')), ())
        self.assertEqual(engine.process(bar(2, '98', '110', '97', '108')), ())
        gap, = engine.process(bar(3, '108', '115', '105', '112'))
        self.assertEqual((gap.kind, gap.direction, gap.lower, gap.upper),
                         ('FVG', 'LONG', D('100'), D('105')))
        self.assertEqual(gap.observed_at, bar(3).close_time)

    def test_touching_gap_edges_do_not_create_fvg(self):
        engine=GapEngine()
        engine.process(bar(1,'95','100','90','98'))
        engine.process(bar(2,'98','110','97','108'))
        self.assertEqual(engine.process(bar(3,'108','115','100','112')),())

    def test_ifvg_needs_close_crossing_far_edge_not_wick_or_equality(self):
        engine = GapEngine()
        engine.process(bar(1, '112', '115', '110', '112'))
        engine.process(bar(2, '112', '113', '99', '101'))
        gap, = engine.process(bar(3, '101', '105', '98', '100'))
        self.assertEqual(gap.direction, 'SHORT')
        engine.process(bar(4, '100', '112', '99', '110'))
        results = engine.process(bar(5, '110', '113', '108', '111'))
        inverted = [g for g in results if g.kind == 'iFVG']
        self.assertEqual(len(inverted), 1)
        self.assertEqual((inverted[0].direction, inverted[0].lower, inverted[0].upper),
                         ('LONG', D('105'), D('110')))
        self.assertFalse(any(g.kind == 'iFVG' for g in engine.process(bar(6, '111', '115', '110', '113'))))

class RiskPaperTests(unittest.TestCase):
    def candidate(self, direction='LONG'):
        return TradeCandidate(direction, D('90') if direction=='LONG' else D('110'),
                              D('78') if direction=='LONG' else D('122'), D('100'),
                              bar(3).close_time, ('gap-evidence',))

    def test_risk_sizes_down_and_broker_fills_only_next_open(self):
        config = BrainConfig(equity=D('1000'), risk_fraction=D('.01'), quantity_step=D('.01'))
        risk = RiskPolicy(config)
        self.assertEqual(risk.size(D('90'), D('78'), D('1000')), D('.83'))
        broker = PaperBroker(risk, D('1000'))
        broker.submit(self.candidate())
        self.assertEqual(broker.process(bar(3, '90', '95', '85', '90')), ())
        opened, = broker.process(bar(4, '92', '96', '85', '94'))
        self.assertEqual(opened.kind, 'PAPER_ORDER_OPENED')
        self.assertEqual((broker.trades[0].entry, broker.trades[0].quantity), (D('92'), D('.71')))
        self.assertLessEqual(broker.trades[0].quantity * D('14'), D('10'))

    def test_gap_past_target_cancels_instead_of_impossible_fill(self):
        broker = PaperBroker(RiskPolicy(BrainConfig()), D('1000'))
        broker.submit(self.candidate())
        value, = broker.process(bar(4, '101', '105', '100', '103'))
        self.assertEqual(value.kind, 'PAPER_ORDER_CANCELLED')
        self.assertEqual(broker.trades, ())

    def test_stop_first_if_fill_bar_touches_both_and_updates_equity(self):
        broker = PaperBroker(RiskPolicy(BrainConfig(equity=D('1000'), quantity_step=D('.01'))), D('1000'))
        broker.submit(self.candidate())
        results = broker.process(bar(4, '90', '105', '75', '95'))
        self.assertEqual([x.kind for x in results], ['PAPER_ORDER_OPENED', 'PAPER_ORDER_CLOSED'])
        self.assertEqual(broker.trades[0].exit_price, D('78'))
        self.assertEqual(broker.trades[0].pnl, D('-9.96'))
        self.assertEqual(broker.equity, D('990.04'))

    def test_short_target_exit_and_gap_stop_use_open_price(self):
        broker = PaperBroker(RiskPolicy(BrainConfig(equity=D('1000'), quantity_step=D('.01'))), D('1000'))
        broker.submit(self.candidate('SHORT'))
        broker.process(bar(4, '110', '115', '105', '108'))
        broker.process(bar(5, '125', '127', '120', '123'))
        self.assertEqual(broker.trades[0].exit_price, D('125'))
        self.assertEqual(broker.trades[0].pnl, D('-12.45'))

    def test_invalid_decimal_risk_geometry_and_unaffordable_size_are_rejected(self):
        for kwargs in ({'risk_fraction': D('0')}, {'risk_fraction': .01},
                       {'boundary_proximity': D('-1')}, {'stop_buffer': D('0')},
                       {'quantity_step': D('NaN')}, {'target': 'MADE_UP'}):
            with self.assertRaises(ValueError):
                BrainConfig(**kwargs)
        policy = RiskPolicy(BrainConfig())
        self.assertIsNone(policy.size(D('90'), D('89.999'), D('1000')))
        self.assertIsNone(policy.size(D('90'), D('90'), D('1000')))

if __name__ == '__main__':
    unittest.main()
