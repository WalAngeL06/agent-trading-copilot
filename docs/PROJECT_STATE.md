# Project state

Updated: 2026-09-12. Owner of this handoff: Codex. This file records current
facts; earlier foundation/Phase 1 reports are historical snapshots.

## Git / safe checkpoints

Current branch: **strategy-v0.1**.
Current HEAD: `667135804a30d8e998d3fc49f0fb2dce236f4a20`.

| Annotated checkpoint tag | Commit |
|---|---|
| foundation-v0.1 | `e4f2fdf6b4bb7dc2be1fd4912a342814c7c8f283` |
| shadow-foundation-v0.2 | `667135804a30d8e998d3fc49f0fb2dce236f4a20` |

Both tags are preserved. Phase 1 was accepted and committed. The current
strategy branch starts from v0.2. No remote or push exists. Documentation is
currently uncommitted; exact paths are listed in [HANDOFF](HANDOFF.md). Do not
treat these worktree-only docs as present in the checkpoint tag.

## Test status and invocation

Latest verified system checkpoint: **36 tests passing**. Fresh verification
after shared-memory setup on 2026-09-12: **36 tests passed, 0 failures/errors**
with `py -B -m unittest discover -s tests -v` (exit 0).
No Python, tests, dependencies or runtime configuration changed.
Infrastructure tests do not empirically validate DD strategy rules.

Full suite, project root:

```powershell
py -B -m unittest discover -s tests -v
```

On this Windows host the interpreter used in verified runs is:

```powershell
& 'C:\Users\Serdar Arif\AppData\Local\Programs\Python\Python314\python.exe' -B -m unittest discover -s tests -v
```

Python 3.11+ is the project's requirement; the path above is a host-specific
fallback, not a portable dependency. Linux/macOS can use `python3`.

## Implemented

- Deterministic incremental replay; Decimal prices/quantities and UTC times.
- Immutable MarketSnapshot and bounded symbol/timeframe-separated histories.
- Official OKX Agent Trade Kit public market-data CLI integration: allowlisted
  ticker, candles and orderbook reads; exact normalization and closed filtering.
- Real BTC-USDT historical bootstrap and configurable 4H / 1H / 15m MTF
  snapshot; bootstrap builds context without calling the decision chain.
- SHADOW mode, including bounded/continuous polling; intent-only execution.
- Detector / decision / acceptance / risk / execution placeholders; default
  NO_TRADE / STRATEGY_NOT_CONFIGURED → NO_ACTION.
- JSONL explainability/error logs, schema_version=2; logs ignored in `runs/`.
- Zero real-order path in the current application flow. External CLI/MCP tools
  can have separate trade permissions; those are not wired to this execution.

## Not implemented

- Real strategy or MarketStructureEngine.
- RangeDetector, DeviationDetector, ManipulationDetector, Momentum/Distribution.
- Real Acceptance rules or a production Risk model.
- Position Manager, live execution or fill/PnL accounting.
- Complete backtest framework or adaptive WindowScanner.
- Strategy-specific HTF/Premium/Discount context, comprehensive stale-data
  policy, automatic retry/backfill or WebSocket ingestion.

## Current strategy work and clarifications

[market-structure-v0.1](specs/market-structure-v0.1.md) exists as an uncommitted
formal draft. The 21 supplied DD rules are **source-confirmed**, not validated
by our own backtest/data. MarketStructureEngine is intentionally blocked by
N-1–N-7: swing confirmation, meaningful/responsible swings, initialization and
retention, protection/transitions, structural scale/boundaries, EQ inputs and
deterministic event/time representation. No algorithm was chosen to fill them.

**[U-PD-001] — confirmed user clarification:** Premium/Discount is
confirmation/context, not an independent entry trigger. EQ may react or be
crossed; reaction/reclaim is not automatically required. A specific approved
setup may define its own requirement. This clarification does not silently
remove DD's ordinary HTF Premium/Discount side blocks; Acceptance integration
still needs its own specification.

Market Structure is persistent derived state/context, not merely a boolean
pattern. This is a documented future design decision; the current Python
PatternResult API has not been replaced. BreakQuality / Deviation /
Manipulation are separate future specs. See [DECISIONS](DECISIONS/) and
[SOURCE_REGISTRY](SOURCE_REGISTRY.md).

## Source priority

1. Market Structure — initial draft exists; core decisions unresolved.
2. Range — **highest-priority next source-ingestion/specification task**.
3. Deviation.
4. Manipulation.
5. Momentum / Distribution.
6. Liquidity / Target.
7. Acceptance.
8. Risk.
9. Microstructure.

This setup task stops after documentation. [NEXT_TASK](NEXT_TASK.md) does not
authorize automatic strategy implementation or fabricated Range rules.

## Runtime evidence / known limits

Phase 1's actual ticker, 3-timeframe historical candle and orderbook probes
succeeded; account read via CLI lacked credentials. OAuth MCP login is separate
from CLI authentication. Those are historical results, not a fresh account
session check. Do not read credential stores to populate handoff docs.

[Phase 1 report](shadow-phase1.md) contains the smoke evidence. Local ignored
logs `runs/shadow-phase1-20260912.jsonl` and
`runs/shadow-poll-20260912.jsonl` demonstrate bootstrap/NO_TRADE/NO_ACTION with
100 closed candles per timeframe and zero orders. They are host-local evidence,
not files another checkout can assume are present. No PnL proof exists.

Public polling stops on malformed/missing required series, gaps or conflicting
retained closed candles; no automatic recovery or partial-candle semantics.
Fixed intraday bars are supported; calendar/session bars are not yet specified.
