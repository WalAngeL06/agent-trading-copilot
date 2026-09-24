# DD Deviation Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strategy V1 trades the DD Finance deviation school, and the live PAPER agent follows it.
- **Entry:** model 1 (entry-timeframe CHoCH) and model 2 (HTF FVG reversal) both run; the first one ready takes the trade.
- **Stop:** at the deviation wick.
- **Exits:** 30% at the range EQ with break-even, 50% at the opposite boundary, and a 20% runner on the trailing stop.

**Architecture:** Every DD rule is a `StrategyProfile` knob.
1. The knobs land first with defaults equal to today's behaviour, so every task leaves the suite green.
2. Each rule is then built and tested with explicit knobs.
3. One final task flips the defaults and pins the shipped scenarios to the legacy knobs.

The new code is in four places:
- a small `ChochTracker` module for model 1;
- one `FvgBook` method for the gap the CHoCH left;
- a model loop in `StrategyV1._consider`;
- a range-EQ step in the broker's favourable-exit path.

**Tech Stack:** Python 3.14, `decimal.Decimal` only, and unittest run with `./.venv/Scripts/python.exe -B -m unittest discover -s tests`.

**Spec:** `docs/specs/dd-deviation-models-2026-09-25.md` [U-DD-DEVIATION-001]

## Global Constraints

- **PAPER only.** No exchange write, no live execution, no OKX call anywhere in this work.
- **Location.** All work happens in `C:/Users/Serdar Arif/Desktop/Agent Trading` on `main`.
  - The desktop session starts in a stale worktree whose Edit/Write tools refuse the canonical checkout.
  - Change files with small scratchpad scripts built on `scratchpad/edit_lib.py`, which makes EOL-preserving, exactly-once replacements.
  - A new file is written to the scratchpad and copied with `cp`.
- **Tests.**
  - Full suite: `./.venv/Scripts/python.exe -B -m unittest discover -s tests`.
  - One module: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_x.py"`. `-m unittest tests.test_x` fails, because test modules import siblings.
  - After every task: `git diff --check`.
- **Arithmetic.** Decimal only. Use `exact_product`/`exact_difference` from `agent_trading.trading_brain.risk`; never floats in engine code.
- **Tags.**
  - The decision tag is `[U-DD-DEVIATION-001]`.
  - Provisional rules are tagged `[H]-DD-EXTREME-001`, `[H]-DD-CHOCH-001`, `[H]-DD-MODEL2-001` and `[H]-DD-EQ-SKIP-001`.
- **Backtest modules** (`agent_trading/backtest/*.py`) must never contain the strings `SwingEngine(`, `RiskEngine(`, `PendingLimitPaperBroker(`, `entry_price(`, `partial_target(` or `tighten_stop(`; the forbidden-strings test in `tests/test_backtest.py` checks this.
- **Final defaults** (Task 6):

  | Knob | Default |
  |---|---|
  | `entry_models` | `('CHOCH_FVG', 'HTF_FVG_REVERSAL')` |
  | `model2_requires_htf_fvg` | `None` |
  | `eq_scale_out_fraction` | `Decimal('0.30')` |
  | `break_even_trigger` | `'RANGE_EQ'` |
  | `secondary_fvg_support_enabled` | `False` |
  | `runner_fraction` | `Decimal('0.20')` |
- **Legacy knobs** (the pre-DD behaviour, kept selectable):

  | Knob | Legacy value |
  |---|---|
  | `entry_models` | `('HTF_FVG_REVERSAL',)` |
  | `model2_requires_htf_fvg` | `False` |
  | `secondary_fvg_support_enabled` | `True` |
  | `eq_scale_out_fraction` | `None` |
  | `break_even_trigger` | `'R_MULTIPLE'` |
  | `runner_fraction` | `Decimal('0.10')` |
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Nothing is pushed without the owner's approval.
- **Do not touch** `Yeni klasör/`, `_archive/`, `data/` or `runs/` contents (other than new run folders).

---

### Task 1: DD knobs on the profile and the command line (legacy defaults)

**Files:**
- Modify: `agent_trading/strategy_v1/config.py` (constants near `TRAILING_MODES`; new fields after `pending_expiry_bars`; `__post_init__`; `_validate_exits`; `as_dict`; a new property)
- Modify: `agent_trading/backtest/cli.py` (`add_profile_arguments`, `profile_from_args`)
- Create: `tests/test_dd_config.py`

**Interfaces:**
- Produces:
  - `config.ENTRY_MODELS == ('CHOCH_FVG', 'HTF_FVG_REVERSAL')` and `config.BREAK_EVEN_TRIGGERS == ('RANGE_EQ', 'R_MULTIPLE')`.
  - `StrategyProfile` fields: `entry_models: tuple`, `model2_requires_htf_fvg: bool | None`, `eq_scale_out_fraction: Decimal | None`, `break_even_trigger: str`.
  - Property `StrategyProfile.effective_model2_requires_htf_fvg -> bool`.
  - CLI flags: `--entry-models`, `--model2-htf-fvg {auto,true,false}`, `--eq-scale-out`, `--break-even-trigger`, and `--secondary-fvg/--no-secondary-fvg`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_dd_config.py`:

```python
"""[U-DD-DEVIATION-001] Profile and command-line knobs for the DD deviation models."""
import argparse
import unittest
from decimal import Decimal as D

from agent_trading.strategy_v1 import StrategyProfile
from agent_trading.strategy_v1.config import BREAK_EVEN_TRIGGERS, ENTRY_MODELS

OLD_GATE = dict(direction='LONG_ONLY', direction_gate='BIAS_LONG_PERMISSION')


class DdProfileTests(unittest.TestCase):
    def test_the_entry_models_are_named_and_kept_as_a_tuple(self):
        self.assertEqual(ENTRY_MODELS, ('CHOCH_FVG', 'HTF_FVG_REVERSAL'))
        profile = StrategyProfile(entry_models=['HTF_FVG_REVERSAL', 'CHOCH_FVG'])
        self.assertEqual(profile.entry_models, ('HTF_FVG_REVERSAL', 'CHOCH_FVG'))

    def test_unknown_duplicate_or_empty_entry_models_are_rejected(self):
        for models in ((), ('MODEL_3',), ('CHOCH_FVG', 'CHOCH_FVG')):
            with self.subTest(models=models), self.assertRaises(ValueError):
                StrategyProfile(entry_models=models)

    def test_model_two_follows_the_gate_unless_set(self):
        self.assertTrue(StrategyProfile(model2_requires_htf_fvg=None)
                        .effective_model2_requires_htf_fvg)
        self.assertFalse(StrategyProfile(model2_requires_htf_fvg=None, **OLD_GATE)
                         .effective_model2_requires_htf_fvg)
        self.assertFalse(StrategyProfile(model2_requires_htf_fvg=False)
                         .effective_model2_requires_htf_fvg)

    def test_the_old_gate_cannot_require_an_htf_fvg(self):
        with self.assertRaises(ValueError):
            StrategyProfile(model2_requires_htf_fvg=True, **OLD_GATE)
        with self.assertRaises(ValueError):
            StrategyProfile(model2_requires_htf_fvg=1)

    def test_the_eq_scale_out_is_a_share_of_the_original_quantity(self):
        profile = StrategyProfile(eq_scale_out_fraction=D('0.30'), runner_fraction=D('0.20'))
        self.assertEqual(profile.eq_scale_out_fraction, D('0.30'))
        for bad in (D('0'), D('1.5'), D('NaN'), 0.3):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                StrategyProfile(eq_scale_out_fraction=bad)

    def test_the_eq_slice_counts_against_the_non_runner_allocation(self):
        with self.assertRaises(ValueError):
            StrategyProfile(eq_scale_out_fraction=D('0.30'), runner_fraction=D('0.20'),
                            partial_take_profits=({'r_multiple': '1', 'close_fraction': '0.60'},))

    def test_the_break_even_trigger_is_validated(self):
        self.assertEqual(BREAK_EVEN_TRIGGERS, ('RANGE_EQ', 'R_MULTIPLE'))
        with self.assertRaises(ValueError):
            StrategyProfile(break_even_trigger='TWO_R')

    def test_the_run_config_shows_the_dd_knobs(self):
        data = StrategyProfile(entry_models=ENTRY_MODELS, model2_requires_htf_fvg=None,
                               eq_scale_out_fraction=D('0.30'), runner_fraction=D('0.20'),
                               break_even_trigger='RANGE_EQ').as_dict()
        self.assertEqual(data['entry_models'], ['CHOCH_FVG', 'HTF_FVG_REVERSAL'])
        self.assertIs(data['model2_requires_htf_fvg'], True)
        self.assertEqual(data['eq_scale_out_fraction'], '0.30')
        self.assertEqual(data['break_even_trigger'], 'RANGE_EQ')


class DdFlagTests(unittest.TestCase):
    def profile(self, *flags):
        from agent_trading.backtest.cli import add_profile_arguments, profile_from_args
        parser = argparse.ArgumentParser()
        add_profile_arguments(parser)
        return profile_from_args(parser.parse_args(list(flags)))

    def test_every_dd_knob_has_a_flag(self):
        profile = self.profile('--entry-models', 'CHOCH_FVG', '--model2-htf-fvg', 'auto',
                               '--eq-scale-out', '0.25', '--break-even-trigger', 'RANGE_EQ',
                               '--runner-fraction', '0.20', '--no-secondary-fvg')
        self.assertEqual(profile.entry_models, ('CHOCH_FVG',))
        self.assertIsNone(profile.model2_requires_htf_fvg)
        self.assertEqual(profile.eq_scale_out_fraction, D('0.25'))
        self.assertEqual(profile.break_even_trigger, 'RANGE_EQ')
        self.assertFalse(profile.secondary_fvg_support_enabled)

    def test_the_legacy_behaviour_is_selectable(self):
        profile = self.profile('--entry-models', 'HTF_FVG_REVERSAL', '--model2-htf-fvg', 'false',
                               '--eq-scale-out', 'none', '--break-even-trigger', 'R_MULTIPLE',
                               '--secondary-fvg')
        self.assertIsNone(profile.eq_scale_out_fraction)
        self.assertIs(profile.model2_requires_htf_fvg, False)
        self.assertTrue(profile.secondary_fvg_support_enabled)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it and watch it fail**

Run: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_dd_config.py"`
Expected: ERROR `ImportError: cannot import name 'BREAK_EVEN_TRIGGERS'`.

- [ ] **Step 3: Implement the profile knobs** in `agent_trading/strategy_v1/config.py`.

1. Below `TRAILING_MODES = ...`:

```python
# [U-DD-DEVIATION-001] DD model 1 (entry-timeframe CHoCH) and model 2 (HTF FVG
# reversal). This order is also the order they are tried in.
ENTRY_MODELS = ('CHOCH_FVG', 'HTF_FVG_REVERSAL')
# RANGE_EQ moves the stop to entry at the range EQ; R_MULTIPLE is the
# inherited 1R favourable-excursion break-even.
BREAK_EVEN_TRIGGERS = ('RANGE_EQ', 'R_MULTIPLE')
```

2. After the `pending_expiry_bars` field, add the temporary legacy defaults. Task 6 flips them.

```python
    # [U-DD-DEVIATION-001] Entry models; the first one ready takes the trade.
    entry_models: tuple = ('HTF_FVG_REVERSAL',)
    # Model 2 needs the deviation to touch an HTF FVG. None follows the gate:
    # true under GUIDE_HTF_CONTEXT, false under BIAS_LONG_PERMISSION (no zones).
    model2_requires_htf_fvg: bool | None = False
    # Share of the ORIGINAL quantity closed at the range EQ; None disables.
    eq_scale_out_fraction: Decimal | None = None
    break_even_trigger: str = 'R_MULTIPLE'
```

3. In `__post_init__`, before `self._validate_exits()`:

```python
        models = tuple(self.entry_models)
        if (not models or len(set(models)) != len(models)
                or any(model not in ENTRY_MODELS for model in models)):
            raise ValueError('entry_models must name CHOCH_FVG and/or HTF_FVG_REVERSAL once each')
        object.__setattr__(self, 'entry_models', models)
        requirement = self.model2_requires_htf_fvg
        if requirement is not None and type(requirement) is not bool:
            raise ValueError('model2_requires_htf_fvg must be True, False or None')
        if requirement is True and self.direction_gate == 'BIAS_LONG_PERMISSION':
            raise ValueError('BIAS_LONG_PERMISSION builds no HTF zones for model 2 to require')
        if self.break_even_trigger not in BREAK_EVEN_TRIGGERS:
            raise ValueError('unknown break-even trigger')
```

4. In `_validate_exits`, replace the allocation check. Replace

```python
        total = sum((level.close_fraction for level in levels), Decimal(0))
        if total > 1 - runner:
```

with

```python
        eq = self.eq_scale_out_fraction
        if eq is not None and (not isinstance(eq, Decimal) or not eq.is_finite()
                               or not 0 < eq <= 1):
            raise ValueError('eq_scale_out_fraction must be a Decimal within (0, 1] or None')
        total = sum((level.close_fraction for level in levels), eq or Decimal(0))
        if total > 1 - runner:
```

5. In `as_dict`, add these keys to the returned dict:

```python
                'entry_models': list(self.entry_models),
                'model2_requires_htf_fvg': self.effective_model2_requires_htf_fvg,
                'eq_scale_out_fraction': None if self.eq_scale_out_fraction is None
                                         else str(self.eq_scale_out_fraction),
                'break_even_trigger': self.break_even_trigger,
```

6. After `effective_htf_zone_tolerance`, add the property:

```python
    @property
    def effective_model2_requires_htf_fvg(self):
        """Model 2's HTF FVG condition, defaulting to what the gate can provide."""
        if self.model2_requires_htf_fvg is not None:
            return self.model2_requires_htf_fvg
        return self.direction_gate == 'GUIDE_HTF_CONTEXT'
```

- [ ] **Step 4: Implement the flags** in `agent_trading/backtest/cli.py`.
  1. Add `import argparse`.
  2. Import `BREAK_EVEN_TRIGGERS` and `ENTRY_MODELS` from `..strategy_v1.config`.
  3. Replace `parser.add_argument('--no-secondary-fvg', action='store_true')` with:

```python
    parser.add_argument('--secondary-fvg', action=argparse.BooleanOptionalAction,
                        default=True, help='tighter stop behind a secondary FVG')
    parser.add_argument('--entry-models', default='HTF_FVG_REVERSAL',
                        help=f"comma list of {', '.join(ENTRY_MODELS)} [U-DD-DEVIATION-001]")
    parser.add_argument('--model2-htf-fvg', default='false', choices=('auto', 'true', 'false'),
                        help='model 2 needs a touched HTF FVG; auto follows the gate')
    parser.add_argument('--eq-scale-out', default='none',
                        help="share of the original quantity closed at range EQ, or 'none'")
    parser.add_argument('--break-even-trigger', default='R_MULTIPLE',
                        choices=BREAK_EVEN_TRIGGERS)
```

  4. In `profile_from_args`, replace `secondary_fvg_support_enabled=not args.no_secondary_fvg,` with:

```python
        secondary_fvg_support_enabled=args.secondary_fvg,
        entry_models=tuple(model.strip() for model in args.entry_models.split(',')
                           if model.strip()),
        model2_requires_htf_fvg={'auto': None, 'true': True,
                                 'false': False}[args.model2_htf_fvg],
        eq_scale_out_fraction=(None if args.eq_scale_out.strip().lower() == 'none'
                               else Decimal(args.eq_scale_out)),
        break_even_trigger=args.break_even_trigger,
```

- [ ] **Step 5: Run the new tests and then the full suite**

Run: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_dd_config.py"`, then the full suite.
Expected: PASS everywhere. `test_backtest_cli.BacktestDefaultsTests` still passes, because the CLI and the profile defaults moved together.

- [ ] **Step 6: Commit**

```bash
git add agent_trading/strategy_v1/config.py agent_trading/backtest/cli.py tests/test_dd_config.py
git commit -m "feat: add the DD entry and management knobs with legacy defaults"
```

---

### Task 2: Scale out at the range EQ and move break-even there (broker)

**Files:**
- Modify: `agent_trading/strategy_v1/models.py`. `EntryPlan` gains `range_eq` and `entry_model`; `PositionLedger` gains `range_eq_done`.
- Modify: `agent_trading/strategy_v1/broker.py`. Add `_range_eq` and `_range_break_even`; change `_favorable` and `_manage`.
- Create: `tests/test_dd_management.py`

**Interfaces:**
- Consumes:
  - `StrategyProfile.eq_scale_out_fraction` and `break_even_trigger` (Task 1).
- Produces:
  - `EntryPlan(..., observed_at, range_eq=None, entry_model=None)`.
  - `PositionLedger.range_eq_done: bool = False`.
  - Slice kind `RANGE_EQ` and event `RANGE_EQ_PARTIAL_EXIT` (payload `PositionExit`).
  - Stop-update reason `RANGE_EQ_BREAK_EVEN`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_dd_management.py`:

```python
"""[U-DD-DEVIATION-001] DD trade management on the broker alone.

30% of the original position closes at the range EQ and the stop moves to entry;
the opposite boundary closes 50%; the last 20% is trailed. A short is the long
reflected about its 128 entry, so every check runs both ways.
"""
import unittest
from decimal import Decimal as D

from agent_trading.market import bar_duration
from agent_trading.trading_brain.models import FVG, TradeCandidate
from agent_trading.trading_brain.risk import RiskEngine
from agent_trading.strategy_v1 import PendingLimitPaperBroker
from agent_trading.strategy_v1.models import EntryPlan, TrackedFvg

from strategy_v1_fixtures import SYMBOL, bias_candles, candle, scenario_profile

STEP = bar_duration('15m')
AXIS = D('256')
SIDES = ('LONG', 'SHORT')
DD = dict(direction='BOTH', eq_scale_out_fraction=D('0.30'), break_even_trigger='RANGE_EQ',
          runner_fraction=D('0.20'), secondary_fvg_support_enabled=False)


def price(side, value):
    value = D(str(value))
    return value if side == 'LONG' else AXIS - value


def bar(side, moment, open_, high, low, close):
    """A long-shaped bar; for a short it is reflected, so high and low swap."""
    if side == 'LONG':
        return candle('15m', moment, open_, high, low, close)
    return candle('15m', moment, price(side, open_), price(side, low),
                  price(side, high), price(side, close))


def boundary_kind(side):
    return 'RANGE_HIGH' if side == 'LONG' else 'RANGE_LOW'


def open_trade(side='LONG', eq=140, **overrides):
    """Fill a RiskEngine-approved DD plan at 128.

    Long: sweep 119, stop 118, boundary 160, range EQ 140. R is 10, quantity 10.
    Short: the same prices reflected about 256 (stop 138, boundary 96, EQ 116).
    """
    settings = dict(DD)
    settings.update(overrides)
    profile = scenario_profile(**settings)
    risk = RiskEngine(profile.risk_config())
    broker = PendingLimitPaperBroker(risk, D('10000'), profile)
    start = bias_candles()[0].close_time
    gap = FVG(side, D('126'), D('130'), (start, start, start), start)
    candidate = TradeCandidate(side, D('128'), price(side, 119), price(side, 160), start, (),
                               sweep_extreme=price(side, 119))
    decision = risk.evaluate(candidate, D('10000'), (), symbol=SYMBOL, timeframe='15m')
    assert decision.plan is not None, 'DD management fixture must be approvable'
    plan = EntryPlan(TrackedFvg('p1', gap), 'FVG_EQ', D('128'), price(side, 160),
                     'MANIPULATION_SWEEP_LOW' if side == 'LONG' else 'MANIPULATION_SWEEP_HIGH',
                     None, None, None, start,
                     range_eq=None if eq is None else price(side, eq), entry_model='CHOCH_FVG')
    broker.submit(decision.plan, plan)
    broker.process(bar(side, start + STEP, 129, 129.5, 128, 128.5))
    assert broker.trades[-1].status == 'OPEN'
    return broker, start + STEP


def kinds(events):
    return [event.kind for event in events]


class EqScaleOutTests(unittest.TestCase):
    def test_thirty_percent_closes_at_the_range_eq(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                events = broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                record = next(e.payload for e in events if e.kind == 'RANGE_EQ_PARTIAL_EXIT')
                self.assertEqual(record.kind, 'RANGE_EQ')
                self.assertEqual((record.exit_price, record.target_price),
                                 (price(side, 140), price(side, 140)))
                self.assertEqual((record.quantity, record.remaining_quantity), (D('3'), D('7')))
                self.assertEqual(record.realized_pnl, D('36'))

    def test_eq_moves_the_stop_to_entry_and_announces_break_even(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                events = broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                trade = broker.trades[-1]
                self.assertEqual(trade.stop, D('128'))
                self.assertEqual(trade.stop_updates[-1].reason, 'RANGE_EQ_BREAK_EVEN')
                protected = next(e.payload for e in events if e.kind == 'BREAK_EVEN_PROTECTED')
                self.assertEqual(protected.structural_reference, 'RANGE_EQ_BREAK_EVEN')

    def test_one_r_alone_no_longer_moves_the_stop(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                events = broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                self.assertEqual(broker.trades[-1].stop, price(side, 118))
                self.assertNotIn('BREAK_EVEN_PROTECTED', kinds(events))

    def test_the_boundary_closes_half_and_leaves_a_twenty_percent_runner(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                events = broker.process(bar(side, moment + 2 * STEP, 140.5, 161, 140, 160.5))
                ledger = broker.trades[-1].ledger
                self.assertEqual([(x.kind, x.quantity) for x in ledger.exits],
                                 [('RANGE_EQ', D('3')), (boundary_kind(side), D('5'))])
                self.assertEqual(ledger.remaining_quantity, D('2'))
                self.assertIn('RUNNER_OPEN', kinds(events))

    def test_one_bar_through_eq_and_the_boundary_books_eq_first(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side)
                broker.process(bar(side, moment + STEP, 130, 161, 129, 160))
                trade = broker.trades[-1]
                self.assertEqual([(x.kind, x.quantity) for x in trade.ledger.exits],
                                 [('RANGE_EQ', D('3')), (boundary_kind(side), D('5'))])
                self.assertEqual(trade.stop, D('128'))

    def test_an_eq_outside_the_trade_is_skipped_and_break_even_waits_for_the_boundary(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side, eq=125)        # behind the entry
                events = broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                self.assertNotIn('RANGE_EQ_PARTIAL_EXIT', kinds(events))
                self.assertEqual(broker.trades[-1].stop, price(side, 118))
                broker.process(bar(side, moment + 2 * STEP, 140.5, 161, 140, 160.5))
                trade = broker.trades[-1]
                self.assertEqual([(x.kind, x.quantity) for x in trade.ledger.exits],
                                 [(boundary_kind(side), D('8'))])
                self.assertEqual(trade.stop, D('128'))
                self.assertEqual(trade.stop_updates[-1].reason, 'RANGE_EQ_BREAK_EVEN')

    def test_without_an_eq_slice_eq_still_protects_the_entry(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side, eq_scale_out_fraction=None)
                events = broker.process(bar(side, moment + STEP, 130, 141, 129, 140.5))
                self.assertNotIn('RANGE_EQ_PARTIAL_EXIT', kinds(events))
                self.assertIn('BREAK_EVEN_PROTECTED', kinds(events))
                self.assertEqual(broker.trades[-1].stop, D('128'))

    def test_the_legacy_trigger_keeps_the_one_r_break_even(self):
        for side in SIDES:
            with self.subTest(side=side):
                broker, moment = open_trade(side, break_even_trigger='R_MULTIPLE',
                                            eq_scale_out_fraction=None,
                                            runner_fraction=D('0.10'))
                broker.process(bar(side, moment + STEP, 130, 138.5, 129, 138))
                trade = broker.trades[-1]
                self.assertEqual((trade.stop, trade.stop_updates[-1].reason),
                                 (D('128'), 'BREAK_EVEN'))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it and watch it fail**

Run: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_dd_management.py"`
Expected: ERROR `TypeError: EntryPlan.__init__() got an unexpected keyword argument 'range_eq'`.

- [ ] **Step 3: Extend the models** in `agent_trading/strategy_v1/models.py`.
  - `EntryPlan`: insert these two lines after `observed_at: datetime` and before `source_ids`:

```python
    # [U-DD-DEVIATION-001] the range EQ frozen with the plan, and the DD model
    # (CHOCH_FVG / HTF_FVG_REVERSAL) that produced it.
    range_eq: Decimal | None = None
    entry_model: str | None = None
```

  - `PositionLedger`: insert after `range_high_done: bool = False`:

```python
    range_eq_done: bool = False
```

  - `PositionExit`: extend the `kind` comment to read `# PARTIAL_TP | RANGE_EQ | RANGE_HIGH | RANGE_LOW | RUNNER | STOP`.

- [ ] **Step 4: Implement the broker step** in `agent_trading/strategy_v1/broker.py`.
  1. Add `from decimal import Decimal` if it is missing; it is already imported.
  2. In `_favorable`, keep the `has_upside_target` guard and replace the lines from `long_ = trade.direction == 'LONG'` through `events = []` with:

```python
        long_ = trade.direction == 'LONG'
        trade, first = self._range_eq(trade, candle)
        events = list(first)
        ledger = trade.ledger
```

     Update the docstring to `"""Range EQ scale-out, configured R partials in order, then the boundary exit."""`.

  3. Add after `_favorable`:

```python
    def _range_eq(self, trade, candle):
        """[U-DD-DEVIATION-001] Close `eq_scale_out_fraction` at the range EQ.

        Reaching EQ also arms the RANGE_EQ break-even, with or without a slice.
        [H]-DD-EQ-SKIP-001 An EQ that is not strictly between the entry and the
        boundary target is skipped; break-even then waits for the boundary.
        """
        plan, ledger = self.pending, trade.ledger
        eq = None if plan is None else plan.range_eq
        if eq is None or ledger.range_eq_done:
            return trade, ()
        long_ = trade.direction == 'LONG'
        if not (trade.entry < eq < trade.tp if long_ else trade.tp < eq < trade.entry):
            return trade, ()
        if candle.high < eq if long_ else candle.low > eq:
            return trade, ()
        trade = self._store(replace(trade, ledger=replace(ledger, range_eq_done=True)))
        fraction = self.profile.eq_scale_out_fraction
        quantity = (Decimal(0) if fraction is None
                    else floor_to_step(exact_product(ledger.original_quantity, fraction),
                                       self.profile.quantity_step))
        if quantity <= 0:
            return trade, ()
        price = candle.open if (candle.open > eq if long_ else candle.open < eq) else eq
        trade, record = self._realise(trade, 'RANGE_EQ', quantity, price, candle.close_time,
                                      target_price=eq)
        trade = self._store(trade)
        return trade, (BrokerEvent('RANGE_EQ_PARTIAL_EXIT', candle.close_time, record),)

    def _range_break_even(self, trade, candle):
        """[U-DD-DEVIATION-001] Entry protection once EQ, or the boundary when EQ
        was skipped, has traded. It replaces the inherited 1R rule."""
        ledger = trade.ledger
        if not (ledger.range_eq_done or ledger.range_high_done):
            return trade
        return self.risk.tighten_stop(trade, trade.entry, candle.close_time,
                                      'RANGE_EQ_BREAK_EVEN')
```

  4. In `_manage`, replace

```python
        managed = self.risk.manage(trade, candle)          # inherited 1R break-even
```

     with

```python
        managed = (self.risk.manage(trade, candle)        # inherited 1R break-even
                   if self.profile.break_even_trigger == 'R_MULTIPLE'
                   else self._range_break_even(trade, candle))
```

- [ ] **Step 5: Run the module, then the full suite**

Run: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_dd_management.py"`, then the full suite.
Expected: PASS. Legacy scenarios are untouched, because their plans carry `range_eq=None` and the default trigger is still `R_MULTIPLE`.

- [ ] **Step 6: Commit**

```bash
git add agent_trading/strategy_v1/models.py agent_trading/strategy_v1/broker.py tests/test_dd_management.py
git commit -m "feat: scale out at the range EQ and move break-even there"
```

---

### Task 3: Detect the entry-timeframe CHoCH and the gap it leaves

**Files:**
- Create: `agent_trading/strategy_v1/choch.py`
- Modify: `agent_trading/strategy_v1/entry.py` (add `FvgBook.choch_gap`)
- Create: `tests/test_dd_choch.py`

**Interfaces:**
- Produces:
  - `ChochConfirmation(direction, level, swing, extreme, extreme_at, candle, confirmed_at, source_ids)`.
  - `ChochTracker(window: int)` with `process(candle, manipulation, swing_highs, swing_lows, range_bar) -> ChochConfirmation | None`, plus the attributes `extreme`, `extreme_at` and `confirmed`.
  - `FvgBook.choch_gap(direction, profile, confirmation, now) -> TrackedFvg | None`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_dd_choch.py`:

```python
"""[U-DD-DEVIATION-001] DD model 1: the entry-timeframe CHoCH and the gap it leaves."""
import unittest
from dataclasses import replace
from decimal import Decimal as D

from agent_trading.market import bar_duration
from agent_trading.swing import ConfirmedSwing, SwingSide
from agent_trading.trading_brain.models import FVG, ManipulationEvent, SwingHigh, SwingLow
from agent_trading.strategy_v1.choch import ChochConfirmation, ChochTracker
from agent_trading.strategy_v1.entry import FvgBook

from strategy_v1_fixtures import ENTRY_START, SYMBOL, candle, scenario_profile

STEP, HOUR = bar_duration('15m'), bar_duration('1H')
AXIS = D('256')


def at(index):
    return ENTRY_START + index * STEP


def bar(index, open_, high, low, close):
    return candle('15m', at(index), open_, high, low, close)


def swing(side, price, index):
    raw = ConfirmedSwing(SYMBOL, '15m', side, D(str(price)), at(index), at(index + 1), 1,
                         D('1'), D('1'))
    return SwingHigh(raw) if side is SwingSide.HIGH else SwingLow(raw)


def swept(direction, index, extreme, phase='SWEPT'):
    """The range bar that swept closes together with entry bar `index`."""
    return ManipulationEvent(direction, phase, D(str(extreme)), at(index), at(index),
                             at(index + 4) if phase == 'RECLAIMED' else None)


def mirror(c):
    return replace(c, open=AXIS - c.open, high=AXIS - c.low, low=AXIS - c.high,
                   close=AXIS - c.close)


PRE = [bar(1, 127, 129, 126, 127), bar(2, 127, 129, 126, 128),
       bar(3, 128, 128, 125, 126), bar(4, 126, 126, 124, 125)]
IN_SWEEP_BAR = [bar(5, 125, 125, 120, 121), bar(6, 121, 121, 116, 117),
                bar(7, 117, 118, 113, 114)]
EXTREME = bar(8, 114, 115, 112, 113)
RISE = [bar(9, 113, 117, 112, 116), bar(10, 116, 121, 116, 120),
        bar(11, 120, 126, 120, 125)]
BREAK = bar(12, 125, 131, 125, 130)                  # closes above the 129 swing high
LEVEL = swing(SwingSide.HIGH, 129, 2)


def run(tracker, candles, manipulation, highs=(LEVEL,), lows=()):
    found = []
    for item in candles:
        result = tracker.process(item, manipulation, highs, lows, HOUR)
        if result is not None:
            found.append(result)
    return found


def primed():
    """The sweep's range bar is only known once it closes, with bar 8."""
    tracker = ChochTracker(4)
    run(tracker, PRE + IN_SWEEP_BAR, None)
    return tracker


class ChochTrackerTests(unittest.TestCase):
    def test_the_extreme_includes_bars_seen_before_the_sweep_was_known(self):
        tracker = primed()
        run(tracker, [EXTREME, RISE[0]], swept('LONG', 8, 112))
        self.assertEqual((tracker.extreme, tracker.extreme_at), (D('112'), at(8)))

    def test_a_body_close_above_the_last_swing_high_before_the_extreme_confirms(self):
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [BREAK], swept('LONG', 8, 112))
        self.assertEqual(len(found), 1)
        choch = found[0]
        self.assertIsInstance(choch, ChochConfirmation)
        self.assertEqual((choch.direction, choch.level, choch.extreme, choch.extreme_at,
                          choch.confirmed_at), ('LONG', D('129'), D('112'), at(8), at(12)))
        self.assertIs(choch.swing, LEVEL)
        self.assertEqual(choch.candle, BREAK)

    def test_a_wick_through_the_level_is_not_a_change_of_character(self):
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [bar(12, 125, 131, 125, 128.5)],
                    swept('LONG', 8, 112))
        self.assertEqual(found, [])

    def test_the_level_is_the_most_recent_swing_high_before_the_extreme(self):
        highs = (swing(SwingSide.HIGH, 135, 1), swing(SwingSide.HIGH, 129, 2),
                 swing(SwingSide.HIGH, 140, 10))
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [BREAK], swept('LONG', 8, 112), highs)
        self.assertEqual(found[0].level, D('129'))

    def test_no_swing_before_the_extreme_means_no_change_of_character(self):
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [BREAK], swept('LONG', 8, 112),
                    (swing(SwingSide.HIGH, 125, 10),))
        self.assertEqual(found, [])

    def test_a_new_extreme_while_still_swept_restarts_the_watch(self):
        tracker = primed()
        self.assertEqual(len(run(tracker, [EXTREME, bar(9, 113, 131, 113, 130)],
                                 swept('LONG', 8, 112))), 1)
        run(tracker, [bar(10, 130, 130, 108, 109)], swept('LONG', 8, 108))
        self.assertIsNone(tracker.confirmed)
        self.assertEqual((tracker.extreme, tracker.extreme_at), (D('108'), at(10)))

    def test_after_the_reclaim_the_extreme_is_frozen(self):
        tracker = primed()
        run(tracker, [EXTREME], swept('LONG', 8, 112))
        run(tracker, [bar(9, 113, 114, 111, 113)], swept('LONG', 8, 112, 'RECLAIMED'))
        self.assertEqual((tracker.extreme, tracker.extreme_at), (D('112'), at(8)))

    def test_a_lost_or_new_manipulation_resets_the_watch(self):
        tracker = primed()
        run(tracker, [EXTREME] + RISE + [BREAK], swept('LONG', 8, 112))
        run(tracker, [bar(13, 130, 131, 129, 130)], None)
        self.assertIsNone(tracker.confirmed)
        self.assertIsNone(tracker.extreme)
        run(tracker, [bar(14, 130, 131, 110, 111)], swept('LONG', 14, 110))
        self.assertEqual((tracker.extreme, tracker.extreme_at), (D('110'), at(14)))

    def test_a_confirmation_is_reported_once(self):
        tracker = primed()
        found = run(tracker, [EXTREME] + RISE + [BREAK, bar(13, 130, 133, 129, 132)],
                    swept('LONG', 8, 112))
        self.assertEqual(len(found), 1)

    def test_a_short_mirrors_it(self):
        tracker = ChochTracker(4)
        run(tracker, [mirror(c) for c in PRE + IN_SWEEP_BAR], None, lows=())
        found = run(tracker, [mirror(c) for c in [EXTREME] + RISE + [BREAK]],
                    swept('SHORT', 8, 144), highs=(), lows=(swing(SwingSide.LOW, 127, 2),))
        self.assertEqual((found[0].direction, found[0].level, found[0].extreme),
                         ('SHORT', D('127'), D('144')))


class ChochGapTests(unittest.TestCase):
    def setUp(self):
        self.book = FvgBook(True)
        self.profile = scenario_profile()
        self.choch = ChochConfirmation('LONG', D('129'), LEVEL, D('112'), at(8), BREAK, at(12))

    def gap(self, gap_id, lower, upper, first, direction='LONG', kind='FVG'):
        formed = (at(first), at(first + 1), at(first + 2))
        return self.book.publish(FVG(direction, D(str(lower)), D(str(upper)), formed,
                                     at(first + 2), kind=kind), gap_id)

    def test_the_gap_whose_candles_include_the_break_is_chosen(self):
        self.gap('before', 117, 122, 8)            # published at bar 10
        self.gap('left', 126, 130, 11)             # bars 11..13 include bar 12
        self.gap('later', 131, 133, 12)            # also includes it, published later
        self.assertEqual(self.book.choch_gap('LONG', self.profile, self.choch, at(14)).gap_id,
                         'left')

    def test_a_gap_not_yet_published_is_not_chosen(self):
        self.gap('left', 126, 130, 11)
        self.assertIsNone(self.book.choch_gap('LONG', self.profile, self.choch, at(12)))

    def test_a_touched_gap_gives_way_to_the_next_one(self):
        self.gap('left', 126, 130, 11)
        self.gap('later', 131, 133, 12)
        self.book.process(bar(15, 130.5, 130.5, 129.5, 130))
        self.assertEqual(self.book.choch_gap('LONG', self.profile, self.choch, at(15)).gap_id,
                         'later')

    def test_only_fresh_gaps_of_the_setup_side_and_kind_count(self):
        self.gap('short', 126, 130, 11, direction='SHORT')
        self.gap('inverse', 126, 130, 11, kind='iFVG')
        self.assertIsNone(self.book.choch_gap('LONG', self.profile, self.choch, at(14)))
        allowed = scenario_profile(allow_ifvg_entry=True)
        self.assertEqual(self.book.choch_gap('LONG', allowed, self.choch, at(14)).gap_id,
                         'inverse')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it and watch it fail**

Run: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_dd_choch.py"`
Expected: ERROR `ModuleNotFoundError: No module named 'agent_trading.strategy_v1.choch'`.

- [ ] **Step 3: Implement** — create `agent_trading/strategy_v1/choch.py`:

```python
"""DD deviation model 1: the entry-timeframe change of character [U-DD-DEVIATION-001].

After a range deviation the DD school waits for the entry timeframe to break,
with a body close, the last internal swing that carried price to the deviation
extreme. This module only watches for that break; it holds no order, price or
size logic.

[H]-DD-EXTREME-001 The extreme is the most extreme entry candle since the range
bar that swept (earliest on ties), followed until the sweep is reclaimed.
[H]-DD-CHOCH-001 The level is the most recent entry swing on the other side
that formed before that candle.
"""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..models import Candle
from ..trading_brain.models import SwingHigh, SwingLow

SOURCE_IDS = ('[U-DD-DEVIATION-001]', '[H]-DD-CHOCH-001')


@dataclass(frozen=True)
class ChochConfirmation:
    """Auditable evidence that the entry timeframe changed character."""
    direction: str
    level: Decimal
    swing: SwingHigh | SwingLow
    extreme: Decimal
    extreme_at: datetime
    candle: Candle
    confirmed_at: datetime
    source_ids: tuple[str, ...] = SOURCE_IDS


class ChochTracker:
    def __init__(self, window):
        if type(window) is not int or window < 1:
            raise ValueError('window must be a positive number of entry bars')
        self.recent = deque(maxlen=window)
        self._reset()

    def _reset(self):
        self.swept_at = self.direction = None
        self.extreme = self.extreme_at = None
        self.confirmed = None

    def _track(self, candle):
        """Follow the extreme; ties keep the earliest candle."""
        long_ = self.direction == 'LONG'
        price = candle.low if long_ else candle.high
        if self.extreme is None or (price < self.extreme if long_ else price > self.extreme):
            self.extreme, self.extreme_at = price, candle.close_time
            self.confirmed = None            # a new extreme needs a new break

    def process(self, candle, manipulation, swing_highs, swing_lows, range_bar):
        """Consume one closed entry candle; return a new confirmation or None."""
        if manipulation is None or manipulation.direction is None:
            self._reset()
            self.recent.append(candle)
            return None
        if (manipulation.swept_at != self.swept_at
                or manipulation.direction != self.direction):
            self._reset()
            self.swept_at, self.direction = manipulation.swept_at, manipulation.direction
            opened = manipulation.swept_at - range_bar
            for earlier in self.recent:
                if earlier.close_time > opened:
                    self._track(earlier)
        self.recent.append(candle)
        if (manipulation.phase == 'SWEPT'
                and candle.close_time > manipulation.swept_at - range_bar):
            self._track(candle)
        if (self.confirmed is not None or self.extreme_at is None
                or candle.close_time <= self.extreme_at):
            return None
        long_ = self.direction == 'LONG'
        level = None
        # Swings arrive in confirmation order, which is chronological.
        for swing in reversed(swing_highs if long_ else swing_lows):
            if swing.swing_time < self.extreme_at and swing.confirmed_at <= candle.close_time:
                level = swing
                break
        if level is None:
            return None
        if not (candle.close > level.price if long_ else candle.close < level.price):
            return None
        self.confirmed = ChochConfirmation(self.direction, level.price, level, self.extreme,
                                           self.extreme_at, candle, candle.close_time)
        return self.confirmed
```

Then add to `FvgBook` in `agent_trading/strategy_v1/entry.py`, after `eligible_long`:

```python
    def choch_gap(self, direction, profile, confirmation, now):
        """[H]-DD-CHOCH-001 The gap the break left: its three candles include the
        CHoCH bar. The first one published wins; it must still be fresh."""
        kinds = self._kinds(profile)
        found = None
        for item in reversed(self.tracked):          # publication order, newest first
            if item.observed_at < confirmation.confirmed_at:
                break
            if (item.direction != direction or item.gap.kind not in kinds
                    or item.observed_at > now):
                continue
            if profile.fvg_freshness_enabled and not item.fresh:
                continue
            if item.formed_at <= confirmation.confirmed_at:
                found = item
        return found
```

- [ ] **Step 4: Run the module, then the full suite**

Run: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_dd_choch.py"`, then the full suite.
Expected: PASS. Nothing calls the tracker yet.

- [ ] **Step 5: Commit**

```bash
git add agent_trading/strategy_v1/choch.py agent_trading/strategy_v1/entry.py tests/test_dd_choch.py
git commit -m "feat: detect the entry-timeframe CHoCH and the gap it leaves"
```

---

### Task 4: Take DD model 1 and model 2 entries, first ready wins (strategy)

**Files:**
- Modify: `agent_trading/strategy_v1/strategy.py`:
  - `__init__`: add the tracker and its state.
  - `_entry`: run the CHoCH watch and consider after each bar.
  - `_consider`: rewrite it as a loop over the models.
  - New methods `_choch_gap`, `_reversal_gap` and `_enter`.
- Modify: `agent_trading/paper_session.py` (`SESSION_FORMAT = 2`)
- Create: `tests/dd_fixtures.py`, `tests/test_dd_entry.py`
- Modify: `tests/test_paper_session.py` (one test)

**Interfaces:**
- Consumes:
  - `ChochTracker` and `FvgBook.choch_gap` (Task 3).
  - `EntryPlan.range_eq` and `entry_model` (Task 2).
  - `ENTRY_MODELS` and `effective_model2_requires_htf_fvg` (Task 1).
- Produces:
  - Event `CHOCH_CONFIRMED` (payload `ChochConfirmation`).
  - `ENTRY_PLAN` and `PENDING_ENTRY` payloads carry `entry_model` and `range_eq`.
  - `tests/dd_fixtures.py` exposes `DD`, `dd_profile()`, `fvg_bias_candles()`, `late_choch_entry_candles()`, `model_one_long_candles()`, `model_two_long_candles()`, `both_ready_long_candles()`, `model_one_short_candles()` and `run_dd()`.

- [ ] **Step 1: Write the fixtures** — create `tests/dd_fixtures.py`:

```python
"""Scenarios for the DD deviation entry models [U-DD-DEVIATION-001].

They reuse the wider acceptance range (118 .. 170, EQ 144) under the guide gate.

- **Model 1 long.** The 4H context only offers the Valid Low band at the sweep,
  so model 2 is unavailable. The trade comes from the 15m CHoCH: the 15:30 close
  of 130.5 breaks the 129 swing high, and the entry is the 126..130 gap that
  break left.
- **Model 2 long.** An older 4H FVG at 110..117, never filled, sits under the
  range. A 134 spike before the sweep delays the CHoCH to 16:45, so model 2's
  15:45 gap is ready first.
- **Short.** The shipped mirrored acceptance scenario.
"""
from dataclasses import replace
from datetime import timedelta

from agent_trading.strategy_v1 import StrategyV1
from agent_trading.strategy_v1.config import ENTRY_MODELS
from guide_fixtures import guide_bias_candles, guide_profile, short_acceptance_candles
from strategy_v1_fixtures import (D, SYMBOL, BIAS_START, _flat, acceptance_entry_candles,
                                  acceptance_range_candles, bars)

DD = dict(entry_models=ENTRY_MODELS, model2_requires_htf_fvg=None,
          secondary_fvg_support_enabled=False, eq_scale_out_fraction=D('0.30'),
          break_even_trigger='RANGE_EQ', runner_fraction=D('0.20'), partial_take_profits=())


def dd_profile(**overrides):
    """The guide gate with every DD knob explicit, whatever the defaults are."""
    settings = dict(DD)
    settings.update(overrides)
    return guide_profile(**settings)


def fvg_bias_candles():
    """guide_bias_candles() preceded by a 4H FVG at 110..117 that is never filled.

    The dealing range stays 120 .. 200.
    """
    rows = (_flat(4, D('100')) + [(100, 110, 98, 108), (108, 140, 108, 138),
                                  (138, 152, 117, 150)] + _flat(8, D('150')))
    start = BIAS_START - timedelta(hours=4 * len(rows))
    return bars('4H', start, rows) + guide_bias_candles()


def late_choch_entry_candles():
    """A 134 spike at 11:45 makes 134 the swing high before the sweep."""
    candles = list(acceptance_entry_candles())
    candles[14] = replace(candles[14], high=D('134'))
    return candles


def model_one_long_candles():
    return guide_bias_candles() + acceptance_range_candles() + acceptance_entry_candles()


def model_two_long_candles():
    return fvg_bias_candles() + acceptance_range_candles() + late_choch_entry_candles()


def both_ready_long_candles():
    return fvg_bias_candles() + acceptance_range_candles() + acceptance_entry_candles()


def model_one_short_candles():
    return short_acceptance_candles()


def run_dd(candles, **overrides):
    strategy = StrategyV1(SYMBOL, dd_profile(**overrides))
    strategy.feed(candles)
    return strategy
```

- [ ] **Step 2: Write the failing tests** — create `tests/test_dd_entry.py`:

```python
"""[U-DD-DEVIATION-001] DD model 1 (CHoCH) and model 2 (HTF FVG), end to end."""
import unittest

from dd_fixtures import (DD, both_ready_long_candles, model_one_long_candles,
                         model_one_short_candles, model_two_long_candles, run_dd)
from strategy_v1_fixtures import (D, SYMBOL, acceptance_candles, events_of, first_event,
                                  run_scenario, scenario_profile)


class ModelOneLongTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strategy = run_dd(model_one_long_candles())
        cls.trade = cls.strategy.broker.trades[0]

    def test_the_choch_breaks_the_last_swing_high_before_the_sweep(self):
        choch = first_event(self.strategy, 'CHOCH_CONFIRMED').payload
        self.assertEqual((choch.direction, choch.level, choch.extreme),
                         ('LONG', D('129'), D('112')))
        self.assertEqual((choch.extreme_at.strftime('%H:%M'),
                          choch.confirmed_at.strftime('%H:%M')), ('13:00', '15:30'))

    def test_one_model_one_trade_enters_at_the_gap_the_break_left(self):
        self.assertEqual(len(self.strategy.broker.trades), 1)
        pending = first_event(self.strategy, 'PENDING_ENTRY')
        self.assertEqual(pending.observed_at.strftime('%H:%M'), '15:45')
        plan = pending.payload
        self.assertEqual(plan.entry_model, 'CHOCH_FVG')
        self.assertEqual((plan.primary.lower, plan.primary.upper, plan.range_eq),
                         (D('126'), D('130'), D('144')))
        self.assertEqual(self.trade.entry, D('128'))

    def test_the_stop_sits_behind_the_deviation_wick(self):
        self.assertEqual(self.trade.approved_plan.stop, D('111'))
        self.assertEqual(first_event(self.strategy, 'ENTRY_PLAN').payload.stop_source,
                         'MANIPULATION_SWEEP_LOW')

    def test_thirty_percent_at_eq_fifty_at_the_boundary_and_the_runner_trails_out(self):
        self.assertEqual([(x.kind, x.exit_price, x.quantity) for x in self.trade.ledger.exits],
                         [('RANGE_EQ', D('144'), D('1.76470588')),
                          ('RANGE_HIGH', D('170'), D('2.94117648')),
                          ('RUNNER', D('160'), D('1.17647058'))])

    def test_break_even_comes_from_eq_then_the_stop_trails_the_trades_own_lows(self):
        self.assertEqual([(u.reason, u.new_stop) for u in self.trade.stop_updates],
                         [('RANGE_EQ_BREAK_EVEN', D('128')), ('STRUCTURAL_TRAIL', D('130.5')),
                          ('STRUCTURAL_TRAIL', D('140')), ('STRUCTURAL_TRAIL', D('160'))])

    def test_the_trade_closes_in_profit(self):
        self.assertEqual(self.trade.status, 'CLOSED')
        self.assertEqual(self.strategy.broker.equity, D('10189.4117648'))


class ModelOneShortTests(unittest.TestCase):
    def test_a_model_one_short_mirrors_the_long(self):
        strategy = run_dd(model_one_short_candles())
        trade = strategy.broker.trades[0]
        self.assertEqual(first_event(strategy, 'PENDING_ENTRY').payload.entry_model, 'CHOCH_FVG')
        self.assertEqual((trade.direction, trade.entry, trade.approved_plan.stop),
                         ('SHORT', D('160'), D('177')))
        self.assertEqual([(x.kind, x.exit_price, x.quantity) for x in trade.ledger.exits],
                         [('RANGE_EQ', D('144'), D('1.76470588')),
                          ('RANGE_LOW', D('118'), D('2.94117648')),
                          ('RUNNER', D('128'), D('1.17647058'))])
        self.assertEqual(strategy.broker.equity, D('10189.4117648'))


class ModelTwoTests(unittest.TestCase):
    def test_without_an_htf_fvg_model_two_takes_nothing(self):
        strategy = run_dd(model_one_long_candles(), entry_models=('HTF_FVG_REVERSAL',))
        verdict = first_event(strategy, 'HTF_CONTEXT').payload
        self.assertTrue(verdict.allowed)
        self.assertNotIn('HTF_FVG', [zone.kind for zone in verdict.zones])
        self.assertEqual(events_of(strategy, 'PENDING_ENTRY'), ())

    def test_a_sweep_into_an_htf_fvg_trades_the_first_reversal_gap(self):
        strategy = run_dd(model_two_long_candles())
        verdict = first_event(strategy, 'HTF_CONTEXT').payload
        self.assertIn('HTF_FVG', [zone.kind for zone in verdict.zones])
        pending = first_event(strategy, 'PENDING_ENTRY')
        self.assertEqual((pending.payload.entry_model, pending.observed_at.strftime('%H:%M')),
                         ('HTF_FVG_REVERSAL', '15:45'))
        self.assertGreater(first_event(strategy, 'CHOCH_CONFIRMED').observed_at,
                           pending.observed_at)
        trade = strategy.broker.trades[0]
        self.assertEqual((trade.entry, trade.approved_plan.stop), (D('128'), D('111')))

    def test_when_both_are_ready_on_one_bar_model_one_is_tried_first(self):
        strategy = run_dd(both_ready_long_candles())
        self.assertEqual([e.payload.entry_model for e in events_of(strategy, 'PENDING_ENTRY')],
                         ['CHOCH_FVG'])

    def test_the_old_gate_keeps_the_pre_dd_entry(self):
        profile = scenario_profile(**dict(DD, entry_models=('HTF_FVG_REVERSAL',)))
        strategy = run_scenario(profile=profile, candles=acceptance_candles())
        self.assertFalse(profile.effective_model2_requires_htf_fvg)
        self.assertEqual(first_event(strategy, 'PENDING_ENTRY').payload.entry_model,
                         'HTF_FVG_REVERSAL')

    def test_model_one_alone_ignores_the_reversal_gap(self):
        strategy = run_dd(model_two_long_candles(), entry_models=('CHOCH_FVG',))
        pending = first_event(strategy, 'PENDING_ENTRY')
        self.assertEqual((pending.payload.entry_model, pending.observed_at.strftime('%H:%M')),
                         ('CHOCH_FVG', '16:45'))


if __name__ == '__main__':
    unittest.main()
```

Add to `tests/test_paper_session.py` (with `import pickle` at the top if missing):

```python
    def test_a_session_from_before_the_dd_entry_models_is_not_resumed(self):
        # SESSION_FORMAT 2 [U-DD-DEVIATION-001]: format-1 brains lack the CHoCH state.
        profile = StrategyProfile()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper_session.pickle"
            with path.open("wb") as handle:
                pickle.dump({"format": 1, "symbol": "BTC-USDT", "profile": profile,
                             "brain": object(), "stream_as_of": {}}, handle)
            self.assertIsNone(PaperSessionStore(path).load("BTC-USDT", profile))
```

- [ ] **Step 3: Run them and watch them fail**

Run:
- `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_dd_entry.py"`
- `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_paper_session.py"`

Expected:
- `test_dd_entry` FAILs: there is no `CHOCH_CONFIRMED` event, and `entry_model` is `None`.
- The session test FAILs: a format-1 brain is resumed.

- [ ] **Step 4: Implement the strategy wiring** in `agent_trading/strategy_v1/strategy.py`.

1. Imports: add `from .choch import ChochTracker`, and change the config import to `from .config import ENTRY_MODELS, StrategyProfile`.
2. In `__init__`, after `self.book = FvgBook(...)`:

```python
        # [U-DD-DEVIATION-001] DD model 1 watches the entry timeframe for a CHoCH.
        self.choch = ChochTracker(bar_duration(roles.range) // bar_duration(roles.entry))
        self._choch_id = None
        self._tried_gaps = set()          # one entry attempt per gap, whatever the model
```

3. In `_entry`, replace the final gap loop

```python
        for gap in self.gaps.process(candle):
            gap_id = self._emit(gap.kind, candle.timeframe, gap)
            self.book.publish(gap, gap_id)
            self._consider(candle, gap_id)
```

   with

```python
        if 'CHOCH_FVG' in self.profile.entry_models:
            confirmation = self.choch.process(candle, self.manipulation.active,
                                              self.entry_swing_highs, self.entry_swing_lows,
                                              bar_duration(self.roles.range))
            if confirmation is not None:
                self._choch_id = self._emit('CHOCH_CONFIRMED', candle.timeframe, confirmation,
                                            (self._sweep_id,), sources=confirmation.source_ids)
        for gap in self.gaps.process(candle):
            gap_id = self._emit(gap.kind, candle.timeframe, gap)
            self.book.publish(gap, gap_id)
            self._consider(candle, (gap_id,))
        self._consider(candle)            # model 1 can be ready on a bar with no new gap
```

4. Replace the whole `_consider` method with:

```python
    def _consider(self, candle, published=()):
        """[U-DD-DEVIATION-001] Try each enabled entry model, DD model 1 first.

        The first model whose plan the RiskEngine approves takes the trade.
        """
        direction = self.active_setup()
        if self._setup_consumed or direction is None:
            return
        if (self.broker.pending_plan is not None
                or any(t.status == 'OPEN' for t in self.broker.trades)):
            return
        for model in ENTRY_MODELS:
            if model not in self.profile.entry_models:
                continue
            primary = (self._choch_gap(direction, candle) if model == 'CHOCH_FVG'
                       else self._reversal_gap(direction, candle, published))
            if primary is not None and self._enter(model, direction, primary, candle):
                return

    def _choch_gap(self, direction, candle):
        """DD model 1: the fresh gap the CHoCH left [H]-DD-CHOCH-001."""
        confirmation = self.choch.confirmed
        if confirmation is None or confirmation.direction != direction:
            return None
        gap = self.book.choch_gap(direction, self.profile, confirmation, candle.close_time)
        return None if gap is None or gap.gap_id in self._tried_gaps else gap

    def _reversal_gap(self, direction, candle, published):
        """DD model 2: the first reversal gap after the reclaim [H]-DD-MODEL2-001.

        Under the guide gate the deviation must have touched an HTF FVG; the
        superseded gate has no HTF zones and keeps the pre-DD entry.
        """
        if not published:
            return None
        if (self.profile.effective_model2_requires_htf_fvg
                and not any(zone.kind == 'HTF_FVG' for zone in self.htf_verdict.zones)):
            return None
        eligible = self.book.eligible(direction, self.profile, self.manipulation.active,
                                      candle.close_time)
        for gap_id in published:
            if gap_id in self._tried_gaps:
                continue
            primary = next((g for g in eligible if g.gap_id == gap_id), None)
            if primary is not None:
                return primary
        return None

    def _enter(self, model, direction, primary, candle):
        """Plan, risk-check and submit one entry; True once an order rests."""
        self._tried_gaps.add(primary.gap_id)
        long_ = direction == 'LONG'
        manipulation, state = self.manipulation.active, self.range.state
        gap_id = primary.gap_id
        price = entry_price(primary.gap, self.profile.entry_level, self.profile.entry_level_ratio)
        # The terminal target is the opposite boundary, never EQ.
        target = state.range_high if long_ else state.range_low
        secondary = self.book.secondary_beyond(direction, self.profile, primary, manipulation,
                                               candle.close_time)
        protecting = zones = None
        sweep_source = 'MANIPULATION_SWEEP_LOW' if long_ else 'MANIPULATION_SWEEP_HIGH'
        stop_source = sweep_source
        if secondary is not None:
            protecting = protecting_swing(direction,
                                          self.entry_swing_lows if long_
                                          else self.entry_swing_highs,
                                          secondary.lower if long_ else secondary.upper,
                                          candle.close_time)
            if protecting is not None:
                stop_source = 'SECONDARY_FVG_PROTECTING_SWING'
                zones = (SupportingZone(secondary.gap_id, secondary.gap.kind, direction,
                                        secondary.lower, secondary.upper, protecting.price,
                                        secondary.observed_at, self.symbol, self.roles.entry,
                                        source_ids=secondary.gap.source_ids
                                        + ('[H]-SV1-STOP-001',)),)
        plan = EntryPlan(primary, self.profile.entry_level, price, target, stop_source,
                         secondary if stop_source != sweep_source else None,
                         protecting, protecting.price if protecting is not None else None,
                         candle.close_time, range_eq=state.eq, entry_model=model)
        structural = protecting.price if protecting is not None else manipulation.extreme
        refs = (self._range_id, self._reclaim_id, gap_id)
        if model == 'CHOCH_FVG' and self._choch_id is not None:
            refs = (self._range_id, self._reclaim_id, self._choch_id, gap_id)
        candidate = TradeCandidate(direction, price, structural, target, candle.close_time,
                                   refs, sweep_extreme=manipulation.extreme)
        candidate_id = self._emit('TRADE_CANDIDATE', candle.timeframe, candidate, refs)
        self._emit('ENTRY_PLAN', candle.timeframe, plan, (candidate_id, gap_id))
        decision = self.risk.evaluate(candidate, self.broker.equity, zones or (),
                                      symbol=self.symbol, timeframe=self.roles.entry)
        self._emit('RISK_APPROVED' if decision.plan is not None else 'BLOCKED',
                   candle.timeframe, decision, (candidate_id,))
        if decision.plan is None:
            return False
        self.entry_plan = plan
        self.broker.submit(decision.plan, plan)
        self._setup_consumed = True
        self._emit('PENDING_ENTRY', candle.timeframe, plan, (candidate_id,))
        return True
```

   This is the old `_consider` body with four changes:
   - the plan carries `range_eq` and `entry_model`;
   - a model 1 candidate also references its `CHOCH_CONFIRMED` event, while model 2 refs stay exactly as before;
   - it returns `False` on a risk block;
   - it returns `True` once the order rests.

5. In `agent_trading/paper_session.py`, set `SESSION_FORMAT = 2` with the comment `# 2: StrategyV1 gained DD entry state [U-DD-DEVIATION-001]`.

- [ ] **Step 5: Run the modules, then the full suite**

Run `test_dd_entry.py`, `test_paper_session.py`, then the full suite.
Expected: PASS.
- The legacy scenarios produce identical trades. Their `ENTRY_PLAN`/`PENDING_ENTRY` payloads now also carry `range_eq`/`entry_model`.
- If a legacy expectation fails, stop and compare events. Model 1 is off by default, so no legacy decision may change.

- [ ] **Step 6: Commit**

```bash
git add agent_trading/strategy_v1/strategy.py agent_trading/paper_session.py tests/dd_fixtures.py tests/test_dd_entry.py tests/test_paper_session.py
git commit -m "feat: take DD model 1 and model 2 entries, first ready wins"
```

---

### Task 5: Record and report each trade's entry model

**Files:**
- Modify: `agent_trading/backtest/recorder.py`:
  - `BREAK_EVEN_REASONS` and `EXIT_REASONS`;
  - `TradeRecord.entry_model` and `as_dict`;
  - `record_trades`: `entry_model` and `partial_count`.
- Modify: `agent_trading/backtest/report.py` (`TRADE_COLUMNS`)
- Modify: `agent_trading/backtest/metrics.py` (`SETUP_EVENTS`)
- Modify: `agent_trading/backtest/sweep.py` (`pooled` gains `by_entry_model`)
- Modify: `agent_trading/bot_service.py` (the notification kinds)
- Create: `tests/test_dd_reporting.py`

**Interfaces:**
- Consumes: the `PENDING_ENTRY` payload's `entry_model` (Task 4), and the `RANGE_EQ` slices and `RANGE_EQ_BREAK_EVEN` reason (Task 2).
- Produces:
  - `TradeRecord.entry_model: str | None = None`, as the last field.
  - The CSV column `entry_model`.
  - Funnel keys `choch_confirmations` and `range_eq_exits`.
  - `pooled()['by_entry_model']`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_dd_reporting.py`:

```python
"""[U-DD-DEVIATION-001] The entry model and the DD exits reach every report."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from agent_trading.backtest import report, sweep
from agent_trading.backtest.config import BacktestConfig
from agent_trading.backtest.engine import run
from agent_trading.bot_service import BotService
from agent_trading.config import Config
from agent_trading.strategy_v1 import StrategyV1

from dd_fixtures import dd_profile, model_one_long_candles, model_one_short_candles
from strategy_v1_fixtures import D, SYMBOL, events_of
from test_backtest import dump
from test_sweep import GRID, relabel

DD_FLAGS = ('--entry-models', 'CHOCH_FVG,HTF_FVG_REVERSAL', '--model2-htf-fvg', 'auto',
            '--eq-scale-out', '0.30', '--break-even-trigger', 'RANGE_EQ',
            '--runner-fraction', '0.20', '--no-secondary-fvg')


class DdRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.result = run(BacktestConfig(SYMBOL, dump(model_one_long_candles(), root / 'data'),
                                        D('10000'), profile=dd_profile()))
        cls.record = cls.result.trades[0]
        cls.out = root / 'out'
        report.write(cls.result, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_trade_record_names_its_entry_model(self):
        self.assertEqual(self.record.entry_model, 'CHOCH_FVG')
        self.assertEqual(self.record.as_dict()['entry_model'], 'CHOCH_FVG')

    def test_the_eq_slice_and_eq_break_even_are_counted(self):
        self.assertTrue(self.record.break_even_reached)
        self.assertEqual(self.record.partial_count, 1)
        self.assertEqual([s.kind for s in self.record.slices], ['RANGE_EQ', 'RANGE_HIGH', 'RUNNER'])
        self.assertEqual(self.record.exit_reason, 'RUNNER_STOP')

    def test_the_funnel_counts_chochs_and_eq_exits(self):
        funnel = self.result.summary_document()['funnel']
        self.assertEqual(funnel['choch_confirmations'],
                         len(events_of(self.result.strategy, 'CHOCH_CONFIRMED')))
        self.assertGreaterEqual(funnel['choch_confirmations'], 1)
        self.assertEqual(funnel['range_eq_exits'], 1)

    def test_trades_csv_carries_the_entry_model(self):
        with (self.out / 'trades.csv').open(encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]['entry_model'], 'CHOCH_FVG')


class DdSweepTests(unittest.TestCase):
    def test_the_sweep_pools_trades_by_entry_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root, out = Path(directory) / 'data', Path(directory) / 'out'
            dump(relabel(model_one_long_candles(), 'AAA-USDT'), root / 'AAA', 'AAA-USDT')
            dump(relabel(model_one_short_candles(), 'BBB-USDT'), root / 'BBB', 'BBB-USDT')
            self.assertEqual(sweep.main(['--data', str(root), '--output', str(out),
                                         *GRID, *DD_FLAGS]), 0)
            pooled = json.loads((out / 'sweep_summary.json').read_text('utf-8'))['pooled']
            self.assertEqual(pooled['by_entry_model']['CHOCH_FVG']['trades'], 2)
            self.assertEqual(pooled['by_entry_model']['HTF_FVG_REVERSAL']['trades'], 0)
            with (out / 'sweep_trades.csv').open(encoding='utf-8', newline='') as handle:
                self.assertEqual({row['entry_model'] for row in csv.DictReader(handle)},
                                 {'CHOCH_FVG'})


class DdNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_panel_hears_about_the_choch_and_the_eq_exit(self):
        bot = BotService(Config())
        bot.brain = StrategyV1(SYMBOL, dd_profile())
        bot.brain.feed(model_one_long_candles())
        bot._check_notifications()
        titles = [event['title'] for event in bot.ui_events]
        self.assertIn('CHOCH_CONFIRMED', titles)
        self.assertIn('RANGE_EQ_PARTIAL_EXIT', titles)


if __name__ == '__main__':
    unittest.main()
```

(`dump` in `tests/test_backtest.py` creates the folder and returns it; `ShortAccountingTests` uses it the same way.)

- [ ] **Step 2: Run it and watch it fail**

Run: `./.venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_dd_reporting.py"`
Expected: FAIL/ERROR (`AttributeError: 'TradeRecord' object has no attribute 'entry_model'`, missing funnel keys, missing `by_entry_model`, missing UI events).

- [ ] **Step 3: Implement.**

1. **`recorder.py`.**
   - Set `BREAK_EVEN_REASONS = ('BREAK_EVEN', 'RECOVERY_BREAK_EVEN', 'RANGE_EQ_BREAK_EVEN')`.
   - Add `'RANGE_EQ': 'RANGE_EQ', 'RANGE_LOW': 'RANGE_LOW'` to `EXIT_REASONS`.
   - Add `entry_model: str | None = None` as the last `TradeRecord` field, and `'entry_model': self.entry_model` in `as_dict` after `'direction'`.
   - In `record_trades`, before the loop:

```python
    # [U-DD-DEVIATION-001] One order rests at a time, so the plan that became a
    # trade is the PENDING_ENTRY emitted on its candidate's own bar.
    plans = {event.observed_at: event.payload for event in strategy.events
             if event.kind == 'PENDING_ENTRY'}
```

   - Pass these to `TradeRecord(...)`:

```python
            partial_count=len(ledger.partial_exits) + len(ledger.of_kind('RANGE_EQ')),
            entry_model=getattr(plans.get(trade.candidate.observed_at), 'entry_model', None),
```

     `partial_count` replaces the existing argument.

2. **`report.py`.** In `TRADE_COLUMNS`, insert `'entry_model'` right after `'direction'`.

3. **`metrics.py`.** Add to `SETUP_EVENTS`: `'choch_confirmations': 'CHOCH_CONFIRMED'` and `'range_eq_exits': 'RANGE_EQ_PARTIAL_EXIT'`.

4. **`sweep.py`.** Import `from ..strategy_v1.config import ENTRY_MODELS`. In `pooled`, after the `by_direction` loop, add:

```python
    by_entry_model = {}
    for model in ENTRY_MODELS:
        mine = [record for record in closed if record.entry_model == model]
        by_entry_model[model] = {
            'trades': sum(1 for record in records if record.entry_model == model),
            'wins': sum(1 for record in mine if record.net_pnl > 0),
            'total_r': plain(_total(record.r_multiple for record in mine
                                    if record.r_multiple is not None))}
```

   and `'by_entry_model': by_entry_model` in the returned dict.

5. **`bot_service.py`.** Add `"CHOCH_CONFIRMED", "RANGE_EQ_PARTIAL_EXIT",` to the notification kinds tuple in `_check_notifications`.

- [ ] **Step 4: Run the module, then the full suite** (the forbidden-strings test must stay green)

Run the `test_dd_reporting.py` module, then the full suite. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_trading/backtest/recorder.py agent_trading/backtest/report.py agent_trading/backtest/metrics.py agent_trading/backtest/sweep.py agent_trading/bot_service.py tests/test_dd_reporting.py
git commit -m "feat: record and report each trade's entry model"
```

---

### Task 6: Make the DD models the default

**Files:**
- Modify: `agent_trading/strategy_v1/config.py` (six defaults).
- Modify: `agent_trading/backtest/cli.py` (five defaults: `--secondary-fvg`, `--entry-models`, `--model2-htf-fvg`, `--eq-scale-out`, `--break-even-trigger`; plus `--runner-fraction` `'0.10'` → `'0.20'`).
- Modify: `tests/strategy_v1_fixtures.py` (`LEGACY` in `scenario_profile`), `tests/guide_fixtures.py` (`LEGACY` in `guide_profile`).
- Modify: `tests/test_sweep.py` (`GRID` gains the legacy flags; the direct comparison gets `**LEGACY`).
- Modify: `tests/test_backtest.py` (the CLI test gets the legacy flags).
- Modify: the default assertions in `tests/test_strategy_v1.py` (secondary default) and `tests/test_strategy_v1_partials.py` (runner default).
- Local, gitignored: `config/strategy.json` (the panel's stored settings).

**Interfaces:**
- Produces: `strategy_v1_fixtures.LEGACY`, a dict of the six legacy knobs used by every shipped scenario.

- [ ] **Step 1: Write the failing test** — add to `tests/test_dd_config.py`:

```python
class DdDefaultTests(unittest.TestCase):
    def test_the_dd_models_are_the_default(self):
        profile = StrategyProfile()
        self.assertEqual(profile.entry_models, ENTRY_MODELS)
        self.assertIsNone(profile.model2_requires_htf_fvg)
        self.assertTrue(profile.effective_model2_requires_htf_fvg)
        self.assertEqual(profile.eq_scale_out_fraction, D('0.30'))
        self.assertEqual(profile.break_even_trigger, 'RANGE_EQ')
        self.assertFalse(profile.secondary_fvg_support_enabled)
        self.assertEqual(profile.runner_fraction, D('0.20'))
```

- [ ] **Step 2: Run it and watch it fail** (`test_dd_config.py`). Expected: FAIL on `entry_models`.

- [ ] **Step 3: Flip the defaults.**
  - `config.py`: `entry_models: tuple = ENTRY_MODELS`, `model2_requires_htf_fvg: bool | None = None`, `eq_scale_out_fraction: Decimal | None = Decimal('0.30')`, `break_even_trigger: str = 'RANGE_EQ'`, `secondary_fvg_support_enabled: bool = False`, `runner_fraction: Decimal = Decimal('0.20')`. Tag the changed comments `[U-DD-DEVIATION-001]`.
  - `cli.py` defaults: `--secondary-fvg` `False`, `--entry-models` `'CHOCH_FVG,HTF_FVG_REVERSAL'`, `--model2-htf-fvg` `'auto'`, `--eq-scale-out` `'0.30'`, `--break-even-trigger` `'RANGE_EQ'`, `--runner-fraction` `'0.20'`.

- [ ] **Step 4: Pin the shipped scenarios to the legacy knobs.**
  - In `tests/strategy_v1_fixtures.py`, above `scenario_profile`:

```python
# [U-DD-DEVIATION-001] The shipped scenarios were built for the pre-DD entry and
# exits and keep covering them; DD scenarios live in dd_fixtures.py.
LEGACY = dict(entry_models=('HTF_FVG_REVERSAL',), model2_requires_htf_fvg=False,
              secondary_fvg_support_enabled=True, eq_scale_out_fraction=None,
              break_even_trigger='R_MULTIPLE', runner_fraction=D('0.10'))
```

    Then add `**LEGACY` to the `settings = dict(...)` in `scenario_profile`, before `settings.update(overrides)`.
  - In `tests/guide_fixtures.py`, import `LEGACY` and add `**LEGACY` to `guide_profile`'s `settings = dict(...)`.
  - `dd_profile` still passes every DD knob explicitly, so DD tests are unaffected.

- [ ] **Step 5: Update the tests that assert the old defaults.** These are deliberate changes; each one gets a `# [U-DD-DEVIATION-001]` comment.
  - `tests/test_strategy_v1.py`, `CustomizationTests`: `assertTrue(profile.secondary_fvg_support_enabled)` → `assertFalse(...)`.
  - `tests/test_strategy_v1_partials.py`, the default-profile test: `runner_fraction == D('0.10')` → `D('0.20')`.
  - `tests/test_backtest.py`, `CliTests.test_the_cli_runs_a_whole_backtest_and_writes_artifacts`: append the legacy flags `'--entry-models', 'HTF_FVG_REVERSAL', '--model2-htf-fvg', 'false', '--eq-scale-out', 'none', '--break-even-trigger', 'R_MULTIPLE', '--secondary-fvg'`. Ending equity stays `'10302'`.
  - `tests/test_sweep.py`:
    - extend the import to `from strategy_v1_fixtures import LEGACY, entry_candles`;
    - add `LEGACY_FLAGS = ('--entry-models', 'HTF_FVG_REVERSAL', '--model2-htf-fvg', 'false', '--eq-scale-out', 'none', '--break-even-trigger', 'R_MULTIPLE', '--secondary-fvg', '--runner-fraction', '0.10')`;
    - set `GRID = ('--scale', 'none', '--boundary-proximity', '5', '--stop-buffer', '1') + LEGACY_FLAGS`;
    - in `test_the_sweep_matches_a_single_backtest_of_the_same_dataset`, build the direct profile as `StrategyProfile(boundary_proximity=D('5'), stop_buffer=D('1'), **LEGACY)`.
  - `tests/test_dd_reporting.py` imports `GRID`, which now ends with the legacy flags. Its `DD_FLAGS` come after them, and argparse keeps the last value, so the DD sweep test stays DD.

- [ ] **Step 6: Run the full suite and read every failure.**
  - Expected: PASS once the list above is applied.
  - Any other failure means one of two things:
    - a scenario that still runs on defaults and needs `LEGACY`; pin it and note it in the commit;
    - or a real behaviour change; stop and investigate.
  - In particular, check `tests/test_strategy_settings_api.py`. Settings with partials above 0.5 now exceed the non-runner allocation because of the 0.30 EQ slice.

- [ ] **Step 7: Align the panel's stored settings** (local, gitignored `config/strategy.json`).
  - The file holds `secondaryFvgSupport: true` and `runnerPct: "10.00"`, which would override the DD stop and runner for the local PAPER agent.
  - With an EOL-preserving script, set `entry.secondaryFvgSupport` to `false` and `exits.runnerPct` to `"20.00"`.
  - Validate: `./.venv/Scripts/python.exe -B -c "from agent_trading.strategy_settings import StrategyStore; print(StrategyStore('config/strategy.json').current.to_profile().runner_fraction)"`. Expected: `0.2000`.
  - Report this change to the owner; it can be reverted from the panel.

- [ ] **Step 8: Commit** (only the tracked files; `config/strategy.json` is ignored)

```bash
git add agent_trading/strategy_v1/config.py agent_trading/backtest/cli.py tests/
git commit -m "feat: make the DD deviation models the default"
```

---

### Task 7: Verify on real data

**Files:** none tracked. Outputs go to `runs/eval-dd`, `runs/eval-dd-legacy` and `runs/sweep-okx-tr-dd`, all gitignored. Scratchpad scripts: `verify_fix.py` and `analyze_sweep.py`.

- [ ] **Step 1: Run the full Python suite, then the frontend tests and build.**

```bash
./.venv/Scripts/python.exe -B -m unittest discover -s tests
```

```bash
npm test
```

```bash
npm run build
```

- [ ] **Step 2: Legacy is unchanged on the BTC reference.** Run BTC with the legacy flags:

```bash
./.venv/Scripts/python.exe -B -m agent_trading.backtest --data data/btc_deep --output runs/eval-dd-legacy --label eval-dd-legacy --entry-models HTF_FVG_REVERSAL --model2-htf-fvg false --eq-scale-out none --break-even-trigger R_MULTIPLE --secondary-fvg --runner-fraction 0.10
```

Expected: `metrics` equal to `runs/eval-direction-fixed` (1 trade, ending equity `10112.627090374`).

- [ ] **Step 3: BTC under DD.**

```bash
./.venv/Scripts/python.exe -B -m agent_trading.backtest --data data/btc_deep --output runs/eval-dd --label eval-dd
```

Record the trades, their entry models, the exits and the ending equity.

- [ ] **Step 4: The 30-pair sweep under DD** (in the background, ~15 minutes):

```bash
./.venv/Scripts/python.exe -B -m agent_trading.backtest.sweep --data data/okx_tr_usdt_top30 --output runs/sweep-okx-tr-dd --label okx-tr-usdt-top30
```

- [ ] **Step 5: Check and analyse.**
  - `verify_fix.py runs/sweep-okx-tr-dd`: the three trailing invariants must be 0. The regression line compares with the pre-fix run and is informational only here.
  - Extend `analyze_sweep.py` with an `entry_model` split of the stats and the slice kinds.
  - Report, without changing any threshold:
    - CORE (22), YOUNG (7) and XAUT separately;
    - pooled R, LONG/SHORT, and model 1 vs model 2;
    - exit kinds, break-even share and fee sensitivity;
    - trades per manipulation.

---

### Task 8: Documentation

**Files:**
- Modify:
  - `docs/specs/strategy-v1.md`: a new section "DD deviation entries and scale-out [U-DD-DEVIATION-001]"; "Structural trailing" names both break-even triggers; the partials section describes the EQ slice and the 20% runner.
  - `docs/specs/dd-deviation-models-2026-09-25.md`: Status becomes "implemented", with the date of the Task 6 commit. The line about `TRADE_CANDIDATE` becomes "the `ENTRY_PLAN` and `PENDING_ENTRY` events and the trade record carry `entry_model`". `TradeCandidate` is shared with `trading_brain` and stays unchanged.
  - `docs/specs/backtest-v0.1.md`: the new funnel keys, the `entry_model` column, `by_entry_model`, and the DD and legacy CLI flags.
  - `docs/PROJECT_STATE.md`, `docs/HANDOFF.md`, `docs/NEXT_TASK.md`:
    - the result of Task 7;
    - that the local PAPER agent and a fresh VPS deploy trade DD by default;
    - the panel's `config/strategy.json` change;
    - the known panel limitation: the new knobs are not on the settings screen, and panel partials above 0.5 now exceed the allocation;
    - the next steps.

- [ ] **Step 1: Apply the edits** with scratchpad scripts (`edit_lib.edit`), then run `git diff --check` and the secret scan (`scratchpad/secret_scan.py`).
- [ ] **Step 2: Commit**

```bash
git add docs/
git commit -m "docs: record the DD deviation models and their first result"
```
