# RR Ladder, Trailing Modes and Relative Tolerances Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make four changes to Strategy V1, then compare the three trailing methods on the 30 OKX TR pairs.
- Tolerances and stop buffers become price-relative in the multi-pair research.
- An R ladder takes profit independently of EQ: break-even at 1R (or at EQ), 30% at 2R.
- Trailing starts after that break-even.
- Two new trailing methods: internal pivots and ATR tiers.

**Architecture:**
- **Engines:** each shared engine (RangeEngine, HtfContext, RiskEngine) accepts an optional ratio next to its absolute value.
- **Profile:** StrategyProfile carries the ratios and wires them in; the sweep sets them instead of converting to absolute prices at the first close.
- **Broker:** the R ladder reuses the R-partial machinery and a new break-even trigger. It gains a pivot-fed trail and ATR tier exits.
- **Strategy:** StrategyV1 feeds pivots or ATR to the broker.

**Tech Stack:** Python 3.14, `decimal.Decimal`, unittest (`./.venv/Scripts/python.exe -B -m unittest discover -s tests`).

**Spec:** `docs/specs/rr-trailing-scaling-2026-09-25.md` [U-RR-TRAIL-001]

## Global Constraints

**Safety and location**
- PAPER only. No exchange write, no OKX call.
- Work in `C:/Users/Serdar Arif/Desktop/Agent Trading` on `main`.
- Change files with scratchpad scripts built on `scratchpad/edit_lib.py` (EOL-preserving, exactly-once replacements). New files are written in the scratchpad and copied in.

**Testing**
- One module: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "<file>"`.
- After every task: the full suite and `git diff --check`.

**Code rules**
- Decimal only in engine code. Use `exact_product` / `exact_difference` from `agent_trading.trading_brain.risk` where the codebase does.
- Tags: `[U-RR-TRAIL-001]`, `[H]-REL-TOL-001`, `[H]-PIVOT-N-001`, `[H]-ATR-TIERS-001`.
- `agent_trading/backtest/*.py` must not contain the strings `SwingEngine(`, `RiskEngine(`, `PendingLimitPaperBroker(`, `entry_price(`, `partial_target(` or `tighten_stop(`.

**Behaviour to preserve**
- The live BTC absolute tolerances (500 / 100) do not change.
- Shipped scenarios keep their results through `LEGACY` / `LEGACY_FLAGS` / `DD`.

**New defaults**

| Field | Default |
|---|---|
| `partial_take_profits` | `(PartialTakeProfit(Decimal('2'), Decimal('0.30')),)` |
| `break_even_trigger` | `'EQ_OR_R_MULTIPLE'` |
| `trailing_mode` | `'CONFIRMED_HIGHER_LOW'` (unchanged) |
| `trailing_pivot_bars` | `3` |
| `trailing_atr_tiers` | `((0.75, 0.25), (1.25, 0.50), (1.5, 1))` |
| `boundary_proximity_ratio` | `None` |
| `stop_buffer_ratio` | `None` |

**Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push.

---

### Task 1: The engines accept price-relative tolerances

**Files:**
- Modify: `agent_trading/trading_brain/range.py`: `RangeEngine.__init__`, a new `_near`, and `_register_touch`.
- Modify: `agent_trading/strategy_v1/context.py`: `HtfContext.__init__` and `zones_touching`.
- Modify: `agent_trading/trading_brain/risk_models.py`: `RiskConfig`.
- Modify: `agent_trading/trading_brain/risk.py`: `RiskEngine.evaluate`, at the stop computation.
- Create: `tests/test_relative_tolerances.py`

**Interfaces:**
- Produces:
  - `RangeEngine(..., proximity_ratio=None)`.
  - `HtfContext(timeframe, tolerance, require_zone, tolerance_ratio=None)`.
  - `RiskConfig(..., stop_buffer_ratio=None)`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_relative_tolerances.py`:

```python
"""[U-RR-TRAIL-001] Tolerances as a share of the price being tested [H]-REL-TOL-001."""
from decimal import Decimal as D
import unittest

import test_htf_context as htf
from test_range_guide_rules import candidate
from test_trading_brain import bar, raw
from agent_trading.swing import SwingSide
from agent_trading.trading_brain.models import TradeCandidate
from agent_trading.trading_brain.risk import RiskEngine
from agent_trading.trading_brain.risk_models import RiskConfig

from strategy_v1_fixtures import bias_candles

START = bias_candles()[0].close_time


class RangeTouchTests(unittest.TestCase):
    """Candidate 80 .. 120, EQ 100; a 1% ratio is 0.8 at RL and 1.2 at RH."""

    def test_a_low_touch_is_measured_on_the_range_low(self):
        engine = candidate(proximity_ratio=D('0.01'))
        engine.process(bar(9, '85', '90', '81', '86'), (), (raw(SwingSide.LOW, '81', 8, 9),))
        engine.process(bar(10, '95', '101', '94', '100'))
        self.assertEqual(engine.state.phase, 'WAIT_LOW_TOUCH')         # 1.0 above RL > 0.8
        engine.process(bar(11, '85', '90', '80.5', '86'), (),
                       (raw(SwingSide.LOW, '80.5', 10, 11),))
        state, = engine.process(bar(12, '95', '101', '94', '100'))
        self.assertEqual((state.phase, state.low_touch.price), ('WAIT_HIGH_TOUCH', D('80.5')))

    def test_a_high_touch_is_measured_on_the_range_high(self):
        engine = candidate(proximity_ratio=D('0.01'))
        engine.process(bar(9, '85', '90', '80.5', '86'), (), (raw(SwingSide.LOW, '80.5', 8, 9),))
        engine.process(bar(10, '95', '101', '94', '100'))
        engine.process(bar(11, '110', '118.5', '109', '118'), (),
                       (raw(SwingSide.HIGH, '118.5', 10, 11),))
        engine.process(bar(12, '105', '106', '99', '100'))
        self.assertEqual(engine.state.phase, 'WAIT_HIGH_TOUCH')        # 1.5 below RH > 1.2
        engine.process(bar(13, '110', '119', '109', '118'), (),
                       (raw(SwingSide.HIGH, '119', 12, 13),))
        state, = engine.process(bar(14, '105', '106', '99', '100'))
        self.assertEqual((state.phase, state.high_touch.price), ('RANGE_CONFIRMED', D('119')))

    def test_a_bad_ratio_is_rejected(self):
        for bad in (D('0'), D('1'), D('NaN'), 0.01):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                candidate(proximity_ratio=bad)


class HtfBandTests(unittest.TestCase):
    """Frame 100 .. 200; a 2% ratio is a band of 2 at 100 and 4 at 200."""

    def framed(self):
        engine = htf.context(require_zone=True, tolerance_ratio=D('0.02'))
        low, high = htf.frame_levels()
        engine.process(htf.bar(3), (low,))
        engine.process(htf.bar(5), (high,))
        return engine

    def test_the_band_scales_with_each_level(self):
        engine = self.framed()
        self.assertEqual([z.kind for z in engine.zones_touching(D('97.5'), D('98'))],
                         ['HTF_VALID_LOW'])
        self.assertEqual(engine.zones_touching(D('97'), D('97.9')), ())
        self.assertEqual([z.kind for z in engine.zones_touching(D('196'), D('196.5'))],
                         ['HTF_VALID_HIGH'])
        self.assertEqual(engine.zones_touching(D('195'), D('195.9')), ())

    def test_a_bad_ratio_is_rejected(self):
        with self.assertRaises(ValueError):
            htf.context(tolerance_ratio=D('-0.1'))


class StopBufferTests(unittest.TestCase):
    def test_the_buffer_is_measured_on_the_invalidation_price(self):
        risk = RiskEngine(RiskConfig(stop_buffer=D('100'), stop_buffer_ratio=D('0.001')))
        long_ = TradeCandidate('LONG', D('128'), D('120'), D('140'), START, (),
                               sweep_extreme=D('120'))
        short = TradeCandidate('SHORT', D('128'), D('136'), D('116'), START, (),
                               sweep_extreme=D('136'))
        self.assertEqual(risk.evaluate(long_, D('10000')).plan.stop, D('119.88'))
        self.assertEqual(risk.evaluate(short, D('10000')).plan.stop, D('136.136'))

    def test_without_a_ratio_the_absolute_buffer_is_unchanged(self):
        risk = RiskEngine(RiskConfig(stop_buffer=D('1')))
        long_ = TradeCandidate('LONG', D('128'), D('120'), D('140'), START, (),
                               sweep_extreme=D('120'))
        self.assertEqual(risk.evaluate(long_, D('10000')).plan.stop, D('119'))

    def test_a_bad_ratio_is_rejected(self):
        for bad in (D('0'), D('1'), D('-0.001')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                RiskConfig(stop_buffer_ratio=bad)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it and watch it fail**: `TypeError: ... unexpected keyword argument 'proximity_ratio'`.

- [ ] **Step 3: Implement.**
  - `range.py`: add the `proximity_ratio=None` parameter (validated: Decimal, finite, 0 < r < 1).
  - `range.py`: add the helper below, and use `self._near(state.range_low)` / `self._near(state.range_high)` in place of `self.proximity` in `_register_touch`.

```python
    def _near(self, boundary):
        """[U-RR-TRAIL-001] Touch tolerance: absolute, or a share of the boundary."""
        return self.proximity if self.proximity_ratio is None else boundary * self.proximity_ratio
```

  - `context.py`: add `tolerance_ratio=None` (same validation). In `zones_touching`, use:

```python
            pad = self.tolerance if self.tolerance_ratio is None else level.price * self.tolerance_ratio
            band = (level.price - pad, level.price + pad)
```

  - `risk_models.py`: add `stop_buffer_ratio: Decimal | None = None` as the last `RiskConfig` field, with validation: `None`, or a finite Decimal with 0 < r < 1.
  - `risk.py` `evaluate`:

```python
            buffer = (config.stop_buffer if config.stop_buffer_ratio is None
                      else exact_product(invalidation, config.stop_buffer_ratio))
            stop = exact_difference(invalidation, buffer if candidate.direction == 'LONG'
                                    else buffer.copy_negate())
```

- [ ] **Step 4:** Run the module, then the full suite. Expected: PASS; nothing else changes, since every default is `None`.
- [ ] **Step 5: Commit** `feat: let the range, HTF and risk engines take relative tolerances`.

---

### Task 2: The profile and the sweep use relative tolerances

**Files:**
- Modify: `agent_trading/strategy_v1/config.py`:
  - fields `boundary_proximity_ratio`, `stop_buffer_ratio`, with validation;
  - `effective_htf_zone_tolerance_ratio`, `trailing_buffer_at(price)`;
  - `risk_config`, `as_dict`.
- Modify: `agent_trading/strategy_v1/strategy.py`: pass the ratios to `RangeEngine` / `HtfContext`.
- Modify: `agent_trading/strategy_v1/broker.py`: in `_trail`, the buffer comes from `self.profile.trailing_buffer_at(swing.price)` inside the loop. The loop walks swings newest first and stops at the first swing confirmed before the fill.
- Modify: `agent_trading/backtest/sweep.py`:
  - `scale_profile(profile, proximity_ratio, stop_buffer_ratio)`;
  - new row columns `proximity_ratio` and `stop_buffer_ratio`, with the absolute columns empty in price mode;
  - drop `FIXED_REFERENCE_PRICE`;
  - the scale document and the docstring.
- Modify: `tests/test_sweep.py` (ScaleTests and `test_price_scaling_reads_the_first_entry_close`); append to `tests/test_relative_tolerances.py`.

**Interfaces:**
- Produces:
  - `StrategyProfile.boundary_proximity_ratio` and `.stop_buffer_ratio` (`Decimal | None`).
  - `.effective_htf_zone_tolerance_ratio`: `None` when `htf_zone_tolerance` is set.
  - `.trailing_buffer_at(price) -> Decimal`: an explicit `trailing_buffer` wins, then the ratio × price, then `stop_buffer`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_relative_tolerances.py` (with `from agent_trading.strategy_v1 import StrategyProfile` and `from test_strategy_v1_trailing import confirmed_low, open_long, protect, STEP` plus `from strategy_v1_fixtures import candle, scenario_profile`):

```python
class ProfileRatioTests(unittest.TestCase):
    def test_the_ratios_are_optional_and_validated(self):
        self.assertIsNone(StrategyProfile().boundary_proximity_ratio)
        self.assertIsNone(StrategyProfile().stop_buffer_ratio)
        for name in ('boundary_proximity_ratio', 'stop_buffer_ratio'):
            for bad in (D('0'), D('1'), D('NaN')):
                with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                    StrategyProfile(**{name: bad})

    def test_the_htf_band_and_the_trail_follow_the_ratios(self):
        profile = StrategyProfile(boundary_proximity_ratio=D('0.005'), stop_buffer_ratio=D('0.001'))
        self.assertEqual(profile.effective_htf_zone_tolerance_ratio, D('0.005'))
        self.assertEqual(profile.trailing_buffer_at(D('127')), D('0.127'))
        self.assertEqual(profile.risk_config().stop_buffer_ratio, D('0.001'))
        explicit = StrategyProfile(boundary_proximity_ratio=D('0.005'), htf_zone_tolerance=D('3'),
                                   stop_buffer_ratio=D('0.001'), trailing_buffer=D('2'))
        self.assertIsNone(explicit.effective_htf_zone_tolerance_ratio)
        self.assertEqual(explicit.trailing_buffer_at(D('127')), D('2'))
        data = profile.as_dict()
        self.assertEqual((data['boundary_proximity_ratio'], data['stop_buffer_ratio']),
                         ('0.005', '0.001'))

    def test_the_trail_buffer_is_a_share_of_the_swing(self):
        broker, moment = open_long(scenario_profile(stop_buffer_ratio=D('0.01')))
        protect(broker, moment)
        broker.process(candle('15m', moment + 2 * STEP, 138, 139, 136, 137),
                       (confirmed_low(131, moment + 2 * STEP),))
        self.assertEqual(broker.trades[-1].stop, D('129.69'))           # 131 - 1.31
```

- In `tests/test_sweep.py`, replace `ScaleTests.test_both_price_knobs_scale_with_the_reference_price` with:

```python
    def test_price_scaling_sets_ratios_of_the_price_being_tested(self):
        profile = sweep.scale_profile(StrategyProfile(), D('0.005'), D('0.001'))
        self.assertEqual((profile.boundary_proximity_ratio, profile.stop_buffer_ratio),
                         (D('0.005'), D('0.001')))
        self.assertEqual(profile.effective_htf_zone_tolerance_ratio, D('0.005'))
        self.assertEqual(profile.trailing_buffer_at(D('127')), D('0.127'))
```

- In `tests/test_sweep.py`, change `test_price_scaling_reads_the_first_entry_close` to assert `(row['reference_price'], row['proximity_ratio'], row['stop_buffer_ratio'], row['boundary_proximity'], row['stop_buffer']) == ('127', '0.005', '0.001', None, None)`, and rename it `test_price_scaling_records_the_ratios`.

- [ ] **Step 2: Run the tests and watch them fail**: missing attributes, and `scale_profile` has the wrong arity.
- [ ] **Step 3: Implement** as described under Files.
  - The trail loop becomes:

```python
        for swing in reversed(swing_lows if long_ else swing_highs):
            if swing.confirmed_at < trade.filled_at:
                break               # every earlier swing was confirmed before the fill
            if swing.confirmed_at > candle.close_time or swing.swing_time < trade.filled_at:
                continue            # unconfirmed, or structure from before this trade
            buffer = self.profile.trailing_buffer_at(swing.price)
```

    Then compute `proposed` with that buffer, exactly as today.

  - Candidates are now scanned newest first. With the strict `>` (`<` for shorts), two swings with the same proposal now record the newer one as the reference. The stop value is unchanged.
- [ ] **Step 4:** Run the modules and the full suite. Expected: PASS, including `test_price_scaling_makes_the_result_independent_of_the_price_level`.
- [ ] **Step 5: Commit** `feat: measure sweep tolerances on the current price`.

---

### Task 3: R ladder — break-even at 1R or EQ, 30% at 2R

**Files:**
- Modify: `agent_trading/strategy_v1/config.py`:
  - `BREAK_EVEN_TRIGGERS` gains `'EQ_OR_R_MULTIPLE'`;
  - the default `partial_take_profits` is `(PartialTakeProfit(Decimal('2'), Decimal('0.30')),)`;
  - the default `break_even_trigger` is `'EQ_OR_R_MULTIPLE'`.
- Modify: `agent_trading/strategy_v1/broker.py` (`_manage`).
- Modify: `agent_trading/backtest/cli.py`: defaults `--partial-tp '2:0.30'` and `--break-even-trigger EQ_OR_R_MULTIPLE`.
- Modify:
  - `tests/strategy_v1_fixtures.py`: `LEGACY` gains `partial_take_profits=()`;
  - `tests/test_sweep.py`: `LEGACY_FLAGS` gains `'--partial-tp', ''`;
  - `tests/test_dd_config.py` and `tests/test_strategy_v1_partials.py`: the default assertions.
- Create: `tests/test_rr_ladder.py`
- Local: `config/strategy.json` (gitignored) gets the 2R / 30% partial.

- [ ] **Step 1: Write the failing tests** — create `tests/test_rr_ladder.py`:

```python
"""[U-RR-TRAIL-001] The R ladder: break-even at 1R (or EQ), 30% at 2R.

Long: entry 128, stop 118, R 10, quantity 10; a short is the reflection about 256.
"""
import unittest
from decimal import Decimal as D

from agent_trading.market import bar_duration
from agent_trading.trading_brain.models import FVG, TradeCandidate
from agent_trading.trading_brain.risk import RiskEngine
from agent_trading.strategy_v1 import PendingLimitPaperBroker
from agent_trading.strategy_v1.models import EntryPlan, TrackedFvg

from strategy_v1_fixtures import SYMBOL, bias_candles, candle, scenario_profile
from test_dd_management import SIDES, bar, price

STEP = bar_duration('15m')
LADDER = dict(direction='BOTH', eq_scale_out_fraction=D('0.30'),
              break_even_trigger='EQ_OR_R_MULTIPLE', runner_fraction=D('0.20'),
              secondary_fvg_support_enabled=False,
              partial_take_profits=({'r_multiple': '2', 'close_fraction': '0.30'},))


def open_ladder(side='LONG', eq=150, target=160, **overrides):
    settings = dict(LADDER)
    settings.update(overrides)
    profile = scenario_profile(**settings)
    risk = RiskEngine(profile.risk_config())
    broker = PendingLimitPaperBroker(risk, D('10000'), profile)
    start = bias_candles()[0].close_time
    gap = FVG(side, D('126'), D('130'), (start, start, start), start)
    cand = TradeCandidate(side, D('128'), price(side, 119), price(side, target), start, (),
                          sweep_extreme=price(side, 119))
    decision = risk.evaluate(cand, D('10000'), (), symbol=SYMBOL, timeframe='15m')
    assert decision.plan is not None
    plan = EntryPlan(TrackedFvg('p1', gap), 'FVG_EQ', D('128'), price(side, target),
                     'MANIPULATION_SWEEP_LOW' if side == 'LONG' else 'MANIPULATION_SWEEP_HIGH',
                     None, None, None, start, range_eq=price(side, eq), entry_model='CHOCH_FVG')
    broker.submit(decision.plan, plan)
    broker.process(bar(side, start + STEP, 129, 129.5, 128, 128.5))
    return broker, start + STEP


def exits(broker):
    return [(x.kind, x.quantity, x.exit_price) for x in broker.trades[-1].ledger.exits]


class LadderTests(unittest.TestCase):
    def test_one_r_moves_the_stop_to_entry_before_eq(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side)
                events = broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                trade = broker.trades[-1]
                self.assertEqual((trade.stop, trade.stop_updates[-1].reason), (D('128'), 'BREAK_EVEN'))
                self.assertIn('BREAK_EVEN_PROTECTED', [e.kind for e in events])

    def test_two_r_closes_thirty_percent_of_the_original(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side)
                broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                broker.process(bar(side, moment + 2 * STEP, 138, 148.5, 137, 148))
                self.assertEqual(exits(broker), [('PARTIAL_TP', D('3'), price(side, 148))])

    def test_a_trade_that_reached_two_r_and_fell_back_ends_in_profit(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side)
                broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                broker.process(bar(side, moment + 2 * STEP, 138, 148.5, 137, 148))
                broker.process(bar(side, moment + 3 * STEP, 140, 141, 127, 127.5))
                trade = broker.trades[-1]
                self.assertEqual(exits(broker), [('PARTIAL_TP', D('3'), price(side, 148)),
                                                 ('STOP', D('7'), D('128'))])
                self.assertEqual((trade.status, trade.ledger.total_realized_pnl), ('CLOSED', D('60')))

    def test_eq_and_the_boundary_still_close_their_parts(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side)
                broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                broker.process(bar(side, moment + 2 * STEP, 138, 148.5, 137, 148))
                broker.process(bar(side, moment + 3 * STEP, 148, 150.5, 147, 150))
                events = broker.process(bar(side, moment + 4 * STEP, 150, 160.5, 149, 160))
                boundary = 'RANGE_HIGH' if side == 'LONG' else 'RANGE_LOW'
                self.assertEqual(exits(broker), [('PARTIAL_TP', D('3'), price(side, 148)),
                                                 ('RANGE_EQ', D('3'), price(side, 150)),
                                                 (boundary, D('2'), price(side, 160))])
                self.assertEqual(broker.trades[-1].ledger.remaining_quantity, D('2'))
                self.assertIn('RUNNER_OPEN', [e.kind for e in events])

    def test_eq_before_one_r_protects_the_entry_at_eq(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side, eq=133)
                broker.process(bar(side, moment + STEP, 130, 133.5, 129, 133))
                trade = broker.trades[-1]
                self.assertEqual(exits(broker), [('RANGE_EQ', D('3'), price(side, 133))])
                self.assertEqual((trade.stop, trade.stop_updates[-1].reason),
                                 (D('128'), 'RANGE_EQ_BREAK_EVEN'))

    def test_a_two_r_level_beyond_the_boundary_is_left_to_the_boundary_exit(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_ladder(side, eq=136, target=145)
                broker.process(bar(side, moment + STEP, 130, 145.5, 129, 145))
                kinds = [kind for kind, _q, _p in exits(broker)]
                self.assertNotIn('PARTIAL_TP', kinds)
                self.assertEqual(kinds, ['RANGE_EQ', 'RANGE_HIGH' if side == 'LONG' else 'RANGE_LOW'])


class LadderDefaultTests(unittest.TestCase):
    def test_the_ladder_is_the_default(self):
        from agent_trading.strategy_v1 import StrategyProfile
        from agent_trading.strategy_v1.config import BREAK_EVEN_TRIGGERS, PartialTakeProfit
        profile = StrategyProfile()
        self.assertIn('EQ_OR_R_MULTIPLE', BREAK_EVEN_TRIGGERS)
        self.assertEqual(profile.break_even_trigger, 'EQ_OR_R_MULTIPLE')
        self.assertEqual(profile.partial_take_profits, (PartialTakeProfit(D('2'), D('0.30')),))


if __name__ == '__main__':
    unittest.main()
```

- Also change the assertions that pin the old defaults:
  - `tests/test_strategy_v1_partials.py`, `test_an_empty_partial_list_is_the_default_and_is_valid`: rename it `test_the_default_ladder_takes_thirty_percent_at_two_r`; assert the default ladder, then `StrategyProfile(partial_take_profits=())` is still valid.
  - `tests/test_dd_config.py`, `DdDefaultTests`: assert `break_even_trigger == 'EQ_OR_R_MULTIPLE'`.

- [ ] **Step 2: Run them and watch them fail.**
- [ ] **Step 3: Implement.**
  - `_manage`:

```python
        trigger = self.profile.break_even_trigger
        managed = trade
        if trigger in ('R_MULTIPLE', 'EQ_OR_R_MULTIPLE'):
            managed = self.risk.manage(managed, candle)        # inherited 1R break-even
        if trigger in ('RANGE_EQ', 'EQ_OR_R_MULTIPLE'):
            managed = self._range_break_even(managed, candle)
        if managed != trade:
```

  - Update the config defaults and comments, the CLI defaults, and the `LEGACY` pin in `tests/strategy_v1_fixtures.py` (`partial_take_profits=()`).
  - `LEGACY_FLAGS` in `tests/test_sweep.py` gains `'--partial-tp', ''`.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5: Local panel settings.** Add `{"id": "rr-2r", "rMultiple": "2", "closePct": "30"}` to `exits.partialTakeProfits` in `config/strategy.json`, then validate with `StrategyStore('config/strategy.json').current.to_profile()`.
- [ ] **Step 6: Commit** `feat: add the R ladder: break-even at 1R or EQ and 30% at 2R`.

---

### Task 4: Internal-pivot trailing

**Files:**
- Create: `agent_trading/strategy_v1/pivots.py`, `tests/test_pivots.py`, `tests/test_trailing_modes.py`
- Modify: `agent_trading/strategy_v1/config.py`: `TRAILING_MODES` and `trailing_pivot_bars` (int, 1..10, default 3).
- Modify: `agent_trading/strategy_v1/broker.py`: `TRAIL_REFERENCE` is keyed by `(mode, direction)`.
- Modify: `agent_trading/strategy_v1/strategy.py`: a `PivotTracker` in `INTERNAL_PIVOT` mode, with `ENTRY_PIVOT_LOW/HIGH` events and pivots passed to the broker.
- Modify: `agent_trading/backtest/cli.py`: `--trailing-mode` (choices `TRAILING_MODES`) and `--pivot-bars`.

**Interfaces:**
- Produces:
  - `Pivot(side, price, swing_time, confirmed_at, bars)`.
  - `PivotTracker(bars).process(candle) -> tuple[Pivot, ...]`.
  - Trail labels `INTERNAL_PIVOT_LOW` / `INTERNAL_PIVOT_HIGH`.

- [ ] **Step 1: Write the failing tests.** `tests/test_pivots.py`:

```python
"""[U-RR-TRAIL-001] Guide §2 step 1 pivots on the entry timeframe [H]-PIVOT-N-001."""
from decimal import Decimal as D
import unittest

from agent_trading.market import bar_duration
from agent_trading.strategy_v1.pivots import Pivot, PivotTracker
from strategy_v1_fixtures import ENTRY_START, candle

STEP = bar_duration('15m')


def run(tracker, rows):
    found = []
    for i, (h, l) in enumerate(rows, 1):
        found.extend(tracker.process(candle('15m', ENTRY_START + i * STEP, l, h, l, l)))
    return found


class PivotTests(unittest.TestCase):
    def test_a_low_below_n_bars_on_each_side_is_confirmed_n_bars_later(self):
        found = run(PivotTracker(2), [(12, 10), (11, 9), (10, 7), (11, 8), (12, 9)])
        self.assertEqual(found, [Pivot('LOW', D('7'), ENTRY_START + 3 * STEP,
                                       ENTRY_START + 5 * STEP, 2)])

    def test_an_equal_neighbour_is_not_a_pivot(self):
        self.assertEqual([p for p in run(PivotTracker(2), [(12, 10), (11, 7), (10, 7),
                                                            (11, 8), (12, 9)]) if p.side == 'LOW'], [])

    def test_highs_mirror_lows(self):
        found = run(PivotTracker(1), [(10, 5), (13, 6), (11, 5)])
        self.assertEqual([(p.side, p.price) for p in found], [('HIGH', D('13'))])

    def test_nothing_is_known_before_the_window_fills(self):
        self.assertEqual(run(PivotTracker(3), [(12, 10), (11, 9), (10, 7), (11, 8), (12, 9)]), [])

    def test_n_is_validated(self):
        for bad in (0, 11, 2.0, '3'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                PivotTracker(bad)
```

  The rows are `(high, low)`. `candle(tf, time, o, h, l, c)` with open = close = low keeps each bar consistent.

  `tests/test_trailing_modes.py`, first part:

```python
"""[U-RR-TRAIL-001] Trailing modes: internal pivots and ATR tiers."""
from decimal import Decimal as D
import unittest

from agent_trading.strategy_v1 import StrategyProfile
from agent_trading.strategy_v1.pivots import Pivot
from dd_fixtures import model_one_long_candles, run_dd
from strategy_v1_fixtures import candle, scenario_profile
from test_strategy_v1_trailing import STEP, open_long, protect


class PivotTrailTests(unittest.TestCase):
    def test_the_mode_and_n_are_validated(self):
        self.assertEqual(StrategyProfile().trailing_pivot_bars, 3)
        with self.assertRaises(ValueError):
            StrategyProfile(trailing_pivot_bars=0)
        StrategyProfile(trailing_mode='INTERNAL_PIVOT')

    def test_a_pivot_low_trails_the_stop_with_its_own_label(self):
        broker, moment = open_long(scenario_profile(trailing_mode='INTERNAL_PIVOT'))
        _events, moment = protect(broker, moment)
        pivot = Pivot('LOW', D('131'), moment - STEP, moment, 1)
        events = broker.process(candle('15m', moment + STEP, 138, 139, 136, 137), (pivot,))
        record = next(e.payload for e in events if e.kind == 'TRAILING_STOP_UPDATED')
        self.assertEqual((record.new_stop, record.structural_reference), (D('130'), 'INTERNAL_PIVOT_LOW'))

    def test_the_strategy_trails_on_pivots_formed_after_the_fill(self):
        strategy = run_dd(model_one_long_candles(), trailing_mode='INTERNAL_PIVOT',
                          trailing_pivot_bars=1)
        trade = strategy.broker.trades[0]
        pivots = {(e.payload.price, e.payload.confirmed_at): e.payload
                  for e in strategy.events if e.kind == 'ENTRY_PIVOT_LOW'}
        updates = [e.payload for e in strategy.events if e.kind == 'TRAILING_STOP_UPDATED']
        self.assertTrue(updates)
        for record in updates:
            self.assertEqual(record.structural_reference, 'INTERNAL_PIVOT_LOW')
            self.assertGreaterEqual(pivots[(record.reference_price, record.confirmed_at)].swing_time,
                                    trade.filled_at)
```

- [ ] **Step 2: Run them and watch them fail** (`ModuleNotFoundError: agent_trading.strategy_v1.pivots`).
- [ ] **Step 3: Implement.**
  - `pivots.py`, as specified in the design:
    - frozen `Pivot`;
    - `PivotTracker` with a `deque(maxlen=2N+1)`;
    - the middle bar is a pivot low when its low is strictly below every other low in the window (highs mirrored);
    - `confirmed_at` is the current candle's close time.
  - Config: `TRAILING_MODES = ('CONFIRMED_HIGHER_LOW', 'INTERNAL_PIVOT', 'ATR_TIERS')` and `trailing_pivot_bars: int = 3`, validated as an int within 1..10.
  - Broker:

```python
TRAIL_REFERENCE = {('CONFIRMED_HIGHER_LOW', 'LONG'): 'CONFIRMED_HIGHER_LOW',
                   ('CONFIRMED_HIGHER_LOW', 'SHORT'): 'CONFIRMED_LOWER_HIGH',
                   ('INTERNAL_PIVOT', 'LONG'): 'INTERNAL_PIVOT_LOW',
                   ('INTERNAL_PIVOT', 'SHORT'): 'INTERNAL_PIVOT_HIGH'}
```

    `_trail` returns `()` in `ATR_TIERS` mode and labels the record with `TRAIL_REFERENCE[(self.profile.trailing_mode, trade.direction)]`.
  - StrategyV1:
    - `self.entry_pivots = PivotTracker(n) if mode == 'INTERNAL_PIVOT' else None`, plus the `entry_pivot_lows` / `entry_pivot_highs` tuples.
    - The broker gets the pivot tuples in that mode, the ATR swings otherwise.
    - After the swing engine, pivots are processed and emitted as `ENTRY_PIVOT_LOW` / `ENTRY_PIVOT_HIGH` (sources `pivot.source_ids`).
  - CLI: `--trailing-mode` (default `CONFIRMED_HIGHER_LOW`, choices `TRAILING_MODES`) and `--pivot-bars` (type int, default 3), wired into `profile_from_args`.
- [ ] **Step 4:** Run the full suite. Expected: PASS. `test_strategy_v1_trailing` still rejects `trailing_mode='ATR'`.
- [ ] **Step 5: Commit** `feat: trail on internal pivots of the entry timeframe`.

---

### Task 5: ATR-tier trailing exits

**Files:**
- Modify: `agent_trading/strategy_v1/config.py`: `trailing_atr_tiers`, normalised to Decimal pairs and validated (non-empty, ascending positive multiples, fractions within (0, 1]).
- Modify: `agent_trading/strategy_v1/models.py`: the `PositionExit.kind` comment gains `ATR_TIER`.
- Modify: `agent_trading/strategy_v1/broker.py`:
  - `_reset_trade_state` resets `peak` and `tiers_done`; `_fill` sets `peak = entry`;
  - `process(..., atr=None)`;
  - `_manage` calls tiers in that mode, and `_track_peak`;
  - new `_atr_tiers`.
- Modify: `agent_trading/strategy_v1/strategy.py`: `broker.process(..., atr=self.entry_swing.state.atr)`.
- Modify:
  - `agent_trading/backtest/recorder.py`: `EXIT_REASONS['ATR_TIER'] = 'ATR_TIER'`;
  - `agent_trading/backtest/metrics.py`: `'atr_tier_exits': 'ATR_TIER_EXIT'`;
  - `agent_trading/bot_service.py`: notify on `ATR_TIER_EXIT`;
  - `agent_trading/backtest/cli.py`: `--atr-tiers '0.75:0.25,1.25:0.5,1.5:1'`.
- Test: append to `tests/test_trailing_modes.py`.

**Interfaces:**
- Consumes: `trailing_mode == 'ATR_TIERS'`.
- Produces:
  - Slice kind `ATR_TIER` and event `ATR_TIER_EXIT` (payload `PositionExit`, `target_price` = tier level).
  - `broker.process(candle, swing_lows=(), swing_highs=(), atr=None)`.

- [ ] **Step 1: Write the failing tests** (append):

```python
from agent_trading.backtest.metrics import SETUP_EVENTS
from agent_trading.backtest.recorder import EXIT_REASONS

ATR = D('2')                                   # tiers at peak - 1.5, - 2.5, - 3


class AtrTierTests(unittest.TestCase):
    def _protected(self, **overrides):
        broker, moment = open_long(scenario_profile(trailing_mode='ATR_TIERS', **overrides))
        broker.process(candle('15m', moment + STEP, 128, 138.5, 127.5, 138), atr=ATR)  # BE
        return broker, moment + STEP

    def test_the_tiers_are_validated(self):
        self.assertEqual(StrategyProfile().trailing_atr_tiers,
                         ((D('0.75'), D('0.25')), (D('1.25'), D('0.5')), (D('1.5'), D('1'))))
        for bad in ((), ((D('1'), D('0')),), ((D('1'), D('0.5')), (D('0.5'), D('1')))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                StrategyProfile(trailing_atr_tiers=bad)

    def test_each_tier_closes_its_share_of_the_open_position(self):
        broker, moment = self._protected()                     # peak 138.5 after this bar
        broker.process(candle('15m', moment + STEP, 138, 138.2, 137, 137.5), atr=ATR)
        broker.process(candle('15m', moment + 2 * STEP, 137.5, 137.6, 136, 136.5), atr=ATR)
        events = broker.process(candle('15m', moment + 3 * STEP, 136.5, 136.6, 135.4, 135.5),
                                atr=ATR)
        ledger = broker.trades[-1].ledger
        self.assertEqual([(x.kind, x.quantity, x.exit_price) for x in ledger.exits],
                         [('ATR_TIER', D('2.5'), D('137')), ('ATR_TIER', D('3.75'), D('136')),
                          ('ATR_TIER', D('3.75'), D('135.5'))])
        self.assertEqual(broker.trades[-1].status, 'CLOSED')
        self.assertIn('PAPER_ORDER_CLOSED', [e.kind for e in events])

    def test_no_tier_fires_before_break_even_or_without_atr(self):
        broker, moment = open_long(scenario_profile(trailing_mode='ATR_TIERS'))
        broker.process(candle('15m', moment + STEP, 128.5, 133, 128.2, 132), atr=ATR)
        broker.process(candle('15m', moment + 2 * STEP, 132, 132, 129, 129.5), atr=ATR)
        self.assertEqual(broker.trades[-1].ledger.exits, ())
        broker, moment = self._protected()
        broker.process(candle('15m', moment + STEP, 138, 138.2, 135, 135.5), atr=None)
        self.assertEqual(broker.trades[-1].ledger.exits, ())

    def test_one_bar_through_several_tiers_fills_them_in_order_at_the_open_when_gapped(self):
        broker, moment = self._protected()
        broker.process(candle('15m', moment + STEP, 136.8, 136.9, 135, 135.2), atr=ATR)
        ledger = broker.trades[-1].ledger
        self.assertEqual([(x.quantity, x.exit_price) for x in ledger.exits],
                         [(D('2.5'), D('136.8')), (D('3.75'), D('136')),
                          (D('3.75'), D('135.5'))])

    def test_the_strategy_passes_the_previous_bars_atr(self):
        from agent_trading.strategy_v1 import StrategyV1
        from dd_fixtures import dd_profile
        from strategy_v1_fixtures import SYMBOL
        strategy = StrategyV1(SYMBOL, dd_profile(trailing_mode='ATR_TIERS'))
        seen, original = [], strategy.broker.process
        def spy(candle, lows=(), highs=(), atr=None):
            seen.append((atr, strategy.entry_swing.state.atr))
            return original(candle, lows, highs, atr=atr)
        strategy.broker.process = spy
        strategy.feed(model_one_long_candles())
        self.assertTrue(any(a is not None for a, _b in seen))
        self.assertTrue(all(a == b for a, b in seen))

    def test_reports_know_the_tier_exit(self):
        self.assertEqual(EXIT_REASONS['ATR_TIER'], 'ATR_TIER')
        self.assertEqual(SETUP_EVENTS['atr_tier_exits'], 'ATR_TIER_EXIT')
```

  The long ladder here is the legacy `open_long`: entry 128, stop 118, 10 units, BE at 1R under `LEGACY`'s `R_MULTIPLE`.
  - Tier quantities, 25% / 50% / rest of the open position: 10 → 2.5, then 7.5 → 3.75, then 3.75.
  - The gapped-bar test opens at 136.8, which is below tier 1's 137 level. So tier 1 fills at the open, and tiers 2 and 3 at their levels.
  - The spy test checks that the broker receives the entry-timeframe ATR as of the bar before (the swing engine has not yet seen the current bar when the broker runs).

- [ ] **Step 2: Run them and watch them fail.**
- [ ] **Step 3: Implement.**
  - Broker:

```python
    def _track_peak(self, trade, candle):
        """Best price since the fill for ATR tiers [H]-ATR-TIERS-001. The fill bar is
        skipped: its extreme may have printed before the order filled."""
        if trade.status != 'OPEN' or self.peak is None or candle.close_time <= trade.filled_at:
            return
        self.peak = max(self.peak, candle.high) if trade.direction == 'LONG' else min(self.peak, candle.low)

    def _atr_tiers(self, trade, candle, atr):
        """[U-RR-TRAIL-001] After break-even each tier closes its share of the open
        position once price trades back `multiple x ATR` from the peak."""
        if (not self.profile.trailing_enabled or self.break_even_at is None
                or trade.status != 'OPEN' or atr is None or atr <= 0 or self.peak is None):
            return ()
        long_ = trade.direction == 'LONG'
        events, tiers = [], self.profile.trailing_atr_tiers
        while self.tiers_done < len(tiers):
            multiple, fraction = tiers[self.tiers_done]
            distance = exact_product(atr, multiple)
            level = exact_difference(self.peak, distance if long_ else distance.copy_negate())
            if candle.low > level if long_ else candle.high < level:
                break
            self.tiers_done += 1
            trade = self.trades[-1]
            remaining = trade.ledger.remaining_quantity
            quantity = (remaining if fraction >= 1 else
                        floor_to_step(exact_product(remaining, fraction), self.profile.quantity_step))
            if quantity <= 0:
                continue
            price = candle.open if (candle.open < level if long_ else candle.open > level) else level
            trade, record = self._realise(trade, 'ATR_TIER', quantity, price, candle.close_time,
                                          target_price=level)
            trade = self._store(trade)
            events.append(BrokerEvent('ATR_TIER_EXIT', candle.close_time, record))
            if trade.ledger.remaining_quantity <= 0:
                events.append(BrokerEvent('PAPER_ORDER_CLOSED', candle.close_time,
                                          self._close(trade, candle.close_time)))
                break
        return tuple(events)
```

  - `_manage` ends with:

```python
        if self.profile.trailing_mode == 'ATR_TIERS':
            result.extend(self._atr_tiers(self.trades[-1], candle, atr))
        else:
            result.extend(self._trail(self.trades[-1], candle, swing_lows, swing_highs))
        self._track_peak(self.trades[-1], candle)
        return tuple(result)
```

- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: add ATR-tier trailing exits`.

---

### Task 6: Compare on 30 pairs and record

- [ ] **Step 1: Run the five sweeps in parallel** (20 cores), each into `runs/sweep-rr-sN`:

| Run | Flags |
|---|---|
| S0 | `--partial-tp '' --break-even-trigger RANGE_EQ` |
| S1 | none (defaults) |
| S2 | `--trailing-mode INTERNAL_PIVOT --pivot-bars 2` |
| S3 | `--trailing-mode INTERNAL_PIVOT --pivot-bars 3` |
| S4 | `--trailing-mode ATR_TIERS` |

- [ ] **Step 2: Run the invariant check** (scratchpad `verify_fix.py`, extended so that `ENTRY_PIVOT_*` payloads resolve `swing_time`). There must be zero trails before the fill, before break-even, or beyond the close.
- [ ] **Step 3: Compare** (scratchpad `compare_runs.py`). Per run:
  - trades, win rate, average / median / total R, PF, max drawdown in R;
  - CORE / YOUNG, long / short;
  - average R at 0.1% per side;
  - exit kinds;
  - trades that reached ≥2R and still closed at ≤ −0.9R.
- [ ] **Step 4: Document**: the strategy spec and backtest spec sections, PROJECT_STATE, HANDOFF, NEXT_TASK, with the result table; the default trailing method is left to the owner. Commit `docs: record the R ladder, trailing modes and their comparison`.
- [ ] **Step 5: Ask the owner** to choose the default trailing method. The report page is regenerated for the chosen run after that decision.
