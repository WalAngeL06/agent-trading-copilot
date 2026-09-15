"""Causal guarantees for the production SwingEngine.

These tests establish causality, immutability and configurability. They do not
establish that the detected swings are structurally meaningful: the
opposing-movement predicate is still ALGORITHMIC DEFINITION PENDING (N-1) and
the ATR model is a project hypothesis [H].

Offline. The real-BTC cases use saved candle JSONL and skip when it is absent.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from agent_trading.models import Candle
from agent_trading.swing import (ConfirmedSwing, SwingConfig, SwingEngine, SwingEvent,
                                 SwingEventType, SwingSide, SwingState, SwingStatus)

SYMBOL = "BTC-USDT"
TIMEFRAME = "15m"
START = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
STEP = timedelta(minutes=15)
DATA_DIR = Path(__file__).resolve().parent / "data"
FAST = SwingConfig(atr_length=2, atr_multiplier=Decimal("1.0"), bootstrap_candles=10)


def build(rows, symbol=SYMBOL, timeframe=TIMEFRAME, step=STEP):
    """rows: (open, high, low, close) decimal strings, oldest first."""
    return tuple(
        Candle(symbol=symbol, timeframe=timeframe, close_time=START + step * index,
               open=Decimal(o), high=Decimal(h), low=Decimal(l), close=Decimal(c),
               volume=Decimal("1"))
        for index, (o, h, l, c) in enumerate(rows))


FLAT = [("100", "101", "99", "100")] * 3

# Warmup, then a rise (which resolves the seed by confirming the low at 99),
# a higher peak at 112, then a close far enough below it to confirm the high.
RISE_THEN_DROP = FLAT + [("100", "106", "100", "105"), ("105", "112", "104", "111"),
                         ("111", "112", "95", "96")]
# Mirror: the seed resolves on the high, then a trough at 88 is confirmed.
DROP_THEN_RISE = FLAT + [("100", "100", "94", "95"), ("95", "96", "88", "89"),
                         ("89", "105", "88", "104")]


def load_real(timeframe):
    path = DATA_DIR / ("btcusdt_%s.jsonl" % timeframe)
    if not path.is_file():
        return None
    candles = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            candles.append(Candle.from_dict(json.loads(line, parse_float=Decimal)))
    return tuple(candles)


def confirmed_of(events):
    return tuple(e for e in events if e.status is SwingStatus.CONFIRMED)


class ConfigTests(unittest.TestCase):

    def test_defaults_are_usable_and_immutable(self):
        config = SwingConfig()
        self.assertEqual(config.atr_length, 14)
        self.assertEqual(config.bootstrap_candles, 200)
        self.assertIsInstance(config.atr_multiplier, Decimal)
        with self.assertRaises(Exception):
            config.atr_length = 5

    def test_multiplier_accepts_strings_and_normalises_to_decimal(self):
        self.assertEqual(SwingConfig(atr_multiplier="1.5").atr_multiplier, Decimal("1.5"))
        self.assertEqual(SwingConfig(atr_multiplier=2).atr_multiplier, Decimal("2"))

    def test_invalid_configuration_is_rejected(self):
        for length in (0, 1, -3, 2.5, 501):
            with self.assertRaises(ValueError):
                SwingConfig(atr_length=length)
        for multiplier in ("0", "-1", "0.001", "25", Decimal("NaN")):
            with self.assertRaises(ValueError):
                SwingConfig(atr_multiplier=multiplier)
        for bootstrap in (0, -1, 5001):
            with self.assertRaises(ValueError):
                SwingConfig(bootstrap_candles=bootstrap)

    def test_bootstrap_length_must_exceed_warmup(self):
        with self.assertRaises(ValueError):
            SwingConfig(atr_length=14, bootstrap_candles=14)
        self.assertTrue(SwingConfig(atr_length=14, bootstrap_candles=15))

    def test_engine_rejects_unusable_symbol_timeframe_or_config(self):
        for symbol, timeframe in ((" ", "15m"), ("BTC-USDT", ""), ("BTC-USDT", "1D"),
                                  ("BTC-USDT", "7m")):
            with self.assertRaises(ValueError):
                SwingEngine(symbol, timeframe)
        with self.assertRaises(ValueError):
            SwingEngine(SYMBOL, TIMEFRAME, config={"atr_length": 14})

    def test_any_supported_timeframe_is_accepted(self):
        for timeframe in ("1m", "5m", "15m", "30m", "1H", "4H", "12H"):
            self.assertEqual(SwingEngine(SYMBOL, timeframe).timeframe, timeframe)


class WarmupTests(unittest.TestCase):

    def test_no_event_is_emitted_before_the_atr_window_is_full(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, SwingConfig(atr_length=5,
                                                            bootstrap_candles=10))
        candles = build([("100", "101", "99", "100")] * 8)
        emitted = [engine.process(candle) for candle in candles]
        self.assertEqual(emitted[0], ())
        self.assertFalse(any(emitted[:4]), "events before warmup completed")
        self.assertFalse(engine.state.warmup_complete is True and len(emitted[:4][0]) > 0)

    def test_warmup_completes_exactly_at_atr_length_candles(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, SwingConfig(atr_length=4,
                                                            bootstrap_candles=10))
        candles = build([("100", "101", "99", "100")] * 5)
        for index, candle in enumerate(candles):
            engine.process(candle)
            self.assertEqual(engine.state.warmup_complete, index >= 3)

    def test_threshold_and_atr_are_unavailable_until_warmup(self):
        config = SwingConfig(atr_length=3, atr_multiplier="2.0", bootstrap_candles=10)
        engine = SwingEngine(SYMBOL, TIMEFRAME, config)
        candles = build([("100", "102", "98", "100")] * 4)
        engine.process(candles[0])
        self.assertIsNone(engine.state.atr)
        self.assertIsNone(engine.state.threshold)
        for candle in candles[1:3]:
            engine.process(candle)
        self.assertEqual(engine.state.atr, Decimal("4"))
        self.assertEqual(engine.state.threshold, Decimal("4") * config.atr_multiplier)

    def test_a_longer_warmup_delays_the_first_confirmation(self):
        rows = FLAT + [("100", "120", "99", "119"), ("119", "120", "70", "71")]
        short = SwingEngine(SYMBOL, TIMEFRAME, SwingConfig(atr_length=2, bootstrap_candles=5))
        long = SwingEngine(SYMBOL, TIMEFRAME, SwingConfig(atr_length=5, bootstrap_candles=6))
        candles = build(rows)
        self.assertTrue(confirmed_of(short.bootstrap(candles)))
        self.assertFalse(confirmed_of(long.bootstrap(candles)))


class CandidateTests(unittest.TestCase):

    def test_first_warm_candle_opens_both_candidates(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        candles = build(FLAT)
        engine.process(candles[0])
        events = engine.process(candles[1])
        self.assertEqual([e.event_type for e in events],
                         [SwingEventType.CANDIDATE_CREATED] * 2)
        self.assertEqual({e.side for e in events}, {SwingSide.HIGH, SwingSide.LOW})

    def test_candidate_high_updates_on_a_higher_wick(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(build(FLAT))
        events = engine.process(build(FLAT + [("100", "110", "99", "100")])[3])
        highs = [e for e in events if e.side is SwingSide.HIGH]
        self.assertEqual([e.event_type for e in highs], [SwingEventType.CANDIDATE_UPDATED])
        self.assertEqual(highs[0].price, Decimal("110"))
        self.assertEqual(highs[0].status, SwingStatus.CANDIDATE)
        self.assertIsNone(highs[0].confirmed_at)

    def test_candidate_low_updates_on_a_lower_wick(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(build(FLAT))
        events = engine.process(build(FLAT + [("100", "101", "90", "100")])[3])
        lows = [e for e in events if e.side is SwingSide.LOW]
        self.assertEqual([e.event_type for e in lows], [SwingEventType.CANDIDATE_UPDATED])
        self.assertEqual(lows[0].price, Decimal("90"))

    def test_a_wick_that_does_not_improve_produces_no_candidate_event(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(build(FLAT))
        events = engine.process(build(FLAT + [("100", "100.5", "99.5", "100")])[3])
        self.assertEqual([e for e in events if e.event_type is SwingEventType.CANDIDATE_UPDATED], [])

    def test_provisional_extremes_are_visible_while_seeding(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(build(FLAT + [("100", "103", "100", "101")]))
        state = engine.state
        self.assertIsInstance(state, SwingState)
        self.assertTrue(state.seeding)
        self.assertIsNone(state.candidate_side)
        self.assertEqual(state.pending_high_price, Decimal("103"))
        self.assertEqual(state.pending_low_price, Decimal("99"))
        self.assertEqual(engine.confirmed, ())

    def test_a_tracked_candidate_is_visible_in_state_and_is_not_confirmed(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(build(RISE_THEN_DROP[:5]))
        state = engine.state
        self.assertFalse(state.seeding)
        self.assertEqual(state.candidate_side, SwingSide.HIGH)
        self.assertEqual(state.candidate_price, Decimal("112"))
        self.assertEqual(state.confirmed_count, 1)     # only the seed low so far
        self.assertNotIn(Decimal("112"), [s.price for s in engine.confirmed])


class ConfirmationTests(unittest.TestCase):

    def test_high_confirms_when_a_later_close_falls_far_enough(self):
        candles = build(RISE_THEN_DROP)
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(candles)
        highs = [s for s in engine.confirmed if s.side is SwingSide.HIGH]
        self.assertEqual(len(highs), 1)
        swing = highs[0]
        self.assertEqual(swing.price, Decimal("112"))
        self.assertEqual(swing.swing_time, candles[4].close_time)
        self.assertEqual(swing.confirmed_at, candles[5].close_time)
        self.assertEqual(swing.confirmation_delay_bars, 1)

    def test_low_confirms_when_a_later_close_rises_far_enough(self):
        candles = build(DROP_THEN_RISE)
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(candles)
        lows = [s for s in engine.confirmed if s.side is SwingSide.LOW]
        self.assertEqual(len(lows), 1)
        swing = lows[0]
        self.assertEqual(swing.price, Decimal("88"))
        self.assertEqual(swing.swing_time, candles[4].close_time)
        self.assertEqual(swing.confirmed_at, candles[5].close_time)

    def test_a_close_that_is_not_far_enough_confirms_nothing(self):
        """Flat candles never travel an ATR multiple away from either extreme."""
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(build(FLAT * 3))
        self.assertEqual(engine.confirmed, ())
        self.assertTrue(engine.state.warmup_complete)

    def test_confirmation_carries_the_volatility_context_that_produced_it(self):
        candles = build(RISE_THEN_DROP)
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(candles)
        swing = [s for s in engine.confirmed if s.side is SwingSide.HIGH][0]
        self.assertGreater(swing.atr, 0)
        self.assertEqual(swing.threshold, swing.atr * FAST.atr_multiplier)
        self.assertLessEqual(candles[5].close, swing.price - swing.threshold)

    def test_a_bigger_multiplier_requires_a_bigger_move(self):
        candles = build(RISE_THEN_DROP)
        loose = SwingEngine(SYMBOL, TIMEFRAME, SwingConfig(atr_length=2, atr_multiplier="1.0",
                                                           bootstrap_candles=5))
        strict = SwingEngine(SYMBOL, TIMEFRAME, SwingConfig(atr_length=2, atr_multiplier="10",
                                                            bootstrap_candles=5))
        loose.bootstrap(candles)
        strict.bootstrap(candles)
        self.assertTrue(loose.confirmed)
        self.assertEqual(strict.confirmed, ())

    def test_no_same_candle_confirmation_even_on_a_huge_reversal_bar(self):
        """One candle makes the high and closes far below it: not confirmable."""
        candles = build(FLAT + [("100", "200", "59", "60"), ("60", "61", "59", "60")])
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        reversal = engine.bootstrap(candles[:4])
        self.assertNotIn(Decimal("200"), [e.price for e in confirmed_of(reversal)])
        later = confirmed_of(engine.process(candles[4]))
        self.assertEqual([e.price for e in later], [Decimal("200")])
        self.assertGreaterEqual(later[0].confirmation_delay_bars, 1)
        self.assertLess(later[0].swing_time, later[0].confirmed_at)

    def test_the_event_contract_forbids_a_same_candle_confirmation(self):
        moment = START
        with self.assertRaises(ValueError):
            SwingEvent(symbol=SYMBOL, timeframe=TIMEFRAME,
                       event_type=SwingEventType.SWING_CONFIRMED, side=SwingSide.HIGH,
                       status=SwingStatus.CONFIRMED, price=Decimal("100"),
                       swing_time=moment, observed_at=moment, confirmed_at=moment,
                       confirmation_delay_bars=0, atr=Decimal("1"), threshold=Decimal("1"))

    def test_confirmed_swings_alternate_and_advance_in_time(self):
        for timeframe in ("5m", "15m", "1H", "4H"):
            candles = load_real(timeframe)
            if candles is None:
                self.skipTest("no saved BTC candles")
            engine = SwingEngine(SYMBOL, timeframe, SwingConfig(atr_multiplier="1.5"))
            engine.bootstrap(candles)
            swings = engine.confirmed
            with self.subTest(timeframe=timeframe):
                self.assertTrue(swings)
                sides = [s.side for s in swings]
                self.assertFalse([a for a, b in zip(sides, sides[1:]) if a is b])
                times = [s.swing_time for s in swings]
                self.assertEqual(times, sorted(times))
                self.assertEqual(len(times), len(set(times)))
                for swing in swings:
                    self.assertLess(swing.swing_time, swing.confirmed_at)
                    self.assertGreaterEqual(swing.confirmation_delay_bars, 1)


class AntiRepaintTests(unittest.TestCase):

    def _confirmed(self, candles, config):
        engine = SwingEngine(candles[0].symbol, candles[0].timeframe, config)
        engine.bootstrap(candles)
        return engine.confirmed

    def test_every_prefix_is_a_prefix_of_the_final_confirmed_history(self):
        config = SwingConfig(atr_length=5, atr_multiplier="1.0", bootstrap_candles=10)
        candles = load_real("15m")
        if candles is None:
            self.skipTest("no saved BTC candles")
        candles = candles[:140]
        final = self._confirmed(candles, config)
        self.assertTrue(final)
        for length in range(1, len(candles) + 1):
            prefix = self._confirmed(candles[:length], config)
            self.assertEqual(prefix, final[:len(prefix)],
                             "confirmed history changed after %d candles" % length)

    def test_confirmed_swings_are_field_for_field_stable_as_candles_arrive(self):
        config = SwingConfig(atr_length=5, atr_multiplier="1.25", bootstrap_candles=10)
        candles = load_real("1H")
        if candles is None:
            self.skipTest("no saved BTC candles")
        candles = candles[:120]
        seen = {}
        for length in range(1, len(candles) + 1):
            for position, swing in enumerate(self._confirmed(candles[:length], config)):
                if position in seen:
                    self.assertEqual(seen[position], swing)
                else:
                    seen[position] = swing

    def test_confirmed_history_only_grows(self):
        config = SwingConfig(atr_length=5, atr_multiplier="1.0", bootstrap_candles=10)
        candles = load_real("5m")
        if candles is None:
            self.skipTest("no saved BTC candles")
        candles = candles[:120]
        counts = [len(self._confirmed(candles[:n], config)) for n in range(1, len(candles) + 1)]
        self.assertEqual(counts, sorted(counts))
        self.assertGreater(counts[-1], 0)

    def test_a_future_suffix_cannot_change_an_earlier_evaluation(self):
        config = SwingConfig(atr_multiplier="1.5")
        candles = load_real("15m")
        if candles is None:
            self.skipTest("no saved BTC candles")
        early = self._confirmed(candles[:150], config)
        full = self._confirmed(candles, config)
        self.assertTrue(early)
        self.assertEqual(early, full[:len(early)])


class EquivalenceTests(unittest.TestCase):

    def _events(self, candles, config):
        engine = SwingEngine(candles[0].symbol, candles[0].timeframe, config)
        return engine.bootstrap(candles)

    def test_two_identical_runs_produce_identical_event_streams(self):
        config = SwingConfig(atr_multiplier="1.25")
        candles = load_real("15m") or None
        if candles is None:
            self.skipTest("no saved BTC candles")
        self.assertEqual(self._events(candles, config), self._events(candles, config))

    def test_bootstrap_replay_equals_candle_by_candle_live_processing(self):
        config = SwingConfig(atr_multiplier="1.5")
        for timeframe in ("5m", "15m", "1H", "4H"):
            candles = load_real(timeframe)
            if candles is None:
                self.skipTest("no saved BTC candles")
            batch = self._events(candles, config)
            engine = SwingEngine(SYMBOL, timeframe, config)
            live = []
            for candle in candles:
                live.extend(engine.process(candle))
            with self.subTest(timeframe=timeframe):
                self.assertEqual(batch, tuple(live))

    def test_bootstrap_then_live_continuation_matches_one_full_replay(self):
        config = SwingConfig(atr_multiplier="1.5")
        candles = load_real("1H")
        if candles is None:
            self.skipTest("no saved BTC candles")
        whole = self._events(candles, config)
        split = 200                       # the planned bootstrap context length
        engine = SwingEngine(SYMBOL, "1H", config)
        events = list(engine.bootstrap(candles[:split]))
        for candle in candles[split:]:    # then live, same engine
            events.extend(engine.process(candle))
        self.assertEqual(whole, tuple(events))
        self.assertEqual(engine.state.bars_processed, len(candles))

    def test_bootstrap_requires_a_fresh_engine(self):
        candles = build(FLAT)
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.bootstrap(candles)
        with self.assertRaises(ValueError):
            engine.bootstrap(candles)


class InputDisciplineTests(unittest.TestCase):

    def test_duplicate_or_out_of_order_candles_are_rejected(self):
        candles = build(FLAT)
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.process(candles[0])
        engine.process(candles[1])
        with self.assertRaises(ValueError):
            engine.process(candles[1])
        with self.assertRaises(ValueError):
            engine.process(candles[0])

    def test_a_candle_from_another_symbol_or_timeframe_is_rejected(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        engine.process(build(FLAT)[0])
        with self.assertRaises(ValueError):
            engine.process(build(FLAT, symbol="ETH-USDT")[1])
        with self.assertRaises(ValueError):
            engine.process(build(FLAT, timeframe="1H")[1])

    def test_non_candle_input_is_rejected(self):
        engine = SwingEngine(SYMBOL, TIMEFRAME, FAST)
        for bad in (None, "100", 100, [build(FLAT)[0]]):
            with self.assertRaises(ValueError):
                engine.process(bad)

    def test_open_candles_cannot_be_constructed_so_cannot_be_detected(self):
        with self.assertRaises(ValueError):
            Candle(symbol=SYMBOL, timeframe=TIMEFRAME, close_time=START,
                   open=Decimal("1"), high=Decimal("2"), low=Decimal("1"),
                   close=Decimal("1"), volume=Decimal("1"), closed=False)


class IndependentStateTests(unittest.TestCase):

    def test_each_timeframe_engine_keeps_its_own_state(self):
        engines = {}
        for timeframe in ("5m", "15m", "1H", "4H"):
            candles = load_real(timeframe)
            if candles is None:
                self.skipTest("no saved BTC candles")
            engine = SwingEngine(SYMBOL, timeframe, SwingConfig(atr_multiplier="1.5"))
            engine.bootstrap(candles)
            engines[timeframe] = engine
        counts = {tf: len(e.confirmed) for tf, e in engines.items()}
        self.assertEqual(len(set(counts.values())) > 1, True,
                         "timeframes should not produce identical swing counts")
        for timeframe, engine in engines.items():
            self.assertTrue(all(s.timeframe == timeframe for s in engine.confirmed))
            self.assertEqual(engine.state.timeframe, timeframe)

    def test_interleaved_engines_do_not_contaminate_each_other(self):
        fast, slow = load_real("5m"), load_real("1H")
        if fast is None or slow is None:
            self.skipTest("no saved BTC candles")
        config = SwingConfig(atr_multiplier="1.5")
        a = SwingEngine(SYMBOL, "5m", config)
        b = SwingEngine(SYMBOL, "1H", config)
        for index in range(max(len(fast), len(slow))):
            if index < len(fast):
                a.process(fast[index])
            if index < len(slow):
                b.process(slow[index])
        solo_a = SwingEngine(SYMBOL, "5m", config)
        solo_a.bootstrap(fast)
        solo_b = SwingEngine(SYMBOL, "1H", config)
        solo_b.bootstrap(slow)
        self.assertEqual(a.confirmed, solo_a.confirmed)
        self.assertEqual(b.confirmed, solo_b.confirmed)

    def test_the_same_series_under_two_configurations_is_independent(self):
        candles = load_real("15m")
        if candles is None:
            self.skipTest("no saved BTC candles")
        loose = SwingEngine(SYMBOL, "15m", SwingConfig(atr_multiplier="0.75"))
        strict = SwingEngine(SYMBOL, "15m", SwingConfig(atr_multiplier="2.0"))
        loose.bootstrap(candles)
        strict.bootstrap(candles)
        self.assertGreater(len(loose.confirmed), len(strict.confirmed))


class IsolationTests(unittest.TestCase):

    def test_swing_module_does_not_reach_into_strategy_layers(self):
        source = (Path(__file__).resolve().parent.parent / "agent_trading" / "swing.py"
                  ).read_text(encoding="utf-8")
        for forbidden in ("components", "engine", "analysis_", "okx", "journal", "shadow"):
            self.assertNotIn("from .%s" % forbidden, source)
            self.assertNotIn("import %s" % forbidden, source)

    def test_decision_pipeline_is_unchanged(self):
        from agent_trading.components import DecisionRouter
        self.assertEqual(DecisionRouter().route(()),
                         {"action": "NO_TRADE", "reason": "STRATEGY_NOT_CONFIGURED"})

    def test_confirmed_identity_requires_a_confirmed_event(self):
        candidate = SwingEvent(symbol=SYMBOL, timeframe=TIMEFRAME,
                               event_type=SwingEventType.CANDIDATE_CREATED,
                               side=SwingSide.HIGH, status=SwingStatus.CANDIDATE,
                               price=Decimal("100"), swing_time=START, observed_at=START)
        with self.assertRaises(ValueError):
            ConfirmedSwing.from_event(candidate)


if __name__ == "__main__":
    unittest.main()
