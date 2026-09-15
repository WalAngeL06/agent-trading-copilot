# RiskEngine evidence — 2026-09-12

Base e9ff346b151587c8deaf903b9ffc40d289659725; isolated work/risk-engine at
C:/Users/Serdar Arif/Desktop/Agent Trading/.worktrees/risk-engine.
Authority [U-RISK-ENGINE-001]. [Spec](specs/risk-engine-v0.1.md);
[exact evidence JSON](research/risk-engine-evidence.json).

Risk approval is separate from signal generation and paper execution. Generic
validated fresh support supplies the thesis invalidation, with sweep fallback;
only engine-issued plans reach the broker. Actual fill is separately reapproved.
BLOCKED carries a machine-readable reason and full available geometry/sizing
evidence. The original plan remains on the paper trade after stop changes.
STRUCTURE_BE uses configurable favorable excursion; FIXED_SL_TP preserves SL/TP.
Offline report v0.2 has pending_plan and explicit approval/stop evidence.
Production analysis API, Swing, frozen Range, gaps and manipulation are preserved.

## Approved example — synthetic literals, all risk defaults

Explicitly supplied validated fresh LONG FVG synthetic-zone-1 at 99000..99500,
invalidation 99000; entry 100000, TP 103000, equity 10000. Default buffer 100
produces stop 98900. Risk distance 1100, reward 3000, reward/risk
2.727272727272727272727272727. Budget 100, rounded size .09090909 base units,
actual risk 99.999999 and notional 9090.909. APPROVED. Next open 100000 gets
its own approval and PAPER_ORDER_OPENED. Surviving fill candle HIGH101100 reaches
1R; at its close stop becomes 100000. Subsequent candle hits it: paper PnL0.
Evidence includes source, zone, invalidation, profile, trigger and stop history.
This hand-supplied zone example verifies the risk boundary, not gap detection
or market profitability.

## Blocked example — same synthetic support, all risk defaults

Entry100000, stop98900, TP100500. Risk1100, reward500, ratio
.4545454545454545454545454545 < minimum1. BLOCKED / MIN_REWARD_RISK; plan null.
Calculated size/budget/amount remain in evidence; no order is opened.

## Preserved real SwingEngine full chain — explicit synthetic configuration

The saved corrected25-candle synthetic fixture still drives the real SwingEngine
through valid pair, frozen inside-only range touches, post-confirmation sweep,
reclaim and FVG. Explicit test/replay config: ATR length2/multiplier.1,
bootstrap30, boundary proximity2000, stop buffer1000, opposing BOUNDARY target.
New LONG plan: entry92000, FVG invalidation82000, stop81000, TP120000,
size.00909090, actual risk99.9999, ratio2.545454545454545454545454545.
At default1R its final state is OPEN (final high101000 has not reached103000).
With unchanged EQ target100000 and default minimum1 the same signal is blocked.
Legacy EQ literal fill tests explicitly set minimum.5; this is test configuration,
not a changed default or empirically justified trading rule.

## Verification and limitations

Baseline292 passed. Final full verification323 passed (292 existing methods,
31 new risk methods), zero failures/errors,13.458s. Existing raw-Swing and frozen-Range
files/tests are unchanged. Every-prefix real replay checks remain (four299-row
fixtures plus249-row bounded window), with synthetic prefixes and split replay.
Seven offline CLI smokes pass: full5m/15m/1H/4H, bounded15m, synthetic structure
profile and synthetic fixed profile. Full real fixtures produce no orders;
bounded15m now produces five risk blocks (R:R or unleveraged notional cap).
Saved evidence reports actual counts; it does not claim a profitable strategy.
Independent read-only review identified skipped first fills and precision-boundary
rounding. Regression tests now enforce exact next-open timing, all supplied
Decimal digits and exact rational quantity flooring; re-review confirms fixes
and no material new defects. Structure already crossed at fill is BLOCKED.
Final suite and7 smokes passed after these fixes. HANDOFF/PROJECT_STATE agree.

Exact [H] defaults: STRUCTURE_BE; 1R closed-candle HIGH/LOW excursion;
price-only entry break-even after old-stop/TP checks; minimum R:R1;
maximum absolute stop distance disabled; buffer100; equity10000;
risk fraction.01; size step.00000001 rounded down; notional <= equity.
Nearest invalidation/newest/id deterministic support selection; current gap/
inversion validation; fresh at publication, removed by later wick edge touch
or gap past invalidation; no age expiry. Preserved EQ target, next-open fills,
stop-first ambiguous exits and gap-at-open exits remain their original [H] rules.

Gaps: no Breaker/Order Block detectors, semantic zone expiry/quality or reaction
classifier; no SWING_TRAIL/ATR_TRAIL; no costs, slippage, exchange lot/tick rules,
leverage/margin, portfolio policy, durable order/stop state or production execution.
Buffer/quantity configuration is operator-supplied, not exchange-aware. Plans are
engine-instance issued in memory, so restored execution needs a separate durable
approval design. No LIVE, integration merge/push/tag or empirical validation.
Commit the requested feature then STOP.
