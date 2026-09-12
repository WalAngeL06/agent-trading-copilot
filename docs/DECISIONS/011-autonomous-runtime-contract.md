# ADR 011 — Autonomous trading runtime and contract boundaries

Date: 2026-09-12. Status: accepted user direction; future runtime unimplemented.
Source: [U-AUTONOMOUS-CONTRACT-001].
Supersedes manual/timeframe framing of the intended product; preserves
[ADR 010](010-persisted-analysis-api.md)'s existing backend behavior and
[ADR 008](008-llm-decision-boundary.md)'s deterministic authority boundary.
Current wire correction: [Analysis API v0.2](../specs/analysis-api-v0.2.md).

## Context and decision

The final product is an autonomous trading agent. START BOT is the future
long-running entry point. Users configure permissions, risk and symbol scope;
an approved strategy profile determines required timeframe states.
The existing manual analysis endpoint remains useful for debugging, testing,
audit/demo and inspection. A display timeframe does not determine strategy inputs.

Future **AutonomousTradingRuntime** responsibilities:

1. Continuously obtain validated public ATK/API data and maintain independent
   closed-market state per symbol/timeframe.
2. Resolve the approved strategy profile's required timeframe collection.
3. Evaluate newly closed, causally available information according to a
   specified trigger/ordering; handle freshness and missing-state failures.
4. Avoid duplicate evaluations/candidates using a specified durable identity
   including symbol, profile/version, knowledge cutoff and relevant state.
5. Produce TradeCandidate or NO_SETUP only through an implemented approved
   deterministic strategy; preserve WAIT/BLOCKED reasons where supported.
6. Pass candidates through separate Acceptance; construct a deterministic
   Trade Plan for accepted candidates; pass that plan to separate Risk for
   approval. Risk does not supply missing strategy/plan rules.
7. Route approved plans by authorized execution mode; log/notify actual results.
8. Preserve original evidence, source/confirmation times and execution records.

These are interface responsibilities, not code, a polling algorithm, timer
frequency, storage lease or implemented duplicate-evaluation system.
Read failures are operational failures, never NO_SETUP or WAIT.
LLMs may explain/orchestrate validated reads but cannot override deterministic
prices, state, decisions, acceptance/risk or execution authorization.

## Conceptual execution modes

| Mode | Final-product semantics | Current state |
|---|---|---|
| ANALYZE | Produce deterministic analysis/candidate/plan when supported; no order | Current manual inspection is conceptually ANALYZE, with no configured strategy/plan |
| PAPER | Execute approved plans in a specified simulator, tracking simulated fills/positions | Unimplemented; existing SHADOW logs intent only and is not PAPER |
| LIVE | Send real exchange orders only with explicit enabled permissions/authorization and successful Acceptance/Risk | Disabled/unimplemented; no exchange write path, secret handling, account/order route or usable live toggle |

A configured external CLI/MCP account does not authorize application LIVE.
Current MVP remains public/read-only/intent-only. Conceptual long-term LIVE
support does not expand the present hackathon execution scope.

## Future decision model

Operational AnalysisReport status is distinct from the planned decision outcome:

| Outcome | Meaning when a future approved implementation supports it |
|---|---|
| NO_SETUP | Strategy evaluated sufficient valid inputs and found no supported setup |
| WAIT | A specified setup requires further causal confirmation; reasons/evidence identify it |
| TRADE_CANDIDATE | Strategy produced a candidate; no acceptance, risk approval or execution implied |
| BLOCKED | A supported candidate/plan is withheld by an explicit Acceptance/Risk/permission gate |
| EXECUTED | Actual execution evidence exists; identify PAPER versus LIVE and its real result |

These outcomes are reserved contract concepts, not current runtime enum values.
Current NO_TRADE / STRATEGY_NOT_CONFIGURED stays unchanged. COMPLETED means the
data/core/audit/persistence flow succeeded, not an established setup.
Acceptance/Risk placeholders cannot approve a plan. Partial execution and
rejected/cancelled fills require a future execution contract; this ADR supplies
no fill, sizing or PnL algorithm.

## Intelligence dependency and next step

**Causal Swing Engine** is the next trading-intelligence foundation:
Swing -> Market Structure -> Range -> Premium/Discount -> Deviation ->
Acceptance -> Trade Plan -> Risk -> Execution.
This is a dependency sequence, not new predicates or execution approval.

Next task: **SWING ENGINE R&D / SPEC**. Preserve [D-DD-MSB-001] and [U-PD-001].
Resolve observable opposing-movement confirmation, occurrence versus knowable
confirmation time, initialization/ties/retention and necessary cross-timeframe
ordering with source-labelled definitions and prefix-invariant fixtures.
ALGORITHMIC DEFINITION PENDING remains explicit. Do not substitute a generic
2/3/5-bar pivot, library defaults, ATR or retracement thresholds for DD semantics.
The complete MarketStructureEngine remains blocked by N-1–N-7.
No SwingEngine, structure/range/deviation, SMT/SSMT, Quarterly Theory or other
intelligence is implemented by this correction.

## Consequences and verification boundary

The current service receives a bounded configured timeframe collection and
new versioned reports expose that actual context. Default4H/1H/15m retains its
verified behavior. Original v0.1 SQLite history, existing routes/JSONL/CLI/MCP
and Decimal/UTC survive. No continuous runtime, scheduler, queue or WebSocket
is added. Future profile triggers, calendar bars, leases/deduplication,
simulation, permission policy and deployment need their own approved specs.

Wire versions use explicit schema discrimination and v0.2 consistency checks;
implementation references: [Pydantic discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions-with-str-discriminators)
and [model validators](https://docs.pydantic.dev/latest/concepts/validators/#model-validators).
Tests establish bounded contract compatibility/causality, not strategy or
profitability validation. Ch.1 remains incomplete.
