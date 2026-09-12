"""Causal swing-detection R&D. Not wired into the strategy/decision pipeline.

Every detector here is a project hypothesis [H]; none is a DD-confirmed rule.
See docs/specs/swing-engine-rnd-v0.1.md.
"""

from .events import (SwingEvent, SwingEventType, SwingSide, SwingStatus,
                     ConfirmedSwing)
from .detectors import (CausalSwingDetector, FractalSwingDetector,
                        ZigZagSwingDetector, DirectionalChangeDetector,
                        AtrReversalDetector, default_detectors)
from .replay import replay, replay_prefixes, confirmed_only, format_event_table

__all__ = ["SwingEvent", "SwingEventType", "SwingSide", "SwingStatus",
           "ConfirmedSwing", "CausalSwingDetector", "FractalSwingDetector",
           "ZigZagSwingDetector", "DirectionalChangeDetector",
           "AtrReversalDetector", "default_detectors", "replay",
           "replay_prefixes", "confirmed_only", "format_event_table"]
