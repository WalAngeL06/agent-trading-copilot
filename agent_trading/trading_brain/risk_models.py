"""Immutable risk contracts. All numerical defaults are provisional [H]."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from .models import TradeCandidate


@dataclass(frozen=True)
class RiskConfig:
    profile: str = 'STRUCTURE_BE'
    break_even_r: Decimal = Decimal('1')
    min_reward_risk: Decimal = Decimal('1')
    max_stop_distance: Decimal | None = None
    risk_per_trade: Decimal = Decimal('.01')
    stop_buffer: Decimal = Decimal('100')
    quantity_step: Decimal = Decimal('.00000001')

    def __post_init__(self):
        if self.profile not in ('STRUCTURE_BE', 'FIXED_SL_TP'):
            raise ValueError('unknown stop-management profile')
        for name in ('break_even_r', 'min_reward_risk', 'risk_per_trade',
                     'stop_buffer', 'quantity_step', 'max_stop_distance'):
            value = getattr(self, name)
            if name == 'max_stop_distance' and value is None:
                continue
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError(f'{name} must be a positive finite Decimal')
        if self.risk_per_trade > 1:
            raise ValueError('risk_per_trade must be at most 1')


@dataclass(frozen=True)
class SupportingZone:
    zone_id: str
    zone_type: str
    direction: str
    lower: Decimal
    upper: Decimal
    invalidation_level: Decimal
    validated_at: datetime
    symbol: str
    timeframe: str
    validated: bool = True
    fresh: bool = True
    source_ids: tuple[str, ...] = ('[H]-RISK-ZONE-001',)


@dataclass(frozen=True)
class RiskEvidence:
    entry: Decimal | None
    tp: Decimal | None
    profile: str
    break_even_trigger: str | None
    break_even_r: Decimal | None
    min_reward_risk: Decimal
    max_stop_distance: Decimal | None
    risk_per_trade: Decimal
    risk_budget: Decimal | None
    initial_stop_source: str | None = None
    supporting_zone_id: str | None = None
    supporting_zone_type: str | None = None
    invalidation_level: Decimal | None = None
    initial_stop: Decimal | None = None
    risk_distance: Decimal | None = None
    reward_distance: Decimal | None = None
    reward_risk_ratio: Decimal | None = None
    position_size: Decimal | None = None
    risk_amount: Decimal | None = None
    blocked_reason: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    zone_source_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ('[U-RISK-ENGINE-001]', '[H]-RISK-ENGINE-001')


@dataclass(frozen=True)
class ApprovedTradePlan:
    candidate: TradeCandidate
    entry: Decimal
    stop: Decimal
    tp: Decimal
    quantity: Decimal
    risk_budget: Decimal
    risk_amount: Decimal
    approved_at: datetime
    evidence: RiskEvidence
    source_ids: tuple[str, ...] = ('[U-RISK-ENGINE-001]', '[H]-RISK-ENGINE-001')

    @property
    def direction(self): return self.candidate.direction
    @property
    def observed_at(self): return self.approved_at


@dataclass(frozen=True)
class RiskDecision:
    status: str
    reason: str | None
    candidate: TradeCandidate
    observed_at: datetime
    evidence: RiskEvidence
    plan: ApprovedTradePlan | None = None
    source_ids: tuple[str, ...] = ('[U-RISK-ENGINE-001]', '[H]-RISK-ENGINE-001')


@dataclass(frozen=True)
class StopUpdate:
    observed_at: datetime
    previous_stop: Decimal
    new_stop: Decimal
    reason: str
    trigger: str | None = None
    threshold_r: Decimal | None = None
    measured_r: Decimal | None = None
    source_ids: tuple[str, ...] = ('[H]-RISK-ENGINE-001',)
