"""Which OKX TR spot pairs a multi-pair sweep tests [U-MULTI-PAIR-001].

Guide section 3, step 1 asks for liquid, major pairs only. The selection is a
pure function of one listing snapshot: live spot pairs in one quote currency,
minus stablecoin and fiat bases, ranked by 24h quote volume. The written
document records how the list was chosen and what that choice cannot see: a
pair liquid today may not have been a year ago, and delisted pairs are absent.
Nothing here reaches the network.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
import re

from ..market_observations import SpotInstrument, SpotVolume
from .files import write_atomic
from .format import plain

SCHEMA = 'okx-universe-v0.1'
# [H]-UNIVERSE-EXCLUDE-001 A stablecoin or fiat base has no range worth trading.
STABLE_BASES = ('USDT', 'USDC', 'DAI', 'TUSD', 'FDUSD', 'USDE', 'PYUSD', 'USDP', 'USDD',
                'BUSD', 'USDG', 'RLUSD', 'USD1', 'EURC', 'EURT', 'EUR', 'TRY')
LIMITATIONS = ('SELECTED_BY_CURRENT_24H_VOLUME', 'SURVIVORSHIP_BIAS', 'DELISTED_PAIRS_ABSENT')
COUNTS = ('instruments', 'live', 'quote_matches', 'excluded', 'missing_ticker',
          'candidates', 'selected')


def _code(value, name):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z0-9]+', value):
        raise ValueError(f'{name} must be an uppercase currency code')
    return value


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('as_of must be a timezone-aware datetime')
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    base: str
    quote_volume_24h: Decimal
    last: Decimal | None = None
    list_time: datetime | None = None

    def as_dict(self):
        return {'symbol': self.symbol, 'base': self.base,
                'quote_volume_24h': plain(self.quote_volume_24h),
                'last': None if self.last is None else plain(self.last),
                'list_time': None if self.list_time is None else self.list_time.isoformat()}

    @classmethod
    def from_dict(cls, data):
        return cls(data['symbol'], data['base'], Decimal(data['quote_volume_24h']),
                   None if data['last'] is None else Decimal(data['last']),
                   None if data['list_time'] is None
                   else datetime.fromisoformat(data['list_time']))


@dataclass(frozen=True)
class Universe:
    as_of: datetime
    quote: str
    top: int
    exclude_bases: tuple
    members: tuple
    counts: dict
    site: str = 'tr'
    ranking: str = 'quote_volume_24h'
    limitations: tuple = LIMITATIONS

    @property
    def symbols(self):
        return tuple(member.symbol for member in self.members)

    def as_dict(self):
        return {'schema_version': SCHEMA, 'as_of': self.as_of.isoformat(), 'site': self.site,
                'quote': self.quote, 'top': self.top, 'ranking': self.ranking,
                'exclude_bases': list(self.exclude_bases), 'counts': dict(self.counts),
                'members': [member.as_dict() for member in self.members],
                'limitations': list(self.limitations),
                'source_ids': ['[U-MULTI-PAIR-001]', '[H]-UNIVERSE-EXCLUDE-001']}

    @classmethod
    def from_dict(cls, data):
        if data.get('schema_version') != SCHEMA:
            raise ValueError('unsupported universe document')
        return cls(_utc(datetime.fromisoformat(data['as_of'])), data['quote'], data['top'],
                   tuple(data['exclude_bases']),
                   tuple(UniverseMember.from_dict(item) for item in data['members']),
                   {name: data['counts'][name] for name in COUNTS}, data['site'],
                   data['ranking'], tuple(data['limitations']))


def select_universe(instruments, volumes, *, quote='USDT', top=30,
                    exclude_bases=STABLE_BASES, as_of):
    """Live spot pairs in `quote`, minus excluded bases, top `top` by 24h volume."""
    _code(quote, 'quote')
    if type(top) is not int or top <= 0:
        raise ValueError('top must be a positive integer')
    as_of = _utc(as_of)
    excluded = tuple(_code(base, 'excluded base') for base in exclude_bases)
    if any(not isinstance(item, SpotInstrument) for item in instruments) or any(
            not isinstance(item, SpotVolume) for item in volumes):
        raise ValueError('selection needs normalized spot instruments and volumes')
    by_symbol = {volume.symbol: volume for volume in volumes}
    counts = dict.fromkeys(COUNTS, 0)
    counts['instruments'] = len(instruments)
    candidates = []
    for instrument in instruments:
        if instrument.state != 'live':
            continue
        counts['live'] += 1
        if instrument.quote != quote:
            continue
        counts['quote_matches'] += 1
        if instrument.base in excluded:
            counts['excluded'] += 1
            continue
        volume = by_symbol.get(instrument.symbol)
        if volume is None:
            counts['missing_ticker'] += 1          # counted, never guessed
            continue
        candidates.append(UniverseMember(instrument.symbol, instrument.base,
                                         volume.quote_volume_24h, volume.last,
                                         instrument.list_time))
    counts['candidates'] = len(candidates)
    # Highest volume first; equal volumes resolve by symbol, so it is stable.
    candidates.sort(key=lambda member: member.symbol)
    candidates.sort(key=lambda member: member.quote_volume_24h, reverse=True)
    members = tuple(candidates[:top])
    counts['selected'] = len(members)
    return Universe(as_of, quote, top, excluded, members, counts)


def write_universe(universe, path):
    return write_atomic(path, json.dumps(universe.as_dict(), indent=2, sort_keys=True) + '\n')


def read_universe(path):
    with open(path, encoding='utf-8') as handle:
        return Universe.from_dict(json.load(handle))
