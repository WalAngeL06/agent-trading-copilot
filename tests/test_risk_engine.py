"""Literal risk expectations catch wrong sides, unsupported stops and unsafe fills."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
from pathlib import Path
from fractions import Fraction
import unittest

from agent_trading.models import Candle, to_jsonable
from agent_trading.data import read_candles
from agent_trading.trading_brain import (
    RiskEngine, RiskConfig, SupportingZone, SupportingZoneBook,
    PaperBroker, TradeCandidate, BrainConfig, replay, TradingBrain, FVG,
)
from agent_trading.swing import SwingConfig

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def bar(i, o='100', h='105', l='95', c='100'):
    return Candle('BTC-USDT', '15m', START + timedelta(minutes=15*i),
                  D(o), D(h), D(l), D(c), D('1'))


def candidate(direction='LONG', **changes):
    value = TradeCandidate(direction, D('100'),
                           D('90') if direction == 'LONG' else D('110'),
                           D('120') if direction == 'LONG' else D('80'),
                           bar(3).close_time, ('signal',),
                           sweep_extreme=D('91') if direction == 'LONG' else D('109'))
    return replace(value, **changes)


def zone(direction='LONG', **changes):
    value = SupportingZone('z1', 'FVG', direction,
                           D('90') if direction == 'LONG' else D('105'),
                           D('95') if direction == 'LONG' else D('110'),
                           D('90') if direction == 'LONG' else D('110'),
                           bar(2).close_time, 'BTC-USDT', '15m')
    return replace(value, **changes)


def engine(**changes):
    return RiskEngine(RiskConfig(stop_buffer=D('1'), quantity_step=D('.01'), **changes))


def approve(risk, value=None, zones=()):
    return risk.evaluate(value or candidate(), D('1000'), zones,
                         symbol='BTC-USDT', timeframe='15m')


class RiskApprovalTests(unittest.TestCase):
    def test_tiny_buffer_remains_strictly_beyond_structure_invalidation(self):
        for direction, stop in (('LONG', '89.999999999999999999999999999999'),
                                ('SHORT', '110.000000000000000000000000000001')):
            result = approve(RiskEngine(RiskConfig(stop_buffer=D('1E-30'), quantity_step=D('.01'))),
                             candidate(direction), (zone(direction),))
            self.assertEqual(result.status, 'APPROVED')
            self.assertEqual(result.plan.stop, D(stop))

    def test_quantity_floor_cannot_round_risk_above_budget_at_precision_boundary(self):
        risk = RiskEngine(RiskConfig(profile='FIXED_SL_TP', quantity_step=D('1')))
        for direction, stop in (('LONG', '98.99999999999999999999999999999'),
                                ('SHORT', '101.00000000000000000000000000001')):
            result = approve(risk, candidate(direction, stop=D(stop)))
            self.assertEqual((result.status, result.plan.quantity), ('APPROVED', D('9')))
            self.assertEqual(result.evidence.risk_distance, D('1.00000000000000000000000000001'))
            exact_risk = Fraction(result.plan.quantity) * abs(Fraction(result.plan.entry) - Fraction(result.plan.stop))
            self.assertLessEqual(exact_risk, Fraction(result.plan.risk_budget))

    def test_structure_long_stop_protects_zone_and_retains_complete_evidence(self):
        result = approve(engine(), zones=(zone(),))
        self.assertEqual(result.status, 'APPROVED')
        self.assertIsNone(result.reason)
        plan = result.plan
        self.assertEqual((plan.entry, plan.stop, plan.tp, plan.quantity),
                         (D('100'), D('89'), D('120'), D('.90')))
        self.assertEqual((plan.risk_budget, plan.risk_amount), (D('10'), D('9.90')))
        evidence = result.evidence
        self.assertEqual((evidence.initial_stop_source, evidence.supporting_zone_id,
                          evidence.supporting_zone_type, evidence.invalidation_level),
                         ('SUPPORTING_ZONE', 'z1', 'FVG', D('90')))
        self.assertEqual((evidence.risk_distance, evidence.reward_distance), (D('11'), D('20')))
        self.assertEqual(evidence.reward_risk_ratio, D('20') / D('11'))
        self.assertEqual((evidence.profile, evidence.break_even_trigger, evidence.break_even_r),
                         ('STRUCTURE_BE', 'FAVORABLE_EXCURSION_R', D('1')))

    def test_structure_short_stop_is_symmetric_and_future_types_need_no_risk_change(self):
        for kind in ('iFVG', 'Breaker', 'Order Block', 'FUTURE_ZONE'):
            result = approve(engine(), candidate('SHORT'), (zone('SHORT', zone_type=kind),))
            self.assertEqual((result.status, result.plan.stop, result.plan.quantity),
                             ('APPROVED', D('111'), D('.90')))
            self.assertEqual(result.evidence.supporting_zone_type, kind)

    def test_no_support_uses_sweep_extreme_not_candidate_stop(self):
        result = approve(engine(), candidate(stop=D('50')))
        self.assertEqual(result.plan.stop, D('90'))
        self.assertEqual((result.evidence.initial_stop_source, result.evidence.invalidation_level),
                         ('SWEEP_EXTREME', D('91')))
        self.assertEqual(approve(engine(), candidate('SHORT')).plan.stop, D('110'))

    def test_stale_unvalidated_future_foreign_and_wrong_side_zones_cannot_support(self):
        values = (zone(fresh=False), zone(validated=False), zone(direction='SHORT'),
                  zone(validated_at=bar(4).close_time), zone(symbol='ETH-USDT'),
                  zone(timeframe='1H'), zone(lower=D('101'), upper=D('105'), invalidation_level=D('101')),
                  zone(invalidation_level=D('92')), zone(lower=90.0))
        for value in values:
            with self.subTest(value=value):
                result = approve(engine(), zones=(value,))
                self.assertEqual(result.plan.stop, D('90'))
                self.assertEqual(result.evidence.initial_stop_source, 'SWEEP_EXTREME')

    def test_support_selection_is_nearest_then_newest_and_input_order_independent(self):
        closer = zone(zone_id='near', lower=D('94'), upper=D('97'), invalidation_level=D('94'))
        for values in ((zone(), closer), (closer, zone())):
            result = approve(engine(), zones=values)
            self.assertEqual((result.plan.stop, result.evidence.supporting_zone_id), (D('93'), 'near'))
        same = replace(closer, zone_id='new', validated_at=bar(3).close_time)
        self.assertEqual(approve(engine(), zones=(closer, same)).evidence.supporting_zone_id, 'new')

    def test_invalid_support_cannot_fall_through_to_foreign_unspecified_context(self):
        result = engine().evaluate(candidate(), D('1000'), (zone(symbol=None, timeframe=None),))
        self.assertEqual(result.evidence.initial_stop_source, 'SWEEP_EXTREME')

    def test_missing_sweep_blocks_instead_of_unproven_fallback(self):
        result = approve(engine(), candidate(sweep_extreme=None))
        self.assertEqual((result.status, result.reason, result.plan), ('BLOCKED', 'MISSING_SWEEP_EXTREME', None))

    def test_poor_rr_blocks_and_configured_boundary_passes(self):
        risk = engine()
        result = approve(risk, candidate(tp=D('105')))
        self.assertEqual((result.status, result.reason, result.plan), ('BLOCKED', 'MIN_REWARD_RISK', None))
        self.assertEqual(result.evidence.reward_risk_ratio, D('.5'))
        self.assertEqual(approve(engine(min_reward_risk=D('.5')), candidate(tp=D('105'))).status, 'APPROVED')

    def test_invalid_stop_side_and_zero_risk_are_machine_readable(self):
        for extreme, reason in (('102', 'INVALID_STOP_SIDE'), ('101', 'NON_POSITIVE_RISK_DISTANCE')):
            result = approve(engine(), candidate(sweep_extreme=D(extreme)))
            self.assertEqual((result.status, result.reason), ('BLOCKED', reason))
        fixed = approve(engine(profile='FIXED_SL_TP'), candidate(stop=D('101')))
        self.assertEqual(fixed.reason, 'INVALID_STOP_SIDE')

    def test_price_direction_equity_and_size_gates_fail_closed(self):
        for changes, reason in (({'entry': D('0')}, 'INVALID_ENTRY'),
                                ({'entry': 100.0}, 'INVALID_ENTRY'),
                                ({'entry': D('NaN')}, 'INVALID_ENTRY'),
                                ({'direction': 'FLAT'}, 'INVALID_DIRECTION'),
                                ({'tp': D('99')}, 'INVALID_TP_SIDE'),
                                ({'tp': D('Infinity')}, 'INVALID_TP'),
                                ({'sweep_extreme': D('0')}, 'INVALID_SWEEP_EXTREME')):
            self.assertEqual(approve(engine(), candidate(**changes)).reason, reason)
        self.assertEqual(engine().evaluate(candidate(), D('0')).reason, 'INVALID_EQUITY')
        self.assertEqual(approve(RiskEngine(RiskConfig(stop_buffer=D('1'), quantity_step=D('100')))).reason,
                         'ZERO_POSITION_SIZE')
        self.assertEqual(approve(engine(), candidate(sweep_extreme=D('100.99'))).reason, 'INSUFFICIENT_EQUITY')

    def test_max_stop_distance_is_optional_and_inclusive(self):
        self.assertEqual(approve(engine(max_stop_distance=D('9'))).reason, 'MAX_STOP_DISTANCE')
        self.assertEqual(approve(engine(max_stop_distance=D('10'))).status, 'APPROVED')

    def test_config_rejects_float_nonfinite_zero_and_unknown_profiles(self):
        for changes in ({'risk_per_trade': .01}, {'risk_per_trade': D('0')},
                        {'risk_per_trade': D('1.1')}, {'min_reward_risk': D('NaN')},
                        {'break_even_r': D('0')}, {'stop_buffer': D('0')},
                        {'quantity_step': D('-1')}, {'max_stop_distance': D('0')},
                        {'profile': 'ATR_TRAIL'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                RiskConfig(**changes)


class ApprovedPaperTests(unittest.TestCase):
    def broker(self, direction='LONG', **config):
        risk = engine(**config)
        broker = PaperBroker(risk, D('1000'))
        broker.submit(approve(risk, candidate(direction)).plan)
        return risk, broker

    def test_unapproved_candidate_and_tampered_plan_cannot_open(self):
        risk = engine()
        broker = PaperBroker(risk, D('1000'))
        with self.assertRaises(ValueError): broker.submit(candidate())
        with self.assertRaises(ValueError): broker.submit(None)
        plan = approve(risk).plan
        with self.assertRaises(ValueError): broker.submit(replace(plan, quantity=D('100')))
        with self.assertRaises(ValueError): PaperBroker(engine(), D('1000')).submit(plan)
        self.assertEqual(broker.process(bar(4)), ())
        self.assertEqual(broker.trades, ())

    def test_fill_reapproval_preserves_stop_and_blocks_gap_with_poor_rr(self):
        _, broker = self.broker()
        self.assertEqual(broker.process(bar(3)), ())
        events = broker.process(bar(4, '112', '115', '111', '114'))
        self.assertEqual([e.kind for e in events], ['BLOCKED', 'PAPER_ORDER_CANCELLED'])
        self.assertEqual(events[0].payload.reason, 'MIN_REWARD_RISK')
        self.assertEqual(events[0].payload.evidence.initial_stop, D('90'))
        self.assertEqual(broker.trades, ())

    def test_first_fill_cannot_skip_next_candle_or_mutate_pending(self):
        _, broker = self.broker()
        pending = broker.pending
        with self.assertRaises(ValueError): broker.process(bar(20))
        self.assertIs(broker.pending, pending)
        self.assertEqual(broker.trades, ())
        changes = broker.process(bar(4))
        self.assertEqual([e.kind for e in changes], ['RISK_APPROVED', 'PAPER_ORDER_OPENED'])

    def test_fill_beyond_support_invalidation_blocks_thesis_already_failed(self):
        risk = RiskEngine(RiskConfig(stop_buffer=D('10'), quantity_step=D('.01')))
        result = approve(risk, zones=(zone(),))
        self.assertEqual(result.status, 'APPROVED')
        broker = PaperBroker(risk, D('1000'))
        broker.submit(result.plan)
        changes = broker.process(bar(4, '85', '89', '83', '86'))
        self.assertEqual([e.kind for e in changes], ['BLOCKED', 'PAPER_ORDER_CANCELLED'])
        self.assertEqual(changes[0].payload.reason, 'SUPPORT_INVALIDATED_AT_FILL')
        self.assertEqual(broker.trades, ())

    def test_actual_fill_plan_and_size_are_approved_before_open(self):
        _, broker = self.broker()
        events = broker.process(bar(4, '102', '105', '99', '104'))
        self.assertEqual([e.kind for e in events], ['RISK_APPROVED', 'PAPER_ORDER_OPENED'])
        trade, = broker.trades
        self.assertEqual((trade.entry, trade.stop, trade.quantity), (D('102'), D('90'), D('.83')))
        self.assertEqual(trade.approved_plan, events[0].payload.plan)
        self.assertEqual(trade.approved_plan.evidence.risk_distance, D('12'))

    def test_break_even_uses_initial_r_and_moves_only_after_surviving_trigger_bar(self):
        _, broker = self.broker(break_even_r=D('1.5'))
        broker.process(bar(4, '100', '114', '95', '110'))
        self.assertEqual(broker.trades[0].stop, D('90'))
        changes = broker.process(bar(5, '110', '115', '96', '112'))
        self.assertEqual([e.kind for e in changes], ['PAPER_STOP_UPDATED'])
        trade = broker.trades[0]
        self.assertEqual((trade.stop, trade.status, trade.tp), (D('100'), 'OPEN', D('120')))
        self.assertEqual(trade.approved_plan.stop, D('90'))
        self.assertEqual(trade.stop_updates[0].measured_r, D('1.5'))
        broker.process(bar(6, '112', '114', '99', '101'))
        self.assertEqual((broker.trades[0].exit_price, broker.trades[0].pnl), (D('100'), D('0')))

    def test_short_break_even_is_symmetric(self):
        _, broker = self.broker('SHORT')
        events = broker.process(bar(4, '100', '105', '90', '92'))
        self.assertEqual([e.kind for e in events], ['RISK_APPROVED', 'PAPER_ORDER_OPENED', 'PAPER_STOP_UPDATED'])
        self.assertEqual(broker.trades[0].stop, D('100'))
        broker.process(bar(5, '92', '101', '91', '99'))
        self.assertEqual(broker.trades[0].exit_price, D('100'))

    def test_initial_stop_first_prevents_retroactive_break_even_on_ambiguous_bar(self):
        _, broker = self.broker()
        events = broker.process(bar(4, '100', '115', '89', '110'))
        self.assertEqual([e.kind for e in events], ['RISK_APPROVED', 'PAPER_ORDER_OPENED', 'PAPER_ORDER_CLOSED'])
        self.assertEqual((broker.trades[0].stop, broker.trades[0].exit_price), (D('90'), D('90')))
        self.assertEqual(broker.trades[0].stop_updates, ())

    def test_stop_proposals_never_loosen_and_break_even_cannot_undo_tighter_stop(self):
        for direction, tighter, looser in (('LONG', '105', '80'), ('SHORT', '95', '120')):
            risk, broker = self.broker(direction)
            broker.process(bar(4))
            trade = risk.tighten_stop(broker.trades[0], D(tighter), bar(4).close_time, 'TEST')
            self.assertEqual(risk.tighten_stop(trade, D(looser), bar(5).close_time, 'TEST'), trade)
            reaction = bar(5, '100', '115', '85', '100')
            self.assertEqual(risk.manage(trade, reaction).stop, D(tighter))

    def test_fixed_profile_preserves_original_sl_tp_until_exit(self):
        risk, broker = self.broker(profile='FIXED_SL_TP')
        broker.process(bar(4, '100', '115', '95', '110'))
        trade = broker.trades[0]
        self.assertEqual((trade.stop, trade.tp), (D('90'), D('120')))
        self.assertEqual(risk.tighten_stop(trade, D('100'), bar(4).close_time, 'TEST'), trade)
        broker.process(bar(5, '110', '121', '96', '119'))
        self.assertEqual((broker.trades[0].stop, broker.trades[0].exit_price), (D('90'), D('120')))
        self.assertEqual(broker.trades[0].stop_updates, ())

    def test_invalid_foreign_or_earlier_management_candle_is_rejected(self):
        risk, broker = self.broker()
        broker.process(bar(4))
        with self.assertRaises(ValueError): risk.manage(broker.trades[0], 'bad')
        with self.assertRaises(ValueError): risk.manage(broker.trades[0], bar(3))
        with self.assertRaises(ValueError): risk.manage(broker.trades[0], replace(bar(5), symbol='ETH-USDT'))

    def test_broker_invalid_candle_fails_before_pending_or_trade_mutation(self):
        _, broker = self.broker()
        pending = broker.pending
        for invalid in ('bad', replace(bar(4), symbol='ETH-USDT'),
                        replace(bar(4), timeframe='5m')):
            with self.assertRaises(ValueError): broker.process(invalid)
            self.assertIs(broker.pending, pending)
            self.assertEqual(broker.trades, ())
        broker.process(bar(4))
        trade = broker.trades
        with self.assertRaises(ValueError): broker.process(bar(4))
        self.assertEqual(broker.trades, trade)


class SupportFreshnessTests(unittest.TestCase):
    def test_new_gap_is_fresh_until_later_wick_edge_touch_and_never_revives(self):
        book = SupportingZoneBook('BTC-USDT', '15m')
        gap = FVG('LONG', D('90'), D('95'), (bar(0).close_time, bar(1).close_time, bar(2).close_time),
                  bar(2).close_time)
        book.publish(gap, 'gap1')
        book.process(bar(2))
        self.assertTrue(book.zones[0].fresh)
        book.process(bar(3, '100', '105', '96', '101'))
        self.assertTrue(book.zones[0].fresh)
        book.process(bar(4, '100', '105', '95', '101'))
        self.assertFalse(book.zones[0].fresh)
        book.process(bar(5, '100', '105', '96', '101'))
        self.assertFalse(book.zones[0].fresh)

    def test_gap_past_invalidation_cannot_leave_support_fresh(self):
        for direction, row in (('LONG', ('85', '89', '80', '86')),
                               ('SHORT', ('100', '105', '99', '102'))):
            book = SupportingZoneBook('BTC-USDT', '15m')
            gap = FVG(direction, D('90'), D('95'), (bar(0).close_time, bar(1).close_time, bar(2).close_time),
                      bar(2).close_time, kind='iFVG')
            book.publish(gap, 'gap1')
            book.process(bar(3, *row))
            self.assertFalse(book.zones[0].fresh)

    def test_support_book_rejects_foreign_or_invalid_candles_before_mutation(self):
        book = SupportingZoneBook('BTC-USDT', '15m')
        gap = FVG('LONG', D('90'), D('95'), (bar(0).close_time, bar(1).close_time, bar(2).close_time),
                  bar(2).close_time)
        book.publish(gap, 'gap1')
        before = book.zones
        for invalid in ('bad', replace(bar(3), symbol='ETH-USDT')):
            with self.assertRaises(ValueError): book.process(invalid)
            self.assertEqual(book.zones, before)


class RiskReplayTests(unittest.TestCase):
    def test_default_boundary_target_approves_and_explicit_eq_is_blocked(self):
        fixture = ROOT / 'tests/data/trading_brain_synthetic.jsonl'
        config = BrainConfig(swing=SwingConfig(atr_length=2, atr_multiplier=D('.1'), bootstrap_candles=30),
                             boundary_proximity=D('2000'), stop_buffer=D('1000'))
        approved = replay(read_candles(fixture), config)
        trade, = approved.broker.trades
        self.assertEqual((trade.entry, trade.stop, trade.tp, trade.quantity),
                         (D('92000'), D('81000'), D('120000'), D('.00909090')))
        self.assertEqual(trade.approved_plan.evidence.supporting_zone_type, 'FVG')
        blocked = replay(read_candles(fixture), replace(config, target='EQ'))
        decision = next(e.payload for e in blocked.events if e.kind == 'BLOCKED')
        self.assertEqual(decision.reason, 'MIN_REWARD_RISK')
        self.assertEqual(blocked.broker.trades, ())
        self.assertFalse(any(e.kind == 'PAPER_ORDER_OPENED' for e in blocked.events))

    def test_replay_prefixes_evidence_and_price_serialization_are_deterministic(self):
        candles = tuple(read_candles(ROOT / 'tests/data/trading_brain_synthetic.jsonl'))
        config = BrainConfig(swing=SwingConfig(atr_length=2, atr_multiplier=D('.1'), bootstrap_candles=30),
                             boundary_proximity=D('2000'), stop_buffer=D('1000'), target='BOUNDARY',
                             break_even_r=D('.25'))
        final = replay(candles, config)
        stream = TradingBrain('BTC-USDT', '15m', config)
        for i, candle in enumerate(candles):
            stream.process(candle)
            self.assertEqual(replay(candles[:i+1], config).snapshot(), stream.snapshot())
            self.assertEqual(stream.events, tuple(e for e in final.events if e.observed_at <= candle.close_time))
        known = {}
        for event in final.events:
            for ref in event.evidence_ids:
                self.assertIn(ref, known)
                self.assertLessEqual(known[ref].observed_at, event.observed_at)
            known[event.id] = event
            if event.kind == 'PAPER_ORDER_OPENED':
                self.assertTrue(any(known[ref].kind == 'RISK_APPROVED' for ref in event.evidence_ids))
        wire = json.loads(json.dumps(to_jsonable(final.report())))
        evidence = wire['trades'][0]['approved_plan']['evidence']
        self.assertEqual((evidence['initial_stop'], evidence['risk_distance'], evidence['break_even_r']),
                         ('81000', '11000', '0.25'))
        self.assertEqual(wire['trades'][0]['stop'], '92000')


if __name__ == '__main__':
    unittest.main()
