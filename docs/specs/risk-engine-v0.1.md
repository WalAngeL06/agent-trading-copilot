# Configurable structure-aware PAPER risk v0.1

2026-09-12. Authority: [U-RISK-ENGINE-001], urgent user RiskEngine task.
Exact base: e9ff346b151587c8deaf903b9ffc40d289659725. This authorization
supersedes inherited STOP instructions only for this risk change. SwingEngine,
RangeEngine, structural pair selection and manipulation semantics stay intact.
No LIVE, merge, push or tag. Commit the requested feature then STOP.

## Contracts and separation

TradeCandidate is signal evidence, not execution approval. RiskEngine evaluates
it against caller-supplied validated fresh SupportingZone records, sweep extreme,
paper equity and configuration. Return immutable RiskDecision: APPROVED with
ApprovedTradePlan or BLOCKED with a machine-readable reason and risk evidence.
PaperBroker accepts only a plan issued by its RiskEngine. Revalidate the exact
initial stop/TP against the actual next-open entry before opening; an invalid
fill emits BLOCKED and PAPER_ORDER_CANCELLED, never PAPER_ORDER_OPENED.
Every successful fill publishes its own RISK_APPROVED before PAPER_ORDER_OPENED.
The fill bar's opening time must equal the signal plan's approval time, even on
the broker's first processed candle; missing next bars fail before mutation.
Structure support already crossed at the actual open blocks
SUPPORT_INVALIDATED_AT_FILL (strict below LONG invalidation / above SHORT).

SupportingZone is independent of detector type: id/type, symbol/timeframe,
direction, bounds, invalidation level, validated_at, validated and fresh.
Future Breaker/Order Block providers can supply the same interface without risk
code changes. A provider owns validation/freshness; risk never validates a trading
zone by guessing its type. Reject foreign/future, stale/unvalidated or malformed
support. Only LONG zones below/around entry (lower <= entry, invalidation <= lower)
and SHORT zones above/around entry (upper >= entry, invalidation >= upper) qualify.
Use the closest qualifying invalidation to entry, then newest validation time,
then zone id/type/bounds for deterministic ties, independent of input order [H].
The chosen stop must be strictly beyond its invalidation: invalidation - buffer
for LONG; invalidation + buffer for SHORT. With no support use sweep extreme
minus/plus buffer [H]; missing sweep evidence blocks STRUCTURE_BE approval.

FIXED_SL_TP preserves the candidate's original SL/TP and performs the same
quality/sizing gates. STRUCTURE_BE uses structure/fallback and configurable
favorable-excursion break-even. Stop proposals share one monotonic guard: LONG
can only increase, SHORT can only decrease. Fixed profile ignores stop proposals.
A stop-management Protocol permits future strategies; SWING_TRAIL/ATR_TRAIL are
not implemented. No other module may authorize stop loosening.

## Exact provisional defaults [H]-RISK-ENGINE-001

- Profile STRUCTURE_BE. Favorable-excursion threshold 1 R (configurable positive
  Decimal); R always uses actual fill entry and approved initial stop.
- Maximum favorable excursion uses HIGH for LONG / LOW for SHORT on a closed
  candle, including the fill candle. Resolve initial SL/TP exits first. Only a
  surviving trade moves to its actual fill entry at that candle's close; the new
  stop applies to subsequent candles. No intrabar ordering is inferred. Break-even
  is price break-even, with no cost adjustment.
- Minimum reward/risk = 1; equality passes. Optional maximum absolute stop
  distance defaults to None (disabled); equality passes when configured.
- Stop buffer = 100 absolute price units, paper equity = 10000 quote units,
  risk_per_trade = .01 equity fraction, quantity_step = .00000001 base units.
  Sizing = floor((equity * fraction / risk distance) / step) * step. Block zero
  quantity and notional > equity; retain the existing unleveraged PAPER cap.
  Buffer/distance/budget/products preserve all supplied Decimal digits; sizing
  floors an exact rational quotient. R:R and BE gates use exact cross-products;
  recurring ratios are displayed at the Decimal context precision.
- Runtime FVG validation uses the preserved strict three-candle gap; iFVG uses
  the preserved far-edge close inversion. A new directional publication is fresh
  at publication; any later candle whose wick intersects its interval removes
  freshness, conservatively including an edge touch or a gap past invalidation. LONG invalidation is lower,
  SHORT is upper. No age expiry is added. Risk only sees causal publications.
  This is a risk-support adapter, not a rewrite of gap or Range semantics.
- Existing configurable EQ/opposing-boundary target and stop-first/gap-at-open
  PAPER exit conventions are preserved from trading-brain-v0.1.

These hypotheses are user-authorized MVP choices, not DD source confirmations
or empirically validated strategy/risk rules. No reaction classifier, swing
trailing, ATR trailing, portfolio policy, exchange lot/tick rules, costs,
slippage, margin/liquidation or persistent stop management is claimed.

## Gates, evidence and verification

Block invalid direction/entry/stop/TP; wrong stop side; zero risk distance;
unfavorable TP; R:R below minimum; optional stop distance above maximum;
invalid equity; missing fallback; zero/unaffordable size. Decimal only, UTC
knowledge times, closed causal data. Configuration rejects nonfinite/float,
nonpositive thresholds/increments, risk fraction outside (0,1] and unknown profiles.
Evidence retains initial stop source, zone id/type and invalidation, entry,
initial stop/TP, risk/reward distances and ratio, size/budget/amount, profile,
trigger/threshold, configuration gates and blocked reason. Paper trades retain
the original approved plan and every stop update with measurement/time.
Offline report version is trading-brain-paper-v0.2; pending_plan carries the
approved plan. Production analysis-api-v0.1/v0.2 schemas and routes are unchanged.

Tests cover both directions, type-independent support selection/freshness,
sweep fallback, monotonic stops, configurable break-even, fixed SL/TP,
all quality gates, approved-plan-only execution, fill revalidation, conservative
same-bar handling, evidence serialization and deterministic causal prefixes.
Run the full existing suite. Historical literal risk plans are superseded by
this spec; historical Range/Swing expectations remain unchanged.
