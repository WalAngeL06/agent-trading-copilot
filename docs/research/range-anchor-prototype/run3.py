"""Run prototype v3 on every pair; writes runs/range-anchor-v3_<under>_<over>.json.

Run from the repository root:
  python docs/research/range-anchor-prototype/run3.py 0.05:0.10
"""
from decimal import Decimal as D
import json
from pathlib import Path
import sys

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from detector3 import Detector3, Params3                                  # noqa: E402
from run import DATA, ROOT, export                                        # noqa: E402
from agent_trading.backtest.dataset import discover, load_stream           # noqa: E402


def main(under=None, over=None, out_name='ranges3.json'):
    out = []
    for pair_dir in sorted(p for p in DATA.iterdir() if p.is_dir()):
        pair = pair_dir.name
        candles = load_stream(discover(pair_dir, '1H'), pair, '1H').candles
        det = Detector3(Params3())
        if under is not None:
            det.under = D(under)
        if over is not None:
            det.over = D(over)
        found = det.run(candles, pair)
        out.extend(export(pair, c) for c in found)
    (ROOT / 'runs' / out_name).write_text(json.dumps(out, indent=0), 'utf-8')
    return out


if __name__ == '__main__':
    for combo in (sys.argv[1:] or ['0.05:0.15']):
        under, over = combo.split(':')
        rows = main(under, over, f'range-anchor-v3_{under}_{over}.json')
        print(f'under {under} over {over}: {len(rows)} ranges')
