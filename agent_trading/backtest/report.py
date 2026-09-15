"""Deterministic run artifacts the WebApp can consume directly."""
import csv
import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .format import plain

TRADE_COLUMNS = ('trade_id', 'symbol', 'direction', 'setup_at', 'entry_at', 'entry_price',
                 'initial_stop', 'initial_r', 'original_quantity', 'initial_risk_amount',
                 'final_exit_at', 'exit_reason', 'status', 'gross_pnl', 'cost', 'net_pnl',
                 'r_multiple', 'duration_seconds', 'partial_count', 'range_high_reached',
                 'runner_opened', 'runner_stopped', 'break_even_reached', 'trailing_updates')
EQUITY_COLUMNS = ('observed_at', 'equity', 'peak_equity', 'drawdown', 'drawdown_percent',
                  'trade_id', 'event')
FILES = ('backtest_summary.json', 'trades.csv', 'events.jsonl', 'equity_curve.csv',
         'run_config.json', 'setup_funnel.json')


def jsonable(value):
    """Decimals become strings so no precision is lost on the way to the UI."""
    if isinstance(value, Decimal):
        return plain(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        if hasattr(value, 'as_dict'):
            return jsonable(value.as_dict())
        return {field.name: jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _write_json(path, payload):
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        json.dump(jsonable(payload), handle, indent=2, sort_keys=True)
        handle.write('\n')


def _write_csv(path, columns, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, '') for column in columns})


def event_row(event):
    """One audit event, flattened, with its payload preserved as data."""
    return {'id': event.id, 'kind': event.kind, 'timeframe': event.timeframe,
            'observed_at': event.observed_at.isoformat(),
            'evidence_ids': list(event.evidence_ids),
            'source_ids': list(event.source_ids),
            'payload': jsonable(event.payload)}


def write(result, output_dir):
    """Write every artifact for one run and return the paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / 'run_config.json', result.config.as_dict())
    _write_json(output_dir / 'backtest_summary.json', result.summary_document())
    _write_json(output_dir / 'setup_funnel.json', result.summary_document()['funnel'])

    trade_rows = []
    for record in result.trades:
        payload = record.as_dict()
        payload.pop('slices', None)
        trade_rows.append({key: '' if value is None else value
                           for key, value in payload.items()})
    _write_csv(output_dir / 'trades.csv', TRADE_COLUMNS, trade_rows)
    _write_csv(output_dir / 'equity_curve.csv', EQUITY_COLUMNS,
               [point.as_row() for point in result.curve])

    with (output_dir / 'events.jsonl').open('w', encoding='utf-8', newline='\n') as handle:
        for event in result.events:
            handle.write(json.dumps(event_row(event), sort_keys=True) + '\n')

    # Trade slices live beside the flat CSV so partial detail is never lost.
    _write_json(output_dir / 'trades_detail.json',
                [record.as_dict() for record in result.trades])
    return tuple(sorted(path for path in output_dir.iterdir() if path.is_file()))
