"""Swing-quality diagnostics. Deliberately no PnL, no profitability claim.

Every number here describes detector behaviour on a synthetic benchmark. None
of it validates a trading rule (SOURCE_REGISTRY: [E] requires real evidence and
a stated methodology; these fixtures are neither).
"""

from decimal import Decimal

from .events import SwingEventType, SwingSide
from .replay import confirmed_only, replay, replay_prefixes


def prefix_violations(candles, swing_fn, start=1):
    """Every prefix's published swing history must be a prefix of the final one.

    A violation means a published swing was moved, repriced, retimed, reordered
    or removed by a later candle: the anti-repaint contract is broken. This
    works for any function from a candle series to published swings, so a
    non-causal baseline can be held to the same standard.
    """
    ordered = tuple(candles)
    final = swing_fn(ordered)
    violations = []
    for length in range(start, len(ordered) + 1):
        prefix = swing_fn(ordered[:length])
        if prefix != final[:len(prefix)]:
            violations.append({
                "prefix_length": length,
                "prefix_published": len(prefix),
                "first_mismatch": _first_mismatch(prefix, final),
            })
    return violations


def repaint_violations(candles, detector_factory):
    """Anti-repaint probe for a streaming detector."""
    return prefix_violations(
        candles, lambda series: confirmed_only(replay(series, detector_factory)))


def _first_mismatch(prefix, final):
    for index, item in enumerate(prefix):
        if index >= len(final):
            return {"index": index, "prefix": item, "final": None}
        if item != final[index]:
            return {"index": index, "prefix": item, "final": final[index]}
    return None


def _global_extremes(candles):
    high = max(candles, key=lambda c: (c.high, c.close_time))
    low = min(candles, key=lambda c: (c.low, c.close_time))
    return high.close_time, low.close_time


def evaluate(candles, detector_factory, check_repaint=True):
    """Behavioural profile of one detector on one benchmark series."""
    ordered = tuple(candles)
    events = replay(ordered, detector_factory)
    confirmed = [e for e in events if e.event_type is SwingEventType.SWING_CONFIRMED]
    delays = [e.confirmation_delay_bars for e in confirmed]
    counts = {kind: 0 for kind in SwingEventType}
    for event in events:
        counts[event.event_type] += 1
    high_time, low_time = _global_extremes(ordered)
    captured = {
        "global_high": any(e.side is SwingSide.HIGH and e.swing_time == high_time
                           for e in confirmed),
        "global_low": any(e.side is SwingSide.LOW and e.swing_time == low_time
                          for e in confirmed),
    }
    violations = repaint_violations(ordered, detector_factory) if check_repaint else []
    sides = [e.side for e in confirmed]
    return {
        "bars": len(ordered),
        "confirmed": len(confirmed),
        "density_per_100": (Decimal(len(confirmed)) * 100 / Decimal(len(ordered))
                            ).quantize(Decimal("0.1")) if ordered else Decimal(0),
        "candidate_created": counts[SwingEventType.CANDIDATE_CREATED],
        "candidate_updated": counts[SwingEventType.CANDIDATE_UPDATED],
        "candidate_discarded": counts[SwingEventType.CANDIDATE_DISCARDED],
        "delay_mean": (Decimal(sum(delays)) / Decimal(len(delays))).quantize(Decimal("0.1"))
                      if delays else None,
        "delay_max": max(delays) if delays else None,
        "first_confirmation_bar": next(
            (i for i, e in enumerate(events) if e.event_type is SwingEventType.SWING_CONFIRMED),
            None) if confirmed else None,
        "alternation_violations": sum(1 for a, b in zip(sides, sides[1:]) if a is b),
        "captured_global_high": captured["global_high"],
        "captured_global_low": captured["global_low"],
        "repaint_violations": len(violations),
    }


_COLUMNS = (("detector", "%-22s"), ("bars", "%5s"), ("confirmed", "%10s"),
            ("density_per_100", "%8s"), ("candidate_updated", "%10s"),
            ("delay_mean", "%11s"), ("delay_max", "%10s"),
            ("alternation_violations", "%7s"), ("captured_global_high", "%7s"),
            ("captured_global_low", "%7s"), ("repaint_violations", "%8s"))

_HEADINGS = ("detector", "bars", "confirmed", "dens/100", "cand_upd", "delay_mean",
             "delay_max", "alt_v", "hi_hit", "lo_hit", "repaint")


def format_table(rows):
    """rows: sequence of (detector_name, metrics dict)."""
    fmt = " ".join(spec for _, spec in _COLUMNS)
    lines = [fmt % _HEADINGS]
    lines.append("-" * len(lines[0]))
    for name, metrics in rows:
        values = [name]
        for key, _ in _COLUMNS[1:]:
            value = metrics[key]
            if isinstance(value, bool):
                value = "yes" if value else "no"
            values.append("-" if value is None else str(value))
        lines.append(fmt % tuple(values))
    return "\n".join(lines)
