"""Turn production ledgers into logical-trade records and a realised equity curve.

This module reads what Strategy V1 already produced. It never decides an entry,
an exit, a stop or a size, and it never re-derives a strategy rule.
"""
from dataclasses import dataclass
from decimal import Decimal

from ..trading_brain.risk import exact_difference, exact_product
from .format import plain

BREAK_EVEN_REASONS = ('BREAK_EVEN', 'RECOVERY_BREAK_EVEN', 'RANGE_EQ_BREAK_EVEN')
EXIT_REASONS = {'RUNNER': 'RUNNER_STOP', 'STOP': 'STOP_LOSS', 'RANGE_HIGH': 'RANGE_HIGH',
                'PARTIAL_TP': 'PARTIAL_TP', 'RANGE_EQ': 'RANGE_EQ', 'RANGE_LOW': 'RANGE_LOW'}


def add(left, right):
    """Exponent-aligned addition, matching the shipped Decimal discipline."""
    return exact_difference(left, right.copy_negate())


@dataclass(frozen=True)
class SliceRecord:
    kind: str
    trigger_r: Decimal | None
    target_price: Decimal | None
    quantity: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    cost: Decimal
    net_pnl: Decimal
    remaining_quantity: Decimal
    observed_at: object

    def as_dict(self):
        return {'kind': self.kind,
                'trigger_r': None if self.trigger_r is None else plain(self.trigger_r),
                'target_price': None if self.target_price is None else plain(self.target_price),
                'quantity': plain(self.quantity), 'exit_price': plain(self.exit_price),
                'gross_pnl': plain(self.gross_pnl), 'cost': plain(self.cost),
                'net_pnl': plain(self.net_pnl),
                'remaining_quantity': plain(self.remaining_quantity),
                'observed_at': self.observed_at.isoformat()}


@dataclass(frozen=True)
class TradeRecord:
    trade_id: str
    symbol: str
    direction: str
    setup_at: object
    entry_at: object
    entry_price: Decimal
    initial_stop: Decimal
    initial_r: Decimal
    original_quantity: Decimal
    initial_risk_amount: Decimal
    slices: tuple
    final_exit_at: object | None
    exit_reason: str
    status: str
    gross_pnl: Decimal
    cost: Decimal
    net_pnl: Decimal
    r_multiple: Decimal | None
    duration_seconds: int | None
    partial_count: int
    range_high_reached: bool
    runner_opened: bool
    runner_stopped: bool
    break_even_reached: bool
    trailing_updates: int
    entry_model: str | None = None

    def as_dict(self):
        return {'trade_id': self.trade_id, 'symbol': self.symbol,
                'direction': self.direction, 'entry_model': self.entry_model,
                'setup_at': self.setup_at.isoformat(),
                'entry_at': self.entry_at.isoformat(),
                'entry_price': plain(self.entry_price),
                'initial_stop': plain(self.initial_stop),
                'initial_r': plain(self.initial_r),
                'original_quantity': plain(self.original_quantity),
                'initial_risk_amount': plain(self.initial_risk_amount),
                'final_exit_at': None if self.final_exit_at is None
                                 else self.final_exit_at.isoformat(),
                'exit_reason': self.exit_reason, 'status': self.status,
                'gross_pnl': plain(self.gross_pnl), 'cost': plain(self.cost),
                'net_pnl': plain(self.net_pnl),
                'r_multiple': None if self.r_multiple is None else plain(self.r_multiple),
                'duration_seconds': self.duration_seconds,
                'partial_count': self.partial_count,
                'range_high_reached': self.range_high_reached,
                'runner_opened': self.runner_opened,
                'runner_stopped': self.runner_stopped,
                'break_even_reached': self.break_even_reached,
                'trailing_updates': self.trailing_updates,
                'slices': [item.as_dict() for item in self.slices]}


@dataclass(frozen=True)
class EquityPoint:
    observed_at: object
    equity: Decimal
    peak: Decimal
    drawdown: Decimal
    drawdown_percent: Decimal
    trade_id: str | None
    event: str

    def as_row(self):
        return {'observed_at': self.observed_at.isoformat(), 'equity': plain(self.equity),
                'peak_equity': plain(self.peak), 'drawdown': plain(self.drawdown),
                'drawdown_percent': plain(self.drawdown_percent),
                'trade_id': self.trade_id or '', 'event': self.event}


def slice_cost(costs, entry_price, exit_price, quantity):
    """Fees on both notional legs plus adverse slippage on both sides."""
    if not costs.enabled:
        return Decimal(0)
    notional = add(exact_product(quantity, entry_price), exact_product(quantity, exit_price))
    fees = exact_product(costs.fee_rate, notional)
    slip = exact_product(exact_product(costs.slippage, quantity), Decimal(2))
    return add(fees, slip)


def record_trades(strategy, costs, symbol):
    """One record per logical trade, partial exits folded into it."""
    records = []
    # [U-DD-DEVIATION-001] One order rests at a time, so the plan that became a
    # trade is the PENDING_ENTRY emitted on its candidate's own bar.
    plans = {event.observed_at: event.payload for event in strategy.events
             if event.kind == 'PENDING_ENTRY'}
    for index, trade in enumerate(strategy.broker.trades, 1):
        ledger = trade.ledger
        if ledger is None:
            raise ValueError('backtest requires a Strategy V1 ledger on every trade')
        slices, gross, cost = [], Decimal(0), Decimal(0)
        for item in ledger.exits:
            item_cost = slice_cost(costs, trade.entry, item.exit_price, item.quantity)
            net = exact_difference(item.realized_pnl, item_cost)
            slices.append(SliceRecord(item.kind, item.trigger_r, item.target_price,
                                      item.quantity, item.exit_price, item.realized_pnl,
                                      item_cost, net, item.remaining_quantity,
                                      item.observed_at))
            gross = add(gross, item.realized_pnl)
            cost = add(cost, item_cost)
        net_pnl = exact_difference(gross, cost)
        risk_amount = exact_product(ledger.initial_r, ledger.original_quantity)
        r_multiple = (net_pnl / risk_amount) if risk_amount > 0 else None
        closed = trade.status == 'CLOSED'
        last = slices[-1] if slices else None
        reason = ('OPEN_AT_END' if not closed
                  else EXIT_REASONS.get(last.kind, last.kind) if last is not None
                  else 'UNKNOWN')
        duration = (int((last.observed_at - trade.opened_at).total_seconds())
                    if closed and last is not None else None)
        runner_stopped = any(item.kind == 'RUNNER' for item in slices)
        runner_opened = ledger.range_high_done and (runner_stopped
                                                    or ledger.remaining_quantity > 0)
        records.append(TradeRecord(
            trade_id=f'T{index:04d}', symbol=symbol, direction=trade.direction,
            setup_at=trade.candidate.observed_at, entry_at=trade.opened_at,
            entry_price=trade.entry, initial_stop=trade.approved_plan.stop,
            initial_r=ledger.initial_r, original_quantity=ledger.original_quantity,
            initial_risk_amount=risk_amount, slices=tuple(slices),
            final_exit_at=last.observed_at if closed and last is not None else None,
            exit_reason=reason, status=trade.status, gross_pnl=gross, cost=cost,
            net_pnl=net_pnl, r_multiple=r_multiple, duration_seconds=duration,
            partial_count=len(ledger.partial_exits) + len(ledger.of_kind('RANGE_EQ')),
            entry_model=getattr(plans.get(trade.candidate.observed_at), 'entry_model', None),
            range_high_reached=ledger.range_high_done,
            runner_opened=runner_opened, runner_stopped=runner_stopped,
            break_even_reached=any(u.reason in BREAK_EVEN_REASONS
                                   for u in trade.stop_updates),
            trailing_updates=sum(1 for u in trade.stop_updates
                                 if u.reason == 'STRUCTURAL_TRAIL')))
    return tuple(records)


def equity_curve(records, starting_equity, opened_at=None):
    """Realised equity only: one point per realised slice, plus the opening point.

    Unrealised movement between exits is deliberately not modelled, so the curve
    never implies a mark-to-market the replay did not compute.
    """
    points, equity, peak = [], starting_equity, starting_equity
    first = opened_at or (records[0].setup_at if records else None)
    if first is not None:
        points.append(EquityPoint(first, equity, peak, Decimal(0), Decimal(0), None, 'START'))
    every = sorted(((item, record) for record in records for item in record.slices),
                   key=lambda pair: pair[0].observed_at)
    for item, record in every:
        equity = add(equity, item.net_pnl)
        if equity > peak:
            peak = equity
        drawdown = exact_difference(peak, equity)
        percent = (exact_product(drawdown / peak, Decimal(100))
                   if peak > 0 else Decimal(0))
        points.append(EquityPoint(item.observed_at, equity, peak, drawdown, percent,
                                  record.trade_id, item.kind))
    return tuple(points)
