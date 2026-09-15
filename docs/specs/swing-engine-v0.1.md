# Swing Engine v0.1 — production causal swing core

Status: **IMPLEMENTED, NOT WIRED TO ANY DECISION**. Date: 2026-09-12.
Branch `work/swing-engine`, from `9d842077581f51b8264344fb331d1123665955e7`.
Module: `agent_trading/swing.py`. Research prototype:
[swing-engine-rnd-v0.1](swing-engine-rnd-v0.1.md).

Detects **raw** turning points for any supported symbol/timeframe stream.
**Raw swing != structural swing** (DD-1). Nothing here decides protected
levels, responsible swings, BOS, external/internal scale, dealing range,
premium/discount, direction, acceptance, risk or execution. The decision
pipeline is unchanged and still returns `NO_TRADE / STRATEGY_NOT_CONFIGURED`.

## A. Source discipline

| Label | Applies to |
|---|---|
| **[D]** source-confirmed | Swings are priced from **wick** extremes (DD-4). Genuine opposing movement is required, and no fixed 2/3/5-bar pivot is approved (DD-18, DD-19). Occurrence and confirmation are distinct (DD-18). |
| **[H]** project hypothesis | The entire ATR confirmation model below, the 14-length simple-mean ATR, the multiplier default, the seed tie-break, and the strict-comparison tie policy. |
| **[E]** empirical observation | The benchmark numbers in section F: behaviour of this code on 299 saved BTC-USDT candles per timeframe. Not validation of a trading rule. |

**DD N-1 remains unresolved.** What exactly qualifies as genuine opposing
movement is still **ALGORITHMIC DEFINITION PENDING**. The ATR predicate is a
provisional stand-in, isolated in `_threshold()` / `_beyond()` so it can be
replaced without touching the state machine. It is not DD Finance's rule.

## B. Confirmation model [H]

* A candidate extreme is a **wick** high/low.
* It is confirmed when a **later candle's close** is at least
  `ATR(length) * multiplier` beyond it:
  * HIGH: `close <= candidate_high - threshold`
  * LOW: `close >= candidate_low + threshold`
* Never from its own candle, so confirmation delay is always `>= 1`.

ATR is a **simple rolling mean** of True Range over closed candles [H], not
Wilder smoothing. A rolling window is reproducible from the last `atr_length`
candles alone, so a bootstrapped engine and a streamed engine hold identical
volatility state with no seeding convention to agree on.

## C. Contract

`SwingConfig(atr_length=14, atr_multiplier=Decimal("1.25"), bootstrap_candles=200)`
— all validated and immutable. `bootstrap_candles` must exceed `atr_length`.

`SwingEngine(symbol, timeframe, config)` owns exactly one symbol and one
timeframe; the timeframe must be a supported fixed interval (`bar_duration`).

| Method | Behaviour |
|---|---|
| `process(candle)` | Reveal one closed candle; return the events it makes knowable |
| `bootstrap(candles)` | Replay a context batch oldest -> newest; requires a fresh engine |
| `state` | `SwingState` view at the current knowledge time |
| `confirmed` | Append-only `ConfirmedSwing` history |

`SwingEvent`: symbol, timeframe, event_type, side, status, price, `swing_time`,
`observed_at`, `confirmed_at`, `confirmation_delay_bars`, `atr`, `threshold`,
evidence, source_ids, sequence.

| Field | Meaning |
|---|---|
| `swing_time` | Close time of the candle whose wick holds the extreme |
| `observed_at` | Knowledge time: close time of the candle being processed |
| `confirmed_at` | When the evidence became knowable; always `== observed_at` |

Event types: `CANDIDATE_CREATED`, `CANDIDATE_UPDATED`, `SWING_CONFIRMED`.
`ConfirmedSwing` is the immutable identity; its stability across replays *is*
the anti-repaint contract.

## D. Invariants (all test-enforced)

1. Closed candles only — `Candle` rejects `closed=False`.
2. Chronological incremental processing; duplicate/out-of-order candles raise.
3. Candidates may update freely before confirmation.
4. Confirmed swings never repaint — every prefix's history is a prefix of the final.
5. Confirmed price never changes. 6. `swing_time` never changes. 7. Never deleted.
8. No same-candle confirmation — enforced twice: the state machine returns early
   when a candle improves the candidate, and `SwingEvent` rejects
   `swing_time >= confirmed_at`.
9. Live incremental == historical replay — one code path, asserted per timeframe.
10. Identical input == identical event stream.
11. Independent state per symbol/timeframe; foreign candles raise.
12. Explicit warmup: **no event at all** before the ATR window is full.

On 12: candidate tracking starts only once a threshold exists. Otherwise the
first candidate would be seeded by wherever the bootstrap window happens to
begin, and its confirmation delay would measure the warmup rather than the
market — observed as a spurious 13-bar first delay before this rule was added.

## E. Bootstrap and live continuation

```python
engine = SwingEngine("BTC-USDT", "15m", SwingConfig())
engine.bootstrap(history)        # ~200 closed candles, oldest -> newest
for candle in live_stream:       # same engine, same code path
    events = engine.process(candle)
```

`bootstrap(...)` then `process(...)` is asserted equal to one full replay of
the same candles. 200 is configurable context, not a trading rule.

Nothing assumes a timeframe set. A future strategy profile declares what it
needs and orchestration takes the union; the engine does not care why a
timeframe was requested.

## F. Benchmark [E]

Real BTC-USDT, 299 closed candles per timeframe, collected once through the
public ATK MCP path (`agent_trading.swing_smoke`) and saved offline to
`tests/data/`. The test suite never touches the network. Reproduce with
`python -m agent_trading.research.swing.review`.

Confirmed swings per 100 bars (mean confirmation delay in bars):

| mult | 5m | 15m | 1H | 4H |
|---|---|---|---|---|
| 0.75 | 24.7 (1.5) | 22.7 (1.5) | 22.4 (2.0) | 27.1 (1.6) |
| 1.0 | 19.1 (1.7) | 19.4 (2.2) | 19.7 (2.5) | 21.7 (2.0) |
| **1.25** | **16.4 (2.3)** | **15.4 (2.7)** | **17.7 (3.0)** | **16.4 (2.5)** |
| 1.5 | 14.4 (2.8) | 14.0 (3.1) | 14.4 (3.4) | 11.4 (3.1) |
| 2.0 | 8.7 (4.2) | 8.4 (4.2) | 7.7 (4.5) | 9.4 (4.0) |

**Anti-repaint: 7,365 prefixes checked across 4 real timeframes, 6 synthetic
scenarios and 5 multipliers — 0 confirmed repaints.**

### Provisional default: `atr_multiplier = 1.25` [H]

The evidence does not single out an optimum. 1.25 holds density near 15-18 per
100 bars with mean delay under ~3 bars and the tightest cross-timeframe spread
in the mid range. This is a density/latency judgement, **not** a validated
constant, and it is fully configurable. A raw-swing layer should err toward
slightly more swings than fewer: a missed turn cannot be recovered downstream,
whereas an extra raw swing can still be filtered by the future meaningfulness
rule (N-2).

## G. Known failure modes

1. **A candle that both extends the candidate and prints the opposing extreme
   loses that extreme.** Real case: on 15m the series low 76001 (2026-09-11
   12:45) sits on a candle that also made a new candidate high, so it can never
   become a swing low; the lowest confirmed 15m low is 463.7 higher. The **5m
   engine confirms 76001 exactly.** This is intrinsic to one candidate per side
   plus the refusal to infer an intrabar high->low order, and the architectural
   remedy is the lower timeframe, which per-timeframe engines already provide.
   A future multi-scale swing hierarchy is the other option.
2. **An ATR threshold does not suppress chop.** ATR rises with the noise, so
   the synthetic `choppy_range` yields ~12 swings at every multiplier from 0.75
   to 1.5, where a fixed-percentage threshold went silent. Volatility adaptation
   buys regime portability and gives up the "go quiet in chop" property.
3. **Opposing-extreme tracking is approximate after a flip.** The next
   candidate is re-seeded from the confirming candle, so an extreme between the
   new candidate's bar and the confirming bar can be missed. Self-correcting,
   never a causality or immutability violation.
4. **The seed is arbitrary at the edges.** Before the first confirmation both
   extremes are provisional (`SwingState.seeding`, `pending_high_price`,
   `pending_low_price`). If both sides qualify on one candle the earlier extreme
   wins, ties resolve to HIGH — a documented tie-break [H], not a DD rule.
5. **No meaningfulness filter.** Every qualifying alternation is confirmed.
   DD-1 says not every local extreme is structural; that filter (N-2) does not
   exist yet, here or downstream.
6. **Bounded-history retention is unaddressed** (N-3): what happens to a
   confirmed swing whose candle leaves a bounded store is not specified.

## H. Unresolved before this is a DD engine

1. **(N-1)** What observable opposing movement confirms a swing? ATR-vs-close is
   a stand-in. Blocking question.
2. **(N-1)** Measured wick-to-close, wick-to-wick or close-to-close; relative to
   price, to the preceding leg, or to volatility?
3. **(N-2)** Which extremes are meaningful, and which swing is responsible for
   a progression?
4. **(N-7)** Same-candle ordering and equal-extreme ties.
5. **(N-3)** Causal seeding from a bootstrap window, and retention.
6. **(N-5)** Whether micro/internal/major is a per-timeframe hierarchy or a
   cross-timeframe relationship.

The repository holds no DD recording or transcript, so these need user
clarification or new DD material. None was invented here.

## I. Next task

Answer question 1. Until then no swing output should feed a trading decision.
Market Structure stays blocked: N-1–N-7 remain open.
