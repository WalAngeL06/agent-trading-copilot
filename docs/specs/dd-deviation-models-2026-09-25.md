# DD deviation models - design, 2026-09-25 [U-DD-DEVIATION-001]

Status: approved by the owner on 2026-09-25, not yet implemented.

## Source

On 2026-09-25 the owner supplied two things.

- **Two sketches.**
  - An accumulation range after a downtrend: price deviates below the range
    low, reclaims, and the move continues up through the range high.
  - A distribution range after an uptrend: price deviates above the range high,
    falls back inside, and the downtrend follows.
- **The DD Finance deviation text.** It describes three entry models and the
  TP/SL rules, and it bans entering blindly on a deviation.

The owner's instruction: the engine should take trades by these structures and
this school. Profitability tuning comes later.

## Decisions

| # | Decision | Source |
|---|---|---|
| D1 | Scale-out: 30% of the position at the range EQ, with the stop moved to entry; 50% at the opposite boundary; the last 20% runs on the trailing stop | owner |
| D2 | Entry: Model 1 (entry-timeframe CHoCH) and Model 2 (HTF FVG reversal) both run; the first one to be ready takes the trade | owner |
| D3 | Model 2 runs only when the deviation touched a fresh HTF FVG, the DD condition | owner |
| D4 | Stop at the deviation wick extreme, minus or plus `stop_buffer` | DD text |
| D5 | Out of scope: Model 3 (DXY: no DXY feed on OKX), breaker/S-R flip entries, new fields on the panel settings screen | agreed |

## Unchanged

- Range confirmation on the range timeframe.
- Sweep and body-close reclaim.
- The guide's HTF verdict (4.3 zone confluence, 4.4 premium/discount).
- The 50% deviation limit: a body close beyond `range_deviation_ratio` of
  (RH - EQ) retires the range and cancels a resting order.
- Multi-setup, risk sizing, and the minimum reward/risk check against the
  opposite boundary.
- The trailing rules fixed on 2026-09-24.

## Entry

### Arming (unchanged)

A setup is armed in a direction when four things hold:
- the range is `RANGE_CONFIRMED`;
- the active manipulation is `RECLAIMED` in that direction;
- the HTF verdict allows that direction;
- the profile allows that direction.

At most one order is pending or open at a time.

### Deviation extreme on the entry timeframe [H]-DD-EXTREME-001

For the active manipulation, the strategy finds the entry-timeframe candle
that printed the deviation extreme:
- long: the lowest low; short: the highest high;
- search window: entry candles whose close time is after
  `swept_at - range bar` and not after now;
- ties go to the earliest candle.

The strategy keeps the entry candles of the current manipulation for this. The
buffer resets when a new manipulation starts, the range reseeks, or a sweep
turns ambiguous. The extreme may keep moving while the manipulation is still
`SWEPT`; after the reclaim it is frozen, as the manipulation's own extreme is.

### Model 1 - `CHOCH_FVG` [H]-DD-CHOCH-001 (DD model 1)

- **Level.** The most recent entry-timeframe swing high (a swing low for a short)
  that meets two conditions:
  - its `swing_time` is before the extreme candle;
  - it is confirmed by the evaluation time.

  Swings come from the existing entry `SwingEngine`. With no such swing, Model 1
  is unavailable for this manipulation.
- **CHoCH.** The first entry candle after the extreme candle whose close is
  above the level (a short: below). It is emitted once as `CHOCH_CONFIRMED`,
  carrying the level, the swing, the breaking candle and the extreme.
- **Entry gap.** A fresh directional entry-timeframe FVG formed at or after the
  extreme candle:
  - if one is already published at the CHoCH, the newest such gap;
  - otherwise the first one published afterwards.

  The limit price is `entry_level` (default FVG EQ).
- **When it is evaluated.** On the CHoCH bar, on every gap publication, and when
  the setup arms. The CHoCH may close before the range-timeframe reclaim bar
  does, so arming must also check it.

### Model 2 - `HTF_FVG_REVERSAL` [H]-DD-MODEL2-001 (DD model 2)

- **Condition.** The zones of the HTF verdict include an `HTF_FVG`, meaning an
  unfilled bias-timeframe FVG. A Valid High/Low band alone does not qualify.
- **Entry gap.** Today's rule: the first fresh directional entry-timeframe FVG
  that is published after the reclaim and formed at or after the sweep. The
  limit price is `entry_level`.

### Arbitration

- At each evaluation Model 1 is tried before Model 2 [H]. The first model to
  produce a RiskEngine-approved plan submits it.
- A later-ready model never replaces a resting or open order.
- The plan, the `TRADE_CANDIDATE`/`ENTRY_PLAN` events and the trade record carry
  `entry_model`.

### Superseded gate

`BIAS_LONG_PERMISSION` builds no HTF zones. Under it, Model 2 runs without the
HTF FVG condition, which is the pre-DD entry. This is explicit in
configuration:
- `model2_requires_htf_fvg` defaults to `None`, which follows the gate: true
  under `GUIDE_HTF_CONTEXT`, false under `BIAS_LONG_PERMISSION`. The resolved
  value is exposed as `effective_model2_requires_htf_fvg`.
- An explicit `True` combined with the old gate is rejected, never silently
  ignored.

## Stop (D4)

- The stop source is the manipulation extreme, minus or plus `stop_buffer`.
- `secondary_fvg_support_enabled` now defaults to false. The tighter
  protecting-swing stop and the recovery chain remain available as configuration.

## Trade management (D1)

- **EQ level.** `eq_scale_out_fraction` (default 0.30, `None` disables) is a share
  of the original quantity. The range EQ is frozen into `EntryPlan.range_eq` when
  the plan is made.
- **EQ fill.** It follows the conservative stop-first bar rule. A bar that
  reaches EQ fills the slice at the bar's open when the open is already beyond
  EQ, and at EQ otherwise. The slice kind is `RANGE_EQ` and the event is
  `RANGE_EQ_PARTIAL_EXIT`. The same bar may then reach the boundary; EQ is booked
  first.
- **Break-even.** `break_even_trigger` is `RANGE_EQ` (default) or `R_MULTIPLE`
  (the inherited 1R rule, kept as the legacy option).
  - Under `RANGE_EQ` the inherited 1R manager is not called.
  - The EQ bar moves the stop to entry with the reason `RANGE_EQ_BREAK_EVEN`.
  - `BREAK_EVEN_PROTECTED` is announced and trailing may start.
- **Skip rule** [H]-DD-EQ-SKIP-001. When EQ does not lie strictly between the
  entry and the boundary target, the EQ slice is skipped. Break-even then
  happens at the boundary exit.
- **Boundary.** The boundary exit closes the position down to the runner.
  `runner_fraction` now defaults to 0.20, so after 30% at EQ the boundary closes
  50%.
- **Runner.** The last 20% is managed by the trailing stop alone.
- **R-multiple partials.** They stay available (default empty) and independent
  of the EQ slice.

## Recording and reporting

- **Trade record.** `entry_model` is taken from the `ENTRY_PLAN` event behind the
  trade's candidate. It appears in `trades.csv`, in `trades_detail.json`, and in
  the sweep's `sweep_trades.csv` and pooled `by_entry_model`.
- **Funnel.** New `choch_confirmations` count; `range_eq_exits` counts EQ slices.
- **Partials.** `partial_count` includes `RANGE_EQ` slices.

## Live PAPER agent and panel

The local PAPER agent builds its profile from `StrategyProfile` defaults and the
stored panel settings, so it trades the DD rules without code changes of its
own. The panel schema (`strategy-config-v1`) does not expose the new knobs; its
round-trip keeps their profile defaults.

Two panel fields change meaning:
- `runnerPct` defaults to 20.
- `secondaryFvgSupport` defaults to false.

`breakEvenTriggerR` is still stored, but it is only used under `R_MULTIPLE`.
Showing the new knobs on the panel is a separate, later task.

## Testing

- **Discipline.** TDD for every rule, with long and short cases.
- **Existing tests.** Fixtures that assert pre-DD behaviour pin it explicitly
  with legacy settings:
  - `entry_models=('HTF_FVG_REVERSAL',)`
  - `model2_requires_htf_fvg=False` (implied under the old gate)
  - `secondary_fvg_support_enabled=True`
  - `eq_scale_out_fraction=None`
  - `break_even_trigger='R_MULTIPLE'`
  - `runner_fraction=0.10`

  Tests of the old defaults are updated as deliberate changes.
- **New scenarios on the guide gate.**
  - A deviation that touches only a 4H Valid level: no Model 2, and a Model 1
    trade after a CHoCH.
  - A deviation into a fresh 4H FVG: a Model 2 trade.
  - The EQ slice, break-even at EQ, the boundary slice and the runner.
  - Short mirrors.
- **Verification.** The full suite, the BTC reference, and the 30-pair sweep
  reported by entry model and direction. No threshold tuning.

## Provisional choices [H]

Each is tagged in code and easy to change:
- the extreme and CHoCH definitions, on the existing ATR swing engine;
- Model 1 is tried before Model 2;
- the EQ skip rule.
