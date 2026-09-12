# Causal range sweep PAPER strategy v0.1

2026-09-12. Authority: [U-TRADING-BRAIN-001], explicit urgent implementation.
Base adbafa485c900164c95ed0e13fce0d267da8b645; isolated work/trading-brain.
This task supersedes inherited STOP/no-strategy gates only for this slice.
SwingEngine is preserved byte-for-byte. No general DD MarketStructureEngine
completion, API/frontend integration, live exchange writes or profitability claim.

## Provenance
[D-DD-MSB-001] DD-1 separates raw from structural swings; DD-4 prices levels
from responsible wick extremes; DD-5/6 distinguish strict body-close breaks
from wick penetration/equality; DD-18/19 require opposing movement, distinguish
occurrence/knowledge and do not approve fixed pivot counts. SOURCE-CONFIRMED,
not empirically validated. Current ATR raw confirmation stays [H]-SWING-ATR-CLOSE-001.
The user's new valid-pair, low-first range traversal, strict body-close break,
frozen boundaries, sweep/reclaim, FVG/iFVG requirement and PAPER scope are
[U-TRADING-BRAIN-001], not new DD attestations.

## Explicit provisional definitions [H]
- [H]-STRUCTURE-001: on each newly confirmed LOW, select that raw wick and the
  latest earlier confirmed HIGH as its break target (HIGH is symmetric).
  New same-side raw confirmations replace pending unvalidated candidates.
  Confirm only a later-than-swing closed candle with close strictly above/below
  target; equality and wick penetration fail. Examine closes from raw publication
  onward only; earlier breaks are conservatively not promoted retrospectively.
  Publish valid level at the current close; retain raw swing and target identities.
- [H]-RANGE-001: first ValidLow, then a later ValidHigh with higher price creates
  one frozen range. Ignore subsequent valid levels for its boundaries. Require
  a confirmed LOW whose wick time is strictly after ValidHigh publication and
  within configurable absolute-price tolerance of rangeLow; then a confirmed
  HIGH whose wick time is strictly after low-touch publication, near rangeHigh.
  Internal swings are unlimited. These ordered extrema proxy flows without
  imposing monotonic candles. No expiry/reseed in this bounded MVP replay.
- [H]-MANIPULATION-001: only bars strictly after RANGE_CONFIRMED can sweep.
  Strict wick outside + strict close inside confirms reclaim, including on the
  same bar. Track most extreme wick until reclaim. A bar sweeping both boundaries
  cancels pending manipulation and emits ambiguity, since OHLC cannot order it.
  A new sweep before a candidate replaces/cancels the old reclaimed setup.
- [H]-GAP-001: bullish three-closed-candle FVG is first.high < third.low;
  bearish is first.low > third.high, no minimum size/displacement/filter.
  For direct FVG, first bar must be at/after sweep and third strictly after reclaim.
  iFVG: an existing opposite gap flips on a later close strictly through its far
  edge (prior close on the other side); inversion must be after reclaim.
  Each gap inverts at most once; no mitigation/expiry semantics. Matching direction
  and entry still inside range on manipulation side of target are required.
- [H]-PLAN-001: candidate entry = gap/inversion publication close; stop = swept
  wick +/- explicit positive stop buffer; TP = configurable EQ or opposing boundary.
  Reject nonpositive prices or invalid directional stop/entry/TP geometry.
- [H]-RISK-001: explicit paper equity * risk_fraction (0 < fraction <= 1)
  divided by absolute entry-stop, rounded DOWN to configured quantity increment.
  Reject zero quantity or notional greater than paper equity (unleveraged paper).
  No portfolio, fees, slippage, exchange lot/tick policy or production risk approval.
- [H]-PAPER-001: next candle OPEN fills a candidate (never the signal candle's
  earlier OHLC); revalidate geometry and resize using actual fill. One order per
  range, no pyramiding. Invalid/gapped fill cancels it. On fill/later candles,
  stop before TP if both touched (conservative intrabar convention); gap exits
  at open if already beyond SL/TP. Record exit/PnL/equity locally only.
  filled_at is the next bar opening time; opened_at/closed_at are publication
  times at the processed close, preserving the causal knowledge boundary.

## Contract and causality
Every instance owns one symbol/timeframe. Closed contiguous candles, UTC and
Decimal only; malformed/foreign/duplicate/gapped input fails before state mutation.
TradingBrain.process(Candle) drives existing SwingEngine -> StructureEngine ->
RangeEngine -> ManipulationEngine + GapEngine -> TradeCandidate -> PaperBroker.
RiskPolicy is separate from signal recognition. Immutable events reference prior
event IDs and source IDs. Knowledge time is observed_at, never swing_time.
No supplied future raw swing API in the end-to-end runtime; process uses only
SWING_CONFIRMED events returned on the current candle. replay uses that same path.
Full-prefix replay and batch-then-stream must match each event/trade/state exactly.

## Verification and limits
Prefer saved real BTC fixtures; do not tune parameters to claim real profitability.
Synthetic BTC-priced candles are clearly labelled synthetic and must drive the
unaltered real SwingEngine through a complete pair/range/sweep/gap/paper fill.
Test strict closes, frozen boundaries, unlimited internal swings, both directions,
iFVG, risk rounding, gap/cancellation, ambiguous bars, exits and every prefix.
Smoke all saved BTC fixtures and record observed component counts honestly.
Full existing tests are required. Missing DD responsibility/scale/quality rules,
MTF context, production acceptance/risk, costs and validation remain blockers.
