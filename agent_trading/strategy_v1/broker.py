"""Pending limit PAPER entry, partial take profits, boundary exit and runner.

No exchange client exists here. Stops only ever tighten, and every tightening
goes through the shipped RiskEngine so the monotonic invariant is enforced in
one place. One logical trade stays one trade record: partial exits are
accounted in its ledger, never as separate trades.

[U-RANGE-GUIDE-002] Every rule below is written once and read from the trade's
own direction: a short is the reflection of a long, never a second code path.
"""
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

from ..market import bar_duration
from ..models import Candle
from ..trading_brain.models import PaperTrade, BrokerEvent
from ..trading_brain.risk import RiskEngine, exact_difference, exact_product
from .models import PositionExit, PositionLedger, StopProtection

# The structural exit is the opposite range boundary of the setup.
BOUNDARY_EXIT = {'LONG': 'RANGE_HIGH', 'SHORT': 'RANGE_LOW'}
# One trailing mode today; the record names the side it actually followed.
TRAIL_REFERENCE = {'LONG': 'CONFIRMED_HIGHER_LOW', 'SHORT': 'CONFIRMED_LOWER_HIGH'}


def floor_to_step(value, step):
    """Deterministic downward rounding onto the instrument quantity grid."""
    if value <= 0:
        return Decimal(0)
    ratio = Fraction(value) / Fraction(step)
    return exact_product(Decimal(ratio.numerator // ratio.denominator), step)


class PendingLimitPaperBroker:
    """Waits for price to trade back to the configured FVG level.

    It never forces a market fill at an unrelated next open and never fills on
    or before the candle that published the gap.
    """

    def __init__(self, risk, equity, profile):
        if not isinstance(risk, RiskEngine):
            raise ValueError('strategy broker requires RiskEngine')
        self.risk, self.equity, self.profile = risk, equity, profile
        self.pending = None
        self.pending_plan = None
        self.trades = ()
        self._last_candle = None
        self._pending_bars = 0
        self._reset_trade_state()
        self.trailing_updates = ()

    def _reset_trade_state(self):
        """Break-even and the recovery chain belong to one trade.

        [U-MULTI-SETUP-001] lets one broker carry many trades in sequence; a
        later trade that inherited these would trail from its first bar.
        """
        self.primary_failed_at = None
        self.secondary_reacted_at = None
        self.recovery_at = None
        self.break_even_at = None

    # ------------------------------------------------------------------ entry
    def submit(self, plan, entry_plan):
        if self.pending_plan is not None or any(t.status == 'OPEN' for t in self.trades):
            raise ValueError('strategy broker already has a pending/open order')
        if not self.risk.is_approved(plan):
            raise ValueError('paper execution requires a RiskEngine-issued approved plan')
        if not self.profile.allows(plan.direction):
            raise ValueError(f'profile direction {self.profile.direction} forbids a '
                             f'{plan.direction} order')
        self.pending_plan, self.pending = plan, entry_plan
        self._pending_bars = 0
        self._reset_trade_state()

    def cancel_pending(self, reason, observed_at):
        """Drop a resting order whose setup died before it could fill.

        Reachable without price ever returning to the entry: the high timeframe
        context can turn against the setup, or the frozen range can be
        invalidated, while the order rests.
        """
        if self.pending_plan is None:
            return None
        self.pending_plan = self.pending = None
        self._pending_bars = 0
        return BrokerEvent('PAPER_ORDER_CANCELLED', observed_at, reason)

    def process(self, candle, swing_lows=(), swing_highs=()):
        """`swing_lows`/`swing_highs` are entry-timeframe swings confirmed on
        EARLIER candles.

        The caller appends this candle's own swings only after this returns, so
        a stop can never tighten on structure that the finished bar itself
        published and then be used to resolve that same bar's exits.
        """
        if not isinstance(candle, Candle) or candle.closed is not True:
            raise ValueError('paper execution requires a closed Candle')
        if self._last_candle is not None and (
                candle.symbol != self._last_candle.symbol
                or candle.timeframe != self._last_candle.timeframe
                or candle.close_time != self._last_candle.close_time + bar_duration(candle.timeframe)):
            raise ValueError('paper candles must be contiguous within one stream')
        self._last_candle = candle
        result = []
        result.extend(self._fill(candle))
        result.extend(self._manage(candle, swing_lows, swing_highs))
        return tuple(result)

    def _fill(self, candle):
        plan = self.pending_plan
        if plan is None or candle.close_time <= plan.approved_at:
            return ()                       # never fill on the publishing candle
        long_ = plan.direction == 'LONG'
        entry = plan.entry
        reached = candle.low <= entry if long_ else candle.high >= entry
        self._pending_bars += 1
        cancel = None
        if candle.low <= plan.stop if long_ else candle.high >= plan.stop:
            # Defensive only. The structural stop sits beyond the entry, so any
            # candle reaching the stop also traded the limit: the fill wins and
            # the position is stopped on the same bar. Inferring the opposite
            # order would assume intrabar sequencing in the trade's favour.
            cancel = 'STOP_BREACHED_BEFORE_FILL'
        elif (self.profile.pending_expiry_bars is not None
              and self._pending_bars > self.profile.pending_expiry_bars):
            cancel = 'PENDING_ENTRY_EXPIRED'
        if cancel is not None and not reached:
            self.pending_plan = self.pending = None
            return (BrokerEvent('PAPER_ORDER_CANCELLED', candle.close_time, cancel),)
        if not reached:
            return ()
        fill_price = min(candle.open, entry) if long_ else max(candle.open, entry)
        self.pending_plan = None
        decision = self.risk.revalidate_fill(plan, fill_price, self.equity, candle.close_time)
        if decision.plan is None:
            self.pending = None
            return (BrokerEvent('BLOCKED', candle.close_time, decision),
                    BrokerEvent('PAPER_ORDER_CANCELLED', candle.close_time, decision))
        approved = decision.plan
        # Initial R is frozen here and never re-derived, so break-even, trailing
        # and realised partials can never move a partial target price.
        initial_r = exact_difference(approved.entry, approved.stop).copy_abs()
        runner_target = floor_to_step(
            exact_product(approved.quantity, self.profile.runner_fraction),
            self.profile.quantity_step)
        ledger = PositionLedger(approved.quantity, initial_r, self.profile.runner_fraction,
                                runner_target, approved.quantity)
        trade = PaperTrade(approved.direction, approved.entry, approved.stop, approved.tp,
                           approved.quantity, approved.risk_budget, approved.risk_amount,
                           candle.close_time, approved.candidate, filled_at=candle.close_time,
                           approved_plan=approved, ledger=ledger)
        self.trades += (trade,)
        return (BrokerEvent('RISK_APPROVED', candle.close_time, decision),
                BrokerEvent('PAPER_ORDER_OPENED', candle.close_time, trade))

    # ------------------------------------------------------------- management
    def partial_target(self, trade, r_multiple):
        """entry plus r_multiple frozen initial R, on the trade's own side."""
        step = exact_product(trade.ledger.initial_r, r_multiple)
        return exact_difference(trade.entry,
                                step.copy_negate() if trade.direction == 'LONG' else step)

    def _realise(self, trade, kind, quantity, price, observed_at, *, trigger_r=None,
                 target_price=None):
        """Book one slice against the single logical trade."""
        ledger = trade.ledger
        quantity = min(quantity, ledger.remaining_quantity)
        move = (exact_difference(price, trade.entry) if trade.direction == 'LONG'
                else exact_difference(trade.entry, price))
        pnl = exact_product(quantity, move)
        remaining = exact_difference(ledger.remaining_quantity, quantity)
        record = PositionExit(kind, quantity, price, pnl, remaining, observed_at,
                              trigger_r, target_price)
        ledger = replace(ledger, remaining_quantity=remaining, exits=ledger.exits + (record,))
        self.equity = exact_difference(self.equity, pnl.copy_negate())
        return replace(trade, ledger=ledger), record

    def _store(self, trade):
        self.trades = self.trades[:-1] + (trade,)
        return trade

    def _close(self, trade, observed_at):
        ledger = trade.ledger
        last = ledger.exits[-1]
        closed = replace(trade, status='CLOSED', exit_price=last.exit_price,
                         closed_at=observed_at, pnl=ledger.total_realized_pnl)
        return self._store(closed)

    def _manage(self, candle, swing_lows=(), swing_highs=()):
        if not self.trades or self.trades[-1].status != 'OPEN':
            return ()
        trade = self.trades[-1]
        before = trade.stop
        result = []
        stopped = self._stop_out(trade, candle)
        if stopped is not None:
            return stopped
        result.extend(self._favorable(trade, candle))
        # Every step below re-reads the stored trade: a stale copy here would
        # silently roll back the ledger written by the exits above.
        trade = self.trades[-1]
        if trade.status != 'OPEN':
            return tuple(result)
        managed = (self.risk.manage(trade, candle)        # inherited 1R break-even
                   if self.profile.break_even_trigger == 'R_MULTIPLE'
                   else self._range_break_even(trade, candle))
        if managed != trade:
            trade = self._store(managed)
            result.append(BrokerEvent('PAPER_STOP_UPDATED', candle.close_time, managed))
        recovered = self._recovery(trade, candle)
        if recovered is not None and recovered != trade:
            trade = self._store(recovered)
            result.append(BrokerEvent('PAPER_STOP_UPDATED', candle.close_time, recovered))
        result.extend(self._protection(trade, candle, before))
        result.extend(self._trail(self.trades[-1], candle, swing_lows, swing_highs))
        return tuple(result)

    def _stop_out(self, trade, candle):
        """Conservative stop-first: a bar touching the stop awards no upside."""
        long_ = trade.direction == 'LONG'
        if candle.open <= trade.stop if long_ else candle.open >= trade.stop:
            price = candle.open
        elif candle.low <= trade.stop if long_ else candle.high >= trade.stop:
            price = trade.stop
        else:
            return None
        runner = trade.ledger.runner_open
        trade, _record = self._realise(trade, 'RUNNER' if runner else 'STOP',
                                       trade.ledger.remaining_quantity, price,
                                       candle.close_time)
        self._store(trade)
        events = []
        if runner:
            events.append(BrokerEvent('RUNNER_STOPPED', candle.close_time, trade.ledger))
        closed = self._close(trade, candle.close_time)
        events.append(BrokerEvent('PAPER_ORDER_CLOSED', candle.close_time, closed))
        return tuple(events)

    def _favorable(self, trade, candle):
        """Range EQ scale-out, configured R partials in order, then the boundary exit."""
        ledger = trade.ledger
        if not ledger.has_upside_target:
            return ()                              # a runner keeps no fixed target
        long_ = trade.direction == 'LONG'
        trade, first = self._range_eq(trade, candle)
        events = list(first)
        ledger = trade.ledger
        for level in self.profile.partial_take_profits:
            if level.r_multiple in ledger.filled_r:
                continue
            target = self.partial_target(trade, level.r_multiple)
            if target >= trade.tp if long_ else target <= trade.tp:
                break              # the structural exit owns this level instead
            if candle.high < target if long_ else candle.low > target:
                break              # ordered targets: nothing beyond can fill
            quantity = floor_to_step(exact_product(ledger.original_quantity,
                                                   level.close_fraction),
                                     self.profile.quantity_step)
            ledger = replace(ledger, filled_r=ledger.filled_r + (level.r_multiple,))
            trade = self._store(replace(trade, ledger=ledger))
            if quantity <= 0:
                continue           # the grid cannot express this slice
            price = (candle.open if (candle.open > target if long_ else candle.open < target)
                     else target)
            trade, record = self._realise(trade, 'PARTIAL_TP', quantity, price,
                                          candle.close_time, trigger_r=level.r_multiple,
                                          target_price=target)
            trade = self._store(trade)
            ledger = trade.ledger
            events.append(BrokerEvent('PARTIAL_TP_FILLED', candle.close_time, record))
        if candle.high < trade.tp if long_ else candle.low > trade.tp:
            return tuple(events)
        return tuple(events) + self._boundary(self.trades[-1], candle)

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

    def _boundary(self, trade, candle):
        """Close down to exactly the configured runner, then cancel the rest."""
        long_ = trade.direction == 'LONG'
        ledger = trade.ledger
        price = (candle.open if (candle.open > trade.tp if long_ else candle.open < trade.tp)
                 else trade.tp)
        quantity = exact_difference(ledger.remaining_quantity, ledger.runner_target_quantity)
        events = []
        if quantity > 0:
            trade, record = self._realise(trade, BOUNDARY_EXIT[trade.direction], quantity,
                                          price, candle.close_time, target_price=trade.tp)
            trade = self._store(trade)
            ledger = trade.ledger
            events.append(BrokerEvent('RANGE_HIGH_PARTIAL_EXIT', candle.close_time, record))
        # Unfilled R levels die here: the runner is never partially closed by a
        # stale 2R/3R instruction, and it keeps no fixed target.
        ledger = replace(ledger, range_high_done=True,
                         partials_cancelled_at=candle.close_time)
        trade = self._store(replace(trade, ledger=ledger))
        if ledger.remaining_quantity > 0:
            events.append(BrokerEvent('RUNNER_OPEN', candle.close_time, ledger))
        else:
            events.append(BrokerEvent('PAPER_ORDER_CLOSED', candle.close_time,
                                      self._close(trade, candle.close_time)))
        return tuple(events)

    # ------------------------------------------------------------------ stops
    def _protection(self, trade, candle, before):
        """Announce the first move that puts the stop at or beyond entry."""
        long_ = trade.direction == 'LONG'
        if self.break_even_at is not None or (trade.stop < trade.entry if long_
                                              else trade.stop > trade.entry):
            return ()
        self.break_even_at = candle.close_time
        reason = trade.stop_updates[-1].reason if trade.stop_updates else 'BREAK_EVEN'
        return (BrokerEvent('BREAK_EVEN_PROTECTED', candle.close_time,
                            StopProtection('BREAK_EVEN_PROTECTED', before, trade.stop,
                                           reason, trade.entry, candle.close_time,
                                           candle.close_time)),)

    def _range_break_even(self, trade, candle):
        """[U-DD-DEVIATION-001] Entry protection once EQ, or the boundary when EQ
        was skipped, has traded. It replaces the inherited 1R rule."""
        ledger = trade.ledger
        if not (ledger.range_eq_done or ledger.range_high_done):
            return trade
        return self.risk.tighten_stop(trade, trade.entry, candle.close_time,
                                      'RANGE_EQ_BREAK_EVEN')

    def _trail(self, trade, candle, swing_lows, swing_highs):
        """Tighten to `confirmed structure -/+ trailing_buffer` after break-even.

        A long follows confirmed higher lows, a short confirmed lower highs.
        Only structure the trade itself made is eligible: the swing forms at or
        after the fill and was confirmed on an earlier bar. A proposal must be
        strictly tighter than the stop, never past break-even, and on the
        market side of this bar's close, so a stop is never set where price
        already trades beyond it. `tighten_stop` still enforces monotonicity.
        A runner keeps receiving these updates after the boundary exit.
        """
        if (not self.profile.trailing_enabled or self.break_even_at is None
                or trade.status != 'OPEN'):
            return ()
        long_ = trade.direction == 'LONG'
        buffer = self.profile.effective_trailing_buffer
        best = best_swing = None
        for swing in (swing_lows if long_ else swing_highs):
            if swing.confirmed_at > candle.close_time or swing.swing_time < trade.filled_at:
                continue            # unconfirmed, or structure from before this trade
            proposed = exact_difference(swing.price,
                                        buffer if long_ else buffer.copy_negate())
            if long_:
                if (proposed <= trade.stop or proposed < trade.entry
                        or proposed >= candle.close):
                    continue        # only tighten, never past break-even or price
                closer = best is None or proposed > best
            else:
                if (proposed >= trade.stop or proposed > trade.entry
                        or proposed <= candle.close):
                    continue
                closer = best is None or proposed < best
            if closer:
                best, best_swing = proposed, swing
        if best is None:
            return ()
        before = trade.stop
        trailed = self.risk.tighten_stop(trade, best, candle.close_time, 'STRUCTURAL_TRAIL')
        if trailed == trade:
            return ()
        self._store(trailed)
        record = StopProtection('TRAILING_STOP_UPDATED', before, trailed.stop,
                                TRAIL_REFERENCE[trade.direction], best_swing.price,
                                best_swing.confirmed_at, candle.close_time)
        self.trailing_updates += (record,)
        return (BrokerEvent('TRAILING_STOP_UPDATED', candle.close_time, record),)

    def _recovery(self, trade, candle):
        """PRIMARY fails -> SECONDARY holds -> price returns to entry -> BE.

        Every threshold below is provisional: [H]-SV1-PRIMARY-FAIL-001 and
        [H]-SV1-RECOVERY-001. The user has not defined an exact failure event.
        """
        plan = self.pending
        if plan is None or plan.secondary is None:
            return None
        long_ = trade.direction == 'LONG'
        if self.primary_failed_at is None:
            failed = (candle.close < plan.primary.lower if long_     # [H] body close
                      else candle.close > plan.primary.upper)        # beyond PRIMARY
            if failed:
                self.primary_failed_at = candle.close_time
            return None
        if self.secondary_reacted_at is None:
            reached = (candle.low <= plan.secondary.upper if long_
                       else candle.high >= plan.secondary.lower)
            held = (candle.close >= plan.secondary.lower if long_
                    else candle.close <= plan.secondary.upper)
            if reached and held:
                self.secondary_reacted_at = candle.close_time
            return None
        if self.recovery_at is not None:
            return None
        if candle.high >= trade.entry if long_ else candle.low <= trade.entry:
            self.recovery_at = candle.close_time      # recovered to original entry
            return self.risk.tighten_stop(trade, trade.entry, candle.close_time,
                                          'RECOVERY_BREAK_EVEN')
        return None
