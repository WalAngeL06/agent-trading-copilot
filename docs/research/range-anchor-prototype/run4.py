"""Run prototype v4 (5% under, 10% over, no close outside the levels); writes runs/range-anchor-v4.json."""
import json, sys
from decimal import Decimal as D
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from detector4 import Detector4
from detector3 import Params3
from run import DATA, ROOT, export
from agent_trading.backtest.dataset import discover, load_stream
out = []
for pair_dir in sorted(p for p in DATA.iterdir() if p.is_dir()):
    pair = pair_dir.name
    candles = load_stream(discover(pair_dir, '1H'), pair, '1H').candles
    det = Detector4(Params3()); det.under, det.over = D('0.05'), D('0.10')
    out.extend(export(pair, c) for c in det.run(candles, pair))
(ROOT / 'runs' / 'range-anchor-v4.json').write_text(json.dumps(out, indent=0), 'utf-8')
print('v4 ranges', len(out))
