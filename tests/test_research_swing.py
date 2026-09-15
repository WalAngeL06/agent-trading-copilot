"""Causal guarantees for the swing research module.

These tests check causality and immutability, not trading quality. A green run
establishes that confirmed swings never repaint and that replay equals live
processing; it establishes nothing about whether the detected swings are
structurally meaningful (that remains ALGORITHMIC DEFINITION PENDING).
"""

import unittest
from datetime import timedelta
from decimal import Decimal

from agent_trading.models import Candle
from agent_trading.research.swing.baselines import batch_zigzag_swings
from agent_trading.research.swing.detectors import (
    AtrReversalDetector, DirectionalChangeDetector, FractalSwingDetector,
    ZigZagSwingDetector, default_detector_factories)
from agent_trading.research.swing.events import (
    ConfirmedSwing, SwingEvent, SwingEventType, SwingSide, SwingStatus)
from agent_trading.research.swing.fixtures import (
    BENCHMARKS, SYMBOL, TIMEFRAME, all_benchmarks, clean_uptrend, false_breakout)
from agent_trading.research.swing.metrics import (
    evaluate, prefix_violations, repaint_violations)
from agent_trading.research.swing.replay import (
    confirmed_only, format_event_table, replay, replay_prefixes)

FACTORIES = default_detector_factories()
REVERSAL = tuple((n, f) for n, f in FACTORIES if not n.startswith("fractal"))


class AntiRepaintTests(unittest.TestCase):
    """The core contract: a published swing is frozen forever."""

    def test_every_prefix_is_a_prefix_of_the_final_confirmed_history(self):
        for scenario, candles in all_benchmarks().items():
            for name, factory in FACTORIES:
                with self.subTest(scenario=scenario, detector=name):
                    self.assertEqual(repaint_violations(candles, factory), [])

    def test_confirmed_swing_identity_never_changes_as_candles_arrive(self):
        candles = false_breakout()
        for name, factory in FACTORIES:
            with self.subTest(detector=name):
                seen = {}
                for length, events in replay_prefixes(candles, factory):
                    for position, swing in enumerate(confirmed_only(events)):
                        if position in seen:
                            self.assertEqual(
                                seen[position], swing,
                                "swing %d changed after %d candles" % (position, length))
                        else:
                            seen[position] = swing

    def test_confirmed_count_never_decreases(self):
        candles = clean_uptrend()
        for name, factory in FACTORIES:
            with self.subTest(detector=name):
                counts = [len(confirmed_only(events))
                          for _, events in replay_prefixes(candles, factory)]
                self.assertEqual(counts, sorted(counts))

    def test_the_probe_catches_a_genuinely_repainting_baseline(self):
        """Negative control.

        The streaming detectors cannot repaint by construction, so a probe that
        only ever runs against them proves nothing. The realistic failure mode
        is a charting ZigZag that publishes its provisional last leg; that
        baseline must fail this probe, or the probe is not measuring anything.
        """
        for scenario in ("clean_uptrend", "choppy_range", "false_breakout"):
            candles = all_benchmarks()[scenario]
            with self.subTest(scenario=scenario):
                violations = prefix_violations(
                    candles, lambda series: batch_zigzag_swings(series, "0.005"))
                self.assertTrue(
                    violations,
                    "the anti-repaint probe failed to detect a repainting baseline")

    def test_provisional_candidate_is_not_published_as_a_swing(self):
        candles = clean_uptrend()
        detector = ZigZagSwingDetector("0.015")
        published = [e for c in candles for e in detector.process(c)
                     if e.status is SwingStatus.CONFIRMED]
        provisional = detector.provisional_candidate()
        self.assertIsNotNone(provisional)
        self.assertNotIn(provisional["price"], [e.price for e in published])


class ReplayEquivalenceTests(unittest.TestCase):

    def test_replay_equals_live_incremental_processing(self):
        for scenario, candles in all_benchmarks().items():
            for name, factory in FACTORIES:
                with self.subTest(scenario=scenario, detector=name):
                    batch = replay(candles, factory)
                    live, detector = [], factory()
                    for candle in candles:          # one candle at a time, as live
                        live.extend(detector.process(candle))
                    self.assertEqual(batch, tuple(live))

    def test_identical_input_produces_identical_output_twice(self):
        for scenario, candles in all_benchmarks().items():
            for name, factory in FACTORIES:
                with self.subTest(scenario=scenario, detector=name):
                    self.assertEqual(replay(candles, factory), replay(candles, factory))

    def test_detector_sees_a_generator_without_needing_the_series(self):
        candles = clean_uptrend()
        streamed = replay((c for c in candles), lambda: ZigZagSwingDetector("0.005"))
        self.assertEqual(streamed, replay(candles, lambda: ZigZagSwingDetector("0.005")))

    def test_future_suffix_cannot_change_an_earlier_evaluation(self):
        candles = false_breakout()
        cut = 25
        early = replay(candles[:cut], lambda: ZigZagSwingDetector("0.015"))
        full = replay(candles, lambda: ZigZagSwingDetector("0.015"))
        self.assertEqual(early, full[:len(early)])


class CausalInvariantTests(unittest.TestCase):

    def test_swing_time_never_follows_confirmation_and_confirmation_is_its_knowledge_time(self):
        for scenario, candles in all_benchmarks().items():
            for name, factory in FACTORIES:
                for event in replay(candles, factory):
                    self.assertLessEqual(event.swing_time, event.observed_at)
                    if event.status is SwingStatus.CONFIRMED:
                        self.assertEqual(event.confirmed_at, event.observed_at)
                        self.assertLessEqual(event.swing_time, event.confirmed_at)

    def test_swing_time_may_precede_confirmed_at(self):
        events = replay(false_breakout(), lambda: ZigZagSwingDetector("0.015"))
        delayed = [e for e in events
                   if e.status is SwingStatus.CONFIRMED and e.swing_time < e.confirmed_at]
        self.assertTrue(delayed, "expected at least one delayed confirmation")

    def test_reversal_family_never_confirms_a_swing_from_its_own_candle(self):
        """OHLC records no path between a candle's high and low."""
        for scenario, candles in all_benchmarks().items():
            for name, factory in REVERSAL:
                for event in replay(candles, factory):
                    if event.status is SwingStatus.CONFIRMED:
                        with self.subTest(scenario=scenario, detector=name):
                            self.assertGreaterEqual(event.confirmation_delay_bars, 1)

    def test_reversal_family_confirms_at_most_one_swing_per_candle(self):
        for scenario, candles in all_benchmarks().items():
            for name, factory in REVERSAL:
                with self.subTest(scenario=scenario, detector=name):
                    stamps = [e.confirmed_at for e in replay(candles, factory)
                              if e.status is SwingStatus.CONFIRMED]
                    self.assertEqual(len(stamps), len(set(stamps)))

    def test_reversal_family_swing_times_strictly_increase_and_alternate(self):
        for scenario, candles in all_benchmarks().items():
            for name, factory in REVERSAL:
                with self.subTest(scenario=scenario, detector=name):
                    confirmed = [e for e in replay(candles, factory)
                                 if e.status is SwingStatus.CONFIRMED]
                    times = [e.swing_time for e in confirmed]
                    self.assertEqual(times, sorted(times))
                    self.assertEqual(len(times), len(set(times)))
                    sides = [e.side for e in confirmed]
                    self.assertFalse([a for a, b in zip(sides, sides[1:]) if a is b])

    def test_no_swing_identity_is_ever_published_twice(self):
        for scenario, candles in all_benchmarks().items():
            for name, factory in FACTORIES:
                with self.subTest(scenario=scenario, detector=name):
                    swings = confirmed_only(replay(candles, factory))
                    self.assertEqual(len(swings), len(set(swings)))

    def test_fractal_confirmation_delay_equals_its_width(self):
        for width in (1, 2, 3, 5):
            events = replay(clean_uptrend(), lambda w=width: FractalSwingDetector(width=w))
            delays = {e.confirmation_delay_bars for e in events
                      if e.status is SwingStatus.CONFIRMED}
            self.assertIn(delays, ({width}, set()))

    def test_atr_detector_confirms_nothing_before_its_warmup(self):
        candles = clean_uptrend()
        events = replay(candles, lambda: AtrReversalDetector(period=20, multiplier="1.0"))
        confirmed = [e for e in events if e.status is SwingStatus.CONFIRMED]
        self.assertTrue(confirmed)
        earliest = candles[19].close_time
        self.assertTrue(all(e.confirmed_at >= earliest for e in confirmed))


class InputDisciplineTests(unittest.TestCase):

    def _candle(self, offset, price="60000", timeframe=TIMEFRAME, symbol=SYMBOL):
        base = clean_uptrend()[0]
        value = Decimal(price)
        return Candle(symbol=symbol, timeframe=timeframe,
                      close_time=base.close_time + timedelta(minutes=15) * offset,
                      open=value, high=value + 10, low=value - 10, close=value,
                      volume=Decimal("1"))

    def test_repeated_or_backwards_candles_are_rejected(self):
        detector = ZigZagSwingDetector("0.005")
        detector.process(self._candle(0))
        detector.process(self._candle(1))
        with self.assertRaises(ValueError):
            detector.process(self._candle(1))
        with self.assertRaises(ValueError):
            detector.process(self._candle(0))

    def test_a_detector_refuses_a_second_symbol_or_timeframe(self):
        detector = ZigZagSwingDetector("0.005")
        detector.process(self._candle(0))
        with self.assertRaises(ValueError):
            detector.process(self._candle(1, symbol="ETH-USDT"))
        with self.assertRaises(ValueError):
            detector.process(self._candle(2, timeframe="1H"))

    def test_non_candle_input_is_rejected(self):
        detector = ZigZagSwingDetector("0.005")
        for bad in (None, "60000", 60000, [self._candle(0)]):
            with self.assertRaises(ValueError):
                detector.process(bad)

    def test_open_candles_cannot_exist_so_cannot_be_detected(self):
        with self.assertRaises(ValueError):
            Candle(symbol=SYMBOL, timeframe=TIMEFRAME,
                   close_time=clean_uptrend()[0].close_time, open=Decimal("1"),
                   high=Decimal("2"), low=Decimal("1"), close=Decimal("1"),
                   volume=Decimal("1"), closed=False)

    def test_each_timeframe_keeps_independent_state(self):
        fast, slow = ZigZagSwingDetector("0.005"), ZigZagSwingDetector("0.005")
        for index, candle in enumerate(clean_uptrend()):
            fast.process(candle)
            if index % 4 == 0:
                slow.process(Candle(symbol=candle.symbol, timeframe="1H",
                                    close_time=candle.close_time, open=candle.open,
                                    high=candle.high, low=candle.low,
                                    close=candle.close, volume=candle.volume))
        self.assertEqual({e.timeframe for e in replay(clean_uptrend(),
                                                      lambda: ZigZagSwingDetector("0.005"))},
                         {TIMEFRAME})

    def test_detector_rejects_bad_parameters(self):
        for bad in ("0", "1", "-0.1"):
            with self.assertRaises(ValueError):
                ZigZagSwingDetector(bad)
            with self.assertRaises(ValueError):
                DirectionalChangeDetector(bad)
        for bad in (0, -1, 2.5):
            with self.assertRaises(ValueError):
                FractalSwingDetector(width=bad)
        with self.assertRaises(ValueError):
            AtrReversalDetector(period=0)
        with self.assertRaises(ValueError):
            AtrReversalDetector(multiplier="0")


class EventContractTests(unittest.TestCase):

    def _kwargs(self, **overrides):
        candle = clean_uptrend()[4]
        base = dict(symbol=SYMBOL, timeframe=TIMEFRAME, detector="test",
                    event_type=SwingEventType.SWING_CONFIRMED, side=SwingSide.HIGH,
                    status=SwingStatus.CONFIRMED, price=Decimal("60000"),
                    swing_time=candle.close_time, observed_at=candle.close_time,
                    confirmed_at=candle.close_time, confirmation_delay_bars=0)
        base.update(overrides)
        return base

    def test_a_valid_confirmation_is_accepted(self):
        event = SwingEvent(**self._kwargs())
        self.assertEqual(ConfirmedSwing.from_event(event).price, Decimal("60000"))

    def test_confirmation_must_be_published_at_its_knowledge_time(self):
        candle = clean_uptrend()[6]
        with self.assertRaises(ValueError):
            SwingEvent(**self._kwargs(confirmed_at=candle.close_time))

    def test_swing_time_after_observed_at_is_rejected(self):
        later = clean_uptrend()[9].close_time
        with self.assertRaises(ValueError):
            SwingEvent(**self._kwargs(swing_time=later))

    def test_status_and_event_type_must_agree(self):
        with self.assertRaises(ValueError):
            SwingEvent(**self._kwargs(status=SwingStatus.CANDIDATE))
        with self.assertRaises(ValueError):
            SwingEvent(**self._kwargs(event_type=SwingEventType.CANDIDATE_CREATED))

    def test_unconfirmed_events_cannot_carry_confirmation_fields(self):
        with self.assertRaises(ValueError):
            SwingEvent(**self._kwargs(event_type=SwingEventType.CANDIDATE_CREATED,
                                      status=SwingStatus.CANDIDATE))

    def test_prices_must_be_positive_finite_decimals(self):
        for bad in (Decimal("0"), Decimal("-1"), Decimal("NaN")):
            with self.assertRaises(ValueError):
                SwingEvent(**self._kwargs(price=bad))

    def test_only_a_confirmed_event_has_a_confirmed_identity(self):
        candidate = SwingEvent(**self._kwargs(
            event_type=SwingEventType.CANDIDATE_CREATED, status=SwingStatus.CANDIDATE,
            confirmed_at=None, confirmation_delay_bars=None))
        with self.assertRaises(ValueError):
            ConfirmedSwing.from_event(candidate)


class BenchmarkAndReportingTests(unittest.TestCase):

    def test_benchmarks_are_deterministic_and_valid(self):
        first, second = all_benchmarks(), all_benchmarks()
        self.assertEqual(set(first), set(BENCHMARKS))
        for name, candles in first.items():
            with self.subTest(scenario=name):
                self.assertEqual(candles, second[name])
                self.assertTrue(len(candles) >= 40)
                times = [c.close_time for c in candles]
                self.assertEqual(times, sorted(times))
                self.assertEqual(len(times), len(set(times)))

    def test_false_breakout_sweep_is_wick_only(self):
        candles = false_breakout()
        peak = max(candles, key=lambda c: c.high)
        self.assertGreater(peak.high, max(c.close for c in candles))

    def test_wick_detector_sees_the_sweep_and_close_detector_cannot(self):
        candles = false_breakout()
        peak = max(candles, key=lambda c: c.high).high
        wick = [e.price for e in replay(candles, lambda: ZigZagSwingDetector("0.015"))
                if e.status is SwingStatus.CONFIRMED]
        close_only = [e.price for e in replay(candles, lambda: DirectionalChangeDetector("0.015"))
                      if e.status is SwingStatus.CONFIRMED]
        self.assertIn(peak, wick)
        self.assertNotIn(peak, close_only)

    def test_a_wide_threshold_suppresses_chop(self):
        candles = all_benchmarks()["choppy_range"]
        tight = evaluate(candles, lambda: ZigZagSwingDetector("0.005"), check_repaint=False)
        wide = evaluate(candles, lambda: ZigZagSwingDetector("0.015"), check_repaint=False)
        self.assertGreater(tight["confirmed"], wide["confirmed"])
        self.assertEqual(wide["confirmed"], 0)

    def test_metrics_report_zero_repaint_for_every_default_detector(self):
        for scenario, candles in all_benchmarks().items():
            for name, factory in FACTORIES:
                with self.subTest(scenario=scenario, detector=name):
                    self.assertEqual(evaluate(candles, factory)["repaint_violations"], 0)

    def test_event_table_renders_occurrence_and_knowledge_times(self):
        table = format_event_table(
            replay(false_breakout(), lambda: ZigZagSwingDetector("0.015")))
        self.assertIn("swing_time", table)
        self.assertIn("confirmed_at", table)
        self.assertIn("SWING_CONFIRMED", table)


class ProductionIsolationTests(unittest.TestCase):
    """Research must not reach into the decision pipeline."""

    def test_research_package_is_not_imported_by_production_modules(self):
        import pathlib
        import re
        root = pathlib.Path(__file__).resolve().parent.parent / "agent_trading"
        pattern = re.compile(r"^\s*(?:from|import)\s+\S*\bresearch\b", re.MULTILINE)
        offenders = [path.name for path in root.glob("*.py")
                     if pattern.search(path.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])

    def test_decision_pipeline_still_reports_no_configured_strategy(self):
        from agent_trading.components import DecisionRouter
        self.assertEqual(DecisionRouter().route(()),
                         {"action": "NO_TRADE", "reason": "STRATEGY_NOT_CONFIGURED"})


if __name__ == "__main__":
    unittest.main()
