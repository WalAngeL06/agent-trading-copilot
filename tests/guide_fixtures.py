"""Guide-gate scenarios [U-RANGE-GUIDE-002]: a discount long and a premium short.

The 1H and 15m streams are the shipped Strategy V1 scenario. What is new is the
4H context: a dealing range whose equilibrium leaves the traded range in
discount (long) or in premium (short), with a Valid boundary on the swept level
so the guide's confluence rule (4.3) is satisfied.

The short scenario reflects the shipped entry stream about the range axis
(`range_low + range_high`), which maps the range onto itself and turns every
bullish structure into its bearish twin. Its 1H tail is written out rather than
reflected, because the shipped range engine still freezes a candidate Valid Low
first ([H]-RANGE-001) and a reflected 1H stream would offer the High first.
Reflection therefore proves the entry, risk and execution layers are symmetric,
which is exactly the part this change touches.
"""
from dataclasses import replace
from decimal import Decimal

from agent_trading.strategy_v1 import StrategyV1, StrategyProfile, TimeframeRoles
from strategy_v1_fixtures import (D, LEGACY, SYMBOL, BIAS_START, _flat, _leg,
                                  acceptance_entry_candles, acceptance_range_candles,
                                  bars, entry_candles, range_candles)

RANGE_AXIS = D('258')               # 118 + 140, the shipped range
ACCEPTANCE_AXIS = D('288')          # 118 + 170, the wider acceptance range


def mirror(candles, axis=RANGE_AXIS):
    """Reflect a stream about `axis`: lows become highs and the trend flips."""
    return [replace(c, open=axis - c.open, high=axis - c.low,
                    low=axis - c.high, close=axis - c.close) for c in candles]


def guide_bias_candles(scale=D('1')):
    """4H dealing range 120 .. 200 (EQ 160) with the Valid Low on 120.

    `scale` moves the whole dealing range, which is how a scenario chooses
    whether the traded range ends up in discount or in premium.
    """
    def legs(prices):
        return _leg([D(str(price)) * scale for price in prices])

    rows = _flat(16, D('150') * scale)
    rows += legs([150, 160, 170, 180])                  # swing high 180
    rows += legs([180, 165, 150, 135, 120])             # -> ValidHigh(180), swing low 120
    rows += legs([120, 140, 160, 185, 200])             # -> ValidLow(120), swing high 200
    rows += legs([200, 180, 160, 140, 118])             # -> ValidHigh(200)
    rows += _flat(3, D('125') * scale)
    return bars('4H', BIAS_START, rows)


def low_frame_bias_candles():
    """The same 4H shape halved: a dealing range of 60 .. 100 leaves the traded
    range in premium, where guide 4.4 forbids a long."""
    return guide_bias_candles(D('0.5'))


def short_bias_candles(scale=D('0.7')):
    """4H dealing range 84 .. 140: the sweep to 146 is premium, on the Valid High."""
    return guide_bias_candles(scale)


def _short_tail(candles, rows):
    """Replace the downside sweep of a 1H stream with an upside one."""
    kept = candles[:-len(rows)]
    return kept + bars('1H', kept[-1].close_time, rows)


def short_range_candles():
    """1H: the shipped range 118 .. 140, then a sweep to 146 and a reclaim."""
    return _short_tail(range_candles(),
                       [(127, 141, 127, 140),        # 13:00 wick through RangeHigh
                        (140, 146, 139, 142),        # 14:00 still outside: not a reclaim
                        (142, 143, 133, 134),        # 15:00 body close back inside
                        (134, 134, 125, 126),
                        (126, 126, 117, 118)])


def short_acceptance_range_candles():
    """1H: the wider range 118 .. 170, then a sweep to 176 and a reclaim."""
    return _short_tail(acceptance_range_candles(),
                       [(130, 150, 130, 149),
                        (149, 176, 149, 172),
                        (172, 174, 163, 164),
                        (164, 164, 148, 150),
                        (150, 150, 117, 118)])


def guide_profile(**overrides):
    """Same grid as the shipped scenario, on the guide's direction rules."""
    settings = dict(timeframes=TimeframeRoles('4H', '1H', '15m'),
                    boundary_proximity=D('5'), stop_buffer=D('1'),
                    equity=D('10000'), entry_level='FVG_EQ', direction='BOTH', **LEGACY)
    settings.update(overrides)
    return StrategyProfile(**settings)


def guide_acceptance_profile(**overrides):
    """Section 17 exits (1R -> 20%, 2R -> 20%, runner 10%) on the guide gate."""
    settings = dict(partial_take_profits=({'r_multiple': '1.0', 'close_fraction': '0.20'},
                                          {'r_multiple': '2.0', 'close_fraction': '0.20'}),
                    runner_fraction=D('0.10'))
    settings.update(overrides)
    return guide_profile(**settings)


def long_candles():
    return guide_bias_candles() + range_candles() + entry_candles()


def short_candles():
    return (short_bias_candles() + short_range_candles()
            + mirror(entry_candles(), RANGE_AXIS))


def guide_acceptance_candles():
    """The wider acceptance range under the guide's 4H context."""
    return guide_bias_candles() + acceptance_range_candles() + acceptance_entry_candles()


def short_acceptance_candles():
    return (short_bias_candles(D('0.875')) + short_acceptance_range_candles()
            + mirror(acceptance_entry_candles(), ACCEPTANCE_AXIS))


def run_guide(candles=None, profile=None):
    strategy = StrategyV1(SYMBOL, profile if profile is not None else guide_profile())
    strategy.feed(long_candles() if candles is None else candles)
    return strategy
