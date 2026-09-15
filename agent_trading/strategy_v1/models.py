"""Immutable Strategy V1 vocabulary. PAPER only; no exchange write exists here."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..models import Candle
from ..trading_brain.models import FVG, ValidHigh, ValidLow, SwingLow

BIAS_STATES = ('NEUTRAL', 'BULLISH_CONTINUATION', 'BULLISH_REVERSAL', 'LONG_DISABLED')
FVG_STATES = ('FRESH', 'TOUCHED', 'INVALIDATED')


@dataclass(frozen=True)
class BiasBreak:
    """Auditable evidence for one closed-candle structural break on bias_tf."""
    direction: str
    previous_bias: str
    new_bias: str
    broken_level_id: str | None
    broken_price: Decimal
    break_candle: Candle
    close_price: Decimal
    confirmed_at: datetime
    source_ids: tuple[str, ...] = ('[U-STRATEGY-V1-001]', '[H]-SV1-BIAS-001')


@dataclass(frozen=True)
class BiasSnapshot:
    state: str
    long_permission: bool
    current_valid_high: ValidHigh | None = None
    current_valid_low: ValidLow | None = None
    past_valid_high: ValidHigh | None = None
    past_valid_low: ValidLow | None = None
    last_break: BiasBreak | None = None


@dataclass(frozen=True)
class TrackedFvg:
    """A causal gap plus its lifecycle state. Freshness rule is [H]-SV1-FRESH-001."""
    gap_id: str
    gap: FVG
    state: str = 'FRESH'
    touched_at: datetime | None = None
    invalidated_at: datetime | None = None

    @property
    def direction(self): return self.gap.direction
    @property
    def lower(self): return self.gap.lower
    @property
    def upper(self): return self.gap.upper
    @property
    def observed_at(self): return self.gap.observed_at
    @property
    def formed_at(self): return self.gap.formed_from[0]
    @property
    def fresh(self): return self.state == 'FRESH'


@dataclass(frozen=True)
class EntryPlan:
    """A selected primary FVG plus the structural protection chosen beneath it."""
    primary: TrackedFvg
    entry_level: str
    entry_price: Decimal
    target: Decimal
    stop_source: str
    secondary: TrackedFvg | None
    protecting_swing: SwingLow | None
    protecting_price: Decimal | None
    observed_at: datetime
    source_ids: tuple[str, ...] = ('[U-STRATEGY-V1-001]', '[H]-SV1-ENTRY-001')


@dataclass(frozen=True)
class PositionExit:
    """One realised slice of a single logical trade."""
    kind: str                       # PARTIAL_TP | RANGE_HIGH | RUNNER | STOP
    quantity: Decimal
    exit_price: Decimal
    realized_pnl: Decimal
    remaining_quantity: Decimal
    observed_at: datetime
    trigger_r: Decimal | None = None
    target_price: Decimal | None = None
    source_ids: tuple[str, ...] = ('[U-STRATEGY-V1-001]', '[H]-SV1-PARTIAL-001')


@dataclass(frozen=True)
class PositionLedger:
    """Accounting for one logical trade across every partial exit.

    `initial_r` is frozen at the fill and never re-derived, so break-even,
    trailing and realised partials cannot move a partial target price.
    """
    original_quantity: Decimal
    initial_r: Decimal
    runner_fraction: Decimal
    runner_target_quantity: Decimal
    remaining_quantity: Decimal
    exits: tuple[PositionExit, ...] = ()
    filled_r: tuple[Decimal, ...] = ()
    partials_cancelled_at: datetime | None = None
    range_high_done: bool = False
    source_ids: tuple[str, ...] = ('[U-STRATEGY-V1-001]', '[H]-SV1-PARTIAL-001')

    def of_kind(self, kind):
        return tuple(exit for exit in self.exits if exit.kind == kind)

    @property
    def partial_exits(self):
        return self.of_kind('PARTIAL_TP')

    @property
    def range_high_exit(self):
        found = self.of_kind('RANGE_HIGH')
        return found[0] if found else None

    @property
    def runner_exit(self):
        found = self.of_kind('RUNNER') or self.of_kind('STOP')
        return found[-1] if found else None

    @property
    def realized_quantity(self):
        return sum((exit.quantity for exit in self.exits), Decimal(0))

    @property
    def total_realized_pnl(self):
        return sum((exit.realized_pnl for exit in self.exits), Decimal(0))

    @property
    def runner_open(self):
        return self.range_high_done and self.remaining_quantity > 0

    @property
    def has_upside_target(self):
        """A runner is managed by its stop alone: no fixed target survives."""
        return not self.range_high_done


@dataclass(frozen=True)
class StopProtection:
    """Auditable record of one protective stop move. Stops only ever tighten."""
    kind: str
    old_stop: Decimal
    new_stop: Decimal
    structural_reference: str
    reference_price: Decimal | None
    confirmed_at: datetime | None
    observed_at: datetime
    source_ids: tuple[str, ...] = ('[U-STRATEGY-V1-001]', '[H]-SV1-TRAIL-001')


@dataclass(frozen=True)
class CapitalPolicy:
    """Deterministic idle-capital state. This module performs no OKX write."""
    capital_idle: bool
    desired_capital_policy: str
    reason: str
    observed_at: datetime | None = None
    source_ids: tuple[str, ...] = ('[U-STRATEGY-V1-001]', '[H]-SV1-CAPITAL-001')


@dataclass(frozen=True)
class StrategyEvent:
    id: str
    kind: str
    timeframe: str
    observed_at: datetime
    payload: object
    evidence_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
