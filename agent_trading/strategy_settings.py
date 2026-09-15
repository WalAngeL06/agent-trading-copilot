"""Local product settings. Domain validation remains in StrategyProfile."""
from decimal import Decimal, localcontext
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, model_validator

from .strategy_v1.config import StrategyProfile, TimeframeRoles, PartialTakeProfit


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Roles(SettingsModel):
    bias: StrictStr
    range: StrictStr
    entry: StrictStr


class Entry(SettingsModel):
    level: StrictStr
    secondaryFvgSupport: StrictBool


class Risk(SettingsModel):
    riskPct: StrictStr
    minimumRR: StrictStr


class Management(SettingsModel):
    breakEvenEnabled: Literal[True]
    breakEvenTriggerR: StrictStr
    trailingEnabled: StrictBool
    trailingBuffer: StrictStr


class Partial(SettingsModel):
    id: str = Field(max_length=64)
    rMultiple: StrictStr
    closePct: StrictStr


class Exits(SettingsModel):
    partialTakeProfits: list[Partial] = Field(max_length=100)
    runnerPct: StrictStr


def decimal(value):
    # Transport bound only; positivity, allocation and geometry belong to domain.
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise ValueError('A decimal string is required')
    try:
        result = Decimal(value)
    except ArithmeticError:
        raise ValueError('A decimal string is required') from None
    if not result.is_finite() or abs(result.as_tuple().exponent) > 64:
        raise ValueError('A finite decimal string is required')
    return result


class StrategySettings(SettingsModel):
    schemaVersion: Literal['strategy-config-v1']
    profileId: Literal['STRATEGY_V1']
    executionMode: Literal['PAPER']
    timeframes: Roles
    entry: Entry
    risk: Risk
    management: Management
    exits: Exits

    def to_profile(self):
        with localcontext() as context:
            context.prec = 100
            return StrategyProfile(
                timeframes=TimeframeRoles(**self.timeframes.model_dump()),
                entry_level=self.entry.level,
                secondary_fvg_support_enabled=self.entry.secondaryFvgSupport,
                risk_fraction=decimal(self.risk.riskPct) / 100,
                min_reward_risk=decimal(self.risk.minimumRR),
                break_even_r=decimal(self.management.breakEvenTriggerR),
                trailing_enabled=self.management.trailingEnabled,
                trailing_buffer=(decimal(self.management.trailingBuffer)
                                 if self.management.trailingBuffer else None),
                partial_take_profits=tuple(PartialTakeProfit(
                    decimal(level.rMultiple), decimal(level.closePct) / 100)
                    for level in self.exits.partialTakeProfits),
                runner_fraction=decimal(self.exits.runnerPct) / 100,
            )

    @model_validator(mode='after')
    def domain_validation(self):
        self.to_profile()
        return self

    @classmethod
    def from_profile(cls, profile):
        with localcontext() as context:
            context.prec = 100
            return cls.model_validate({
                'schemaVersion': 'strategy-config-v1', 'profileId': 'STRATEGY_V1',
                'executionMode': 'PAPER',
                'timeframes': {'bias': profile.timeframes.bias, 'range': profile.timeframes.range,
                               'entry': profile.timeframes.entry},
                'entry': {'level': profile.entry_level,
                          'secondaryFvgSupport': profile.secondary_fvg_support_enabled},
                'risk': {'riskPct': str(profile.risk_fraction * 100),
                         'minimumRR': str(profile.min_reward_risk)},
                'management': {'breakEvenEnabled': True,
                               'breakEvenTriggerR': str(profile.break_even_r),
                               'trailingEnabled': profile.trailing_enabled,
                               'trailingBuffer': '' if profile.trailing_buffer is None
                               else str(profile.trailing_buffer)},
                'exits': {'runnerPct': str(profile.runner_fraction * 100),
                          'partialTakeProfits': [
                              {'id': f'tp-{i+1}', 'rMultiple': str(level.r_multiple),
                               'closePct': str(level.close_fraction * 100)}
                              for i, level in enumerate(profile.partial_take_profits)]},
            })


class StrategyStore:
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.current = StrategySettings.model_validate_json(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            self.current = StrategySettings.from_profile(StrategyProfile())
        except (OSError, ValueError):
            raise ValueError('Strategy configuration is unreadable or invalid; restore it before starting.') from None

    def save(self, settings):
        canonical = StrategySettings.from_profile(settings.to_profile())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                    prefix='.strategy-', suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(canonical.model_dump(), handle, indent=2, allow_nan=False)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.current = canonical
        return canonical
