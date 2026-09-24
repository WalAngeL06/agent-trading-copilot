"""Replay one production profile over many frozen datasets [U-MULTI-PAIR-001].

Every subdirectory of the data root is one dataset: one pair, or one window of
a pair. The backtest engine runs on each exactly as it does for a single run
and writes its usual artifacts into a folder named after the dataset. This
module adds only the loop, the per-pair scaling of the two knobs quoted in
price units [H]-SWEEP-SCALE-001, and a summary across datasets. It never
reaches the network.

    python -m agent_trading.backtest.sweep --data data/okx_tr_usdt_top30 \\
        --output runs/sweep-okx-tr
"""
import argparse
from collections import Counter
import csv
from dataclasses import replace
from decimal import Decimal, InvalidOperation
import io
import json
from pathlib import Path

from ..strategy_v1.config import ENTRY_MODELS
from ..trading_brain.risk import exact_product
from . import engine, report
from .cli import (add_cost_arguments, add_profile_arguments, costs_from_args,
                  explicit_absolute_flags, profile_from_args)
from .config import BacktestConfig, utc
from .dataset import discover, load_dataset, peek_symbol
from .files import write_atomic
from .format import plain
from .metrics import _mean, _median, funnel
from .recorder import add

SCHEMA = 'strategy-v1-sweep-v0.1'
DEFAULT_PROXIMITY_RATIO, DEFAULT_STOP_BUFFER_RATIO = '0.005', '0.001'
ROW_COLUMNS = ('dataset', 'symbol', 'status', 'reason', 'window_start', 'window_end',
               'reference_price', 'price_drift', 'boundary_proximity', 'stop_buffer',
               'ranges_confirmed', 'manipulations', 'htf_context_checks', 'htf_allowed',
               'setups', 'risk_blocked', 'trades', 'wins', 'losses', 'win_rate', 'total_r',
               'net_pnl', 'ending_equity', 'max_drawdown_percent')


def scale_profile(profile, reference, proximity_ratio, stop_buffer_ratio):
    """[H]-SWEEP-SCALE-001 Both price-unit knobs as a share of the reference.

    The HTF zone tolerance and the trailing buffer default to these two, so
    they follow automatically. 0.005 and 0.001 are 500 and 100 at a BTC price
    of 100,000, the values the single-pair research used.
    """
    return replace(profile, boundary_proximity=exact_product(reference, proximity_ratio),
                   stop_buffer=exact_product(reference, stop_buffer_ratio))


def reference_price(dataset, entry_timeframe):
    """First entry-timeframe close inside the window: known before any trade."""
    return dataset.streams[entry_timeframe].candles[0].close


def dataset_dirs(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f'data root not found: {root}')
    found = [path for path in sorted(root.iterdir(), key=lambda path: path.name)
             if path.is_dir() and not path.name.startswith('.')]
    if not found:
        raise ValueError(f'no dataset folders in {root}')
    return found


def _total(values):
    result = Decimal(0)
    for value in values:
        result = add(result, value)
    return result


def _text(value):
    return None if value is None else plain(value)


def sweep_dataset(directory, args, base_profile, scale, output_root):
    """One dataset: (row, trade records, setup funnel). The run result is dropped."""
    row = dict.fromkeys(ROW_COLUMNS)
    row.update(dataset=directory.name, bars={}, htf_reasons={}, blocked_reasons={})
    roles = base_profile.timeframes
    try:                                    # a dataset that cannot load is SKIPPED
        symbol = peek_symbol(discover(directory, roles.entry))
        config = BacktestConfig(symbol, directory, Decimal(args.starting_equity), args.start,
                                args.end, base_profile, costs_from_args(args),
                                label=f'{args.label}/{directory.name}')
        dataset = load_dataset(config)
    except ValueError as exc:
        row.update(status='SKIPPED', reason=str(exc))
        return row, (), {}
    entry = dataset.streams[roles.entry].candles
    row.update(symbol=symbol, bars={timeframe: load.count
                                    for timeframe, load in dataset.streams.items()},
               window_start=entry[0].close_time.isoformat(),
               window_end=entry[-1].close_time.isoformat())
    try:                                    # a dataset that loads but cannot run is FAILED
        reference = reference_price(dataset, roles.entry)
        profile = (scale_profile(base_profile, reference, scale['proximity_ratio'],
                                 scale['stop_buffer_ratio'])
                   if scale['mode'] == 'price' else base_profile)
        result = engine.run(replace(config, profile=profile), dataset)
        report.write(result, Path(output_root) / directory.name)
    except Exception as exc:
        row.update(status='FAILED', reason=f'{type(exc).__name__}: {exc}')
        return row, (), {}
    strategy, summary = result.strategy, result.summary
    verdicts = [event.payload for event in strategy.events if event.kind == 'HTF_CONTEXT']
    blocked = [event.payload for event in strategy.events if event.kind == 'BLOCKED']
    closed_r = [record.r_multiple for record in result.trades
                if record.status == 'CLOSED' and record.r_multiple is not None]
    row.update(status='COMPLETED', reference_price=plain(reference),
               price_drift=plain((entry[-1].close / entry[0].close).quantize(Decimal('1e-6'))),
               boundary_proximity=plain(profile.boundary_proximity),
               stop_buffer=plain(profile.stop_buffer),
               ranges_confirmed=strategy.counts['RANGE_CONFIRMED'],
               manipulations=strategy.counts['MANIPULATION_CONFIRMED'],
               htf_context_checks=len(verdicts),
               htf_allowed=sum(1 for verdict in verdicts if verdict.allowed),
               setups=summary['setups_total'], risk_blocked=summary['risk_blocked_setups'],
               trades=summary['filled_logical_trades'], wins=summary['wins'],
               losses=summary['losses'], win_rate=summary['win_rate'],
               total_r=plain(_total(closed_r)),
               net_pnl=plain(_total(record.net_pnl for record in result.trades)),
               ending_equity=summary['ending_equity'],
               max_drawdown_percent=summary['max_drawdown_percent'],
               htf_reasons=dict(sorted(Counter(v.reason for v in verdicts).items())),
               blocked_reasons=dict(sorted(Counter(d.reason for d in blocked).items())))
    return row, tuple(result.trades), funnel(strategy)


def pooled(records):
    """Every trade of every dataset together, measured in R."""
    closed = [record for record in records if record.status == 'CLOSED']
    r_values = [record.r_multiple for record in closed if record.r_multiple is not None]
    wins = [record for record in closed if record.net_pnl > 0]
    losses = [record for record in closed if record.net_pnl < 0]
    gained = _total(value for value in r_values if value > 0)
    lost = _total(-value for value in r_values if value < 0)
    by_direction = {}
    for side in ('LONG', 'SHORT'):
        mine = [record for record in closed if record.direction == side]
        by_direction[side] = {
            'trades': sum(1 for record in records if record.direction == side),
            'wins': sum(1 for record in mine if record.net_pnl > 0),
            'total_r': plain(_total(record.r_multiple for record in mine
                                    if record.r_multiple is not None))}
    by_entry_model = {}
    for model in ENTRY_MODELS:
        mine = [record for record in closed if record.entry_model == model]
        by_entry_model[model] = {
            'trades': sum(1 for record in records if record.entry_model == model),
            'wins': sum(1 for record in mine if record.net_pnl > 0),
            'total_r': plain(_total(record.r_multiple for record in mine
                                    if record.r_multiple is not None))}
    return {'trades': len(records), 'closed': len(closed), 'open': len(records) - len(closed),
            'wins': len(wins), 'losses': len(losses),
            'win_rate': _text(Decimal(len(wins)) / Decimal(len(closed)) if closed else None),
            'average_r': _text(_mean(r_values)), 'median_r': _text(_median(r_values)),
            'total_r': plain(_total(r_values)),
            'profit_factor_r': _text(gained / lost if lost > 0 else None),
            'net_pnl': plain(_total(record.net_pnl for record in records)),
            'by_direction': by_direction, 'by_entry_model': by_entry_model}


def _limitations(root, scale):
    tags = ['POOLED_TRADES_NOT_INDEPENDENT', 'DATASET_WINDOWS_DIFFER']
    if scale['mode'] == 'price':
        tags.append('FIXED_REFERENCE_PRICE')
    universe = Path(root) / 'universe.json'
    if universe.is_file():
        try:
            tags += json.loads(universe.read_text(encoding='utf-8')).get('limitations', [])
        except (ValueError, AttributeError):
            tags.append('UNIVERSE_DOCUMENT_UNREADABLE')
    return list(dict.fromkeys(tags))


def _csv(columns, rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns))
    writer.writeheader()
    for row in rows:
        writer.writerow({column: '' if row.get(column) is None else row.get(column)
                         for column in columns})
    return buffer.getvalue()


def write_summary(output, document, rows, trades, timeframes):
    output = Path(output)
    write_atomic(output / 'sweep_summary.json',
                 json.dumps(report.jsonable(document), indent=2, sort_keys=True) + '\n')
    columns = ROW_COLUMNS + tuple(f'bars_{timeframe}' for timeframe in timeframes)
    flat = [dict(row, **{f'bars_{tf}': count for tf, count in row['bars'].items()})
            for row in rows]
    write_atomic(output / 'sweep_symbols.csv', _csv(columns, flat))
    trade_rows = []
    for dataset, record in trades:
        payload = record.as_dict()
        payload.pop('slices', None)
        trade_rows.append(dict(report.jsonable(payload), dataset=dataset))
    write_atomic(output / 'sweep_trades.csv', _csv(('dataset',) + report.TRADE_COLUMNS,
                                                   trade_rows))


def build_parser():
    parser = argparse.ArgumentParser(
        prog='python -m agent_trading.backtest.sweep',
        description='Replay one Strategy V1 profile over every dataset folder [H]')
    parser.add_argument('--data', required=True, type=Path,
                        help='root folder; each subfolder is one dataset')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--label', default='sweep')
    parser.add_argument('--start', help='ISO-8601 window start (inclusive)')
    parser.add_argument('--end', help='ISO-8601 window end (inclusive)')
    parser.add_argument('--scale', default='price', choices=('price', 'none'),
                        help='price: scale the price-unit knobs per dataset [H]-SWEEP-SCALE-001')
    parser.add_argument('--proximity-ratio', default=DEFAULT_PROXIMITY_RATIO,
                        help='boundary proximity as a share of the reference price')
    parser.add_argument('--stop-buffer-ratio', default=DEFAULT_STOP_BUFFER_RATIO,
                        help='stop buffer as a share of the reference price')
    add_profile_arguments(parser)
    add_cost_arguments(parser)
    return parser


def _scale(args):
    if args.scale == 'none':
        return {'mode': 'none'}
    given = explicit_absolute_flags(args)
    if given:
        raise ValueError(f'{", ".join(given)} are price units and would not scale per pair; '
                         'drop them or use --scale none')
    ratios = Decimal(args.proximity_ratio), Decimal(args.stop_buffer_ratio)
    if any(not ratio.is_finite() or ratio <= 0 for ratio in ratios):
        raise ValueError('scaling ratios must be positive')
    return {'mode': 'price', 'proximity_ratio': ratios[0], 'stop_buffer_ratio': ratios[1]}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        base_profile = profile_from_args(args)
        costs_from_args(args)
        utc(args.start), utc(args.end)
        scale = _scale(args)
        directories = dataset_dirs(args.data)
    except (ValueError, InvalidOperation) as exc:
        parser.error(str(exc))
    rows, trades, funnels = [], [], Counter()
    for directory in directories:
        row, records, counts = sweep_dataset(directory, args, base_profile, scale, args.output)
        rows.append(row)
        trades.extend((directory.name, record) for record in records)
        funnels.update(counts)
        detail = (f"trades={row['trades']} total_r={row['total_r']}"
                  if row['status'] == 'COMPLETED' else row['reason'])
        print(f"{directory.name}: {row['status']} {detail}")
    by_symbol = {}
    for row in rows:
        if row['symbol']:
            by_symbol.setdefault(row['symbol'], []).append(row['dataset'])
    counts = {status.lower(): sum(1 for row in rows if row['status'] == status)
              for status in ('COMPLETED', 'SKIPPED', 'FAILED')}
    document = {
        'schema_version': SCHEMA, 'label': args.label, 'data_root': str(args.data),
        'scale': ({'mode': 'price', 'proximity_ratio': plain(scale['proximity_ratio']),
                   'stop_buffer_ratio': plain(scale['stop_buffer_ratio']),
                   'reference': 'first entry-timeframe close inside the window'}
                  if scale['mode'] == 'price' else
                  {'mode': 'none', 'boundary_proximity': plain(base_profile.boundary_proximity),
                   'stop_buffer': plain(base_profile.stop_buffer)}),
        'base_profile': base_profile.as_dict(),
        'datasets': rows, 'counts': counts,
        'pooled': pooled([record for _dataset, record in trades]),
        'funnel': dict(sorted(funnels.items())),
        'htf_reasons': dict(sorted(sum((Counter(row['htf_reasons']) for row in rows),
                                       Counter()).items())),
        'blocked_reasons': dict(sorted(sum((Counter(row['blocked_reasons']) for row in rows),
                                           Counter()).items())),
        'warnings': [f"DUPLICATE_SYMBOL {symbol}: {', '.join(names)}"
                     for symbol, names in sorted(by_symbol.items()) if len(names) > 1],
        'limitations': _limitations(args.data, scale),
        'source_ids': ['[U-MULTI-PAIR-001]', '[H]-SWEEP-SCALE-001']}
    write_summary(args.output, document, rows, trades, base_profile.timeframes.ordered)
    print(json.dumps({'counts': counts, 'pooled': document['pooled'],
                      'warnings': document['warnings']}, indent=2, sort_keys=True))
    return 0 if counts['completed'] and not counts['failed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
