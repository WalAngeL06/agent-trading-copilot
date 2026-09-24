# Causal Strategy V1 backtest engine v0.1

2026-09-12. Authority: user backtest task. Branch `work/backtest-v1`, based on
`9f6884ed74ef81c4540da7ae1bd46b41c77e2a59`. PAPER only, offline only.
**Not a profitability claim.** Every number in an artifact comes from one real
replay of frozen candles; nothing is tuned, fitted or cherry-picked.

## Architecture

```
frozen local candles (JSONL/CSV)
  -> dataset loader          strict: closed-only, contiguous, one symbol
  -> chronological MTF merge  (close_time, then highest timeframe first)
  -> production StrategyV1    every strategy decision happens here
  -> production RiskEngine / PendingLimitPaperBroker / PositionLedger
  -> recorder                 reads ledgers; decides nothing
  -> metrics + artifacts
```

`agent_trading/backtest/` contains `config`, `dataset`, `engine`, `recorder`,
`metrics`, `report`, `format`, `__main__` and a **separate** `fetch` utility.

## No duplicated strategy logic

The engine's only decision is the ORDER in which already-closed candles are
handed to `StrategyV1.process`. Bias, range, manipulation, FVG selection, entry
pricing, sizing, stops, break-even, trailing, partials, the RangeHigh exit and
the runner are all decided inside the shipped strategy. A test asserts that no
backtest module (except the optional fetcher) calls `RangeEngine(`,
`ManipulationEngine(`, `GapEngine(`, `BiasEngine(`, `StructureEngine(`,
`SwingEngine(`, `RiskEngine(`, `PendingLimitPaperBroker(`, `entry_price(`,
`partial_target(` or `tighten_stop(`.

## Causality

Only closed candles are loaded; an unclosed row is excluded and counted, never
guessed. Streams must be gap-free, duplicate-free and single-symbol. The merged
order is `(close_time, timeframe rank)`, so at equal timestamps the higher
timeframe resolves first and a 15m bar can never observe a 1H or 4H bar that has
not closed. The engine asserts the order never regresses, and `StrategyV1`
independently enforces chronology, per-stream contiguity and equal-time ranking.

## Data

Datasets are directories holding `*_4H`, `*_1H` and `*_15m` files (`.jsonl`,
`.json` or `.csv`). The replay never touches the network.

`python -m agent_trading.backtest.fetch --symbol BTC-USDT --out data/btc` is a
separate utility that freezes public candles through the shipped read-only
market adapter (public market reads only: ticker, candles, orderbook and, since
2026-09-21, the spot instrument and ticker listings). It is never imported by
the replay path. Its multi-pair form and the sweep are described in section D.

## Costs

`fee_rate` and `slippage` both default to **0** and no exchange schedule is
assumed. When supplied they are applied to realised slices *after* the strategy
decided, so they change reported PnL but never a stop, target or size. Each
slice records `gross_pnl`, `cost` and `net_pnl` separately.

## Accounting

One logical trade stays one record, read from the production `PositionLedger`:
partial R exits, the RangeHigh exit and the runner exit are slices of it, never
separate trades. Each record carries trade id, setup and entry times, entry
price, initial stop, frozen initial R, original quantity, every slice, final
exit time, exit reason, gross/cost/net PnL, R multiple and duration.

The equity curve is **realised only** — one point per realised slice plus an
opening point. Unrealised movement between exits is deliberately not modelled,
so the curve never implies a mark-to-market the replay did not compute.
Drawdown is measured against the running peak of that curve.

Zero denominators yield `null`, never a fabricated infinity: with no closed
trades, win rate, profit factor and every R statistic are null.

## Artifacts

`backtest_summary.json`, `trades.csv`, `trades_detail.json`, `events.jsonl`,
`equity_curve.csv`, `run_config.json`, `setup_funnel.json`. Decimals serialise
without trailing zeros and never in exponent form. `backtest_summary.json`
carries a `demo` block shaped for a frontend card, built from the real run.

## Known limitation that dominates results

`RangeEngine` keeps **one** range per instance: once a `RangeState` exists it is
never replaced, and a confirmed range is terminal. `StrategyV1` also sets
`_setup_consumed` after one submission. Therefore **one run evaluates at most
one range and can produce at most one logical trade**, however long the dataset
is, and if that first range candidate invalidates, the rest of the run is dead.

This is existing Strategy V1 behaviour (already declared as
`SINGLE_RANGE_SINGLE_SETUP`) and was NOT changed here, because changing it would
change strategy semantics. It is the blocker for statistically meaningful
backtesting and needs an explicit user decision.

## User-authorised semantic changes (A / B / C)

**A - [U-RANGE-RESEEK-001] range re-seek.** `RangeEngine(proximity,
allow_reseek=True)` drops an **invalidated** candidate and waits for a fresh
Valid pair instead of ending the stream. A CONFIRMED range is still terminal.
Default off at the engine, on via `StrategyProfile.range_reseek_enabled`, so the
older `trading_brain` runtime keeps its original one-range behaviour.
`StrategyV1` emits `RANGE_RESEEK` and discards the old manipulation with it.

**B - [U-MULTI-SETUP-001] multi-setup.** `StrategyProfile.multi_setup_enabled`
releases the setup slot once nothing is pending or open, emitting
`SETUP_SLOT_RELEASED`. Bias, range and manipulation state are untouched. The
broker now resets its per-trade protection state on every `submit`, and the
recorder derives break-even and trailing counts from the trade's own
`stop_updates`, so a later trade can never inherit an earlier one's history.
Correction 2026-09-24: the broker reset described here was never in the code
until then; it landed with the trailing fix recorded in the strategy spec,
"Structural trailing".

**C - longer frozen data.** `python -m agent_trading.backtest.fetch` now pages
backwards with `after`, because the shipped adapter caps one call at 300 bars.
`--limit 10000 --timeout 120` produced 4H 2022-02-19+, 1H 2025-07-23+ and 15m
2026-05-31+. Datasets live under a gitignored `data/`; re-fetch to reproduce.

## The remaining blocker: a CONFIRMED range never retires

A fixes invalidated candidates, and it works: 22 candidates instead of 1 on the
60-day set. But the run still ends at zero trades, because the FIRST range that
CONFIRMS freezes the strategy permanently.

Evidence from the 10000-bar run: the range confirmed on 2025-09-10 at
110608.8-113277.5 and stayed. All 42 LONG manipulations landed 2025-09-28 to
2025-11-02 against it. Price then left that band for good. Ten months later the
strategy is still holding the same frozen range, so no LONG setup can form.

More data makes this worse, not better: a deeper 1H history means an earlier
first confirmation and a staler range. This needs an explicit decision on when a
confirmed range should retire, and was NOT invented here.

## D - multi-pair replay [U-MULTI-PAIR-001] (2026-09-21)

**Fetch.** `python -m agent_trading.backtest.fetch --universe --quote USDT --top 30
--limits 4H=10000,1H=10000,15m=36000 --out DIR` selects live OKX TR spot pairs
in the quote currency, drops stablecoin and fiat bases
([H]-UNIVERSE-EXCLUDE-001), ranks them by 24h quote volume and writes
`DIR/universe.json`, one folder per pair (`DIR/<instId>/<slug>_<tf>.jsonl`)
and `DIR/fetch_manifest.json`. Every pair ends at the same moment (`as_of`).
Paging stops at the real end of history; when bars are missing only the newest
unbroken segment is kept and the dropped count is recorded. Calls are paced,
page faults retried with backoff, and a failing pair restarts once on a fresh
session before it is marked FAILED while the run continues. Three failures in a
row, or a contract fault, stop the run. `--resume` continues with the same
choices; `--symbols A,B` skips the listing; `--symbol` keeps the flat layout.

**Sweep.** `python -m agent_trading.backtest.sweep --data DIR --output OUT` runs
the unchanged engine on every dataset folder, writes the usual artifacts per
dataset, and adds `sweep_summary.json`, `sweep_symbols.csv` and
`sweep_trades.csv`. A folder that cannot load is SKIPPED with its reason; one
that loads but cannot run is FAILED. Reruns are byte-identical.

**Scaling [H]-SWEEP-SCALE-001.** `boundary_proximity` and `stop_buffer` are price
units. Under the default `--scale price` they become 0.005 and 0.001 of the
first entry-timeframe close in the window (500 and 100 at a BTC price of
100,000); the HTF tolerance and the trailing buffer follow them. Explicit
price-unit flags are refused in that mode; `--scale none` keeps them absolute.
On the local BTC data `--scale none` reproduces the single-run result exactly
(2 trades, 10096.402343948), and price scaling gives 2 trades, 10095.3721872805.
Both figures predate the 2026-09-24 broker trailing fix; after it the same
single run gives 1 trade and 10112.627090374. The first 30-pair result is in
PROJECT_STATE, 2026-09-24.

**Caveats.** The list is chosen by today's volume, so the past is seen through
survivors and delisted pairs are absent. Pooled trades are not independent
(pairs move together) and windows differ per pair (young listings have less
history). The scaling reference is fixed at the window start, so a pair that
moved a lot drifts from it; `price_drift` in each row shows by how much.
