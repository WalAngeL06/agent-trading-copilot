"""Configurable Strategy V1 profile. Every provisional default is tagged [H].

Timeframe roles are data, not constants: the engine never hardcodes 4H/1H/15m,
so a 1H/15m/5m profile is a configuration change, not a code change.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from ..market import bar_duration
from ..swing import SwingConfig
from ..trading_brain.risk_models import RiskConfig

ENTRY_LEVELS = ('FVG_LOW', 'FVG_EQ', 'FVG_HIGH')
DIRECTIONS = ('LONG_ONLY',)
ENTRY_ZONES = ('BULLISH_FVG',)
TRAILING_MODES = ('CONFIRMED_HIGHER_LOW',)


@dataclass(frozen=True)
class PartialTakeProfit:
    """One R-multiple partial exit.

    `close_fraction` is a fraction of the ORIGINAL filled quantity, never of the
    quantity still open, so a 25% level always realises a quarter of the
    original position regardless of what closed before it.
    """
    r_multiple: Decimal
    close_fraction: Decimal

    def __post_init__(self):
        for name in ('r_multiple', 'close_fraction'):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError(f'{name} must be a finite Decimal')
        if self.r_multiple <= 0:
            raise ValueError('r_multiple must be greater than zero')
        if not 0 < self.close_fraction <= 1:
            raise ValueError('close_fraction must be within (0, 1]')

    @classmethod
    def from_mapping(cls, data):
        """Accept the bot/API shape {"r_multiple": ..., "close_fraction": ...}."""
        if isinstance(data, cls):
            return data
        try:
            return cls(Decimal(str(data['r_multiple'])), Decimal(str(data['close_fraction'])))
        except (TypeError, KeyError) as exc:
            raise ValueError('partial take profit needs r_multiple and close_fraction') from exc

    def as_dict(self):
        return {'r_multiple': str(self.r_multiple), 'close_fraction': str(self.close_fraction)}


@dataclass(frozen=True)
class TimeframeRoles:
    """Role -> timeframe binding. Roles are fixed; timeframes are the user's."""
    bias: str = '4H'
    range: str = '1H'
    entry: str = '15m'

    def __post_init__(self):
        for name in ('bias', 'range', 'entry'):
            bar_duration(getattr(self, name))       # rejects unsupported bars early
        if bar_duration(self.bias) <= bar_duration(self.range):
            raise ValueError('bias timeframe must be higher than range timeframe')
        if bar_duration(self.range) <= bar_duration(self.entry):
            raise ValueError('range timeframe must be higher than entry timeframe')

    @property
    def ordered(self):
        """Highest timeframe first: equal close times resolve top-down."""
        return (self.bias, self.range, self.entry)

    def rank(self, timeframe):
        return self.ordered.index(timeframe)


@dataclass(frozen=True)
class StrategyProfile:
    """User-facing Strategy V1 configuration."""
    timeframes: TimeframeRoles = field(default_factory=TimeframeRoles)
    direction: str = 'LONG_ONLY'
    entry_zone: str = 'BULLISH_FVG'
    entry_level: str = 'FVG_EQ'
    # [H]-SV1-ENTRY-LEVEL-001: FVG_EQ is the midpoint. Kept as an explicit ratio
    # so 0.5 is never hardcoded in the engine and can be retuned later.
    entry_level_ratio: Decimal = Decimal('0.5')
    boundary_proximity: Decimal = Decimal('500')
    swing: SwingConfig = field(default_factory=SwingConfig)
    equity: Decimal = Decimal('10000')
    stop_buffer: Decimal = Decimal('100')
    risk_fraction: Decimal = Decimal('.01')
    quantity_step: Decimal = Decimal('.00000001')
    min_reward_risk: Decimal = Decimal('1')
    max_stop_distance: Decimal | None = None
    # [H]-SV1-BE-001: inherited 1R favorable-excursion break-even.
    break_even_r: Decimal = Decimal('1')
    secondary_fvg_support_enabled: bool = True
    # [U-RANGE-RESEEK-001] look for a new range after a candidate invalidates.
    range_reseek_enabled: bool = True
    # [U-RANGE-RETIRE-001] retire a confirmed range on a body close outside it.
    range_retire_enabled: bool = True
    # [U-MULTI-SETUP-001] allow a new setup once the previous trade has closed.
    multi_setup_enabled: bool = True
    # Structural trailing: only confirmed entry-timeframe higher lows, only
    # after break-even protection. [H]-SV1-TRAIL-001.
    trailing_enabled: bool = True
    trailing_mode: str = 'CONFIRMED_HIGHER_LOW'
    # None reuses stop_buffer so the two cannot silently drift apart.
    trailing_buffer: Decimal | None = None
    # Optional R-multiple partial exits. Empty is the Strategy V1 default.
    partial_take_profits: tuple = ()
    # Fraction of the ORIGINAL position left running past the RangeHigh exit.
    runner_fraction: Decimal = Decimal('0.10')
    # [H]-SV1-ALLOW-IFVG-001: iFVG stays available but is not required.
    allow_ifvg_entry: bool = False
    # [H]-SV1-FRESH-001: freshness reuses the shipped zone rule.
    fvg_freshness_enabled: bool = True
    # [H]-SV1-PRIMARY-FAIL-001: PRIMARY_FVG "failed" == closed entry candle
    # whose body closes below PRIMARY_FVG.lower. The user has not defined this.
    primary_failure_mode: str = 'CLOSE_BELOW_PRIMARY_LOW'
    # [H]-SV1-PENDING-EXPIRY-001: None disables expiry.
    pending_expiry_bars: int | None = None

    def __post_init__(self):
        if self.direction not in DIRECTIONS:
            raise ValueError('Strategy V1 is LONG_ONLY')
        if self.entry_zone not in ENTRY_ZONES:
            raise ValueError('unknown entry zone')
        if self.entry_level not in ENTRY_LEVELS:
            raise ValueError('unknown entry level')
        if self.primary_failure_mode != 'CLOSE_BELOW_PRIMARY_LOW':
            raise ValueError('unknown primary failure mode')
        if self.trailing_mode not in TRAILING_MODES:
            raise ValueError('unknown trailing mode')
        if self.trailing_buffer is not None and (
                not isinstance(self.trailing_buffer, Decimal)
                or not self.trailing_buffer.is_finite() or self.trailing_buffer <= 0):
            raise ValueError('trailing_buffer must be a positive finite Decimal or None')
        self._validate_exits()
        if not isinstance(self.timeframes, TimeframeRoles):
            raise ValueError('timeframes must be TimeframeRoles')
        if not isinstance(self.swing, SwingConfig):
            raise ValueError('swing must be SwingConfig')
        for name in ('entry_level_ratio', 'boundary_proximity', 'equity', 'stop_buffer',
                     'risk_fraction', 'quantity_step', 'min_reward_risk', 'break_even_r'):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError(f'{name} must be a finite Decimal')
        if not 0 <= self.entry_level_ratio <= 1:
            raise ValueError('entry_level_ratio must be within [0, 1]')
        if self.boundary_proximity < 0:
            raise ValueError('boundary_proximity must not be negative')
        for name in ('equity', 'stop_buffer', 'risk_fraction', 'quantity_step',
                     'min_reward_risk', 'break_even_r'):
            if getattr(self, name) <= 0:
                raise ValueError(f'{name} must be positive')
        if self.pending_expiry_bars is not None and (
                type(self.pending_expiry_bars) is not int or self.pending_expiry_bars <= 0):
            raise ValueError('pending_expiry_bars must be a positive integer or None')
        self.risk_config()

    def _validate_exits(self):
        """Reject impossible exit plans outright; never silently repair them."""
        runner = self.runner_fraction
        if not isinstance(runner, Decimal) or not runner.is_finite() or not 0 <= runner <= 1:
            raise ValueError('runner_fraction must be a Decimal within [0, 1]')
        levels = tuple(PartialTakeProfit.from_mapping(item)
                       for item in self.partial_take_profits)
        seen = set()
        for level in levels:
            if level.r_multiple in seen:
                raise ValueError('duplicate partial take profit R level')
            seen.add(level.r_multiple)
        total = sum((level.close_fraction for level in levels), Decimal(0))
        if total > 1 - runner:
            raise ValueError('partial close fractions exceed the non-runner allocation')
        # Ascending R is the execution order; normalise it once, here.
        object.__setattr__(self, 'partial_take_profits',
                           tuple(sorted(levels, key=lambda level: level.r_multiple)))

    def as_dict(self):
        """Bot/API-ready view of the exit plan. No UI is implemented here."""
        return {'partial_take_profits': [level.as_dict() for level in self.partial_take_profits],
                'runner_fraction': str(self.runner_fraction),
                'entry_level': self.entry_level,
                'entry_level_ratio': str(self.entry_level_ratio),
                'direction': self.direction,
                'timeframes': {'bias': self.timeframes.bias, 'range': self.timeframes.range,
                               'entry': self.timeframes.entry},
                'range_reseek_enabled': self.range_reseek_enabled,
                'range_retire_enabled': self.range_retire_enabled,
                'multi_setup_enabled': self.multi_setup_enabled,
                'trailing_enabled': self.trailing_enabled,
                'trailing_mode': self.trailing_mode,
                'trailing_buffer': None if self.trailing_buffer is None
                                   else str(self.trailing_buffer)}

    @property
    def effective_trailing_buffer(self):
        """Trailing buffer, defaulting to the structural stop buffer."""
        return self.stop_buffer if self.trailing_buffer is None else self.trailing_buffer

    def risk_config(self):
        """Strategy V1 always manages stops through the shipped RiskEngine."""
        return RiskConfig(profile='STRUCTURE_BE', break_even_r=self.break_even_r,
                          min_reward_risk=self.min_reward_risk,
                          max_stop_distance=self.max_stop_distance,
                          risk_per_trade=self.risk_fraction, stop_buffer=self.stop_buffer,
                          quantity_step=self.quantity_step)
