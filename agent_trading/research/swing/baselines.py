"""NON-CAUSAL baselines. Never use these for decisions; they exist to fail.

A charting ZigZag draws its last leg to the running extreme, which has not yet
been confirmed by any opposing movement. That last pivot then moves as new
candles arrive: the classic repaint. This module reproduces that behaviour so
the anti-repaint probe has a control that genuinely fails, which is the only
way to know the probe is measuring something.

The streaming detectors in `detectors` cannot repaint by construction, because
`process` is handed one candle and holds no future series. That structural
guarantee is worth stating, but a test that can never fail proves nothing on
its own -- hence this module.
"""

from .events import ConfirmedSwing, SwingStatus
from .detectors import ZigZagSwingDetector


def batch_zigzag_swings(candles, reversal_pct="0.005"):
    """[H] Charting-style ZigZag: confirmed pivots plus the provisional last leg.

    The trailing provisional pivot is exactly what repaints. Compare against
    `confirmed_only(replay(...))`, which publishes only confirmed swings.
    """
    ordered = tuple(candles)
    if not ordered:
        return ()
    detector = ZigZagSwingDetector(reversal_pct)
    swings = []
    for candle in ordered:
        for event in detector.process(candle):
            if event.status is SwingStatus.CONFIRMED:
                swings.append(ConfirmedSwing.from_event(event))
    provisional = detector.provisional_candidate()
    if provisional is not None:
        swings.append(ConfirmedSwing(
            symbol=provisional["symbol"], timeframe=provisional["timeframe"],
            side=provisional["side"], price=provisional["price"],
            swing_time=provisional["swing_time"],
            confirmed_at=ordered[-1].close_time))
    return tuple(swings)
