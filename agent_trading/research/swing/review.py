"""Human-review artifacts and multiplier benchmark for the production SwingEngine.

    python -m agent_trading.research.swing.review
    python -m agent_trading.research.swing.review --data tests/data --out runs/swing-review

Offline: reads saved candle JSONL, never the network. Produces one CSV per
timeframe so a person can judge whether the confirmed swings resemble
meaningful DD-style turning points. That judgement is the point; the metrics
below cannot make it.

Nothing here is [E] empirical validation of a trading rule.
"""

import argparse
import csv
from decimal import Decimal
from pathlib import Path

from ...swing import SwingConfig, SwingEngine, SwingStatus
from .fixtures import all_benchmarks, load_candle_json

DEFAULT_TIMEFRAMES = ("5m", "15m", "1H", "4H")
MULTIPLIERS = ("0.75", "1.0", "1.25", "1.5", "2.0")
ROW_FIELDS = ("side", "price", "swing_time", "confirmed_at",
              "confirmation_delay_bars", "atr", "threshold")


def swing_rows(candles, config):
    """Confirmed swings with the volatility context that produced them."""
    if not candles:
        return []
    engine = SwingEngine(candles[0].symbol, candles[0].timeframe, config)
    rows = []
    for event in engine.bootstrap(candles):
        if event.status is not SwingStatus.CONFIRMED:
            continue
        rows.append({
            "side": event.side.value,
            "price": str(event.price),
            "swing_time": event.swing_time.strftime("%Y-%m-%d %H:%M:%SZ"),
            "confirmed_at": event.confirmed_at.strftime("%Y-%m-%d %H:%M:%SZ"),
            "confirmation_delay_bars": event.confirmation_delay_bars,
            "atr": str(event.atr.quantize(Decimal("0.01"))),
            "threshold": str(event.threshold.quantize(Decimal("0.01"))),
        })
    return rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def profile(candles, config):
    """Behaviour summary for one series under one configuration."""
    rows = swing_rows(candles, config)
    delays = [row["confirmation_delay_bars"] for row in rows]
    sides = [row["side"] for row in rows]
    highs = max((Decimal(r["price"]) for r in rows if r["side"] == "HIGH"), default=None)
    series_high = max(c.high for c in candles)
    series_low = min(c.low for c in candles)
    lows = min((Decimal(r["price"]) for r in rows if r["side"] == "LOW"), default=None)
    return {
        "bars": len(candles),
        "confirmed": len(rows),
        "density_per_100": (Decimal(len(rows)) * 100 / Decimal(len(candles))
                            ).quantize(Decimal("0.1")),
        "delay_mean": (Decimal(sum(delays)) / Decimal(len(delays))).quantize(Decimal("0.1"))
                      if delays else None,
        "delay_max": max(delays) if delays else None,
        "alternation_violations": sum(1 for a, b in zip(sides, sides[1:]) if a == b),
        "captured_series_high": highs == series_high,
        "captured_series_low": lows == series_low,
    }


def load_series(data_dir, symbol="BTC-USDT", timeframes=DEFAULT_TIMEFRAMES):
    """Saved real candles, if collected. Absent files are skipped, never fetched."""
    series = {}
    for timeframe in timeframes:
        path = Path(data_dir) / ("%s_%s.jsonl" % (symbol.replace("-", "").lower(), timeframe))
        if path.is_file():
            series[timeframe] = load_candle_json(path, symbol, timeframe)
    return series


def multiplier_table(series, multipliers=MULTIPLIERS, atr_length=14):
    header = ("%-8s %-6s %6s %10s %9s %10s %9s %7s %7s"
              % ("series", "mult", "bars", "confirmed", "dens/100", "delay_mean",
                 "delay_max", "hi_hit", "lo_hit"))
    lines = [header, "-" * len(header)]
    for name, candles in series.items():
        for multiplier in multipliers:
            config = SwingConfig(atr_length=atr_length,
                                 atr_multiplier=Decimal(multiplier))
            result = profile(candles, config)
            lines.append("%-8s %-6s %6d %10d %9s %10s %9s %7s %7s" % (
                name, multiplier, result["bars"], result["confirmed"],
                result["density_per_100"],
                "-" if result["delay_mean"] is None else result["delay_mean"],
                "-" if result["delay_max"] is None else result["delay_max"],
                "yes" if result["captured_series_high"] else "no",
                "yes" if result["captured_series_low"] else "no"))
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="SwingEngine review artifacts (offline)")
    parser.add_argument("--data", default="tests/data", help="saved candle JSONL directory")
    parser.add_argument("--out", default="runs/swing-review", help="CSV output directory")
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--atr-length", type=int, default=14)
    parser.add_argument("--multiplier", default="1.0", help="multiplier used for the CSVs")
    args = parser.parse_args(argv)

    real = load_series(args.data, args.symbol)
    synthetic = all_benchmarks()

    print("# SwingEngine v0.1 multiplier benchmark  (ATR length %d)" % args.atr_length)
    print("# Confirmation is a later close beyond the wick extreme by "
          "ATR*multiplier. Hypothesis [H], not a DD rule.\n")
    if real:
        print("## real BTC-USDT (saved offline candles)")
        print(multiplier_table(real, atr_length=args.atr_length))
    else:
        print("## real BTC-USDT: no saved candles in %s "
              "(run agent_trading.swing_smoke to collect)\n" % args.data)
    print("## synthetic benchmarks")
    print(multiplier_table(synthetic, atr_length=args.atr_length))

    config = SwingConfig(atr_length=args.atr_length,
                         atr_multiplier=Decimal(args.multiplier))
    out = Path(args.out)
    written = []
    for name, candles in {**real, **synthetic}.items():
        path = out / ("swings_%s_mult%s.csv" % (name, args.multiplier))
        written.append((str(path), write_csv(path, swing_rows(candles, config))))
    print("## review artifacts (multiplier %s)" % args.multiplier)
    for path, count in written:
        print("%-58s %3d confirmed swings" % (path, count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
