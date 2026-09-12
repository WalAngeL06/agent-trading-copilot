# Causal range sweep PAPER replay evidence

2026-09-12. Isolated `work/trading-brain`, requested base
`adbafa485c900164c95ed0e13fce0d267da8b645`. Commit message:
`feat: add causal range sweep paper strategy` (obtain final hash from Git).
[Spec](specs/trading-brain-v0.1.md), [exact evidence graph and fixture hashes](research/trading-brain-replay-evidence.json).

The opt-in stdlib runtime completes both real BTC and synthetic candle chains
through the preserved SwingEngine. No supplied/injected swings in these replays.
SwingEngine is unchanged. Existing API/decision chain remains its existing behavior;
this module is separately opt-in and has no network/exchange order client.

## Real BTC 4H LONG — default settings, iFVG

All dates/times below are UTC knowledge times, unless labelled wick/fill time.
Saved `tests/data/btcusdt_4H.jsonl`, 299 closed candles. Defaults: raw ATR14 *1.25
(existing [H]), boundary proximity500, stop buffer100, paper equity10000,
risk fraction0.01, quantity step0.00000001, target EQ. No search/tuning for this trade.

| Event | ID | Knowledge time | Evidence |
|---|---|---|---|
| Raw previous high | e000014 | Jul29 20:00 | Wick64751.6 at Jul29 12:00 |
| Raw responsible low | e000015 | Jul30 12:00 | Wick63261.6 at Jul30 00:00 |
| VALID_LOW | e000016 | Jul30 12:00 | Close64795 > previous high64751.6; valid price63261.6 |
| Raw responsible high | e000018 | Jul31 08:00 | Wick65423.7 at Jul31 04:00 |
| VALID_HIGH | e000022 | Jul31 16:00 | Close62725 < previous low63261.6; valid price65423.7 |
| RANGE_CANDIDATE | e000023 | Jul31 16:00 | Frozen low63261.6 / high65423.7 / EQ64342.65 |
| Near-low raw swing | e000033 | Aug03 00:00 | Wick62983.5 at Aug02 12:00; distance278.1 <=500 |
| RANGE_LOW_TOUCH | e000034 | Aug03 00:00 | Low-side traversal recognized |
| Near-high raw swing | e000050 | Aug07 00:00 | Wick65026.6 at Aug06 00:00; distance397.1 <=500 |
| RANGE_CONFIRMED | e000051 | Aug07 00:00 | Ordered low/high touches; no fixed swing-count rule |
| SWEEP | e000084 | Aug11 20:00 | Low63237.6 < rangeLow63261.6 |
| RECLAIM | e000085 | Aug11 20:00 | Same bar close63539.9 inside frozen range |
| Bearish FVG | e000086 | Aug11 20:00 | Three bars12:00/16:00/20:00; gap63655.4–64044.5 |
| Bullish iFVG | e000088 | Aug12 12:00 | Later close64236.3 crosses above far edge64044.5 |
| TRADE_CANDIDATE | e000089 | Aug12 12:00 | LONG entry64236.3 / SL63137.6 / TP64342.65 |
| RISK_APPROVED | e000090 | Aug12 12:00 | [H] paper risk100 USDT; planned size0.09101665 BTC |
| PAPER_ORDER_OPENED | e000091 | Aug12 16:00 | Next-open fill64236.3; effective filled_at Aug12 12:00 |
| PAPER_ORDER_CLOSED | e000092 | Aug12 16:00 | Fill bar touches EQ TP64342.65; gross simulated PnL9.6796207275 |

Actual initial stop risk99.999993355 USDT <=100. This is ~0.0968R gross;
no fees/slippage, minimum reward/risk or profitability assertion. The frozen
range can persist for days because expiry/invalidation/reseed are unspecified.

Reproduce from the worktree root:

```powershell
python -B -m agent_trading.trading_brain --candles tests/data/btcusdt_4H.jsonl --fixture-kind REAL_SAVED_BTC
```

## Real BTC 1H SHORT — FVG

Default settings also produce a real saved-candle SHORT. ValidLow76713.6 on
Sep02 06:00 (close77658.8 >77643.2); ValidHigh77788.1 on Sep02 11:00
(close76683.2 <76713.6); EQ77250.85. Low-touch76963.2 recognized Sep03 03:00;
high-touch78176.1 recognized Sep03 10:00 confirms range. Sweep78066.5 on
Sep11 17:00; reclaim close77532.2 on18:00; bearish FVG77375–77490.8 at20:00.
Candidate close77289.9; next-open fill77289.8, SL78166.5, TP77250.85,
size0.11406410 BTC, initial risk99.999996470 USDT. Fill bar reaches TP;
gross simulated PnL4.4427966950 USDT. Complete IDs/timestamps are in JSON.

## Synthetic full-chain regression

`tests/data/trading_brain_synthetic.jsonl` is **synthetic**, BTC-priced, 22
closed15m candles. ATR2 *0.1, tolerance2000, stop buffer1000 are explicit [H]
test parameters; they are not recommendations or parameters fitted to real BTC.
ValidLow80000 via close114000 >110000; ValidHigh120000 via close79500 <80000.
Frozen EQ100000. Near-low78800, then near-high119000 confirms range.
Sweep77000 then reclaim84000; bullish FVG82000–85000; candidate92000;
next-open PAPER fill92000, SL76000, TP100000, size0.00625 BTC, risk100 USDT.
Later TP gives gross synthetic PnL50 USDT. Synthetic SHORT symmetry is also tested.

```powershell
python -B -m agent_trading.trading_brain --candles tests/data/trading_brain_synthetic.jsonl --atr-length 2 --atr-multiplier .1 --boundary-proximity 2000 --stop-buffer 1000
```

## Offline smoke and tests

| Saved BTC timeframe | Candles | Raw swings | ValidLow/High | Range confirmed | Sweeps/reclaims | FVG/iFVG | PAPER orders |
|---|---|---|---|---|---|---|---|
| 5m | 299 | 49 | 8/8 | 0 | 0/0 | 68/53 | 0 |
| 15m | 299 | 46 | 6/10 | 1 | 9/6 | 60/52 | 0 |
| 1H | 299 | 53 | 9/12 | 1 | 6/5 | 49/42 | 1 |
| 4H | 299 | 49 | 8/10 | 1 | 5/4 | 53/42 | 1 |

Baseline250; final **281 tests pass**, zero failures/errors (31 new).
Every1196 saved BTC prefix and22 synthetic prefixes compare state with streamed
processing; synthetic events also compare with filtered final knowledge-time
prefixes. Bootstrap/stream splits, strict breaks/equalities, frozen boundaries,
unlimited internal swings, no-gap/stale sweep, both directions, risk rounding,
next-open fills/cancel, conservative exits and causal evidence graphs are covered.
Independent read-only review reproduced/fixed an opposing-boundary equality bug;
re-review found no further material defects and passed all31 focused checks.

Full suite (launcher unavailable; reuse existing product-test environment with
imports explicitly directed to this worktree; no package installations):

```powershell
$env:PYTHONPATH=(Get-Location).Path
& 'C:/Users/Serdar Arif/Desktop/Agent Trading-backend/.venv/Scripts/python.exe' -B -m unittest discover -s tests -v
```

All five offline CLI smokes passed. Complete local stdout is ignored under
`runs/trading-brain-*.json`; durable JSON above includes counts/config/hashes and
complete transitive evidence for each opened/closed example. It contains only
public historical market facts, synthetic candles, parameters and paper records.

## Source-confirmed vs provisional and blockers

[D-DD-MSB-001]: raw != structural (DD-1), responsible wick prices (DD-4),
strict body-close breaks/equality (DD-5/6), occurrence vs knowledge and no fixed
pivot count (DD-18/19) are source-confirmed. None is empirically validated here.
New user chain/lifecycle rules are [U-TRADING-BRAIN-001], not new DD attestations.
Every runnable selection/threshold/traversal/gap/plan/risk/fill convention is
explicit [H] in the spec and event sources, including preserved ATR raw swings.

Remaining blockers: DD N-1–N-7, especially responsibility/scale/initialization;
range expiry/invalidation/reseed; gap mitigation/expiry/displacement semantics;
MTF strategy context/acceptance; minimum reward/risk, costs, capital/exchange policy
and independent empirical strategy validation. This is one frozen range/one
order per replay, no durable broker restart recovery, API/UX wiring, autonomous
loop or production portfolio/risk manager. LIVE remains excluded. No merge/push/tag.
STOP after the requested commit.
