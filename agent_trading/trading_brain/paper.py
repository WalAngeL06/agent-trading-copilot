"""Separate provisional risk sizing and local next-open PAPER broker [H]."""
from dataclasses import replace
from decimal import Decimal, ROUND_DOWN
from .models import PaperTrade, BrokerEvent
from ..market import bar_duration

class RiskPolicy:
    def __init__(self, config):
        self.config = config

    @staticmethod
    def geometry(direction, entry, stop, tp):
        if any(not isinstance(x, Decimal) or not x.is_finite() or x <= 0 for x in (entry, stop, tp)):
            return False
        return (stop < entry < tp if direction == 'LONG' else
                tp < entry < stop if direction == 'SHORT' else False)

    def size(self, entry, stop, equity):
        if any(not isinstance(x, Decimal) or not x.is_finite() or x <= 0 for x in (entry, stop, equity)):
            return None
        distance = abs(entry - stop)
        if distance == 0:
            return None
        step = self.config.quantity_step
        quantity = ((equity * self.config.risk_fraction / distance / step)
                    .to_integral_value(rounding=ROUND_DOWN)) * step
        if quantity <= 0 or quantity * entry > equity:
            return None
        return quantity

class PaperBroker:
    def __init__(self, risk, equity):
        self.risk = risk
        self.equity = equity
        self.pending = None
        self.trades = ()

    def submit(self, candidate):
        if self.pending is not None or any(t.status == 'OPEN' for t in self.trades):
            raise ValueError('paper broker already has a pending/open order')
        if not self.risk.geometry(candidate.direction, candidate.entry, candidate.stop, candidate.tp):
            raise ValueError('invalid candidate geometry')
        self.pending = candidate

    def process(self, candle):
        result = []
        if self.pending is not None and candle.close_time > self.pending.observed_at:
            candidate = self.pending
            self.pending = None
            quantity = self.risk.size(candle.open, candidate.stop, self.equity)
            if (quantity is None or not self.risk.geometry(candidate.direction, candle.open,
                                                         candidate.stop, candidate.tp)):
                result.append(BrokerEvent('PAPER_ORDER_CANCELLED', candle.close_time, candidate))
            else:
                trade = PaperTrade(candidate.direction, candle.open, candidate.stop, candidate.tp,
                                   quantity, self.equity * self.risk.config.risk_fraction,
                                   quantity * abs(candle.open-candidate.stop), candle.close_time,
                                   candidate, filled_at=candle.close_time-bar_duration(candle.timeframe))
                self.trades += (trade,)
                result.append(BrokerEvent('PAPER_ORDER_OPENED', candle.close_time, trade))
        if self.trades and self.trades[-1].status == 'OPEN':
            trade = self.trades[-1]
            exit_price = None
            if trade.direction == 'LONG':
                if candle.open <= trade.stop or candle.open >= trade.tp:
                    exit_price = candle.open
                elif candle.low <= trade.stop:
                    exit_price = trade.stop
                elif candle.high >= trade.tp:
                    exit_price = trade.tp
            else:
                if candle.open >= trade.stop or candle.open <= trade.tp:
                    exit_price = candle.open
                elif candle.high >= trade.stop:
                    exit_price = trade.stop
                elif candle.low <= trade.tp:
                    exit_price = trade.tp
            if exit_price is not None:
                pnl = trade.quantity * (exit_price-trade.entry) * (1 if trade.direction=='LONG' else -1)
                closed = replace(trade, status='CLOSED', exit_price=exit_price,
                                 closed_at=candle.close_time, pnl=pnl)
                self.trades = self.trades[:-1] + (closed,)
                self.equity += pnl
                result.append(BrokerEvent('PAPER_ORDER_CLOSED', candle.close_time, closed))
        return tuple(result)
