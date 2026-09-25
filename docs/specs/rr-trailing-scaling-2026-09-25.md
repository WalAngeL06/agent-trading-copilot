# RR ladder, trailing modes and price-relative tolerances - design, 2026-09-25 [U-RR-TRAIL-001]

Status: approved by the owner on 2026-09-25. Implemented on 2026-09-25 (plan:
`docs/superpowers/plans/2026-09-25-rr-trailing-scaling.md`). The R ladder is
the default; the default trailing mode awaits the owner's review of the
comparison.

## Why

The owner reviewed the DD trade report ([dd-deviation-models-2026-09-25.md](dd-deviation-models-2026-09-25.md)).

**Case.** DOGE-USDT, long, 12 Dec 2025.
- The trade reached +2.06R, then closed at -1R.
- Nothing had been realised. EQ sat 3.5R from the entry, and break-even and trailing only start at EQ.

**Range check.** The owner asked for the range detection to be checked first. Findings:
- **DOGE range.** It follows the guide: two touches on each boundary, each followed by an EQ visit. It was confirmed 1.8 days before the trade and is 12.4% wide.
- **All 49 trades.**
  - Median range width is 7.0%.
  - Median range age at the fill is 2.4 days.
  - In 15 trades, EQ sits more than 2R from the entry.
  - Of the 26 full stops, 6 had first reached 1R and 3 had reached 2R.
- **Flaw 1: scaling drift.** The sweep fixes the touch tolerance and the stop buffer once, at 0.5% and 0.1% of the first 15m close (11 Sep 2025). For pairs whose price later fell, the tolerance grew: DOGE 0.9%, SUI 1.8%, XPL 3.7%. That loosens the touch and HTF-level tests. The DOGE trade is not affected.
- **Flaw 2: missing precondition.** The guide's impulse precondition (§3 step 1) is not implemented. It is recorded in the gap report and stays out of scope here.

## Decisions (owner, 2026-09-25)

| # | Decision |
|---|---|
| D1 | Fix the scaling first. Tolerances and the stop buffer become a share of the price they are applied to |
| D2 | R ladder, independent of EQ and the boundary: at 1R the stop moves to entry (at EQ if EQ comes first); at 2R, 30% of the position closes. EQ 30%, the boundary exit down to the runner, and the 20% runner stay as they are |
| D3 | Trailing starts once the stop is at entry, and follows price while it keeps moving in the trade's direction |
| D4 | Add two trailing methods, internal pivots and ATR tiers, keep the current one, and compare all of them on the 30 pairs before choosing the default |

## 1. Price-relative tolerances [U-RR-TRAIL-001], [H]-REL-TOL-001

**New optional profile fields** (`None` keeps today's absolute behaviour):
- `boundary_proximity_ratio`
- `stop_buffer_ratio`

**Where each ratio applies.** When set, it replaces the absolute value at each use, measured on the price being tested:

| Use | Absolute today | Relative |
|---|---|---|
| Range touch (RangeEngine) | `proximity` | `ratio x range_low` for a low touch, `ratio x range_high` for a high touch |
| HTF Valid level band (HtfContext) | `tolerance` | `ratio x level price` |
| Initial stop (RiskEngine) | `invalidation -/+ stop_buffer` | `invalidation -/+ ratio x invalidation` |
| Trailing buffer (broker) | `trailing_buffer`, which defaults to `stop_buffer` | `ratio x swing price` |

**Overrides.** An explicit absolute `htf_zone_tolerance` or `trailing_buffer` still wins over the ratio.

**RiskConfig.** It gains `stop_buffer_ratio`, default `None`. Both `evaluate` and supporting-zone stops use it.

**Sweep.** `--scale price` now sets the two ratios, 0.005 and 0.001, instead of converting them to absolute values at the first close. `--scale none` keeps absolute units. The `FIXED_REFERENCE_PRICE` limitation goes away, and each row reports the ratios.

**Live product.** The live BTC defaults (500 / 100 absolute) do not change.

## 2. R ladder [U-RR-TRAIL-001]

**Defaults change.**
- `partial_take_profits` becomes `({'r_multiple': '2', 'close_fraction': '0.30'},)`: 30% of the original quantity at 2R.
- `break_even_trigger` becomes `EQ_OR_R_MULTIPLE`, a new value.

**Break-even under `EQ_OR_R_MULTIPLE`.**
- The stop moves to entry when the inherited 1R rule (`break_even_r`) fires or when EQ (or the boundary, if EQ was skipped) trades, whichever comes first.
- The reason names the trigger: `BREAK_EVEN` or `RANGE_EQ_BREAK_EVEN`.

**The 2R level** uses the existing R-partial machinery. It is skipped when it lies at or beyond the boundary target, where the boundary exit owns the level.

**Allocation.** EQ 30% + 2R 30% ≤ 1 - runner 20% is validated as today.

**Panel.** The local panel settings (`config/strategy.json`, gitignored) get the 2R/30% partial, so the local PAPER agent trades the ladder.

**Shipped scenarios.** `LEGACY` in the test fixtures pins `partial_take_profits=()`. `DD` in `dd_fixtures.py` already pins it.

## 3. Trailing modes [U-RR-TRAIL-001], [H]-PIVOT-N-001, [H]-ATR-TIERS-001

**Modes.** `trailing_mode` takes one of three values:
- `CONFIRMED_HIGHER_LOW`: today's mode, the default until the comparison.
- `INTERNAL_PIVOT`: new.
- `ATR_TIERS`: new.

**Activation (D3).** Unchanged. Every mode is active only after the trade's own break-even, and never on structure from before the fill.

**`INTERNAL_PIVOT`.**
- **Pivots.** Guide §2 step 1 on the entry timeframe, with `trailing_pivot_bars = N` (default 3). A bar is a pivot low when its low is strictly below the lows of the N bars on each side; pivot highs mirror this. The pivot is confirmed at the close of bar i+N and never earlier.
- **Tracking.** A new `PivotTracker` in `strategy_v1/pivots.py` tracks them. StrategyV1 passes pivots instead of ATR swings to the broker in this mode.
- **Stop.** The trailing rule is today's: the latest eligible pivot minus the buffer, tightening only, never past entry, and strictly on the market side of the close.
- **Record.** It names `INTERNAL_PIVOT_LOW` / `INTERNAL_PIVOT_HIGH`.

**`ATR_TIERS`.**
- **Tiers.** `trailing_atr_tiers = ((0.75, 0.25), (1.25, 0.50), (1.5, 1))`, each pair being an ATR multiple and a share of the open position.
- **ATR.** The entry-timeframe ATR (`swing.atr_length`, 14 bars) as of the previous bar, passed by StrategyV1 to `broker.process(..., atr=...)`.
- **Peak.** The best price since the fill: the high for a long, the low for a short. It starts at the entry and is updated with each bar's extreme after that bar has been evaluated.
- **Trigger.** A tier fires once, when a bar trades back to `peak -/+ k x ATR`. It fills at that level, or at the open when the bar opened beyond it.
- **Quantity.** Each tier closes its share of the quantity still open (floored to the step); the last tier closes the rest. Several tiers may fire on one bar, in order.
- **Record.** Slice kind `ATR_TIER`, event `ATR_TIER_EXIT`.
- **Stop.** In this mode the protective stop is not trailed; the break-even stop remains the floor.
- **State.** The peak and the fired tiers are per-trade and reset on `submit`.

## 4. Comparison

Five 30-pair runs, all with price-relative tolerances:

| Run | R ladder | Trailing |
|---|---|---|
| S0 | no (DD as shipped: EQ break-even, no 2R) | current |
| S1 | yes | current (`CONFIRMED_HIGHER_LOW`) |
| S2 | yes | `INTERNAL_PIVOT`, N=2 |
| S3 | yes | `INTERNAL_PIVOT`, N=3 |
| S4 | yes | `ATR_TIERS` |

**Report per run.**
- CORE / YOUNG / XAUT, and long / short.
- Pooled R, win rate, PF, max drawdown in R.
- Exit kinds and fee sensitivity.
- How many trades that reached ≥1R / ≥2R still ended at -1R.

**Afterwards.** The owner picks the default trailing mode. The report page is regenerated for it.

## Testing

- **Discipline.** TDD for every rule, long and short mirrored.
- **Suites.** Full suite, frontend tests and build.
- **Legacy.** Legacy and shipped scenarios are pinned so their results do not move.
- **Invariant checks.** The sweep checks from 2026-09-24 still hold: no trail on pre-fill structure, none before the trade's own break-even, none beyond the close.

## Out of scope

- The impulse precondition (guide §3 step 1).
- Short-side rules.
- Panel fields for the new knobs.
- Threshold tuning.
