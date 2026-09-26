"""Run the prototype detector on every pair and export its ranges.

Writes runs/range-anchor-prototype.json (gitignored). lowT/highT are the
RL/RH defining swings as bar open times, the review page's format.
Run from the repository root: python docs/research/range-anchor-prototype/run.py
"""
from datetime import timedelta
import json
from pathlib import Path
import sys

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from detector import Detector, Params                                     # noqa: E402
from agent_trading.backtest.dataset import discover, load_stream           # noqa: E402

ROOT = HERE.parents[2]
DATA = ROOT / 'data' / 'okx_tr_usdt_top30'
HOUR = timedelta(hours=1)


def bar(t):
    return int((t - HOUR).timestamp())


def export(pair, cand):
    up = cand.direction == 'UP'
    ref_t, react_t = bar(cand.ref_time), bar(cand.react_time)
    touches = lambda xs: [[bar(t), float(p)] for t, p in xs]
    return dict(
        id=f"{pair}_{cand.ref_time:%Y%m%dT%H}_{cand.direction}",
        pair=pair, direction=cand.direction,
        rl=float(cand.rl), rh=float(cand.rh),
        lowT=react_t if up else ref_t, highT=ref_t if up else react_t,
        born=bar(cand.ref_time), confirmed=bar(cand.confirmed_at),
        end=bar(cand.ended_at) if cand.ended_at else None,
        why=cand.end_reason,
        refTouches=touches(cand.touches_ref), reactTouches=touches(cand.touches_react),
        origin=float(cand.origin),
        hAtr=round(float((cand.rh - cand.rl) / cand.atr), 2))


def main(params=None):
    params = params or Params()
    out = []
    for pair_dir in sorted(p for p in DATA.iterdir() if p.is_dir()):
        pair = pair_dir.name
        candles = load_stream(discover(pair_dir, '1H'), pair, '1H').candles
        found = Detector(params).run(candles, pair)
        out.extend(export(pair, c) for c in found)
        print(f'{pair:<11} {len(found):>3} ranges')
    (ROOT / 'runs' / 'range-anchor-prototype.json').write_text(json.dumps(out, indent=0), 'utf-8')
    print('total', len(out))
    return out


if __name__ == '__main__':
    main()
