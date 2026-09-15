"""Frozen local candle datasets. The replay never touches the network.

Loading is strict: only closed candles enter a stream, every row must belong to
the requested symbol and timeframe, and each stream must be contiguous and
strictly chronological before any replay is allowed to start.
"""
import csv
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ..market import bar_duration
from ..models import Candle

SUFFIXES = ('.jsonl', '.json', '.csv')
FIELDS = ('symbol', 'timeframe', 'close_time', 'open', 'high', 'low', 'close', 'volume')


@dataclass(frozen=True)
class StreamLoad:
    timeframe: str
    path: Path
    candles: tuple
    excluded_open: int = 0
    excluded_window: int = 0

    @property
    def count(self):
        return len(self.candles)

    @property
    def first(self):
        return self.candles[0].close_time if self.candles else None

    @property
    def last(self):
        return self.candles[-1].close_time if self.candles else None


@dataclass(frozen=True)
class Dataset:
    symbol: str
    streams: dict

    def candles(self, roles):
        """One chronological list; equal close times resolve highest timeframe first."""
        every = [candle for load in self.streams.values() for candle in load.candles]
        return sorted(every, key=lambda c: (c.close_time, roles.rank(c.timeframe)))

    @property
    def total(self):
        return sum(load.count for load in self.streams.values())

    def as_dict(self):
        return {'symbol': self.symbol,
                'streams': {timeframe: {'path': str(load.path), 'candles': load.count,
                                        'first': None if load.first is None else load.first.isoformat(),
                                        'last': None if load.last is None else load.last.isoformat(),
                                        'excluded_open': load.excluded_open,
                                        'excluded_outside_window': load.excluded_window}
                            for timeframe, load in self.streams.items()}}


def discover(data_dir, timeframe):
    """Find `*_<timeframe>.<ext>` in a dataset directory, case-insensitively."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise ValueError(f'dataset directory not found: {data_dir}')
    matches = [path for path in sorted(data_dir.iterdir())
               if path.suffix.lower() in SUFFIXES
               and path.stem.lower().endswith('_' + timeframe.lower())]
    if not matches:
        raise ValueError(f'no {timeframe} candle file in {data_dir}')
    if len(matches) > 1:
        raise ValueError(f'ambiguous {timeframe} candle files in {data_dir}: '
                         + ', '.join(path.name for path in matches))
    return matches[0]


def _rows(path):
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as handle:
            for number, row in enumerate(csv.DictReader(handle), 2):
                yield number, row
        return
    with path.open(encoding='utf-8-sig') as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            payload = json.loads(line, parse_float=Decimal)
            if isinstance(payload, list):        # a single JSON array document
                for index, item in enumerate(payload, 1):
                    yield index, item
                return
            yield number, payload


def _normalise(row):
    missing = [field for field in FIELDS if row.get(field) in (None, '')]
    if missing:
        raise ValueError('missing fields: ' + ', '.join(missing))
    closed = row.get('closed', True)
    if isinstance(closed, str):
        closed = closed.strip().lower() in ('1', 'true', 'yes')
    return dict(row, closed=bool(closed))


def load_stream(path, symbol, timeframe, start=None, end=None):
    """Strictly load one timeframe. Open candles are excluded, never guessed."""
    candles, excluded_open, excluded_window = [], 0, 0
    for number, raw in _rows(Path(path)):
        try:
            row = _normalise(raw)
            if not row['closed']:
                excluded_open += 1                 # an unclosed bar is not knowledge
                continue
            candle = Candle.from_dict(row)
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            raise ValueError(f'{path}: row {number}: {exc}') from exc
        if candle.symbol != symbol or candle.timeframe != timeframe:
            raise ValueError(f'{path}: row {number}: expected {symbol} {timeframe}, '
                             f'found {candle.symbol} {candle.timeframe}')
        if (start is not None and candle.close_time < start) or (
                end is not None and candle.close_time > end):
            excluded_window += 1
            continue
        candles.append(candle)
    candles.sort(key=lambda c: c.close_time)
    step = bar_duration(timeframe)
    for earlier, later in zip(candles, candles[1:]):
        if later.close_time == earlier.close_time:
            raise ValueError(f'{path}: duplicate {timeframe} candle at {later.close_time}')
        if later.close_time - earlier.close_time != step:
            raise ValueError(f'{path}: {timeframe} gap between {earlier.close_time} '
                             f'and {later.close_time}')
    return StreamLoad(timeframe, Path(path), tuple(candles), excluded_open, excluded_window)


def load_dataset(config):
    """Load every role timeframe named by the strategy profile."""
    streams = {}
    for timeframe in config.timeframes.ordered:
        path = discover(config.data_dir, timeframe)
        streams[timeframe] = load_stream(path, config.symbol, timeframe,
                                         config.start, config.end)
    empty = [timeframe for timeframe, load in streams.items() if not load.count]
    if empty:
        raise ValueError('no candles in window for: ' + ', '.join(empty))
    return Dataset(config.symbol, streams)
