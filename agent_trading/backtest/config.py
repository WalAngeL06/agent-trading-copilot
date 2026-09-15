"""Backtest run configuration. Owns no strategy rule of its own.

Every strategy decision comes from the production `StrategyProfile`; this module
only says which data to replay, with how much equity, and what costs to apply
to the realised slices afterwards.
"""
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from ..strategy_v1 import StrategyProfile
from .format import plain


def utc(value):
    """Accept an aware datetime or an ISO-8601 string; always return UTC."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.replace('Z', '+00:00')
        value = datetime.fromisoformat(text)
    if not isinstance(value, datetime):
        raise ValueError('timestamps must be datetime or ISO-8601 text')
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class CostModel:
    """Execution costs applied to realised slices after the strategy decided.

    Both default to zero. No exchange fee schedule is assumed or invented: a
    non-zero value only ever comes from the caller.
    """
    fee_rate: Decimal = Decimal('0')        # fraction of notional, charged per side
    slippage: Decimal = Decimal('0')        # absolute price units, adverse per side

    def __post_init__(self):
        for name in ('fee_rate', 'slippage'):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError(f'{name} must be a non-negative finite Decimal')

    @property
    def enabled(self):
        return self.fee_rate > 0 or self.slippage > 0

    def as_dict(self):
        return {'fee_rate': plain(self.fee_rate), 'slippage': plain(self.slippage),
                'applied': self.enabled}


@dataclass(frozen=True)
class BacktestConfig:
    symbol: str
    data_dir: Path
    starting_equity: Decimal = Decimal('10000')
    start: datetime | None = None
    end: datetime | None = None
    profile: StrategyProfile = field(default_factory=StrategyProfile)
    costs: CostModel = field(default_factory=CostModel)
    label: str = 'backtest'

    def __post_init__(self):
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError('symbol must be nonempty')
        if not isinstance(self.profile, StrategyProfile):
            raise ValueError('profile must be a production StrategyProfile')
        if not isinstance(self.costs, CostModel):
            raise ValueError('costs must be a CostModel')
        equity = self.starting_equity
        if not isinstance(equity, Decimal) or not equity.is_finite() or equity <= 0:
            raise ValueError('starting_equity must be a positive finite Decimal')
        object.__setattr__(self, 'data_dir', Path(self.data_dir))
        object.__setattr__(self, 'start', utc(self.start))
        object.__setattr__(self, 'end', utc(self.end))
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError('start must precede end')
        # Position sizing lives in the strategy, so the profile must carry the
        # same equity the run starts with rather than its own default.
        if self.profile.equity != equity:
            object.__setattr__(self, 'profile', replace(self.profile, equity=equity))

    @property
    def timeframes(self):
        return self.profile.timeframes

    def as_dict(self):
        """run_config.json payload. Stable, documented, JSON-ready."""
        return {'schema_version': 'strategy-v1-backtest-v0.1',
                'symbol': self.symbol,
                'label': self.label,
                'data_dir': str(self.data_dir),
                'starting_equity': plain(self.starting_equity),
                'start': None if self.start is None else self.start.isoformat(),
                'end': None if self.end is None else self.end.isoformat(),
                'costs': self.costs.as_dict(),
                'strategy': self.profile.as_dict(),
                'strategy_extra': {
                    'boundary_proximity': str(self.profile.boundary_proximity),
                    'stop_buffer': str(self.profile.stop_buffer),
                    'risk_fraction': str(self.profile.risk_fraction),
                    'quantity_step': str(self.profile.quantity_step),
                    'min_reward_risk': str(self.profile.min_reward_risk),
                    'max_stop_distance': None if self.profile.max_stop_distance is None
                                         else str(self.profile.max_stop_distance),
                    'break_even_r': str(self.profile.break_even_r),
                    'secondary_fvg_support_enabled':
                        self.profile.secondary_fvg_support_enabled,
                    'fvg_freshness_enabled': self.profile.fvg_freshness_enabled,
                    'allow_ifvg_entry': self.profile.allow_ifvg_entry,
                    'primary_failure_mode': self.profile.primary_failure_mode,
                    'pending_expiry_bars': self.profile.pending_expiry_bars,
                    'swing': {'atr_length': self.profile.swing.atr_length,
                              'atr_multiplier': str(self.profile.swing.atr_multiplier)}}}
