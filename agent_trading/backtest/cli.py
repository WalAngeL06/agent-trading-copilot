"""Strategy and cost flags shared by the backtest and sweep command lines.

Every value lands in the production `StrategyProfile` or `CostModel`; nothing
here decides anything about trading on its own.
"""
import argparse
from decimal import Decimal
import json

from ..strategy_v1 import StrategyProfile, TimeframeRoles
from ..strategy_v1.config import BREAK_EVEN_TRIGGERS, ENTRY_MODELS
from .config import CostModel

# Price units, not ratios: BTC-sized by default and meaningless on another pair
# unless scaled for it. `None` in the parsed flags means "not given".
DEFAULT_BOUNDARY_PROXIMITY, DEFAULT_STOP_BUFFER = '500', '100'
ABSOLUTE_PRICE_FLAGS = (('boundary_proximity', '--boundary-proximity'),
                        ('stop_buffer', '--stop-buffer'),
                        ('trailing_buffer', '--trailing-buffer'),
                        ('htf_zone_tolerance', '--htf-zone-tolerance'))


def partials(text):
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
            raise ValueError('each partial must be R:FRACTION')
        levels.append({'r_multiple': r_multiple.strip(), 'close_fraction': fraction.strip()})
    return tuple(levels)


def add_profile_arguments(parser):
    parser.add_argument('--starting-equity', default='10000')
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
                        help='price units; defaults to the boundary proximity')
    parser.add_argument('--no-htf-confluence', action='store_true',
                        help='keep premium/discount but drop the guide 4.3 zone rule')
    parser.add_argument('--risk-per-trade', default='.01')
    parser.add_argument('--min-reward-risk', default='1')
    parser.add_argument('--stop-buffer', default=None,
                        help=f'price units; default {DEFAULT_STOP_BUFFER}')
    parser.add_argument('--boundary-proximity', default=None,
                        help=f'price units; default {DEFAULT_BOUNDARY_PROXIMITY}')
    parser.add_argument('--break-even-r', default='1')
    parser.add_argument('--trailing-buffer', help='price units; defaults to the stop buffer')
    parser.add_argument('--no-trailing', action='store_true')
    parser.add_argument('--secondary-fvg', action=argparse.BooleanOptionalAction,
                        default=False, help='tighter stop behind a secondary FVG')
    parser.add_argument('--entry-models', default=','.join(ENTRY_MODELS),
                        help=f"comma list of {', '.join(ENTRY_MODELS)} [U-DD-DEVIATION-001]")
    parser.add_argument('--model2-htf-fvg', default='auto', choices=('auto', 'true', 'false'),
                        help='model 2 needs a touched HTF FVG; auto follows the gate')
    parser.add_argument('--eq-scale-out', default='0.30',
                        help="share of the original quantity closed at range EQ, or 'none'")
    parser.add_argument('--break-even-trigger', default='RANGE_EQ',
                        choices=BREAK_EVEN_TRIGGERS)
    parser.add_argument('--partial-tp', default='',
                        help="R:FRACTION pairs, e.g. '1.0:0.20,2.0:0.20'")
    parser.add_argument('--runner-fraction', default='0.20')


def add_cost_arguments(parser):
    parser.add_argument('--fee-rate', default='0', help='fraction of notional per side')
    parser.add_argument('--slippage', default='0', help='absolute price units per side')


def _optional(value):
    return None if value is None else Decimal(value)


def profile_from_args(args):
    return StrategyProfile(
        timeframes=TimeframeRoles(args.bias_timeframe, args.range_timeframe,
                                  args.entry_timeframe),
        entry_level=args.entry_level,
        entry_level_ratio=Decimal(args.entry_level_ratio),
        direction=args.direction,
        direction_gate=args.direction_gate,
        htf_confluence_required=not args.no_htf_confluence,
        htf_zone_tolerance=_optional(args.htf_zone_tolerance),
        boundary_proximity=Decimal(args.boundary_proximity or DEFAULT_BOUNDARY_PROXIMITY),
        equity=Decimal(args.starting_equity),
        stop_buffer=Decimal(args.stop_buffer or DEFAULT_STOP_BUFFER),
        risk_fraction=Decimal(args.risk_per_trade),
        min_reward_risk=Decimal(args.min_reward_risk),
        break_even_r=Decimal(args.break_even_r),
        trailing_enabled=not args.no_trailing,
        trailing_buffer=_optional(args.trailing_buffer),
        secondary_fvg_support_enabled=args.secondary_fvg,
        entry_models=tuple(model.strip() for model in args.entry_models.split(',')
                           if model.strip()),
        model2_requires_htf_fvg={'auto': None, 'true': True,
                                 'false': False}[args.model2_htf_fvg],
        eq_scale_out_fraction=(None if args.eq_scale_out.strip().lower() == 'none'
                               else Decimal(args.eq_scale_out)),
        break_even_trigger=args.break_even_trigger,
        partial_take_profits=partials(args.partial_tp),
        runner_fraction=Decimal(args.runner_fraction))


def costs_from_args(args):
    return CostModel(Decimal(args.fee_rate), Decimal(args.slippage))


def explicit_absolute_flags(args):
    """The price-unit flags the user actually gave, in declaration order."""
    given = tuple(flag for name, flag in ABSOLUTE_PRICE_FLAGS
                  if getattr(args, name, None) is not None)
    if Decimal(getattr(args, 'slippage', '0')) != 0:
        given += ('--slippage',)
    return given
