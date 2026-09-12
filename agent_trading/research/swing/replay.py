"""Causal replay harness.

There is exactly one execution path: candles are revealed one at a time, in
chronological order, to a stateful detector. Historical replay and live
incremental processing are therefore the same code, which is what makes
'replay result == streaming result' a structural property rather than a test
that could drift.

Detectors are stateful, so every run takes a factory and builds a fresh one.
"""

from .events import ConfirmedSwing, SwingStatus


def replay(candles, detector_factory):
    """Reveal each candle once, in order, and collect the emitted events."""
    detector = detector_factory()
    events = []
    for candle in candles:
        events.extend(detector.process(candle))
    return tuple(events)


def replay_prefixes(candles, detector_factory, start=1):
    """Yield (prefix_length, events) for every prefix, each from a fresh run.

    This is the anti-repaint probe: it reconstructs what the detector could
    have known at each point in history without ever showing it a later candle.
    """
    ordered = tuple(candles)
    if type(start) is not int or start < 1:
        raise ValueError("prefix start must be a positive integer")
    for length in range(start, len(ordered) + 1):
        yield length, replay(ordered[:length], detector_factory)


def confirmed_only(events):
    """The immutable confirmed-swing identities, in publication order."""
    return tuple(ConfirmedSwing.from_event(event) for event in events
                 if event.status is SwingStatus.CONFIRMED)


def _clock(value):
    return value.strftime("%Y-%m-%d %H:%M") if value is not None else "-"


def format_event_table(events, limit=None):
    """Reviewable event history: what was known, and when it became knowable."""
    header = ("%-16s %-6s %-22s %-5s %-12s %-16s %-16s %5s"
              % ("observed_at", "tf", "event", "side", "price", "swing_time",
                 "confirmed_at", "delay"))
    lines = [header, "-" * len(header)]
    selected = events if limit is None else events[:limit]
    for event in selected:
        lines.append("%-16s %-6s %-22s %-5s %-12s %-16s %-16s %5s" % (
            _clock(event.observed_at), event.timeframe, event.event_type.value,
            event.side.value, event.price, _clock(event.swing_time),
            _clock(event.confirmed_at),
            "-" if event.confirmation_delay_bars is None else event.confirmation_delay_bars))
    if limit is not None and len(events) > limit:
        lines.append("... %d more events" % (len(events) - limit))
    return "\n".join(lines)
