"""Research comparison runner.

    python -m agent_trading.research.swing.compare
    python -m agent_trading.research.swing.compare --candles saved_btc_15m.jsonl

Offline by default. Prints one behaviour table per benchmark, a parameter
sensitivity sweep and a sample causal event history. Produces no trading
decision and touches no production state.
"""

import argparse
from decimal import Decimal

from .detectors import (AtrReversalDetector, DirectionalChangeDetector,
                        FractalSwingDetector, ZigZagSwingDetector,
                        default_detector_factories)
from .baselines import batch_zigzag_swings
from .fixtures import all_benchmarks, load_candle_json
from .metrics import evaluate, format_table, prefix_violations, repaint_violations
from .replay import format_event_table, replay


def _scenario_tables(scenarios, factories, check_repaint=True):
    blocks = []
    for name, candles in scenarios.items():
        rows = [(label, evaluate(candles, factory, check_repaint=check_repaint))
                for label, factory in factories]
        blocks.append("### %s  (%d candles)\n%s" % (name, len(candles), format_table(rows)))
    return blocks


def _sensitivity(scenarios):
    lines = ["### parameter sensitivity (confirmed swing count)"]
    header = "%-22s %s" % ("detector", " ".join("%-18s" % n for n in scenarios))
    lines.append(header)
    lines.append("-" * len(header))
    sweeps = [("zigzag", ZigZagSwingDetector, "reversal_pct",
               ("0.002", "0.005", "0.010", "0.015", "0.030")),
              ("dc", DirectionalChangeDetector, "theta",
               ("0.002", "0.005", "0.010", "0.015", "0.030")),
              ("fractal", FractalSwingDetector, "width", (1, 2, 3, 5, 8))]
    for label, cls, key, values in sweeps:
        for value in values:
            counts = []
            for candles in scenarios.values():
                events = replay(candles, lambda c=cls, k=key, v=value: c(**{k: v}))
                counts.append(sum(1 for e in events if e.confirmed_at is not None))
            lines.append("%-22s %s" % ("%s %s=%s" % (label, key, value),
                                       " ".join("%-18s" % c for c in counts)))
    for mult in ("1.0", "1.5", "2.5"):
        counts = []
        for candles in scenarios.values():
            events = replay(candles, lambda m=mult: AtrReversalDetector(period=14, multiplier=m))
            counts.append(sum(1 for e in events if e.confirmed_at is not None))
        lines.append("%-22s %s" % ("atr p=14 x=%s" % mult,
                                   " ".join("%-18s" % c for c in counts)))
    return "\n".join(lines)


def _repaint_contrast(scenarios):
    """Causal streaming vs a charting ZigZag that publishes its provisional leg."""
    lines = ["### anti-repaint: causal streaming vs non-causal batch baseline",
             "%-22s %8s %16s %18s" % ("scenario", "bars", "streaming_repaint",
                                      "batch_repaint")]
    lines.append("-" * len(lines[1]))
    factories = default_detector_factories()
    for name, candles in scenarios.items():
        streaming = sum(len(repaint_violations(candles, f)) for _, f in factories)
        batch = len(prefix_violations(candles,
                                      lambda s: batch_zigzag_swings(s, "0.005")))
        lines.append("%-22s %8d %16d %18d" % (name, len(candles), streaming, batch))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare causal swing detectors")
    parser.add_argument("--candles", help="optional saved candle JSON/JSONL, offline")
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--events", default="zigzag_0.005",
                        help="detector whose event history is printed")
    parser.add_argument("--event-limit", type=int, default=30)
    args = parser.parse_args(argv)

    factories = default_detector_factories()
    scenarios = all_benchmarks()
    print("# Causal swing detector comparison")
    print("# Synthetic benchmarks; every detector is a hypothesis [H], not a DD rule.\n")
    print("\n\n".join(_scenario_tables(scenarios, factories)))
    print()
    print(_repaint_contrast(scenarios))
    print()
    print(_sensitivity(scenarios))

    if args.candles:
        real = {"saved:%s" % args.candles:
                load_candle_json(args.candles, args.symbol, args.timeframe)}
        print("\n\n# Saved-candle run (offline file, no network)\n")
        print("\n\n".join(_scenario_tables(real, factories)))
        scenarios = {**scenarios, **real}

    chosen = next((f for label, f in factories if label == args.events), None)
    if chosen is not None:
        target = "false_breakout" if "false_breakout" in scenarios else next(iter(scenarios))
        print("\n\n# Causal event history — %s on %s" % (args.events, target))
        print("# swing_time is when the extreme printed; confirmed_at is when it "
              "became knowable.\n")
        print(format_event_table(replay(scenarios[target], chosen), limit=args.event_limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
