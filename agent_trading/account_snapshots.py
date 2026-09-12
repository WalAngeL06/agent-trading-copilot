"""Immutable private observations, not strategy/risk inputs or execution authority."""

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class CurrencyBalance:
    currency: str
    balance: Decimal | None
    available: Decimal | None
    frozen: Decimal | None
    equity: Decimal | None = None
    exchange_time: datetime | None = None


@dataclass(frozen=True)
class AutoEarnState:
    currency: str
    auto_lend: str
    auto_staking: str


@dataclass(frozen=True)
class AccountConfiguration:
    account_level: str
    position_mode: str
    auto_loan: bool | None
    spot_borrow_enabled: bool | None


@dataclass(frozen=True)
class AccountSnapshot:
    observed_at: datetime
    exchange_time: datetime
    trading: tuple[CurrencyBalance, ...]
    funding: tuple[CurrencyBalance, ...]
    total_equity_usd: Decimal | None
    configuration: AccountConfiguration
    auto_earn: tuple[AutoEarnState, ...]
    site: str = "tr"


@dataclass(frozen=True)
class SavingsBalance:
    currency: str
    amount: Decimal
    loan_amount: Decimal | None
    rate: Decimal | None
    earnings: Decimal | None


@dataclass(frozen=True)
class EarnSnapshot:
    observed_at: datetime
    savings: tuple[SavingsBalance, ...]
    auto_earn: tuple[AutoEarnState, ...]
    auto_earn_observed_at: datetime
    auto_earn_source: str = "account_get_balance.details"
    holdings_scope: str = "SIMPLE_EARN_FLEXIBLE_ONLY"
    site: str = "tr"


def _wire(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if is_dataclass(value):
        return {item.name: _wire(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_wire(item) for item in value]
    return value


@dataclass(frozen=True)
class PrivateSnapshotRead:
    status: str
    error_code: str | None = None
    account: AccountSnapshot | None = None
    earn: EarnSnapshot | None = None

    def to_dict(self):
        return _wire(self)
