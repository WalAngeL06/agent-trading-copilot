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
