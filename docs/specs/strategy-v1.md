# Configurable 4H / 1H / 15m LONG-only Strategy V1

2026-09-12. Authority: [U-STRATEGY-V1-001]. Base `8399b99ccd019b2cfb4e7758bd7561e85b182495`
on `work/final-demo` (the `bbaa00e3` checkpoint named in the instruction was no
longer HEAD). Worktree `work/strategy-v1`. PAPER only. Not backtested: no win
rate, profit factor, drawdown or parameter optimisation is claimed or computed.

## Roles and configuration

`StrategyProfile` owns every timeframe role and threshold. The engine reads roles,
never literals, so `TimeframeRoles('1H','15m','5m')` is a configuration change.

| Field | Default | Note |
|---|---|---|
| `timeframes.bias / range / entry` | `4H / 1H / 15m` | must strictly descend |
| `direction` | `LONG_ONLY` | the only accepted value |
| `entry_zone` | `BULLISH_FVG` | |
| `entry_level` | `FVG_EQ` | `FVG_LOW` / `FVG_EQ` / `FVG_HIGH` |
| `entry_level_ratio` | `0.5` | [H]-SV1-ENTRY-LEVEL-001; 0.5 is never inlined |
| `boundary_proximity` | `500` | inherited range tolerance |
| `stop_buffer` | `100` | inherited absolute buffer |
| `min_reward_risk` | `1` | equality passes |
| `break_even_r` | `1` | [H]-SV1-BE-001, inherited |
| `secondary_fvg_support_enabled` | `True` | |
| `allow_ifvg_entry` | `False` | [H]-SV1-ALLOW-IFVG-001; iFVG stays available |
| `fvg_freshness_enabled` | `True` | [H]-SV1-FRESH-001 |
| `primary_failure_mode` | `CLOSE_BELOW_PRIMARY_LOW` | [H]-SV1-PRIMARY-FAIL-001 |
| `pending_expiry_bars` | `None` | [H]-SV1-PENDING-EXPIRY-001 |

## 4H bias

Raw swings and Valid High / Valid Low keep their shipped meaning; structural
breaks remain **body close only**, so a wick beyond a level is never a break and
fixed N-bar pivots are not used. The engine keeps `current_` and `past_` Valid
High/Low plus the unbroken level a break would consume.

A bullish break is the closed bias candle whose **close exceeds the relevant
unbroken Valid High**. It is recognised on that candle; no future Valid High has
to form first. Classification [H]-SV1-BIAS-001: a break from `LONG_DISABLED`
yields `BULLISH_REVERSAL`, otherwise `BULLISH_CONTINUATION`. Both grant long
permission. A closed candle closing below the relevant unbroken Valid Low sets
`LONG_DISABLED` — an observation that only removes long permission. No bearish
state ever creates a SHORT candidate, plan or order anywhere in Strategy V1.

Evidence: broken level id, broken price, break candle, close price, confirmed_at,
previous bias, new bias.

## 1H range

The shipped `RangeEngine` is reused unchanged, so the corrected boundary
semantics hold: the frozen pair is the selected Valid Low / Valid High, EQ is the
midpoint and **contextual only**, and before confirmation any wick below
RangeLow or above RangeHigh invalidates the candidate while every raw swing is
retained. There is no "two touches" rule; internal swing count is unrestricted.
Boundary tolerance stays configurable.

Range detection runs continuously. Bias permission gates the *entry*, not range
formation, so an existing range is not lost because bias arrived later.

## 1H manipulation

The shipped `ManipulationEngine` is reused, so manipulation can only exist after
`RANGE_CONFIRMED`. A LONG setup needs a low below frozen RangeLow followed by a
closed candle whose body closes back inside the range. Evidence carries range id,
RangeLow/RangeHigh, sweep extreme, swept_at, reclaim time and confirmed_at. An
upside sweep stays observable and logged but never becomes a setup.

## MTF causality

Every engine consumes one closed candle. `StrategyV1.process` enforces global
chronology across streams, per-stream contiguity, and — at equal close times —
highest timeframe first, so a 15m decision can never read an unclosed 1H or 4H
bar. Replay and incremental processing are the same code path.

Entry search requires long permission **and** `RANGE_CONFIRMED` **and** a
confirmed downside reclaim.

## 15m entry

`PRIMARY_FVG` is the first eligible fresh bullish gap published **after** the
reclaim whose forming candles start at or after the sweep, so an unrelated
ancient gap cannot be used. Entry price is `FVG_LOW`, `FVG_EQ` or `FVG_HIGH`;
`FVG_EQ = lower + (upper - lower) * entry_level_ratio`, exact Decimal.

Freshness [H]-SV1-FRESH-001 reuses the shipped supporting-zone rule
([H]-RISK-ZONE-001): a later candle whose wick intersects the gap removes
freshness; a close past the protective edge invalidates it. The only addition is
that the two outcomes are named `TOUCHED` and `INVALIDATED` rather than collapsed
into one boolean. A gap's own publishing candle never ages it.

## Entry execution

A pending limit-style PAPER entry waits until price actually trades back to the
configured level. There is no forced market fill at an unrelated next open, and
no fill on or before the publishing candle. Fill price is the entry level, or the
candle open when it gapped past it. Geometry, reward/risk and size are
re-approved at the actual fill through the shipped `RiskEngine.revalidate_fill`.
Intrabar order is never inferred: stop is resolved before target.

## Stops

Preferred chain: `PRIMARY_FVG` -> closest eligible fresh `SECONDARY_FVG` strictly
below it -> most recent confirmed entry-timeframe swing low at or below that
secondary -> stop beyond it by `stop_buffer`. This is expressed as a
caller-supplied `SupportingZone` whose invalidation level is the protecting
swing, so the shipped RiskEngine derives the stop; no new detector exists and no
Order Block or Breaker logic was added.

Fallback when no eligible secondary or no protecting swing exists: the
manipulation sweep extreme minus `stop_buffer` — the shipped `SWEEP_EXTREME`
path. The fallback is not a softer gate: it faces the same reward/risk test and
in the acceptance fixture it correctly blocks the same setup.

## Target

The terminal target is the **frozen 1H RangeHigh**, never EQ. Reward/risk uses
the configured FVG entry, the structural initial stop and RangeHigh. A target not
above entry cannot be approved.

## Break-even and recovery

Stops only tighten; every change goes through `RiskEngine.tighten_stop`, so the
LONG `new_stop >= current_stop` invariant lives in one place. The inherited 1R
favorable-excursion break-even remains ([H]-SV1-BE-001).

Recovery [H]-SV1-RECOVERY-001, because the user has not defined the failure
event mathematically: `PRIMARY_FVG` is treated as failed when a closed entry
candle closes below `PRIMARY_FVG.lower`; the secondary is treated as holding when
a later closed candle reaches `SECONDARY_FVG.upper` without closing below
`SECONDARY_FVG.lower`; once both hold and price trades back to the original
entry, the stop moves to that entry. Recovery is unavailable when no secondary
was selected.

## Structural trailing

`trailing_enabled` (default true), `trailing_mode` (`CONFIRMED_HIGHER_LOW`) and
`trailing_buffer` (None reuses `stop_buffer`) are configuration. [H]-SV1-TRAIL-001.

Trailing starts only after the trade's own break-even protection is reached,
which the broker announces once per trade as `BREAK_EVEN_PROTECTED`; the broker
clears break-even and the recovery chain on every `submit`. From then on, each
closed entry candle considers entry-timeframe swing lows that **formed at or
after the fill** and were **already confirmed on an earlier bar**. The best
eligible proposal is `confirmed higher low - trailing_buffer`, accepted only
when it is strictly tighter than the current stop, not below the entry, and
strictly below the close of the bar it is set on. A short mirrors all of it with
lower highs. `RiskEngine.tighten_stop` still applies, so
`new_stop >= current_stop` holds in one place and a loosening proposal is a
no-op. The RangeHigh target never moves.

Fixed on 2026-09-24 after the first 30-pair sweep: the broker used to keep
break-even across trades and to accept any swing since the start of the run, so
a stop could jump to structure far beyond price (AVAX-USDT, a long at 9.17 had
its stop moved to 34.98) and the next bar's open closed the trade.

Swings confirmed on the current bar are deliberately not used for that bar: the
broker runs before the swing engine, so a stop can never tighten on structure
the finished bar itself published and then be used to resolve that same bar's
exits. Each move emits `TRAILING_STOP_UPDATED` with old_stop, new_stop,
structural_reference, reference_price and confirmed_at.

## Partial take profits, RangeHigh exit and runner

Optional, user-configurable, and off by default. [H]-SV1-PARTIAL-001.

```
partial_take_profits = [{"r_multiple": "1.0", "close_fraction": "0.20"},
                        {"r_multiple": "2.0", "close_fraction": "0.20"}]
runner_fraction      = "0.10"
```

`close_fraction` is a fraction of the **original filled quantity**, never of the
quantity still open, so a 25% level always realises a quarter of the original
position regardless of what closed before it.

**Initial R is frozen at the fill**: `initial_R = entry - initial_stop`, and
`partial_tp_price = entry + r_multiple * initial_R`. Break-even, trailing and
realised partials never re-derive it, so a target price cannot drift.

Configuration is validated, never repaired: `r_multiple > 0`,
`0 < close_fraction <= 1`, `0 <= runner_fraction <= 1`, no duplicate R levels,
and `sum(close_fraction) <= 1 - runner_fraction`. Levels are sorted ascending
once, at construction, and that is the execution order. `StrategyProfile.as_dict`
emits the whole exit plan as JSON-ready strings for the future bot/UI layer; no
UI is implemented here.

`runner_target_quantity = floor(original_quantity * runner_fraction)` on the
configured quantity step. At the frozen RangeHigh the broker closes
`remaining_quantity - runner_target_quantity` (never negative) so exactly the
configured runner survives, then **cancels every unfilled R level** so a stale
2R/3R instruction can never nibble the runner. Defaults give the familiar
90% realised / 10% runner. `runner_fraction = 0` closes everything at RangeHigh;
`runner_fraction = 1` closes nothing and forbids partials; partials summing to
`1 - runner_fraction` leave nothing for RangeHigh to close, which is valid and
emits `RUNNER_OPEN` with no exit record.

After RangeHigh the position keeps **no fixed upside target**. The runner is
managed by its stop alone and still receives confirmed-higher-low trailing. Only
when the runner stop is hit does the logical trade close.

Conservative execution is unchanged: a bar that touches the protective stop
awards no partial, no RangeHigh exit and no upside of any kind, because intrabar
ordering is unknowable. A bar that gaps above a level fills at its open.

One logical trade stays one trade record. `PositionLedger` holds
`original_quantity`, `initial_r`, `remaining_quantity` and every `PositionExit`
(kind, trigger_r, target_price, quantity, exit_price, realized_pnl,
remaining_quantity, time), and derives `partial_exits`, `range_high_exit`,
`runner_exit`, `realized_quantity` and `total_realized_pnl`.

### Audit event names

The shipped project names are kept; the requested names map onto them:

| Requested | Emitted |
|---|---|
| PAPER_TRADE_OPENED | `PAPER_ORDER_OPENED` |
| PARTIAL_TP_FILLED | `PARTIAL_TP_FILLED` |
| STOP_MOVED_TO_BREAK_EVEN | `BREAK_EVEN_PROTECTED` |
| TRAILING_STOP_UPDATED | `TRAILING_STOP_UPDATED` |
| RANGE_HIGH_PARTIAL_EXIT | `RANGE_HIGH_PARTIAL_EXIT` |
| RUNNER_OPEN | `RUNNER_OPEN` |
| RUNNER_STOPPED | `RUNNER_STOPPED` |
| PAPER_TRADE_CLOSED | `PAPER_ORDER_CLOSED` |

## Pending-entry cancellation - reachability

Two cancellation reasons are reachable and tested:

- `PENDING_ENTRY_EXPIRED` — price never returns to the level within
  `pending_expiry_bars`.
- `LONG_PERMISSION_LOST_BEFORE_FILL` — a bias-timeframe body close removes long
  permission while the order rests.

Two are wired but cannot currently fire, and are documented rather than claimed:

- `STOP_BREACHED_BEFORE_FILL` — for a LONG the structural stop sits below the
  entry, so any candle reaching the stop also traded the limit. The fill wins and
  the bar stops the position; cancelling instead would assume intrabar ordering
  in the trade's favour. The real behaviour is tested.
- `RANGE_INVALIDATED_BEFORE_FILL` — entry requires `RANGE_CONFIRMED`, and the
  shipped `RangeEngine` never re-evaluates a confirmed range, so a confirmed
  range is terminal. The guard is kept as defence if that semantics ever change.

## Capital policy

While a confirmed range waits for its manipulation, `capital_idle` is true and
`desired_capital_policy` is `AUTO_EARN_ELIGIBLE`. Once the reclaim confirms, it
becomes false / `RESERVED_FOR_ENTRY`. This module computes state only: it
performs no `earn_auto_set`, order, transfer, redemption or purchase, and holds
no exchange client. Real Auto Earn integration is a separate task.

## Not implemented

Distribution classifier, CRT, OTE/Fibonacci confluence, Breaker, Order Block,
SMT, SSMT and Quarterly Theory are deliberately parked. ATR/swing trailing beyond
the inherited break-even is not added. Costs, slippage, funding, exchange lot and
tick rules, margin and liquidation are not modelled.
