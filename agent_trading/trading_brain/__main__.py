"""Offline JSONL PAPER replay. No toolkit, network, credentials or LIVE mode."""
import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from . import BrainConfig, replay
from ..swing import SwingConfig
from ..data import read_candles
from ..models import to_jsonable


def main():
    parser = argparse.ArgumentParser(description='Causal range sweep PAPER replay [H]')
    parser.add_argument('--candles', required=True, type=Path)
    parser.add_argument('--atr-length', type=int, default=14)
    parser.add_argument('--atr-multiplier', default='1.25')
    parser.add_argument('--boundary-proximity', default='500', help='absolute price units [H]')
    parser.add_argument('--stop-buffer', default='100', help='absolute price units [H]')
    parser.add_argument('--equity', default='10000')
    parser.add_argument('--risk-per-trade', default='.01', help='equity fraction [H]')
    parser.add_argument('--quantity-step', default='.00000001')
    parser.add_argument('--target', choices=('EQ','BOUNDARY'), default='EQ')
    parser.add_argument('--stop-profile', choices=('STRUCTURE_BE', 'FIXED_SL_TP'), default='STRUCTURE_BE')
    parser.add_argument('--break-even-r', default='1', help='favorable excursion in initial R [H]')
    parser.add_argument('--min-reward-risk', default='1', help='minimum reward/risk ratio [H]')
    parser.add_argument('--max-stop-distance', help='optional absolute price distance [H]')
    parser.add_argument('--fixture-kind', choices=('SYNTHETIC','REAL_SAVED_BTC','UNKNOWN'))
    args = parser.parse_args()
    try:
        config = BrainConfig(swing=SwingConfig(atr_length=args.atr_length,
                             atr_multiplier=Decimal(args.atr_multiplier),
                             bootstrap_candles=max(200,args.atr_length+1)),
                             boundary_proximity=Decimal(args.boundary_proximity),
                             stop_buffer=Decimal(args.stop_buffer), equity=Decimal(args.equity),
                             risk_fraction=Decimal(args.risk_per_trade),
                             quantity_step=Decimal(args.quantity_step), target=args.target,
                             stop_profile=args.stop_profile, break_even_r=Decimal(args.break_even_r),
                             min_reward_risk=Decimal(args.min_reward_risk),
                             max_stop_distance=Decimal(args.max_stop_distance) if args.max_stop_distance else None)
        report = replay(read_candles(args.candles),config).report()
        report['fixture_kind'] = args.fixture_kind or ('SYNTHETIC' if
                                 args.candles.name=='trading_brain_synthetic.jsonl' else 'UNKNOWN')
        report['fixture_sha256'] = hashlib.sha256(args.candles.read_bytes()).hexdigest()
    except (ValueError, InvalidOperation, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(to_jsonable(report),sort_keys=True,indent=2))

if __name__=='__main__': main()
