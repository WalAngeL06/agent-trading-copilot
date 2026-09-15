"""Causal real-market smoke for the Strategy V1 multi-timeframe path.

This is NOT a backtest. Nothing here measures or asserts profitability; it only
proves that saved real BTC-USDT 4H/1H/15m candles flow through the production
StrategyV1 chain causally, with no fabricated events and no lookahead. A period
that produces no trade is a valid outcome and is not tuned away.
"""
import unittest
from pathlib import Path

from agent_trading.data import read_candles
from agent_trading.market import bar_duration
from agent_trading.strategy_v1 import StrategyProfile, StrategyV1

DATA = Path(__file__).with_name('data')
STREAMS = (('4H', 'btcusdt_4H.jsonl'), ('1H', 'btcusdt_1H.jsonl'),
           ('15m', 'btcusdt_15m.jsonl'))
SYMBOL = 'BTC-USDT'


def load():
    streams = {}
    for timeframe, name in STREAMS:
        streams[timeframe] = tuple(read_candles(DATA / name))
    return streams


def replay(profile=None):
    strategy = StrategyV1(SYMBOL, profile if profile is not None else StrategyProfile())
    candles = [c for stream in load().values() for c in stream]
    strategy.feed(candles)
    return strategy


class RealFixtureIntegrityTests(unittest.TestCase):
    def test_every_stream_is_closed_contiguous_and_one_symbol(self):
        for timeframe, stream in load().items():
            step = bar_duration(timeframe)
            self.assertTrue(stream, timeframe)
            for candle in stream:
                self.assertTrue(candle.closed)
                self.assertEqual(candle.symbol, SYMBOL)
                self.assertEqual(candle.timeframe, timeframe)
            for earlier, later in zip(stream, stream[1:]):
                self.assertEqual(later.close_time - earlier.close_time, step)

    def test_the_three_streams_overlap(self):
        streams = load()
        latest_start = max(s[0].close_time for s in streams.values())
        earliest_end = min(s[-1].close_time for s in streams.values())
        self.assertLess(latest_start, earliest_end)


class RealReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strategy = replay()

    def test_the_real_multi_timeframe_path_runs_end_to_end(self):
        self.assertIsNotNone(self.strategy.as_of)
        self.assertGreater(len(self.strategy.events), 0)
        self.assertEqual(self.strategy.report()['mode'], 'PAPER')

    def test_every_event_is_chronological(self):
        times = [event.observed_at for event in self.strategy.events]
        self.assertEqual(times, sorted(times))

    def test_no_event_precedes_its_own_evidence(self):
        seen = {}
        for event in self.strategy.events:
            for reference in event.evidence_ids:
                self.assertIn(reference, seen)
                self.assertLessEqual(seen[reference], event.observed_at)
            seen[event.id] = event.observed_at

    def test_bias_transitions_are_recorded_on_the_bias_timeframe(self):
        breaks = [e for e in self.strategy.events if e.kind == 'BIAS_BREAK']
        self.assertTrue(breaks)
        for event in breaks:
            self.assertEqual(event.timeframe, '4H')
            self.assertGreater(event.payload.broken_price, 0)

    def test_entry_search_never_started_without_a_confirmed_manipulation(self):
        confirmations = [e for e in self.strategy.events
                         if e.kind == 'MANIPULATION_CONFIRMED']
        if not confirmations:
            self.assertEqual([e for e in self.strategy.events
                              if e.kind == 'TRADE_CANDIDATE'], [])
        else:
            first = confirmations[0].observed_at
            for event in self.strategy.events:
                if event.kind == 'TRADE_CANDIDATE':
                    self.assertGreater(event.observed_at, first)

    def test_gaps_are_detected_but_gated(self):
        gaps = [e for e in self.strategy.events if e.kind in ('FVG', 'iFVG')]
        self.assertTrue(gaps, 'real 15m data should produce gaps')
        for event in gaps:
            self.assertEqual(event.timeframe, '15m')

    def test_no_short_candidate_or_trade_is_produced_on_real_data(self):
        for event in self.strategy.events:
            if event.kind == 'TRADE_CANDIDATE':
                self.assertEqual(event.payload.direction, 'LONG')
        for trade in self.strategy.broker.trades:
            self.assertEqual(trade.direction, 'LONG')

    def test_a_confirmed_range_is_required_before_any_manipulation(self):
        confirmed = [e.observed_at for e in self.strategy.events
                     if e.kind == 'RANGE_CONFIRMED']
        for event in self.strategy.events:
            if event.kind in ('SWEEP', 'MANIPULATION_CONFIRMED'):
                self.assertTrue(confirmed)
                self.assertGreater(event.observed_at, confirmed[0])

    def test_the_real_replay_is_deterministic(self):
        again = replay()
        self.assertEqual([(e.id, e.kind, e.observed_at) for e in self.strategy.events],
                         [(e.id, e.kind, e.observed_at) for e in again.events])

    def test_this_period_produced_no_paper_trade(self):
        # Recorded as an observation, not a target. Parameters are NOT tuned to
        # force a trade: the smoke exists to prove the data path, not to profit.
        self.assertEqual(self.strategy.broker.trades, ())
        self.assertIsNone(self.strategy.broker.pending_plan)


if __name__ == '__main__':
    unittest.main()
