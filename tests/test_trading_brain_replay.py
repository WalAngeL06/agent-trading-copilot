"""Full real SwingEngine path; no injected swings in end-to-end tests."""
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from datetime import timedelta
import json
import subprocess
import sys
import unittest
from agent_trading.data import read_candles
from agent_trading.models import to_jsonable
from agent_trading.swing import SwingConfig
from agent_trading.trading_brain import BrainConfig, TradingBrain, replay

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests/data/trading_brain_synthetic.jsonl'
CONFIG = BrainConfig(swing=SwingConfig(atr_length=2, atr_multiplier=D('.1'), bootstrap_candles=30),
                     boundary_proximity=D('2000'), stop_buffer=D('1000'))

class ReplayTests(unittest.TestCase):
    def test_synthetic_candles_produce_complete_paper_chain_with_literal_plan(self):
        brain = replay(read_candles(FIXTURE), CONFIG)
        kinds = [e.kind for e in brain.events]
        required = ['VALID_LOW','VALID_HIGH','RANGE_CANDIDATE','RANGE_LOW_TOUCH',
                    'RANGE_CONFIRMED','SWEEP','RECLAIM','TRADE_CANDIDATE',
                    'RISK_APPROVED','PAPER_ORDER_OPENED']
        previous = -1
        for kind in required:
            previous = kinds.index(kind, previous+1)
        candidate = next(e for e in brain.events if e.kind=='TRADE_CANDIDATE')
        gaps = [e for e in brain.events if e.kind in ('FVG','iFVG') and e.id in candidate.evidence_ids]
        self.assertEqual(len(gaps), 1)
        trade, = brain.broker.trades
        self.assertEqual((trade.direction, trade.entry, trade.stop, trade.tp, trade.quantity),
                         ('LONG', D('92000'), D('76000'), D('100000'), D('.00625')))
        self.assertEqual(trade.risk_amount, D('100'))
        self.assertGreater(trade.opened_at, candidate.observed_at)
        self.assertEqual((trade.status, trade.exit_price, trade.pnl), ('CLOSED',D('100000'),D('50')))
        self.assertEqual(brain.broker.equity, D('10050'))
        self.assertEqual((brain.range.state.range_low, brain.range.state.range_high),
                         (D('80000'), D('120000')))

    def test_all_synthetic_prefixes_match_stream_state_and_final_event_prefix(self):
        candles = tuple(read_candles(FIXTURE))
        stream = TradingBrain('BTC-USDT','15m',CONFIG)
        snapshots = []
        for candle in candles:
            stream.process(candle)
            snapshots.append(stream.snapshot())
        for length in range(1,len(candles)+1):
            prefix = replay(candles[:length],CONFIG)
            self.assertEqual(prefix.snapshot(), snapshots[length-1])
            self.assertEqual(prefix.events, tuple(e for e in stream.events if e.observed_at<=candles[length-1].close_time))

    def test_bootstrap_then_stream_is_identical_to_full_replay(self):
        candles = tuple(read_candles(FIXTURE))
        for split in (1,5,14,19,20):
            brain = TradingBrain('BTC-USDT','15m',CONFIG)
            brain.bootstrap(candles[:split])
            for candle in candles[split:]: brain.process(candle)
            self.assertEqual(brain.snapshot(), replay(candles,CONFIG).snapshot())
            with self.assertRaises(ValueError): brain.bootstrap(candles[:1])

    def test_evidence_graph_has_only_prior_known_references_and_exact_prices(self):
        brain = replay(read_candles(FIXTURE),CONFIG)
        prior = {}
        for event in brain.events:
            for ref in event.evidence_ids:
                self.assertIn(ref, prior)
                self.assertLessEqual(prior[ref].observed_at,event.observed_at)
            prior[event.id] = event
        candidate = next(e for e in brain.events if e.kind=='TRADE_CANDIDATE')
        ancestors = set()
        def visit(event):
            for ref in event.evidence_ids:
                if ref not in ancestors:
                    ancestors.add(ref); visit(prior[ref])
        visit(candidate)
        kinds = {prior[x].kind for x in ancestors}
        self.assertTrue({'VALID_LOW','VALID_HIGH','RANGE_CONFIRMED','SWEEP','RECLAIM','FVG'} <= kinds)
        opened = next(e for e in brain.events if e.kind=='PAPER_ORDER_OPENED')
        self.assertTrue(any(prior[ref].kind=='RISK_APPROVED' for ref in opened.evidence_ids))
        self.assertEqual(brain.broker.trades[0].filled_at, candidate.observed_at)
        encoded = json.loads(json.dumps(to_jsonable(brain.report())))
        self.assertEqual(encoded['trades'][0]['entry'],'92000')
        self.assertEqual(encoded['mode'],'PAPER')

    def test_duplicate_foreign_open_or_gapped_input_does_not_mutate_state(self):
        candles = tuple(read_candles(FIXTURE))
        brain = TradingBrain('BTC-USDT','15m',CONFIG)
        brain.process(candles[0])
        initial = brain.snapshot()
        for invalid in (candles[0], candles[2], replace(candles[1],symbol='ETH-USDT'),
                        replace(candles[1],timeframe='5m'), 'bad'):
            with self.assertRaises(ValueError): brain.process(invalid)
            self.assertEqual(brain.snapshot(),initial)
        brain.process(candles[1])

    def test_real_btc_streams_are_causal_for_every_prefix_without_requiring_trade(self):
        for tf in ('5m','15m','1H','4H'):
            candles = tuple(read_candles(ROOT/('tests/data/btcusdt_'+tf+'.jsonl')))
            stream = TradingBrain('BTC-USDT',tf)
            for i,candle in enumerate(candles):
                stream.process(candle)
                prefix = replay(candles[:i+1])
                self.assertEqual(prefix.snapshot(),stream.snapshot())
            self.assertGreater(len(stream.swing.confirmed),0)
            self.assertGreater(len(stream.structure.valid),0)

    def test_real_btc_default_fvg_short_and_ifvg_long_have_exact_replay_plans(self):
        expected = {
            '1H': ('SHORT','77289.8','78166.5','77250.85','0.11406410','FVG'),
            '4H': ('LONG','64236.3','63137.6','64342.65','0.09101665','iFVG'),
        }
        for tf,(direction,entry,stop,tp,quantity,gap_kind) in expected.items():
            brain = replay(read_candles(ROOT/('tests/data/btcusdt_'+tf+'.jsonl')))
            trade, = brain.broker.trades
            self.assertEqual((trade.direction,trade.entry,trade.stop,trade.tp,trade.quantity),
                             (direction,D(entry),D(stop),D(tp),D(quantity)))
            self.assertLessEqual(trade.risk_amount,D('100'))
            candidate = next(e for e in brain.events if e.kind=='TRADE_CANDIDATE')
            self.assertTrue(any(e.kind==gap_kind and e.id in candidate.evidence_ids for e in brain.events))

    def test_low_first_range_can_trade_short_through_fvg_with_real_swing_engine(self):
        candles = list(read_candles(FIXTURE))[:15]
        rows = [('112','119','112','118'),('118','120','118','119'),
                ('119','123','119','121'),('121','122','115','116'),
                ('115','115','107','108'),('108','110','104','106'),
                ('106','107','99','100')]
        first = candles[-1].close_time
        for index,(o,h,l,c) in enumerate(rows,1):
            candles.append(replace(candles[-1],close_time=first+timedelta(minutes=15*index),
                                  open=D(o)*1000,high=D(h)*1000,low=D(l)*1000,close=D(c)*1000))
        brain = replay(candles,CONFIG)
        trade, = brain.broker.trades
        self.assertEqual((trade.direction,trade.entry,trade.stop,trade.tp,trade.quantity),
                         ('SHORT',D('108000'),D('124000'),D('100000'),D('.00625')))

    def test_opposing_boundary_target_is_configurable(self):
        brain = replay(read_candles(FIXTURE),replace(CONFIG,target='BOUNDARY'))
        trade, = brain.broker.trades
        self.assertEqual(trade.tp,D('120000'))
        self.assertEqual(trade.status,'OPEN')

    def test_no_gap_and_new_sweep_cannot_use_old_reclaim_to_create_candidate(self):
        candles = list(read_candles(FIXTURE))
        for low in (D('82000'),D('76000')):
            altered = candles[:20]
            altered[-1] = replace(altered[-1],low=low)
            brain = replay(altered,CONFIG)
            self.assertFalse(any(e.kind=='TRADE_CANDIDATE' for e in brain.events))
            self.assertEqual(brain.broker.trades,())

    def test_cli_replays_fixture_and_serializes_full_evidence(self):
        completed = subprocess.run([sys.executable,'-B','-m','agent_trading.trading_brain',
            '--candles',str(FIXTURE),'--atr-length','2','--atr-multiplier','.1',
            '--boundary-proximity','2000','--stop-buffer','1000'],
            cwd=ROOT,text=True,capture_output=True,check=True)
        report = json.loads(completed.stdout)
        self.assertEqual(report['trades'][0]['entry'],'92000')
        self.assertIn('PAPER_ORDER_OPENED',[e['kind'] for e in report['events']])
        self.assertEqual(report['fixture_kind'],'SYNTHETIC')

if __name__=='__main__': unittest.main()
