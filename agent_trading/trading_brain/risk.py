"""Deterministic PAPER approval and extensible monotonic stop management [H]."""
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Protocol
from ..models import Candle
from .models import PaperTrade, TradeCandidate
from .risk_models import (RiskConfig, SupportingZone, RiskEvidence, RiskDecision,
                          ApprovedTradePlan, StopUpdate)


def positive_decimal(value):
    return isinstance(value, Decimal) and value.is_finite() and value > 0


def utc_time(value):
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() == timedelta(0)


def exact_difference(left, right):
    """Align every supplied Decimal digit before addition/subtraction."""
    with localcontext() as context:
        exponent = min(left.as_tuple().exponent, right.as_tuple().exponent, 0)
        context.prec = max(context.prec, max(left.adjusted(), right.adjusted(), 0) - exponent + 3)
        return left - right


def exact_product(left, right):
    with localcontext() as context:
        context.prec = max(context.prec, len(left.as_tuple().digits) + len(right.as_tuple().digits) + 1)
        return left * right


class StopManagement(Protocol):
    def propose(self, trade: PaperTrade, candle: Candle) -> tuple[Decimal, Decimal] | None: ...


class StructureBreakEven:
    def propose(self, trade, candle):
        evidence = trade.approved_plan.evidence
        favorable = (exact_difference(candle.high, trade.entry) if trade.direction == 'LONG'
                     else exact_difference(trade.entry, candle.low))
        measured_r = favorable / evidence.risk_distance
        if favorable >= exact_product(evidence.risk_distance, evidence.break_even_r):
            return trade.entry, measured_r
        return None


class FixedStopTarget:
    def propose(self, trade, candle):
        return None


class RiskEngine:
    def __init__(self, config=None):
        self.config = config if config is not None else RiskConfig()
        if not isinstance(self.config, RiskConfig):
            raise ValueError('risk config must be RiskConfig')
        self._issued = {}
        self._managers = {'STRUCTURE_BE': StructureBreakEven(), 'FIXED_SL_TP': FixedStopTarget()}

    def is_approved(self, plan):
        # Strong references and identity reject copied/tampered/fabricated plans.
        return isinstance(plan, ApprovedTradePlan) and self._issued.get(id(plan)) is plan

    @staticmethod
    def geometry(direction, entry, stop, tp):
        if not all(positive_decimal(x) for x in (entry, stop, tp)):
            return False
        return (stop < entry < tp if direction == 'LONG' else
                tp < entry < stop if direction == 'SHORT' else False)

    def size(self, entry, stop, equity):
        if not all(positive_decimal(x) for x in (entry, stop, equity)) or entry == stop:
            return None
        quantity = self._quantity(exact_difference(entry, stop).copy_abs(), exact_product(equity, self.config.risk_per_trade))
        return quantity if quantity > 0 and exact_product(quantity, entry) <= equity else None

    def _quantity(self, distance, budget):
        step = self.config.quantity_step
        ratio = Fraction(budget) / Fraction(distance) / Fraction(step)
        units = ratio.numerator // ratio.denominator
        return exact_product(Decimal(units), step)

    @staticmethod
    def _support(zones, candidate, symbol, timeframe):
        if not isinstance(symbol, str) or not symbol.strip() or not isinstance(timeframe, str) or not timeframe.strip():
            return None
        eligible = []
        for zone in zones:
            if (not isinstance(zone, SupportingZone) or zone.validated is not True or zone.fresh is not True
                    or not isinstance(zone.zone_id, str) or not zone.zone_id.strip()
                    or not isinstance(zone.zone_type, str) or not zone.zone_type.strip()
                    or zone.direction != candidate.direction or zone.symbol != symbol or zone.timeframe != timeframe
                    or not utc_time(zone.validated_at) or zone.validated_at > candidate.observed_at
                    or not all(positive_decimal(x) for x in (zone.lower, zone.upper, zone.invalidation_level))
                    or zone.lower >= zone.upper):
                continue
            if candidate.direction == 'LONG':
                supporting = zone.lower <= candidate.entry and zone.invalidation_level <= zone.lower
            else:
                supporting = zone.upper >= candidate.entry and zone.invalidation_level >= zone.upper
            if supporting:
                eligible.append(zone)
        # Stable sorts express ties without float timestamps or price conversion.
        eligible.sort(key=lambda z: (z.zone_id, z.zone_type, z.lower, z.upper))
        eligible.sort(key=lambda z: z.validated_at, reverse=True)
        eligible.sort(key=lambda z: z.invalidation_level, reverse=candidate.direction == 'LONG')
        return eligible[0] if eligible else None

    def evaluate(self, candidate, equity, zones=(), *, symbol=None, timeframe=None):
        if not isinstance(candidate, TradeCandidate):
            raise ValueError('risk requires TradeCandidate')
        config = self.config
        evidence = RiskEvidence(candidate.entry, candidate.tp, config.profile,
                                'FAVORABLE_EXCURSION_R' if config.profile == 'STRUCTURE_BE' else None,
                                config.break_even_r if config.profile == 'STRUCTURE_BE' else None,
                                config.min_reward_risk, config.max_stop_distance,
                                config.risk_per_trade,
                                exact_product(equity, config.risk_per_trade) if positive_decimal(equity) else None,
                                symbol=symbol, timeframe=timeframe)
        for valid, reason in ((utc_time(candidate.observed_at), 'INVALID_OBSERVED_AT'),
                              (candidate.direction in ('LONG', 'SHORT'), 'INVALID_DIRECTION'),
                              (positive_decimal(candidate.entry), 'INVALID_ENTRY')):
            if not valid:
                return self._blocked(candidate, candidate.observed_at, evidence, reason)
        if config.profile == 'FIXED_SL_TP':
            evidence = replace(evidence, initial_stop_source='CANDIDATE_FIXED_STOP', initial_stop=candidate.stop)
        else:
            support = self._support(zones, candidate, symbol, timeframe)
            invalidation = support.invalidation_level if support is not None else candidate.sweep_extreme
            evidence = replace(evidence, initial_stop_source='SUPPORTING_ZONE' if support else 'SWEEP_EXTREME',
                               supporting_zone_id=support.zone_id if support else None,
                               supporting_zone_type=support.zone_type if support else None,
                               zone_source_ids=support.source_ids if support else (), invalidation_level=invalidation)
            if invalidation is None:
                return self._blocked(candidate, candidate.observed_at, evidence, 'MISSING_SWEEP_EXTREME')
            if not positive_decimal(invalidation):
                return self._blocked(candidate, candidate.observed_at, evidence, 'INVALID_SWEEP_EXTREME')
            stop = exact_difference(invalidation, config.stop_buffer if candidate.direction == 'LONG'
                                    else config.stop_buffer.copy_negate())
            evidence = replace(evidence, initial_stop=stop)
        return self._approve_geometry(candidate, candidate.entry, candidate.tp, equity, candidate.observed_at, evidence)

    @staticmethod
    def _blocked(candidate, observed_at, evidence, reason):
        return RiskDecision('BLOCKED', reason, candidate, observed_at, replace(evidence, blocked_reason=reason))

    def _approve_geometry(self, candidate, entry, tp, equity, observed_at, evidence, *, require_support_intact=False):
        stop = evidence.initial_stop
        evidence = replace(evidence, entry=entry, tp=tp,
                           risk_budget=exact_product(equity, evidence.risk_per_trade) if positive_decimal(equity) else None)
        for valid, reason in ((positive_decimal(entry), 'INVALID_ENTRY'),
                              (positive_decimal(stop), 'INVALID_STOP'), (positive_decimal(tp), 'INVALID_TP'),
                              (positive_decimal(equity), 'INVALID_EQUITY')):
            if not valid:
                return self._blocked(candidate, observed_at, evidence, reason)
        risk = exact_difference(entry, stop) if candidate.direction == 'LONG' else exact_difference(stop, entry)
        reward = exact_difference(tp, entry) if candidate.direction == 'LONG' else exact_difference(entry, tp)
        quantity = self._quantity(risk, evidence.risk_budget) if risk > 0 else None
        evidence = replace(evidence, risk_distance=risk, reward_distance=reward,
                           reward_risk_ratio=reward / risk if risk > 0 else None,
                           position_size=quantity, risk_amount=exact_product(quantity, risk) if quantity is not None else None)
        support_failed = (require_support_intact and evidence.initial_stop_source == 'SUPPORTING_ZONE'
                          and (entry < evidence.invalidation_level if candidate.direction == 'LONG'
                               else entry > evidence.invalidation_level))
        for blocked, reason in ((risk == 0, 'NON_POSITIVE_RISK_DISTANCE'), (risk < 0, 'INVALID_STOP_SIDE'),
                                (reward <= 0, 'INVALID_TP_SIDE'),
                                (support_failed, 'SUPPORT_INVALIDATED_AT_FILL'),
                                (risk > 0 and reward < exact_product(risk, evidence.min_reward_risk), 'MIN_REWARD_RISK'),
                                (evidence.max_stop_distance is not None and risk > evidence.max_stop_distance,
                                 'MAX_STOP_DISTANCE'),
                                (quantity is not None and quantity <= 0, 'ZERO_POSITION_SIZE'),
                                (quantity is not None and exact_product(quantity, entry) > equity, 'INSUFFICIENT_EQUITY')):
            if blocked:
                return self._blocked(candidate, observed_at, evidence, reason)
        plan = ApprovedTradePlan(candidate, entry, stop, tp, quantity, evidence.risk_budget,
                                 evidence.risk_amount, observed_at, evidence)
        self._issued[id(plan)] = plan
        return RiskDecision('APPROVED', None, candidate, observed_at, evidence, plan)

    def revalidate_fill(self, plan, entry, equity, observed_at):
        if not self.is_approved(plan):
            raise ValueError('fill requires a plan issued by this RiskEngine')
        if not utc_time(observed_at) or observed_at < plan.approved_at:
            raise ValueError('fill observation must be causal UTC')
        return self._approve_geometry(plan.candidate, entry, plan.tp, equity, observed_at, plan.evidence,
                                      require_support_intact=True)

    def tighten_stop(self, trade, proposed, observed_at, reason, *, measured_r=None):
        if not isinstance(trade, PaperTrade) or not self.is_approved(trade.approved_plan):
            raise ValueError('stop management requires an approved PAPER trade')
        if not utc_time(observed_at) or observed_at < trade.opened_at or (
                trade.stop_updates and observed_at < trade.stop_updates[-1].observed_at):
            raise ValueError('stop update must be causal UTC')
        if not positive_decimal(proposed):
            raise ValueError('proposed stop must be a positive finite Decimal')
        evidence = trade.approved_plan.evidence
        if trade.status != 'OPEN' or evidence.profile == 'FIXED_SL_TP':
            return trade
        stop = max(trade.stop, proposed) if trade.direction == 'LONG' else min(trade.stop, proposed)
        if stop == trade.stop:
            return trade
        update = StopUpdate(observed_at, trade.stop, stop, reason,
                            evidence.break_even_trigger if measured_r is not None else None,
                            evidence.break_even_r if measured_r is not None else None, measured_r)
        return replace(trade, stop=stop, stop_updates=trade.stop_updates + (update,))

    def manage(self, trade, candle):
        if not isinstance(trade, PaperTrade) or not self.is_approved(trade.approved_plan):
            raise ValueError('management requires an approved PAPER trade')
        evidence = trade.approved_plan.evidence
        if (not isinstance(candle, Candle) or candle.closed is not True
                or candle.close_time < trade.opened_at
                or (evidence.symbol is not None and candle.symbol != evidence.symbol)
                or (evidence.timeframe is not None and candle.timeframe != evidence.timeframe)
                or (trade.stop_updates and candle.close_time < trade.stop_updates[-1].observed_at)):
            raise ValueError('management requires a causal closed candle')
        if trade.status != 'OPEN':
            return trade
        proposal = self._managers[trade.approved_plan.evidence.profile].propose(trade, candle)
        return (self.tighten_stop(trade, proposal[0], candle.close_time, 'BREAK_EVEN', measured_r=proposal[1])
                if proposal is not None else trade)
