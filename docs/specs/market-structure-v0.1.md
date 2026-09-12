# Market Structure v0.1 — Formal Specification

Status: **DRAFT — IMPLEMENTATION BLOCKED BY UNRESOLVED DEFINITIONS**.
Source: **[D-DD-MSB-001]**, consisting of the 21 DD rules supplied and confirmed
by the user for this specification. No additional DD material was supplied or
independently verified. No trading logic is implemented by this document.

Repository context inspected: `strategy-v0.1`, based on
`shadow-foundation-v0.2`, commit `667135804a30d8e998d3fc49f0fb2dce236f4a20`.
The existing `MarketSnapshot` supplies closed, symbol-separated,
timeframe-separated histories. Its infrastructure tests do not validate DD.

Evidence labels used throughout:

| Label | Meaning |
|---|---|
| SOURCE-CONFIRMED RULE | A DD statement the user has confirmed in [D-DD-MSB-001]. This establishes source provenance, not trading effectiveness. |
| EMPIRICALLY VALIDATED RULE | A rule supported by the project's own specified backtest/data validation. **None of the DD rules in this document has this status.** |
| DERIVED DESIGN REQUIREMENT | A proposed software contract motivated by [D-DD-MSB-001], explicitly distinguished from a verbatim DD statement. It adds no swing-detection algorithm. |
| ALGORITHMIC DEFINITION PENDING | The deterministic recognition, selection or update procedure is unresolved. A qualitative concept cannot be treated as executable merely because it is source-confirmed. |

`DD-n` below refers to numbered rule n within [D-DD-MSB-001]. All source-confirmed
rules remain empirically unvalidated. Required state fields, diagnostic names
and event representations below are design requirements, not existing Python
types or additional DD rules.

## A. Purpose

Specify the meaning and causal evidence of market structure before coding
`MarketStructureEngine`: structural swings, protected levels, body-close
breaks, structure validity, external/internal relationships, Premium/Discount
and HTF/LTF context. **SOURCE-CONFIRMED RULE**, DD-1–20. [D-DD-MSB-001]

The future engine describes structural state and evidence. A structural break
is distinct from break-quality assessment, liquidity-rejection classification
and approval to execute an order. **DERIVED DESIGN REQUIREMENT**, grounded in
DD-15, DD-20–21. [D-DD-MSB-001]

This is a semantic specification with explicit implementation gates. Pending
definitions in section N prevent treating it as a completed deterministic
algorithm. **DERIVED DESIGN REQUIREMENT**, DD-18–19. [D-DD-MSB-001]

## B. Terminology

| Term | Meaning and epistemic status | Source |
|---|---|---|
| Local high / local low | A local price extreme; being local alone does not make it structural. SOURCE-CONFIRMED RULE, DD-1. | [D-DD-MSB-001] |
| Swing high / swing low | A price extreme represented by a wick, whose occurrence and subsequent confirmation differ. Genuine opposing retracement/reversal is required; recognition is ALGORITHMIC DEFINITION PENDING. DD-4, DD-18–19. | [D-DD-MSB-001] |
| Meaningful high / meaningful low | A reference extreme relevant to structural progression. Its deterministic distinction from an incidental local extreme is ALGORITHMIC DEFINITION PENDING. DD-1–3. | [D-DD-MSB-001] |
| Structural low | In bullish structure, the low responsible for producing/breaking the previous meaningful high and creating the next structural high. SOURCE-CONFIRMED RULE, DD-2. | [D-DD-MSB-001] |
| Structural high | In bearish structure, the high responsible for producing/breaking the previous meaningful low and creating the next structural low. SOURCE-CONFIRMED RULE, DD-3. | [D-DD-MSB-001] |
| Responsible swing | The causally associated origin extreme described above; it is not automatically the immediately preceding local pivot. Selection is ALGORITHMIC DEFINITION PENDING. DD-1–3. | [D-DD-MSB-001] |
| Protected low | In bullish structure, the low responsible for creating the latest meaningful high. SOURCE-CONFIRMED RULE, DD-7. | [D-DD-MSB-001] |
| Protected high | In bearish structure, the high responsible for creating the latest meaningful low. SOURCE-CONFIRMED RULE, DD-8. | [D-DD-MSB-001] |
| Body close | The candle's closing price used to evaluate being beyond a level. Whether its opening price or body placement adds quality is a separate question. DD-5–6, DD-21. | [D-DD-MSB-001] |
| External structure | The primary market structure; determining which swings form that primary structure is ALGORITHMIC DEFINITION PENDING. DD-11. | [D-DD-MSB-001] |
| Internal structure | Smaller movements within external structural boundaries. Scale assignment is ALGORITHMIC DEFINITION PENDING. DD-12–13. | [D-DD-MSB-001] |
| Valid external high / low | The paired external structural extremes used for EQ; not interchangeable with any two rolling maxima/minima. Pair selection/validity is ALGORITHMIC DEFINITION PENDING. DD-1, DD-11, DD-16. | [D-DD-MSB-001] |
| Structural boundaries vs range | Structural boundaries are not proof that a separate valid-range model has been established. Valid-range recognition is ALGORITHMIC DEFINITION PENDING. DD-13, DD-16. | [D-DD-MSB-001] |
| HTF / LTF | Configurable higher/lower timeframe roles; HTF context has priority and LTF primarily confirms or executes its thesis. SOURCE-CONFIRMED RULE, DD-14–15. | [D-DD-MSB-001] |

## C. Inputs

The proposed input contract uses the existing closed-candle `MarketSnapshot`.
The following are **DERIVED DESIGN REQUIREMENTS**; they implement the evidence
discipline of DD-4, DD-6, DD-14–19 rather than claiming DD defines a software API.

| Input | Required semantics | Source |
|---|---|---|
| `symbol`, `as_of` | Identify the instrument and the knowledge boundary for this evaluation; never mix symbols or evidence from later than `as_of`. DD-18. | [D-DD-MSB-001] |
| `histories[timeframe]` | Strictly chronological closed OHLC candles, with wick highs/lows and exact price values; each candle's close time is at or before `as_of`. DD-4–6, DD-18. | [D-DD-MSB-001] |
| Timeframe roles | Explicit HTF/LTF configuration, with optional intraday role. The existing 4H/1H/15m example is operational configuration, not a DD detection rule. DD-14–15. | [D-DD-MSB-001] |
| Prior structural state / initialization evidence | State and evidence sufficient to identify already-knowable structural references. Bootstrap direction, seed selection and retained-history requirements are ALGORITHMIC DEFINITION PENDING. DD-1–3, DD-18–19. | [D-DD-MSB-001] |
| Premium/Discount reference price | Explicit price, its origin and its observation time. DD does not resolve whether this means an HTF close, LTF close or another observed price. ALGORITHMIC DEFINITION PENDING. DD-16, DD-18. | [D-DD-MSB-001] |

Volume exists in the foundation candle contract but no volume threshold or
volume-dependent structural predicate is defined here. No ATR, fixed pivot
count, retracement percentage, score or arbitrary tolerance is an input rule.
**DERIVED DESIGN REQUIREMENT**, preserving DD-19 and the supplied scope.
[D-DD-MSB-001]

## D. Required output state

These are **DERIVED DESIGN REQUIREMENTS**, not an implemented schema. The
state is separated by symbol, timeframe and structural scale. Exact enum names
and persistence format are subject to the decisions in N. [D-DD-MSB-001]

| State element | Minimum information and constraint | Source |
|---|---|---|
| Identity / time | Symbol, timeframe, `as_of`, source provenance and diagnostic reasons. DD-14, DD-18. | [D-DD-MSB-001] |
| Direction and validity | Last established bullish/bearish evidence, whether it remains valid, and whether evidence is undetermined or invalidated. Undetermined is a knowledge state, not an invented sideways trend classification. DD-2–3, DD-9–10, DD-18–19. | [D-DD-MSB-001] |
| Structural swings | References to high/low wick prices, occurrence candle (`swing_time`), `confirmed_at`, supporting evidence and responsible-swing relationships. DD-1–4, DD-18–19. | [D-DD-MSB-001] |
| Protection | Protected high/low reference as applicable, its provenance, when protection became knowable and any invalidating close. No invented protected level when unresolved. DD-7–10, DD-18. | [D-DD-MSB-001] |
| External / internal states | Separate scale-qualified states and references; an internal event cannot silently overwrite external state. DD-11–13. | [D-DD-MSB-001] |
| External dealing boundaries | Valid external high/low references, their joint availability and validity, or explicit unavailability. No substitution of internal extremes. DD-11, DD-16, DD-18. | [D-DD-MSB-001] |
| Premium/Discount | Boundary provenance, EQ, reference price/time and strict PREMIUM or DISCOUNT relation; boundary/equality uncertainties are explicit. DD-16, DD-18. | [D-DD-MSB-001] |
| Structural event evidence | Broken level and scale, direction, closing price, event time, and state before/after; distinguish a structure acceptance candidate from a wick-rejection candidate. DD-5–6, DD-20. | [D-DD-MSB-001] |
| Pending evidence | Local/candidate swings and unresolved relationships remain identifiable as pending, not published as confirmed structural references. DD-1–3, DD-18–19. | [D-DD-MSB-001] |
| Hierarchy constraints | HTF thesis/availability and ordinary-long/short blocking reasons, without claiming an allowed side is approved for trading. DD-14–17. | [D-DD-MSB-001] |

No confidence score, trend score or probability is produced. The evidence
labels SOURCE-CONFIRMED RULE and EMPIRICALLY VALIDATED RULE describe provenance
and validation, not numeric confidence. **DERIVED DESIGN REQUIREMENT**,
preserving the supplied source's lack of such a scoring model. [D-DD-MSB-001]

## E. Structural Swing semantics

**E-1 — SOURCE-CONFIRMED RULE:** Not every local high/low is structural. Wick
extremes represent swing prices; a wick value alone does not establish the
swing's structural responsibility or confirmation. DD-1, DD-4, DD-18.
[D-DD-MSB-001]

**E-2 — SOURCE-CONFIRMED RULE:** In bullish structure, a structural low is the
low responsible for producing/breaking the previous meaningful high and
creating the next structural high. In bearish structure, a structural high is
the high responsible for producing/breaking the previous meaningful low and
creating the next structural low. DD-2–3. [D-DD-MSB-001]

**E-3 — SOURCE-CONFIRMED RULE:** A swing at time t may become knowable only
after a genuine opposing retracement/reversal. DD does not use a fixed 2-bar,
3-bar or 5-bar pivot rule. **ALGORITHMIC DEFINITION PENDING:** what qualifies as
that opposing movement and when it is sufficient to confirm the swing.
DD-18–19. [D-DD-MSB-001]

**E-4 — DERIVED DESIGN REQUIREMENT:** Distinguish occurrence, swing
confirmation and recognition of structural responsibility. A swing may be
confirmed as an extreme while its relationship to a later meaningful break
is still unresolved. Publishing structural responsibility requires the
relationship's evidence to be knowable at the evaluation time. Deterministic
reference selection and linkage are **ALGORITHMIC DEFINITION PENDING**.
DD-1–3, DD-18–19. [D-DD-MSB-001]

**E-5 — DERIVED DESIGN REQUIREMENT:** A body-close break does not instantly
confirm the final wick extreme of an ongoing next swing. Subsequent higher
highs/lower lows and opposing-movement confirmation must not be folded into
the earlier decision. DD-2–4, DD-18–19. [D-DD-MSB-001]

## F. Protected High / Protected Low semantics

**F-1 — SOURCE-CONFIRMED RULE:** In bullish structure, the low responsible for
creating the latest meaningful high becomes the protected low. In bearish
structure, the high responsible for creating the latest meaningful low
becomes the protected high. Protection uses the associated wick extreme,
not a body-price substitute. DD-4, DD-7–8. [D-DD-MSB-001]

**F-2 — SOURCE-CONFIRMED RULE:** Bullish structure becomes invalid when price
body-closes below its protected low. Bearish structure becomes invalid when
price body-closes above its protected high. Wick crossing alone does not
satisfy these invalidation conditions. DD-5–6, DD-9–10. [D-DD-MSB-001]

**F-3 — DERIVED DESIGN REQUIREMENT:** A newer incidental local extreme cannot
replace protection just because it is more recent. Every protected-level
change records the responsible swing, meaningful extreme and causal evidence
that justified it. DD-1–3, DD-7–8, DD-18. [D-DD-MSB-001]

**ALGORITHMIC DEFINITION PENDING:** whether protection updates at the
continuation close, at confirmation of the newly created high/low, or at a
separate causally justified event; candidate competition, supersession and
the representation of an invalidated protected reference. DD-2–3, DD-7–10,
DD-18–19. [D-DD-MSB-001]

## G. Structure Break semantics

For a relevant structural level L and a closed candle with closing price C,
the basic price predicates are:

| Event predicate | Source-confirmed semantics | Source |
|---|---|---|
| `C > L` | Body close beyond an upper structural level; upward structural break / structure acceptance candidate, provided L is a valid relevant structural reference. DD-5–6, DD-20. | [D-DD-MSB-001] |
| `C < L` | Body close beyond a lower structural level; downward structural break / structure acceptance candidate, provided L is a valid relevant structural reference. DD-5–6, DD-20. | [D-DD-MSB-001] |
| Wick crosses L, body does not close beyond L | Insufficient for a structural break. DD-5. | [D-DD-MSB-001] |
| Wick crosses L and close returns inside the boundary | Liquidity sweep / deviation / manipulation **candidate**, not a final classification and not structural acceptance. DD-20. | [D-DD-MSB-001] |

**G-1 — DERIVED DESIGN REQUIREMENT:** “Beyond”, “below” and “above” use strict
price comparisons. Closing exactly on L does not meet a beyond-level break
or protected-level invalidation predicate. No tolerance is supplied. Whether
an equality close counts as liquidity rejection remains pending. DD-5–6,
DD-9–10, DD-20. [D-DD-MSB-001]

**G-2 — DERIVED DESIGN REQUIREMENT:** The relevant level and its scale must be
knowable at the event's evaluation time. A later-recognized local extreme
cannot retroactively become the reference for an earlier actionable break.
Multiple eligible levels and same-candle recognition order are
**ALGORITHMIC DEFINITION PENDING**. DD-1–3, DD-11–13, DD-18. [D-DD-MSB-001]

**G-3 — SOURCE-CONFIRMED RULE:** Body-close structure acceptance and
wick-based liquidity rejection are different concepts. DD-20. [D-DD-MSB-001]

**G-4 — DERIVED DESIGN REQUIREMENT:** Basic structural price predicates do
not automatically approve execution or prove stronger break quality.
DD-15, DD-20–21. [D-DD-MSB-001]

## H. Bullish / Bearish state transitions

The table constrains transition meanings; it does not resolve missing swing
recognition or bootstrap guards. “Established” means the required structural
evidence is causally confirmed, not assumed from the last candle's direction.
**DERIVED DESIGN REQUIREMENT**, DD-1–3, DD-18–19. [D-DD-MSB-001]

| Starting state | Evidence | Required meaning / unresolved part | Source |
|---|---|---|---|
| Undetermined | Proposed bullish structural progression | Bullish establishment needs the meaningful-high/responsible-low relationship. Initialization and confirmation guard: ALGORITHMIC DEFINITION PENDING. DD-2, DD-18–19. | [D-DD-MSB-001] |
| Undetermined | Proposed bearish structural progression | Bearish establishment needs the meaningful-low/responsible-high relationship. Initialization and confirmation guard: ALGORITHMIC DEFINITION PENDING. DD-3, DD-18–19. | [D-DD-MSB-001] |
| Valid bullish | Body close above relevant meaningful structural high | Record upward continuation/break evidence. Confirmation of the resulting high and selection/update of its responsible/protected low remain pending; do not immediately finalize a new swing. DD-2, DD-6–7, DD-18–19. | [D-DD-MSB-001] |
| Valid bullish | Body close below protected low | Bullish validity is invalidated. This alone does not prove bearish structural establishment. DD-3, DD-9, DD-18–19. | [D-DD-MSB-001] |
| Valid bearish | Body close below relevant meaningful structural low | Record downward continuation/break evidence. Confirmation of the resulting low and selection/update of its responsible/protected high remain pending. DD-3, DD-6, DD-8, DD-18–19. | [D-DD-MSB-001] |
| Valid bearish | Body close above protected high | Bearish validity is invalidated. This alone does not prove bullish structural establishment. DD-2, DD-10, DD-18–19. | [D-DD-MSB-001] |
| Either valid structure | Wick-only protected-level violation | No body-close structural invalidation; a return-inside close may create liquidity-rejection evidence. DD-5, DD-9–10, DD-20. | [D-DD-MSB-001] |
| Invalidated former structure | Subsequent opposite structural evidence | Opposite structure requires its own confirmed relationships. Post-invalidation representation, seed/reset rules and reclaim handling: ALGORITHMIC DEFINITION PENDING. DD-2–3, DD-9–10, DD-18–19. | [D-DD-MSB-001] |

An internal break inside a valid range is not automatically an external
trend change. **SOURCE-CONFIRMED RULE**, DD-13. [D-DD-MSB-001]

An event's internal/external scale is explicit before evaluating external
transitions. **DERIVED DESIGN REQUIREMENT**, DD-11–13. [D-DD-MSB-001]

## I. External vs Internal structure

**I-1 — SOURCE-CONFIRMED RULE:** External structure represents primary market
structure. Internal structure represents smaller movements inside external
structural boundaries. DD-11–12. [D-DD-MSB-001]

**I-2 — SOURCE-CONFIRMED RULE:** Internal breaks inside a valid range must not
automatically be treated as external trend changes. DD-13. [D-DD-MSB-001]

**I-3 — DERIVED DESIGN REQUIREMENT:** Keep external and internal references
and event evidence separate. Do not equate “external” with HTF and “internal”
with LTF: scale within boundaries and timeframe hierarchy are distinct
concepts. Their operational mapping is **ALGORITHMIC DEFINITION PENDING**.
DD-11–15. [D-DD-MSB-001]

**ALGORITHMIC DEFINITION PENDING:** primary swing selection, internal nesting,
promotion from internal to external, valid-range recognition, and external
boundary replacement/invalidation. No rolling-window extrema or invented
range detector fills these gaps. DD-1, DD-11–13, DD-16. [D-DD-MSB-001]

## J. Premium / Discount semantics

**J-1 — SOURCE-CONFIRMED RULE:** Use the valid external structural high H and
low L, with `EQ = (H + L) / 2`. For reference price P, `P > EQ` means PREMIUM
and `P < EQ` means DISCOUNT. DD-16. [D-DD-MSB-001]

**J-2 — DERIVED DESIGN REQUIREMENT:** Both boundaries and reference price
carry provenance and knowledge time. If a valid pair is unavailable, report
Premium/Discount as undetermined; do not substitute internal highs/lows or
arbitrary lookback extrema. DD-1, DD-11, DD-16, DD-18. [D-DD-MSB-001]

**J-3 — DERIVED DESIGN REQUIREMENT:** At `P = EQ`, neither strict PREMIUM nor
strict DISCOUNT applies. `AT_EQ` is a proposed descriptive label; DD does not
define ordinary-setup eligibility at equality. That eligibility is
**ALGORITHMIC DEFINITION PENDING**. DD-16–17. [D-DD-MSB-001]

**ALGORITHMIC DEFINITION PENDING:** selection and lifecycle of the valid
external pair, treatment of `H <= L`, reference-price origin and timing, and
whether a boundary violation invalidates/replaces the external pair. If the
pair remains valid, J-1's strict EQ comparison still applies to a price
outside its boundaries; pair lifecycle and setup eligibility remain pending.
No automatic clamping, equality tolerance or execution permission is
specified. DD-16–18. [D-DD-MSB-001]

## K. HTF / LTF hierarchy

**K-1 — SOURCE-CONFIRMED RULE:** HTF context has priority over LTF structure.
LTF structure primarily supplies execution/confirmation for the HTF thesis.
DD-14–15. [D-DD-MSB-001]

**K-2 — SOURCE-CONFIRMED RULE:** HTF DISCOUNT blocks ordinary short setups;
HTF PREMIUM blocks ordinary long setups. DD-17. [D-DD-MSB-001]

**K-3 — DERIVED DESIGN REQUIREMENT:** LTF evidence cannot silently cancel
these HTF ordinary-setup blocks. Being on the other side of EQ does not, by
itself, establish a setup, acceptance approval or risk approval. DD-14–17.
[D-DD-MSB-001]

**K-4 — CONFIRMED PROJECT RULE (USER CLARIFICATION):** Premium/Discount is
context/confirmation, not an independent entry trigger. EQ may react or be
crossed; EQ reaction/reclaim is not a global prerequisite unless a specific
approved setup requires it. Source: [U-PD-001], recorded in
[SOURCE_REGISTRY](../SOURCE_REGISTRY.md). This is an explicit user clarification,
not a newly attributed DD quotation. DD context remains K-1–K-3, DD-14–17
[D-DD-MSB-001]; ordinary HTF side blocks are preserved and their Acceptance
integration is still pending. No current algorithm or runtime behavior changes.

**ALGORITHMIC DEFINITION PENDING:** how the HTF thesis is formed/invalidated,
the role of an intermediate timeframe, the definition of “ordinary” and any
separately authorized exceptional setup, conflicting or missing contexts,
and setup treatment at EQ. No exception is inferred from an LTF break.
DD-14–17. [D-DD-MSB-001]

## L. Causality and look-ahead requirements

All items below are **DERIVED DESIGN REQUIREMENTS** enforcing DD-18–19.

| ID | Requirement | Source |
|---|---|---|
| L-1 | Preserve `swing_time` separately from `confirmed_at`. `swing_time <= confirmed_at <= as_of` for a confirmed swing visible at evaluation. | [D-DD-MSB-001] |
| L-2 | Confirmation is the first evaluation when the eventually specified opposing-movement evidence is knowable, not a timestamp retrospectively assigned to the extreme candle. ALGORITHMIC DEFINITION PENDING. | [D-DD-MSB-001] |
| L-3 | Publish structural responsibility/protection no earlier than all evidence needed for that relationship. Its recognition time can differ from swing occurrence and swing confirmation. | [D-DD-MSB-001] |
| L-4 | Use only closed candles available at `as_of`; an open HTF bar is not a confirmed structural history element, even if its current wick has crossed a level. | [D-DD-MSB-001] |
| L-5 | Appending future data cannot change a past decision's then-available state. A newly confirmed swing may refer to a past extreme, but becomes usable only from its confirmation/recognition time onward. | [D-DD-MSB-001] |
| L-6 | Bootstrap or batch computation cannot leak a later confirmation into an earlier historical evaluation. Replay of a prefix and evaluation of that same prefix from a longer dataset produce the same as-of state. | [D-DD-MSB-001] |
| L-7 | Keep symbol/timeframe/scale state isolated. Align HTF/LTF evidence by availability; shared wall-clock proximity is not proof that the HTF candle has closed. | [D-DD-MSB-001] |
| L-8 | Later follow-through or reversal clues cannot be attached to an earlier actionable break as if known then. Later assessments record their own knowledge time. DD-20–21. | [D-DD-MSB-001] |

The current candle contract supplies candle close timestamps, not the
intrabar instant at which a wick extreme occurred. **ALGORITHMIC DEFINITION
PENDING:** how `swing_time` labels the occurrence candle without inventing
intrabar precision, and how simultaneous cross-timeframe confirmations are
ordered. DD-4, DD-18. [D-DD-MSB-001]

## M. Explicit non-goals for v0.1

The following are **DERIVED DESIGN REQUIREMENTS** separating basic structural
state from later specifications. [D-DD-MSB-001]

| Excluded from the basic structural-state algorithm | Disposition | Source |
|---|---|---|
| Fixed 2/3/5-bar pivot, ATR/retracement/volume thresholds or arbitrary tolerances | No such replacement for genuine opposing retracement/reversal is authorized. DD-19. | [D-DD-MSB-001] |
| Confidence/trend scores or probabilities | No supplied rule defines them; no fabricated scoring model. | [D-DD-MSB-001] |
| Strong / decisive break | Source-confirmed qualitative concept; **ALGORITHMIC DEFINITION PENDING**, reserved for BreakQuality. DD-21. | [D-DD-MSB-001] |
| Little or no reaction at the opposing zone | Source-confirmed qualitative concept; zone/reaction measurement **ALGORITHMIC DEFINITION PENDING**, reserved for BreakQuality. DD-21. | [D-DD-MSB-001] |
| Imbalance / FVG | Source-confirmed concept; identification and causal availability **ALGORITHMIC DEFINITION PENDING**, reserved for BreakQuality. DD-21. | [D-DD-MSB-001] |
| Body placement around 70–80% beyond the level in stronger acceptance cases | Source-confirmed concept, not a chosen threshold. Numerator, denominator and timing **ALGORITHMIC DEFINITION PENDING**, reserved for BreakQuality. DD-21. | [D-DD-MSB-001] |
| Follow-through | Source-confirmed concept; measurement/confirmation **ALGORITHMIC DEFINITION PENDING**, reserved for BreakQuality. DD-21. | [D-DD-MSB-001] |
| Opposite reversal within roughly 1–2 candles | Source-confirmed rejection/deviation clue, not an exact window, grace period or retroactive break cancellation rule. **ALGORITHMIC DEFINITION PENDING**, reserved for Deviation / Manipulation. DD-21. | [D-DD-MSB-001] |
| Final liquidity sweep / deviation / manipulation classification | Wick-plus-return-inside is only candidate evidence; final labels await their own specifications. DD-20–21. | [D-DD-MSB-001] |
| Range detection, entry/exit selection, acceptance/risk sizing or live order execution | Separate specifications; structural evidence and hierarchy alone do not authorize a trade. DD-13–17, DD-20–21. | [D-DD-MSB-001] |

The approximate numbers in DD-19 and DD-21 are recorded only because the
source supplies them; they are not newly chosen implementation parameters.

## N. Ambiguities still unresolved

Every unresolved decision below is **ALGORITHMIC DEFINITION PENDING**. “Gate”
means necessary before coding the complete proposed MarketStructureEngine
state contract, not a demand to implement deferred trading modules.

| ID | Decision to resolve | Gate / dependency | Source |
|---|---|---|---|
| N-1 | What observable opposing retracement/reversal confirms a swing, and at precisely which closed-candle evaluation? | **Core gate**; replaces no concept with a fixed pivot count. DD-18–19. | [D-DD-MSB-001] |
| N-2 | Which highs/lows are meaningful, and which originating swing is responsible for each progression? How are competing candidates linked? | **Core gate**; structural classification and protection depend on it. DD-1–3, DD-7–8. | [D-DD-MSB-001] |
| N-3 | How is first bullish/bearish structure seeded causally? What happens with insufficient or truncated history, and how is established evidence preserved when its candles leave bounded history? | **Core gate**; bootstrap cannot guess direction or silently lose provenance. DD-1–3, DD-18–19. | [D-DD-MSB-001] |
| N-4 | When are new meaningful extremes and protected levels committed/replaced? What are update order, duplicate-break policy, simultaneous level events and post-invalidation/reclaim transitions? | **Core gate**; invalidation is specified, opposite establishment is not. DD-2–3, DD-6–10, DD-18. | [D-DD-MSB-001] |
| N-5 | How are external/internal swings selected, nested and promoted? What makes boundaries/range valid and when does the external pair change? | **Core gate** for the required external/internal state and EQ boundaries; separate valid-range behavior requires a range specification. DD-11–13, DD-16. | [D-DD-MSB-001] |
| N-6 | Which observed price and causal boundary pair feed Premium/Discount? How are degenerate/invalid pairs and equality represented, and how does boundary violation affect pair validity? | **Core gate** for the required Premium/Discount output; a still-valid pair uses the source's strict EQ comparison, while setup permissions at these edges are deferred. DD-16–18. | [D-DD-MSB-001] |
| N-7 | What are the exact state/event representations, timestamp convention for occurrence candles, and equal-time HTF/LTF evaluation ordering? How are ties and multi-level gap closes handled? | **Core gate** for deterministic causal outputs; representation is a design decision, not a new DD predicate. DD-4–6, DD-14–15, DD-18. | [D-DD-MSB-001] |
| N-8 | How is the HTF thesis formed; what is ordinary versus exceptional, and how are conflicting, absent or at-EQ contexts handled? | **Integration gate** before using structural output for setup routing; no trade permission inferred meanwhile. DD-14–17. | [D-DD-MSB-001] |
| N-9 | How are decisive breaks, opposing-zone reaction, FVG/imbalance, body placement and follow-through measured? | Deferred to BreakQuality; **not a prerequisite for bare body-close structural state**. DD-21. | [D-DD-MSB-001] |
| N-10 | How are rejection/deviation/manipulation candidates confirmed, including approximate reversal timing and equality closes? | Deferred to Deviation / Manipulation; not a prerequisite for protected-level body-close invalidation. DD-20–21. | [D-DD-MSB-001] |

No generic engine implementation is authorized until N-1–N-7 have explicit,
causal answers and corresponding expected-state fixtures. Coding an isolated
price comparison would not resolve these engine gates. **DERIVED DESIGN
REQUIREMENT**, DD-1–19. [D-DD-MSB-001]

## O. Edge cases

| Case | Required semantics or unresolved behavior | Source |
|---|---|---|
| Wick crosses protected level; close returns inside | Structure is not invalidated by that wick; liquidity-rejection evidence remains a candidate. DD-5, DD-9–10, DD-20. | [D-DD-MSB-001] |
| Close exactly on protected/broken level | Not a strict beyond-level break or invalidation. Liquidity classification is ALGORITHMIC DEFINITION PENDING. DD-6, DD-9–10, DD-20. | [D-DD-MSB-001] |
| Equal highs/lows, plateau or multiple origin candidates | Wick prices are preserved; tie-breaking, swing identity and responsibility are ALGORITHMIC DEFINITION PENDING. No arbitrary tolerance. DD-1–4, DD-19. | [D-DD-MSB-001] |
| New extreme before opposing movement is confirmed | Do not publish the earlier candidate as a confirmed structural swing merely to keep a rolling pivot available. Candidate replacement is ALGORITHMIC DEFINITION PENDING. DD-18–19. | [D-DD-MSB-001] |
| Body close invalidates protection and later price reclaims it | Record invalidation at the qualifying close; subsequent restoration/opposite-state rules are ALGORITHMIC DEFINITION PENDING. DD-9–10, DD-18. | [D-DD-MSB-001] |
| Gap opens beyond a level or one close crosses several levels | The beyond-level close price predicate is identifiable; event priority, structural reference selection and deduplication are ALGORITHMIC DEFINITION PENDING. DD-5–6, DD-18. | [D-DD-MSB-001] |
| One candle confirms a swing and appears to break it | No intrabar path inferred from OHLC. Ordering and eligibility of a same-candle reference are ALGORITHMIC DEFINITION PENDING. DD-4–6, DD-18–19. | [D-DD-MSB-001] |
| Internal break while external range remains valid | No automatic external trend flip. Recognition of a valid range/external promotion is ALGORITHMIC DEFINITION PENDING. DD-11–13. | [D-DD-MSB-001] |
| LTF confirmation during an open HTF bar | Current HTF partial extrema cannot be used as confirmed HTF structure. Use only causally confirmed evidence; missing-context routing is ALGORITHMIC DEFINITION PENDING. DD-14–15, DD-18. | [D-DD-MSB-001] |
| HTF discount plus LTF short signal; HTF premium plus LTF long signal | Ordinary short/long remains blocked respectively; no automatic LTF exception. DD-14–17. | [D-DD-MSB-001] |
| External pair missing, invalidated or degenerate | No invented EQ pair. Pair validity, diagnostic representation and setup treatment are ALGORITHMIC DEFINITION PENDING. DD-16–18. | [D-DD-MSB-001] |
| Exact EQ or price outside external boundaries | Strict EQ equality is neither PREMIUM nor DISCOUNT. For a still-valid pair, outside prices still use J-1. Boundary-pair lifecycle and setup eligibility are ALGORITHMIC DEFINITION PENDING; do not infer acceptance permission. DD-16–17. | [D-DD-MSB-001] |
| Missing history, missing timeframe, stale or revised data | Preserve explicit unavailable/uncertain evidence rather than fabricating a confirmed state. Recovery, retention and stale-context policy are ALGORITHMIC DEFINITION PENDING; Phase 1 ingestion remains separate. DD-18–19. | [D-DD-MSB-001] |
| Later reversal/FVG/follow-through changes perceived break quality | Publish the later assessment at its own knowledge time; do not repaint the earlier actionable state with future evidence. DD-18, DD-20–21. | [D-DD-MSB-001] |

## P. Required future tests

These are **DERIVED DESIGN REQUIREMENTS** for a future implementation. They
are test specifications, not implemented tests or claims of empirical
validation. Recognition tests need N's approved definitions and fixtures;
semantic tests may use explicitly supplied confirmed-level evidence so they
do not secretly assume a pivot algorithm. [D-DD-MSB-001]

| ID | Future test / expected property | Source |
|---|---|---|
| P-1 | Incidental local extremes are not all structural; bullish responsible-low and bearish responsible-high selection matches approved, evidence-labelled fixtures. Depends on N-1–N-2. DD-1–3. | [D-DD-MSB-001] |
| P-2 | Structural and protected prices use wick highs/lows, including when candle body extremes differ. DD-4, DD-7–8. | [D-DD-MSB-001] |
| P-3 | Wick-only upper/lower level violations do not create body-close breaks. Wick-cross-plus-return-inside produces only candidate rejection evidence. DD-5, DD-20. | [D-DD-MSB-001] |
| P-4 | Strict close above/below a confirmed relevant level creates the appropriate basic break evidence; an equality close does not. DD-6. | [D-DD-MSB-001] |
| P-5 | Bullish close below protected low invalidates bullish validity; bearish close above protected high invalidates bearish validity; mirror cases are covered. DD-9–10. | [D-DD-MSB-001] |
| P-6 | Protection changes only through approved responsible-swing relationships and timing, never simply through a newer local pivot. Depends on N-2, N-4. DD-1–3, DD-7–8. | [D-DD-MSB-001] |
| P-7 | Protected-level invalidation does not automatically establish opposite structural direction; initialization/reclaim cases match approved N-3–N-4 transitions. DD-2–3, DD-9–10. | [D-DD-MSB-001] |
| P-8 | Internal breaks inside a fixture's valid external range do not automatically alter its external trend. Scale promotion follows approved N-5 fixtures. DD-11–13. | [D-DD-MSB-001] |
| P-9 | EQ uses the valid external pair, never internal extremes; strict PREMIUM/DISCOUNT and equality/missing-pair cases match J and approved N-6 output conventions. DD-16. | [D-DD-MSB-001] |
| P-10 | Ordinary short is blocked in HTF discount; ordinary long is blocked in HTF premium despite opposite LTF evidence. No inferred permission for the unblocked side. DD-14–17. | [D-DD-MSB-001] |
| P-11 | For occurrence t and later confirmation u, evaluations before u cannot use the swing, protection or structural linkage as confirmed. At/after their respective recognition times evidence becomes available without rewriting earlier outputs. DD-18–19. | [D-DD-MSB-001] |
| P-12 | Prefix-only replay and as-of evaluation from a longer input agree; future suffixes, bootstrap/batch execution and later quality clues cannot alter earlier state. DD-18, DD-20–21. | [D-DD-MSB-001] |
| P-13 | Open/future HTF candles are invisible to confirmed structure; symbol/timeframe/scale state is isolated; equal-time inputs follow approved N-7 ordering. DD-11–15, DD-18. | [D-DD-MSB-001] |
| P-14 | Genuine opposing-movement confirmation follows approved N-1 fixtures rather than an implicit fixed 2/3/5-bar pivot or unapproved numeric threshold. DD-19. | [D-DD-MSB-001] |
| P-15 | Ties, competing origins, repeated/multi-level/gap closes, invalidated boundaries, missing/truncated history and state retention follow explicit N decisions; no fabricated confirmed state. DD-1–10, DD-16, DD-18–19. | [D-DD-MSB-001] |
| P-16 | Deferred DD-21 quality concepts are recorded as later specification requirements, not hidden prerequisites or numeric thresholds for basic structure breaks. DD-20–21. | [D-DD-MSB-001] |

Passing future semantic/causality unit tests would establish conformance to
the approved algorithm, not trading profitability or EMPIRICALLY VALIDATED
RULE status. Own-data/backtest methodology and evidence remain a separate
validation task. No rule has been empirically validated here.

### Source coverage

| Supplied rule | Covered by | Source |
|---|---|---|
| DD-1: local does not imply structural | B, E, N-2, P-1 | [D-DD-MSB-001] |
| DD-2: bullish responsible structural low | B, E, F, H, N-2 | [D-DD-MSB-001] |
| DD-3: bearish responsible structural high | B, E, F, H, N-2 | [D-DD-MSB-001] |
| DD-4: wick extremes | B, C, E, F, P-2 | [D-DD-MSB-001] |
| DD-5: wick crossing insufficient | F, G, H, O, P-3 | [D-DD-MSB-001] |
| DD-6: body-close break | G, H, O, P-4 | [D-DD-MSB-001] |
| DD-7: bullish protected low | B, F, H, N-4, P-6 | [D-DD-MSB-001] |
| DD-8: bearish protected high | B, F, H, N-4, P-6 | [D-DD-MSB-001] |
| DD-9: bullish invalidation | F, H, O, P-5 | [D-DD-MSB-001] |
| DD-10: bearish invalidation | F, H, O, P-5 | [D-DD-MSB-001] |
| DD-11: primary external structure | B, D, I, N-5 | [D-DD-MSB-001] |
| DD-12: internal movements | B, D, I, N-5 | [D-DD-MSB-001] |
| DD-13: internal break/range distinction | H, I, O, P-8 | [D-DD-MSB-001] |
| DD-14: HTF priority | K, L, O, P-10 | [D-DD-MSB-001] |
| DD-15: LTF confirmation/execution role | K, N-8, P-10 | [D-DD-MSB-001] |
| DD-16: external EQ / Premium / Discount | J, N-6, O, P-9 | [D-DD-MSB-001] |
| DD-17: ordinary HTF side blocks | K, N-8, O, P-10 | [D-DD-MSB-001] |
| DD-18: occurrence vs confirmation | E, L, N-1, N-7, P-11–13 | [D-DD-MSB-001] |
| DD-19: opposing movement, no fixed pivot | E, M, N-1, P-14 | [D-DD-MSB-001] |
| DD-20: acceptance vs liquidity rejection | G, M, N-10, O, P-3 | [D-DD-MSB-001] |
| DD-21: deferred break quality/rejection clues | M, N-9–N-10, L-8, P-16 | [D-DD-MSB-001] |

Deliverable boundary: this specification only. No Python source, strategy,
test, configuration or runtime behavior is changed. Resolve the core gates,
then obtain the next implementation instruction; stop before coding.
