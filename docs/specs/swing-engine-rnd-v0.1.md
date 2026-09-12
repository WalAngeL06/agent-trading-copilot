# Swing Engine R&D v0.1 — causal detection prototype

Status: **RESEARCH PROTOTYPE — NO ENGINE APPROVED, NOT WIRED TO DECISIONS**.
Date: 2026-09-12. Branch `work/swing-engine`, from
`9d842077581f51b8264344fb331d1123665955e7`.
Scope: answer "what swing information was knowable at each moment?", compare
causal candidate algorithms, and prove confirmed swings never repaint.

Every algorithm here is **[H] project hypothesis**. None is DD-confirmed. No
result below is **[E] empirical validation**: the fixtures are synthetic, so
they test causality and immutability, never profitability or structural
meaning. Source discipline follows [SOURCE_REGISTRY](../SOURCE_REGISTRY.md);
DD provenance remains [D-DD-MSB-001].

## A. Boundary

SwingEngine detects causal turning points. It does **not** decide protected
high/low, responsible structural swing, BOS, external/internal scale, dealing
range, premium/discount or direction. Those stay in MarketStructureEngine and
below. **Raw swing != structural swing** (DD-1).

Nothing here changes production behaviour. `agent_trading/research/` is
imported by no production module (enforced by test), and the decision pipeline
still returns `NO_TRADE / STRATEGY_NOT_CONFIGURED`.

## B. Event and state contract

`SwingEvent` (frozen, Decimal prices, UTC): `symbol`, `timeframe`, `detector`,
`event_type`, `side`, `status`, `price`, `swing_time`, `observed_at`,
`confirmed_at`, `confirmation_delay_bars`, `evidence`, `source_ids`, `sequence`.

| Field | Meaning |
|---|---|
| `swing_time` | Close time of the candle whose wick holds the extreme |
| `observed_at` | Knowledge time: close time of the candle being processed |
| `confirmed_at` | When the opposing evidence became knowable; `== observed_at` |

Event types: `CANDIDATE_CREATED`, `CANDIDATE_UPDATED`, `CANDIDATE_DISCARDED`,
`SWING_CONFIRMED`. Status is `CANDIDATE` or `CONFIRMED`.

Enforced in `__post_init__`: `swing_time <= observed_at`; only `SWING_CONFIRMED`
may be `CONFIRMED`; a confirmation must carry `confirmed_at == observed_at` and
a non-negative delay; an unconfirmed event may carry neither.

`ConfirmedSwing` is the immutable identity `(symbol, timeframe, side, price,
swing_time, confirmed_at)`. Equality of these across replays *is* the
anti-repaint contract.

**Timestamp convention [H]:** `swing_time` labels the occurrence *candle*. OHLC
supplies no intrabar instant, so no finer precision is invented (N-7, DD-4).

## C. Causal replay

One execution path: `detector.process(candle)` accepts exactly one candle and
holds no future series, so live and historical processing are the same code.
Look-ahead is prevented by the interface, not by discipline.

```
for candle in chronological_order:
    events = detector.process(candle)      # reveals only this candle
```

`replay(candles, factory)`, `replay_prefixes(...)` and `confirmed_only(...)`
are in `replay.py`. Detectors are stateful, so each run builds a fresh one.
Bootstrap length (~200 closed candles per required timeframe) is a caller
concern; nothing here hardcodes it.

## D. Two intrabar rules

Both follow from an OHLC candle recording no path between its high and low
(market-structure-v0.1 section O, N-7; DD-4, DD-18):

1. **A swing is never confirmed from its own candle.** The opposing excursion
   must come from a strictly later candle, so confirmation delay is always >= 1.
2. **The next candidate never reuses the confirmed swing's candle.** If the only
   opposing extreme sits on that candle, the candidate is dropped and reopened
   from the next one.

These were added after the prototype re-published a single bar as an endless
alternating swing sequence. They yield: at most one confirmed swing per candle,
strictly increasing confirmed `swing_time`, and no duplicate swing identity.

## E. Algorithms compared (all [H])

| Detector | Rule | Price basis |
|---|---|---|
| `fractal_wN` | Strict N-bar symmetric fractal | wick |
| `zigzag_P` | Confirm running extreme after P% opposing retracement | wick |
| `dc_T` | Directional Change, threshold T | close only |
| `atr_pN_xM` | Reversal distance = M * ATR(N), simple mean of True Range | wick |

Thresholds are research parameters, not approved constants. Fractal is a
benchmark reference: DD explicitly does **not** approve a fixed 2/3/5-bar pivot
(DD-19), so it can never be the production rule.

**Non-causal baseline** (`baselines.py`): a charting ZigZag that also publishes
its provisional last leg. It exists to fail the anti-repaint probe.

## F. Results

Six synthetic 15m BTC-scale benchmarks (40–48 bars): clean uptrend, clean
downtrend, V reversal, choppy range, false breakout/sweep, volatility reversal.
Reproduce with `python -m agent_trading.research.swing.compare`.

**Anti-repaint, identical data:**

| | repaint violations |
|---|---|
| All 7 causal detectors, all 6 scenarios | **0** |
| Non-causal batch ZigZag baseline | **238** |

Selected behaviour (`dens/100` = confirmed swings per 100 bars):

| Scenario | zigzag 0.5% | zigzag 1.5% | dc 1.5% | atr 1.5x | fractal w2 |
|---|---|---|---|---|---|
| clean_uptrend | 25.0 | 2.1 | 2.1 | 20.8 | 20.8 |
| choppy_range | 33.3 | **0.0** | 0.0 | 27.1 | 31.2 |
| v_reversal | 5.0 | 5.0 | 5.0 | 5.0 | 2.5 |
| false_breakout | 37.8 | 4.4 | 2.2 | 13.3 | 40.0 |
| volatility_reversal | 4.2 | 4.2 | 4.2 | 20.8 | 4.2 |

Findings:

- **Threshold must exceed typical bar range.** At 0.5% (below the fixtures' bar
  range) every reversal detector degenerates into near-per-bar alternation. At
  1.5% the same code is quiet in chop and still finds the V.
- **Close-only DC cannot see a liquidity sweep.** In `false_breakout` the sweep
  prints only as a wick; `zigzag_1.5%` confirms it, `dc_1.5%` structurally
  cannot. DD prices swings from **wick** extremes (DD-4), so close-only is
  disqualified on source grounds regardless of its metrics.
- **Fractal does not alternate.** It published consecutive same-side swings
  (`alt_v` 1 and 3 on `false_breakout`) because it classifies each candle
  independently, and its delay is a constant N bars regardless of market state.
- **ATR adapts but lags.** It was the only detector to keep density roughly
  stable across the volatility regime change, at the cost of a warmup during
  which no swing can be confirmed, and a longer worst-case delay.

## G. Recommendation for SwingEngine v0.1

**Wick-based reversal detection (`ZigZagSwingDetector` family) as the structural
skeleton, with the reversal distance left as an explicit unresolved parameter.**

Judged against the required criteria, not appearance:

| Criterion | Why this family |
|---|---|
| Causal correctness | Confirms only on later-candle evidence; delay >= 1 by rule |
| Zero repaint | 0 violations, all scenarios; immutability is structural |
| Live/replay equivalence | Same code path; asserted by test |
| Latency | Delay adapts to price action instead of a constant N bars |
| Chop robustness | A threshold above the noise band silences chop entirely |
| Volatility robustness | Weakest point — fixed % does not transfer across regimes |
| Timeframe portability | Percentage is scale-free; the *value* is not portable |
| Structural compatibility | Alternating wick extremes with occurrence/confirmation split are what protected-low and responsible-swing selection need downstream |

Fractal is rejected (DD-19 forbids a fixed pivot; no alternation). DC is
rejected (cannot see wick extremes; conflicts with DD-4). ATR is **not
rejected** — it is the leading candidate for the reversal distance itself, i.e.
keep the ZigZag state machine and make the threshold volatility-scaled. That
combination is untested here and needs its own comparison.

This is a recommended **skeleton**, not an approved algorithm. The reversal
predicate remains **ALGORITHMIC DEFINITION PENDING** until N-1 is answered.

## H. Unresolved DD questions before productionising

These must be answered from source, not chosen by an agent. The repository has
no DD recording/transcript, so they need user clarification or new DD material.

1. **(N-1) What is "genuine opposing movement"?** A percentage retracement is a
   hypothesis. Is the qualifying evidence a retracement fraction, a break of a
   prior minor extreme, a body close beyond a level, or elapsed structure? This
   is the single blocking question.
2. **(N-1) Measured from what, to what?** Wick-to-wick, wick-to-close, or
   close-to-close — and is the threshold relative to price, to the preceding
   leg, or to volatility?
3. **(N-2) Which extremes are meaningful?** This prototype confirms *every*
   qualifying alternation. DD-1 says not every local extreme is structural, so
   a meaningfulness filter is missing and belongs to swing or structure.
4. **(N-7) Same-candle ordering.** When the opposing extreme shares the
   confirmed swing's candle, this prototype refuses it. Is discarding correct,
   or should such a swing be representable?
5. **(N-7) Equal extremes.** Strict comparison means exactly equal highs produce
   no swing. DD's tie policy is unknown.
6. **(N-3) Causal seeding.** The first swing is seeded from an undetermined
   state with an arbitrary HIGH tie-break. How should bootstrap direction be
   established from ~200 candles, and what happens with truncated history?
7. **(N-3) Retention.** What happens to a confirmed swing whose candle leaves
   bounded history — does the evidence survive its candle?
8. **Multi-scale.** Each timeframe already owns independent state and nothing
   derives a 15m swing from 1H labels. Whether micro/internal/major is a
   per-timeframe hierarchy or a cross-timeframe relationship is open (N-5).

## I. Next implementation step

Answer **question 1** (the opposing-movement predicate). Until then no
SwingEngine promotion is justified.

Mechanically, the next step is to **replace the reversal-distance function**
with the approved predicate while keeping this state machine, event contract,
replay harness and test suite. The prototype was built so that predicate is a
single method (`_reversal_distance`), isolating the unresolved decision.

Do not proceed to Market Structure. N-1–N-7 remain open and
MarketStructureEngine stays blocked.
