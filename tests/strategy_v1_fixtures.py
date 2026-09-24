"""Deterministic synthetic Strategy V1 acceptance scenario.

Every candle below is synthetic. The scenario proves the production state
machine wiring end to end; it proves nothing about profitability.
"""
from datetime import datetime, timezone
from decimal import Decimal

from agent_trading.market import bar_duration
from agent_trading.models import Candle
from agent_trading.strategy_v1 import StrategyV1, StrategyProfile, TimeframeRoles

D = Decimal
SYMBOL = 'BTC-USDT'
BIAS_START = datetime(2026, 2, 27, 0, 0, tzinfo=timezone.utc)
RANGE_START = datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc)
ENTRY_START = datetime(2026, 3, 6, 8, 0, tzinfo=timezone.utc)


def candle(timeframe, close_time, open_, high, low, close, volume='10'):
    return Candle(SYMBOL, timeframe, close_time, D(str(open_)), D(str(high)),
                  D(str(low)), D(str(close)), D(volume))


def bars(timeframe, start, rows):
    step = bar_duration(timeframe)
    out, moment = [], start
    for open_, high, low, close in rows:
        moment = moment + step
        out.append(candle(timeframe, moment, open_, high, low, close))
    return out


def _flat(count, base, span=2):
    return [(base, base + span, base - span, base) for _ in range(count)]


def _ramp(count, start, end, span=2):
    rows, price = [], D(str(start))
    step = (D(str(end)) - D(str(start))) / D(count)
    for _ in range(count):
        following = price + step
        rows.append((price, max(price, following) + span, min(price, following) - span, following))
        price = following
    return rows


def _leg(prices, span=0):
    rows = []
    for index in range(1, len(prices)):
        open_, close = D(str(prices[index - 1])), D(str(prices[index]))
        rows.append((open_, max(open_, close) + span, min(open_, close) - span, close))
    return rows


def bias_candles():
    """4H: bearish break first, then a bullish body close -> BULLISH_REVERSAL."""
    rows = (_flat(16, 100) + _ramp(4, 100, 92) + _ramp(5, 92, 120) + _ramp(5, 120, 88)
            + _ramp(6, 88, 132) + _flat(3, 132))
    return bars('4H', BIAS_START, rows)


def range_candles():
    """1H: frozen range 118/140, downside sweep to 112, body-close reclaim."""
    rows = _flat(16, 130)
    rows += _leg([130, 133, 136])
    rows += _leg([136, 130, 124, 118])
    rows += _leg([118, 126, 133, 138])
    rows += _leg([138, 132, 126])
    rows += _leg([126, 132, 140])
    rows += _leg([140, 133, 124])
    rows += _leg([124, 120])
    rows += _leg([120, 127, 133, 138])
    rows += _leg([138, 132, 127])
    rows += [(127, 127, 112, 116)]            # 13:00 sweep below RangeLow
    rows += [(116, 117.5, 113, 117)]          # 14:00 still outside: not a reclaim
    rows += [(117, 125, 115, 124)]            # 15:00 body close back inside -> reclaim
    rows += [(124, 133, 124, 132), (132, 141, 132, 140)]
    return bars('1H', RANGE_START, rows)


FILL_ROW = 33          # rows[:FILL_ROW] ends on the candle that fills the entry


def _entry_rows():
    rows = _flat(16, 127)
    rows += [(127, 127, 124, 124), (124, 124, 120, 120),
             (120, 120, 116, 116), (116, 116, 112, 112)]     # sweep leg to 112
    rows += [(112, 117, 112, 117)]                           # confirms swing low 112
    rows += [(117, 122, 117, 122), (122, 125, 122, 125)]     # rally, high 125
    rows += [(125, 125, 119, 119.5)]                         # confirms high 125; low 119
    rows += [(119.5, 120, 119, 119.8),                       # A  high 120
             (119.8, 124, 119.8, 123.5),                     # B  displacement
             (123.5, 125, 122, 124.5)]                       # C  low 122 -> SECONDARY
    rows += [(124.5, 126, 123, 125.5)]                       # 15:00, 1H reclaim closes here
    rows += [(125.5, 126, 124.5, 125.8),                     # D  high 126
             (125.8, 131, 125.8, 130.5),                     # E  displacement
             (130.5, 132, 130, 131)]                         # F  low 130 -> PRIMARY
    rows += [(131, 131, 129, 129.5)]                         # drift back toward the gap
    rows += [(129.5, 129.5, 128, 128.5)]                     # trades at EQ 128 -> fill
    rows += [(128.5, 133, 128, 132), (132, 137, 132, 136),
             (136, 141, 136, 140)]                           # run into RangeHigh
    return rows


def entry_candles():
    """15m: secondary gap before the reclaim, primary gap after, retrace to EQ."""
    return bars('15m', ENTRY_START, _entry_rows())


def recovery_entry_candles():
    """15m variant: PRIMARY fails, SECONDARY holds, price recovers, then trails."""
    rows = _entry_rows()[:FILL_ROW]                  # shared prefix through the fill
    rows += [(128.5, 129, 124, 125)]                 # 16:30 close below PRIMARY low
    rows += [(125, 125.5, 121, 122)]                 # 16:45 reacts from SECONDARY
    rows += [(122, 128.5, 122, 128)]                 # 17:00 recovers to entry -> BE
    rows += [(128.6, 132, 128.5, 131)]               # 17:15 holds above break-even
    rows += [(131, 135, 131, 134)]                   # 17:30
    rows += [(134, 134, 129.5, 129.8)]               # 17:45 confirms the swing high
    rows += [(129.8, 135, 129.8, 134.5)]             # 18:00 confirms the higher low
    rows += [(134.5, 136, 133, 135)]                 # 18:15 trailing applies
    return bars('15m', ENTRY_START, rows)


def recovery_candles():
    return bias_candles() + range_candles() + recovery_entry_candles()


def acceptance_range_candles():
    """1H variant with a wider frozen range so 1R and 2R sit below RangeHigh."""
    rows = _flat(16, 130)
    rows += _leg([130, 133, 136])
    rows += _leg([136, 130, 124, 118])
    rows += _leg([118, 126, 133, 138])
    rows += _leg([138, 132, 126])
    rows += _leg([126, 145, 170])                 # H2 = 170
    rows += _leg([170, 145, 124])                 # close below L2 -> ValidHigh 170
    rows += _leg([124, 120])                      # low touch near RangeLow
    rows += _leg([120, 135, 150, 168])            # high touch near RangeHigh
    rows += _leg([168, 150, 130])
    rows += [(130, 130, 112, 116)]                # sweep below RangeLow
    rows += [(116, 117.5, 113, 117)]              # still outside
    rows += [(117, 125, 115, 124)]                # body close back inside -> reclaim
    rows += [(124, 140, 124, 138), (138, 171, 138, 170)]
    return bars('1H', RANGE_START, rows)


def acceptance_entry_candles():
    """15m tail: BE, trailing, 1R and 2R partials, RangeHigh, runner, runner stop."""
    rows = _entry_rows()[:FILL_ROW]                    # shared prefix through the fill
    rows += [(128.5, 133, 128, 132)]                   # 16:30 below 1R
    rows += [(132, 138.5, 131.5, 138)]                 # 16:45 1R partial + break-even
    rows += [(138, 138, 131.5, 132)]                   # 17:00 confirms the swing high
    rows += [(132, 140, 132, 139)]                     # 17:15 confirms the higher low
    rows += [(139, 142, 138, 141)]                     # 17:30 trailing update #1
    rows += [(141, 148.5, 140, 148)]                   # 17:45 2R partial
    rows += [(148, 148, 141, 142)]                     # 18:00 confirms the next high
    rows += [(142, 150, 142, 149)]                     # 18:15 confirms the next low
    rows += [(149, 152, 148, 151)]                     # 18:30 trailing update #2
    rows += [(151, 171, 150, 170)]                     # 18:45 RangeHigh -> runner
    rows += [(170, 176, 169, 175)]                     # 19:00 runner, no upside target
    rows += [(175, 175, 161, 162)]                     # 19:15 confirms the runner high
    rows += [(162, 175, 162, 174)]                     # 19:30 confirms the runner low
    rows += [(174, 175, 173, 174.5)]                   # 19:45 runner stop trails up
    rows += [(174.5, 174.5, 159, 160)]                 # 20:00 runner stopped
    return bars('15m', ENTRY_START, rows)


def acceptance_profile(**overrides):
    """Section 17 configuration: 1R -> 20%, 2R -> 20%, runner 10%."""
    settings = dict(partial_take_profits=({'r_multiple': '1.0', 'close_fraction': '0.20'},
                                          {'r_multiple': '2.0', 'close_fraction': '0.20'}),
                    runner_fraction=D('0.10'))
    settings.update(overrides)
    return scenario_profile(**settings)


def acceptance_candles():
    return bias_candles() + acceptance_range_candles() + acceptance_entry_candles()


# [U-DD-DEVIATION-001] The shipped scenarios were built for the pre-DD entry and
# exits and keep covering them; DD scenarios live in dd_fixtures.py.
LEGACY = dict(entry_models=('HTF_FVG_REVERSAL',), model2_requires_htf_fvg=False,
              secondary_fvg_support_enabled=True, eq_scale_out_fraction=None,
              break_even_trigger='R_MULTIPLE', runner_fraction=D('0.10'))


def scenario_profile(**overrides):
    """Buffer/tolerance are scaled to the synthetic price grid, not to BTC.

    This scenario predates [U-RANGE-GUIDE-002] and deliberately keeps the
    superseded BIAS_LONG_PERMISSION gate, so that path stays covered end to
    end. The guide gate has its own scenario in `guide_fixtures.py`.
    """
    settings = dict(timeframes=TimeframeRoles('4H', '1H', '15m'),
                    boundary_proximity=D('5'), stop_buffer=D('1'),
                    equity=D('10000'), entry_level='FVG_EQ',
                    direction='LONG_ONLY', direction_gate='BIAS_LONG_PERMISSION', **LEGACY)
    settings.update(overrides)
    if settings['direction'] != 'LONG_ONLY' and 'direction_gate' not in overrides:
        settings['direction_gate'] = 'GUIDE_HTF_CONTEXT'
    return StrategyProfile(**settings)


def all_candles():
    return bias_candles() + range_candles() + entry_candles()


def run_scenario(profile=None, candles=None):
    strategy = StrategyV1(SYMBOL, profile if profile is not None else scenario_profile())
    strategy.feed(all_candles() if candles is None else candles)
    return strategy


def first_event(strategy, kind):
    return next((e for e in strategy.events if e.kind == kind), None)


def events_of(strategy, kind):
    return tuple(e for e in strategy.events if e.kind == kind)
