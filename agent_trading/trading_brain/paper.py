"""Approved-plan-only local next-open PAPER broker [H]. No exchange client."""
from dataclasses import replace
from .models import PaperTrade, BrokerEvent
from .risk import RiskEngine, exact_difference, exact_product
from ..market import bar_duration
from ..models import Candle

class RiskPolicy(RiskEngine):
    """Compatibility constructor; legacy sizing helpers still use RiskEngine."""
    def __init__(self, config):
        super().__init__(config.risk_config())

class PaperBroker:
    def __init__(self, risk, equity):
        if not isinstance(risk, RiskEngine):
            raise ValueError('paper broker requires RiskEngine')
        self.risk = risk
        self.equity = equity
        self.pending = None
        self.trades = ()
        self._last_candle = None

    def submit(self, plan):
        if self.pending is not None or any(t.status == 'OPEN' for t in self.trades):
            raise ValueError('paper broker already has a pending/open order')
        if not self.risk.is_approved(plan):
            raise ValueError('paper execution requires a RiskEngine-issued approved plan')
        self.pending = plan

    def process(self, candle):
        if not isinstance(candle, Candle) or candle.closed is not True:
            raise ValueError('paper execution requires a closed Candle')
        plan = self.pending or (self.trades[-1].approved_plan if self.trades else None)
        if plan is not None:
            evidence = plan.evidence
            if ((evidence.symbol is not None and candle.symbol != evidence.symbol)
                    or (evidence.timeframe is not None and candle.timeframe != evidence.timeframe)):
                raise ValueError('paper candle does not match approved stream')
        if self._last_candle is not None and (
                candle.symbol != self._last_candle.symbol or candle.timeframe != self._last_candle.timeframe
                or candle.close_time != self._last_candle.close_time + bar_duration(candle.timeframe)):
            raise ValueError('paper candles must be contiguous and chronological within one stream')
        if (self.pending is not None and candle.close_time > self.pending.approved_at
                and candle.close_time - bar_duration(candle.timeframe) != self.pending.approved_at):
            raise ValueError('paper fill must be the immediately next candle open')
        self._last_candle = candle
        result = []
        if self.pending is not None and candle.close_time > self.pending.observed_at:
            plan = self.pending
            self.pending = None
            decision = self.risk.revalidate_fill(plan, candle.open, self.equity, candle.close_time)
            if decision.plan is None:
                result.append(BrokerEvent('BLOCKED', candle.close_time, decision))
                result.append(BrokerEvent('PAPER_ORDER_CANCELLED', candle.close_time, decision))
            else:
                approved = decision.plan
                result.append(BrokerEvent('RISK_APPROVED', candle.close_time, decision))
                trade = PaperTrade(approved.direction, approved.entry, approved.stop, approved.tp,
                                   approved.quantity, approved.risk_budget, approved.risk_amount,
                                   candle.close_time, approved.candidate,
                                   filled_at=candle.close_time-bar_duration(candle.timeframe),
                                   approved_plan=approved)
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
                movement = (exact_difference(exit_price, trade.entry) if trade.direction == 'LONG'
                            else exact_difference(trade.entry, exit_price))
                pnl = exact_product(trade.quantity, movement)
                closed = replace(trade, status='CLOSED', exit_price=exit_price,
                                 closed_at=candle.close_time, pnl=pnl)
                self.trades = self.trades[:-1] + (closed,)
                self.equity = exact_difference(self.equity, pnl.copy_negate())
                result.append(BrokerEvent('PAPER_ORDER_CLOSED', candle.close_time, closed))
            else:
                managed = self.risk.manage(trade, candle)
                if managed != trade:
                    self.trades = self.trades[:-1] + (managed,)
                    result.append(BrokerEvent('PAPER_STOP_UPDATED', candle.close_time, managed))
        return tuple(result)
