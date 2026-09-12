"""Immutable PAPER-only vocabulary. Provisional semantics: trading-brain-v0.1."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from ..swing import ConfirmedSwing, SwingSide, SwingConfig

@dataclass(frozen=True)
class BrainConfig:
    swing: SwingConfig = SwingConfig()
    boundary_proximity: Decimal = Decimal('500')
    stop_buffer: Decimal = Decimal('100')
    equity: Decimal = Decimal('10000')
    risk_fraction: Decimal = Decimal('.01')
    quantity_step: Decimal = Decimal('.00000001')
    target: str = 'EQ'

    def __post_init__(self):
        if not isinstance(self.swing, SwingConfig):
            raise ValueError('swing must be SwingConfig')
        for name in ('boundary_proximity', 'stop_buffer', 'equity', 'risk_fraction', 'quantity_step'):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError(f'{name} must be a finite Decimal')
            if value < 0 or (name != 'boundary_proximity' and value == 0):
                raise ValueError(f'{name} is out of bounds')
        if self.risk_fraction > 1 or self.target not in ('EQ', 'BOUNDARY'):
            raise ValueError('invalid risk fraction or target')

@dataclass(frozen=True)
class SwingHigh:
    raw: ConfirmedSwing
    def __post_init__(self):
        if self.raw.side is not SwingSide.HIGH:
            raise ValueError('SwingHigh requires raw HIGH')
    @property
    def price(self): return self.raw.price
    @property
    def swing_time(self): return self.raw.swing_time
    @property
    def confirmed_at(self): return self.raw.confirmed_at

@dataclass(frozen=True)
class SwingLow:
    raw: ConfirmedSwing
    def __post_init__(self):
        if self.raw.side is not SwingSide.LOW:
            raise ValueError('SwingLow requires raw LOW')
    @property
    def price(self): return self.raw.price
    @property
    def swing_time(self): return self.raw.swing_time
    @property
    def confirmed_at(self): return self.raw.confirmed_at

@dataclass(frozen=True)
class ValidLow:
    swing: SwingLow
    target: SwingHigh
    confirmed_at: datetime
    source_ids: tuple[str, ...] = ('[U-TRADING-BRAIN-001]', '[H]-STRUCTURE-001')
    @property
    def price(self): return self.swing.price

@dataclass(frozen=True)
class ValidHigh:
    swing: SwingHigh
    target: SwingLow
    confirmed_at: datetime
    source_ids: tuple[str, ...] = ('[U-TRADING-BRAIN-001]', '[H]-STRUCTURE-001')
    @property
    def price(self): return self.swing.price

@dataclass(frozen=True)
class RangeState:
    low: ValidLow
    high: ValidHigh
    phase: str = 'WAIT_LOW_TOUCH'
    low_touch: SwingLow | None = None
    high_touch: SwingHigh | None = None
    confirmed_at: datetime | None = None
    source_ids: tuple[str, ...] = ('[U-TRADING-BRAIN-001]', '[H]-RANGE-001')
    @property
    def range_low(self): return self.low.price
    @property
    def range_high(self): return self.high.price
    @property
    def eq(self): return (self.range_high + self.range_low) / Decimal(2)

@dataclass(frozen=True)
class ManipulationEvent:
    direction: str | None
    phase: str
    extreme: Decimal | None
    swept_at: datetime
    observed_at: datetime
    reclaimed_at: datetime | None = None
    source_ids: tuple[str, ...] = ('[U-TRADING-BRAIN-001]', '[H]-MANIPULATION-001')

@dataclass(frozen=True)
class FVG:
    direction: str
    lower: Decimal
    upper: Decimal
    formed_from: tuple[datetime, datetime, datetime]
    observed_at: datetime
    kind: str = 'FVG'
    origin_at: datetime | None = None
    source_ids: tuple[str, ...] = ('[H]-GAP-001',)

@dataclass(frozen=True)
class TradeCandidate:
    direction: str
    entry: Decimal
    stop: Decimal
    tp: Decimal
    observed_at: datetime
    evidence_ids: tuple[str, ...]
    planned_quantity: Decimal | None = None
    risk_budget: Decimal | None = None
    source_ids: tuple[str, ...] = ('[U-TRADING-BRAIN-001]', '[H]-PLAN-001')

@dataclass(frozen=True)
class PaperTrade:
    direction: str
    entry: Decimal
    stop: Decimal
    tp: Decimal
    quantity: Decimal
    risk_budget: Decimal
    risk_amount: Decimal
    opened_at: datetime
    candidate: TradeCandidate
    filled_at: datetime | None = None
    mode: str = 'PAPER'
    status: str = 'OPEN'
    exit_price: Decimal | None = None
    closed_at: datetime | None = None
    pnl: Decimal | None = None
    source_ids: tuple[str, ...] = ('[H]-RISK-001', '[H]-PAPER-001')

@dataclass(frozen=True)
class BrokerEvent:
    kind: str
    observed_at: datetime
    payload: PaperTrade | TradeCandidate

@dataclass(frozen=True)
class BrainEvent:
    id: str
    kind: str
    observed_at: datetime
    payload: object
    evidence_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
