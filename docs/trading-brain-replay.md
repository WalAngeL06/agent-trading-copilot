# Causal PAPER replay — frozen boundary correction

2026-09-12. Branch `work/trading-brain`, worktree Agent Trading-brain.
Correction parent `9adfe26ad61ed63d019f70c3f69a4756710c4599`;
commit message `fix: enforce frozen range boundaries before confirmation`.
[Spec](specs/trading-brain-v0.1.md), [exact current graphs and fixture hashes](research/trading-brain-replay-evidence.json).

## Original real examples are withdrawn

The original 4H LONG is **not valid under the confirmed candidate rule**.
Previous symmetric `abs(swing.price - boundary) <= tolerance` accepted outside
swings, including62983.5 below frozen63261.6; no every-candle wick guard existed.
The corrected replay invalidates earlier, on Jul31 2026 16:00 UTC: forming
candle low62457.1 < frozen ValidLow63261.6. Neither RANGE_CONFIRMED nor PAPER
order is produced. Raw62983.5 remains in the swing/event history.
The original 1H SHORT also disappears: Sep02 11:00 low76261 < rangeLow76713.6.
Original results remain Git history at9adfe26; they are not current valid examples.

## Fixed semantics [U-RANGE-BOUNDARIES-001]

Check every candle while candidate is pending, including its forming bar and
any bar that could publish confirmation. Invalidation has priority over touches:
- low < rangeLow or high > rangeHigh => RANGE_INVALIDATED.
- equality is permitted.
- low touch must satisfy rangeLow <= swingLow <= rangeLow+tolerance.
- high touch must satisfy rangeHigh-tolerance <= swingHigh <= rangeHigh.

Record invalidation knowledge time, breach candle and lower/upper/both reasons.
Preserve frozen valid pair and all raw swings/valid levels; later touches cannot
revive that candidate. Existing one-range/no-reseed MVP policy is unchanged.
Only bars strictly after RANGE_CONFIRMED may sweep/reclaim; breach/reclaim on
an already confirmed range is manipulation and does not invalidate its formation.
SwingEngine, gap/risk/broker rules, production API and dependencies are unchanged.

## Full saved BTC replay — unchanged defaults

| Context | Candles | Range result | PAPER orders |
|---|---|---|---|
| BTC5m full fixture | 299 | WAIT_HIGH_TOUCH | 0 |
| BTC15m full fixture | 299 | RANGE_INVALIDATED | 0 |
| BTC1H full fixture | 299 | RANGE_INVALIDATED | 0 |
| BTC4H full fixture | 299 | RANGE_INVALIDATED | 0 |

No trade was forced. All retained raw/valid/FVG components continue processing.

## New real15m example — explicitly bounded context

A scan of1140 chronological suffix contexts (285 per saved timeframe, at least
15 closed candles each) retained default ATR14 *1.25, tolerance500, buffer100,
equity10000, risk0.01, quantity increment0.00000001 and EQ target throughout.
No thresholds or rules were changed. The earliest positive15m context starts at
source index50, Sep09 2026 21:15 UTC:249 exact copied rows, in
`tests/data/btcusdt_15m_range_window.jsonl`. It is a bounded suffix, **not** an
order from the original299-candle run. Raw seeding/initial pair remain context
dependent [H]; this scan does not implement automatic reseeding or prove a strategy.
87 overlapping15m contexts produced an order, not87 independent setups.
Other timeframes' suffixes produced no orders. Search counts/config/hashes are in JSON.

| Evidence | ID | UTC knowledge time | Value |
|---|---|---|---|
| VALID_LOW | e000059 | Sep11 00:15 | 76541; breaks prior high76817.4 |
| Relevant internal raw low | e000075 | Sep11 08:30 | 77141.7, distinct from frozen first validLow |
| VALID_HIGH | e000080 | Sep11 09:30 | 77498.8; breaks prior raw low77141.7 |
| RANGE_CANDIDATE | e000081 | Sep11 09:30 | Frozen76541–77498.8; EQ77019.9 |
| Inside low touch | e000088 | Sep11 10:00 | 76866;325 above low, within500 |
| Inside high touch / RANGE_CONFIRMED | e000092 | Sep11 11:15 | 77167.6;331.2 below high, within500 |
| Upside SWEEP | e000102 | Sep11 13:00 | Initial78159.9; subsequent extreme79896.3 |
| RECLAIM | e000117 | Sep11 18:15 | Body closes back inside frozen range |
| Bearish FVG | e000120 | Sep11 18:30 | 77255.5–77490.8 |
| TRADE_CANDIDATE / RISK_APPROVED | e000121/e000122 | Sep11 18:30 | SHORT signal77215; budget100 USDT |
| PAPER_ORDER_OPENED | e000123 | Sep11 18:45 | Next-open fill77214.6; effective fill18:30 |
| PAPER_ORDER_CLOSED | e000124 | Sep11 19:00 | EQ TP77019.9 |

Actual plan: **SHORT entry77214.6 / SL79996.3 / TP77019.9 /0.03594923 BTC**;
initial stop risk99.999973091 USDT. Gross simulated PnL6.999315081 excludes costs
and has no profitability implication. Every candle from formation through
confirmation is inside frozen boundaries; the test independently checks all of them.

```powershell
python -B -m agent_trading.trading_brain --candles tests/data/btcusdt_15m_range_window.jsonl --fixture-kind REAL_SAVED_BTC
```

## Corrected synthetic full-chain fixture

The prior synthetic outside touch was also incorrect. The replacement has25
synthetic BTC-priced15m candles. First ValidLow80000 is frozen; an internal raw
low90000 is the later high120000's relevant break target, so its body-close break
at89500 occurs within the frozen80k–120k pair. Candidate-stage low-touch80800
and high-touch119000 are inside, and every candidate candle is contained.
Only after RANGE_CONFIRMED does a77000 wick sweep below80000, reclaim close84000,
bullish FVG82000–85000, candidate92000 and next-open PAPER entry92000 follow.
SL76000, EQ TP100000, size0.00625 BTC, initial risk100 USDT. LONG and SHORT
full chains are tested. ATR2 *0.1/tolerance2000/buffer1000 are explicit synthetic
[H] test settings, not real-market tuning or recommendations.

```powershell
python -B -m agent_trading.trading_brain --candles tests/data/trading_brain_synthetic.jsonl --atr-length 2 --atr-multiplier .1 --boundary-proximity 2000 --stop-buffer 1000
```

## Regression and verification evidence

Full suite **292 tests passed**, zero failures/errors:281 before correction +11
additional methods. Seven boundary methods cover lower/upper/both wick breaches
in both pending phases, forming-bar rejection, same-close breach priority,
terminal invalidation, inside-only tolerance, equality and zero tolerance.
The explicit paired LONG/SHORT regression uses the same wick/reclaim prices:
BEFORE confirmation => RANGE_INVALIDATED, no manipulation;
AFTER confirmation => SWEPT then RECLAIMED, range stays confirmed.

Full-runtime regressions preserve ALL raw swings against independent unchanged
SwingEngine replay, including future raw events after invalidation and real
outside raw62983.5. Synthetic25 prefixes, original real1196 prefixes, and new
bounded real249 prefixes remain causal; new-window events also match filtered
final knowledge-time prefixes. All six offline CLI smokes passed.
Independent read-only correction review passed then-current39 focused checks
and found no material defect. Full292 also covers bounded-window and large-tolerance checks.

```powershell
$env:PYTHONPATH=(Get-Location).Path
& 'C:/Users/Serdar Arif/Desktop/Agent Trading-backend/.venv/Scripts/python.exe' -B -m unittest discover -s tests -v
```

Current evidence JSON replaces obsolete valid-trade assertions, preserving
invalidation graphs and valid bounded/synthetic order graphs. Complete local
stdout is ignored in `runs/trading-brain-*.json`. No secrets/network/exchange writes.
User boundary rules are [U], not newly DD-confirmed or [H]. Selection/ATR, gap,
plan/risk/fill and no-reseed rules remain provisional; DD N-1–N-7, MTF acceptance,
range lifecycle, costs/production risk and empirical validation remain blockers.
No merge/push/tag; STOP after the separate correction commit.
