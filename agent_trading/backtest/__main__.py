"""Offline Strategy V1 backtest CLI. Frozen local data only; no network, no LIVE."""
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ..strategy_v1 import StrategyProfile, TimeframeRoles
from . import engine, report
from .config import BacktestConfig, CostModel


def _partials(text):
    """--partial-tp '1.0:0.20,2.0:0.20' or a JSON list."""
    if not text:
        return ()
    text = text.strip()
    if text.startswith('['):
        return tuple(json.loads(text))
    levels = []
    for chunk in text.split(','):
        if not chunk.strip():
            continue
        r_multiple, _, fraction = chunk.partition(':')
        if not fraction:
            raise argparse.ArgumentTypeError('each partial must be R:FRACTION')
        levels.append({'r_multiple': r_multiple.strip(), 'close_fraction': fraction.strip()})
    return tuple(levels)


def build_parser():
    parser = argparse.ArgumentParser(
        prog='python -m agent_trading.backtest',
        description='Causal Strategy V1 replay over frozen local candles [H]')
    parser.add_argument('--symbol', default='BTC-USDT')
    parser.add_argument('--data', required=True, type=Path,
                        help='directory holding *_4H, *_1H and *_15m candle files')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--starting-equity', default='10000')
    parser.add_argument('--start', help='ISO-8601 window start (inclusive)')
    parser.add_argument('--end', help='ISO-8601 window end (inclusive)')
    parser.add_argument('--label', default='backtest')
    parser.add_argument('--bias-timeframe', default='4H')
    parser.add_argument('--range-timeframe', default='1H')
    parser.add_argument('--entry-timeframe', default='15m')
    parser.add_argument('--entry-level', default='FVG_EQ',
                        choices=('FVG_LOW', 'FVG_EQ', 'FVG_HIGH'))
    parser.add_argument('--entry-level-ratio', default='0.5')
    parser.add_argument('--direction', default='BOTH',
                        choices=('BOTH', 'LONG_ONLY', 'SHORT_ONLY'))
    parser.add_argument('--direction-gate', default='GUIDE_HTF_CONTEXT',
                        choices=('GUIDE_HTF_CONTEXT', 'BIAS_LONG_PERMISSION'),
                        help='guide 4.3/4.4 context, or the superseded 4H permission')
    parser.add_argument('--htf-zone-tolerance',
                        help='defaults to the boundary proximity')
    parser.add_argument('--no-htf-confluence', action='store_true',
                        help='keep premium/discount but drop the guide 4.3 zone rule')
    parser.add_argument('--risk-per-trade', default='.01')
    parser.add_argument('--min-reward-risk', default='1')
    parser.add_argument('--stop-buffer', default='100')
    parser.add_argument('--boundary-proximity', default='500')
    parser.add_argument('--break-even-r', default='1')
    parser.add_argument('--trailing-buffer', help='defaults to the stop buffer')
    parser.add_argument('--no-trailing', action='store_true')
    parser.add_argument('--no-secondary-fvg', action='store_true')
    parser.add_argument('--partial-tp', default='',
                        help="R:FRACTION pairs, e.g. '1.0:0.20,2.0:0.20'")
    parser.add_argument('--runner-fraction', default='0.10')
    parser.add_argument('--fee-rate', default='0', help='fraction of notional per side')
    parser.add_argument('--slippage', default='0', help='absolute price units per side')
    return parser


def build_config(args):
    profile = StrategyProfile(
        timeframes=TimeframeRoles(args.bias_timeframe, args.range_timeframe,
                                  args.entry_timeframe),
        entry_level=args.entry_level,
        entry_level_ratio=Decimal(args.entry_level_ratio),
        direction=args.direction,
        direction_gate=args.direction_gate,
        htf_confluence_required=not args.no_htf_confluence,
        htf_zone_tolerance=(None if args.htf_zone_tolerance is None
                            else Decimal(args.htf_zone_tolerance)),
        boundary_proximity=Decimal(args.boundary_proximity),
        equity=Decimal(args.starting_equity),
        stop_buffer=Decimal(args.stop_buffer),
        risk_fraction=Decimal(args.risk_per_trade),
        min_reward_risk=Decimal(args.min_reward_risk),
        break_even_r=Decimal(args.break_even_r),
        trailing_enabled=not args.no_trailing,
        trailing_buffer=None if args.trailing_buffer is None else Decimal(args.trailing_buffer),
        secondary_fvg_support_enabled=not args.no_secondary_fvg,
        partial_take_profits=_partials(args.partial_tp),
        runner_fraction=Decimal(args.runner_fraction))
    return BacktestConfig(symbol=args.symbol, data_dir=args.data,
                          starting_equity=Decimal(args.starting_equity),
                          start=args.start, end=args.end, profile=profile,
                          costs=CostModel(Decimal(args.fee_rate), Decimal(args.slippage)),
                          label=args.label)


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
