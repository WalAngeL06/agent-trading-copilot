"""Backtest metrics. Zero denominators return null, never a fabricated number."""
from collections import Counter
from decimal import Decimal

from ..trading_brain.risk import exact_difference, exact_product
from .format import plain
from .recorder import add

SETUP_EVENTS = {'setups': 'TRADE_CANDIDATE', 'pending_entries': 'PENDING_ENTRY',
                'cancelled_entries': 'PAPER_ORDER_CANCELLED', 'risk_blocked': 'BLOCKED',
                'ranges_confirmed': 'RANGE_CONFIRMED', 'manipulations': 'MANIPULATION_CONFIRMED',
                'htf_context_checks': 'HTF_CONTEXT',
                'bias_breaks': 'BIAS_BREAK', 'fvgs_detected': 'FVG',
                'partial_tp_fills': 'PARTIAL_TP_FILLED',
                'range_high_exits': 'RANGE_HIGH_PARTIAL_EXIT',
                'runners_opened': 'RUNNER_OPEN', 'runners_stopped': 'RUNNER_STOPPED',
                'break_even_moves': 'BREAK_EVEN_PROTECTED',
                'trailing_updates': 'TRAILING_STOP_UPDATED',
                'choch_confirmations': 'CHOCH_CONFIRMED',
                'range_eq_exits': 'RANGE_EQ_PARTIAL_EXIT'}


def _mean(values):
    if not values:
        return None
    total = Decimal(0)
    for value in values:
        total = add(total, value)
    return total / Decimal(len(values))


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return add(ordered[middle - 1], ordered[middle]) / Decimal(2)


def _text(value):
    return None if value is None else plain(value)


def funnel(strategy):
    """How many setups survived each production gate."""
    counts = Counter(event.kind for event in strategy.events)
    return {name: counts.get(kind, 0) for name, kind in SETUP_EVENTS.items()}


def compute(strategy, records, curve, starting_equity):
    closed = [record for record in records if record.status == 'CLOSED']
    open_at_end = [record for record in records if record.status != 'CLOSED']
    wins = [record for record in closed if record.net_pnl > 0]
    losses = [record for record in closed if record.net_pnl < 0]
    flat = [record for record in closed if record.net_pnl == 0]

    gross_profit = Decimal(0)
    for record in wins:
        gross_profit = add(gross_profit, record.net_pnl)
    gross_loss = Decimal(0)
    for record in losses:
        gross_loss = add(gross_loss, record.net_pnl.copy_abs())

    r_values = [record.r_multiple for record in closed if record.r_multiple is not None]
    win_r = [record.r_multiple for record in wins if record.r_multiple is not None]
    loss_r = [record.r_multiple for record in losses if record.r_multiple is not None]
    durations = [record.duration_seconds for record in closed
                 if record.duration_seconds is not None]

    ending_equity = curve[-1].equity if curve else starting_equity
    peak_drawdown = max((point.drawdown for point in curve), default=Decimal(0))
    peak_drawdown_percent = max((point.drawdown_percent for point in curve),
                                default=Decimal(0))
    total_return = (exact_product(
        exact_difference(ending_equity, starting_equity) / starting_equity, Decimal(100))
        if starting_equity > 0 else None)

    return {
        'setups_total': funnel(strategy)['setups'],
        'pending_entries': funnel(strategy)['pending_entries'],
        'cancelled_entries': funnel(strategy)['cancelled_entries'],
        'risk_blocked_setups': funnel(strategy)['risk_blocked'],
        'filled_logical_trades': len(records),
        'closed_trades': len(closed),
        'open_at_end': len(open_at_end),
        'wins': len(wins), 'losses': len(losses), 'break_even_trades': len(flat),
        'win_rate': _text(Decimal(len(wins)) / Decimal(len(closed)) if closed else None),
        'gross_profit': plain(gross_profit), 'gross_loss': plain(gross_loss),
        'profit_factor': _text((gross_profit / gross_loss) if gross_loss > 0 else None),
        'average_r': _text(_mean(r_values)),
        'median_r': _text(_median(r_values)),
        'expectancy_r': _text(_mean(r_values)),
        'average_winning_r': _text(_mean(win_r)),
        'average_losing_r': _text(_mean(loss_r)),
        'max_drawdown_absolute': plain(peak_drawdown),
        'max_drawdown_percent': plain(peak_drawdown_percent),
        'starting_equity': plain(starting_equity),
        'ending_equity': plain(ending_equity),
        'total_return_percent': _text(total_return),
        'average_trade_duration_seconds': (sum(durations) // len(durations)
                                           if durations else None),
        'exit_reason_counts': dict(sorted(Counter(
            record.exit_reason for record in records).items())),
        'partial_tp_fill_count': sum(record.partial_count for record in records),
        'trades_using_partials': sum(1 for record in records if record.partial_count),
        'range_high_reached_count': sum(1 for record in records if record.range_high_reached),
        'runner_opened_count': sum(1 for record in records if record.runner_opened),
        'runner_stopped_count': sum(1 for record in records if record.runner_stopped),
    }


def demo_card(config, dataset, summary):
    """Compact shape for a frontend card. Every value comes from the real run."""
    streams = dataset.as_dict()['streams']
    firsts = [load['first'] for load in streams.values() if load['first']]
    lasts = [load['last'] for load in streams.values() if load['last']]
    return {'status': 'completed', 'symbol': config.symbol,
            'period': {'start': min(firsts) if firsts else None,
                       'end': max(lasts) if lasts else None,
                       'bars': {tf: load['candles'] for tf, load in streams.items()}},
            'total_trades': summary['filled_logical_trades'],
            'win_rate': summary['win_rate'],
            'profit_factor': summary['profit_factor'],
            'average_r': summary['average_r'],
            'expectancy_r': summary['expectancy_r'],
            'max_drawdown_percent': summary['max_drawdown_percent'],
            'starting_equity': summary['starting_equity'],
            'ending_equity': summary['ending_equity']}
