"""Offline Strategy V1 backtest CLI. Frozen local data only; no network, no LIVE."""
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import engine, report
from .cli import add_cost_arguments, add_profile_arguments, costs_from_args, profile_from_args
from .config import BacktestConfig


def build_parser():
    parser = argparse.ArgumentParser(
        prog='python -m agent_trading.backtest',
        description='Causal Strategy V1 replay over frozen local candles [H]')
    parser.add_argument('--symbol', default='BTC-USDT')
    parser.add_argument('--data', required=True, type=Path,
                        help='directory holding *_4H, *_1H and *_15m candle files')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--start', help='ISO-8601 window start (inclusive)')
    parser.add_argument('--end', help='ISO-8601 window end (inclusive)')
    parser.add_argument('--label', default='backtest')
    add_profile_arguments(parser)
    add_cost_arguments(parser)
    return parser


def build_config(args):
    return BacktestConfig(symbol=args.symbol, data_dir=args.data,
                          starting_equity=Decimal(args.starting_equity),
                          start=args.start, end=args.end, profile=profile_from_args(args),
                          costs=costs_from_args(args), label=args.label)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = build_config(args)
        result = engine.run(config)
        paths = report.write(result, args.output)
    except (ValueError, InvalidOperation, OSError) as exc:
        parser.error(str(exc))
    demo = result.summary_document()['demo']
    print(json.dumps(demo, indent=2, sort_keys=True))
    print('\nwrote:')
    for path in paths:
        print(f'  {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
