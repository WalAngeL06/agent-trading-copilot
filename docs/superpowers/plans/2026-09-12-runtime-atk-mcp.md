# Runtime ATK MCP Market Adapter Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline for this
> authorized backend target. All edits stay in its existing isolated worktree;
> one coherent commit follows the user's final verification gate.

**Goal:** Prove real public OKX TR data through Python product-runtime MCP.
**Architecture:** Add a transport adapter alongside the preserved CLI adapter.
Reuse candle normalization and add immutable live observation contracts. A lazy
SDK runtime context owns the pinned public-only child process and cleanup.
**Tech stack:** Python >=3.11, official mcp 2.2.0, installed ATK MCP 1.4.6, Node.
**Spec:** [runtime gate](../../specs/runtime-atk-mcp-gate.md).

## Global constraints

- `work/copilot-backend` only, descended from Ch.0 `24e1f465a886e2941a8ce2fce8fb51d53b643405`.
- site=tr, modules=market, read-only=true; no private environment/configuration.
- Decimal/UTC, closed candles, causal `as_of`, truthful sanitized provenance.
- Preserve CLI/core; deterministic tests cannot depend on SDK/network/Node.
- No other product/intelligence work; no merge/push/tag; stop after final commit.

## Task 1: Normalized MCP reads and discovery

Files: create `agent_trading/market_observations.py`, `agent_trading/okx_mcp.py`,
`tests/test_okx_mcp.py`.
Interfaces: `OkxMcpMarketAdapter(session, timeout=30, clock=...)`;
`await discover() -> tuple[str, ...]`; `await ticker(symbol)`;
`await candles(symbol, timeframe, limit, *, as_of, after=None)`;
`await orderbook(symbol, depth=5)` return `McpMarketRead(value, provenance)`.

- [x] Write fake-session tests for real envelope/request shapes, discovery,
  name/schema drift, exact values, causal filtering, errors and provenance.
  Representative assertion: `self.assertEqual(read.value[0].close, Decimal("101.1234567890123456789"))`
  for a closed Candle; live observations must retain their own `observed_at`.
- [x] Run `py -B -m unittest discover -s tests -p test_okx_mcp.py -v` and
  confirm failure because the adapter does not yet exist.
- [x] Implement strict envelope decoding, schema-checked allowlisted reads,
  existing candle normalization and new Decimal observation contracts.
  Numeric JSON decoding: `json.loads(text, parse_float=Decimal)`.
- [x] Rerun focused tests; resolve only evidenced failures.

## Task 2: SDK/process lifecycle and explicit smoke

Files: create `agent_trading/okx_mcp_runtime.py`, `agent_trading/mcp_smoke.py`,
`tests/test_atk_mcp_runtime.py`; modify `pyproject.toml` with optional
`runtime-mcp = ["mcp==2.2.0"]`.
Interface: `async with open_atk_mcp(...) as adapter` initializes, verifies
ATK server version, discovers tools and closes the session/process on exit.

- [x] Write deterministic lifecycle/launch tests using fake async contexts,
  including initialization timeout and cleanup after a consumer error.
- [x] Run focused tests and confirm the missing runtime implementation fails.
- [x] Implement package/path verification, fixed launch arguments, isolated
  public environment, lazy imports and the v2 Client context. Use
  `Client(stdio_client(parameters, errlog=errlog), read_timeout_seconds=timeout, cache=None)`.
- [x] Implement smoke using the same runtime adapter, a candle-only
  `MarketSnapshot`, and `json.dumps(to_jsonable(result))`; print fixed error
  categories on failure, exit nonzero, suppress raw errors.
- [x] Run focused tests, then the explicit real smoke with `.venv` Python.
  Diagnose interoperability failures without substituting CLI.

## Task 3: Evidence, review and completion

Files: `docs/runtime-atk-mcp-gate.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`,
`docs/HANDOFF.md`, `docs/NEXT_TASK.md`, `docs/SOURCE_REGISTRY.md`, README and ADR
007 only where their recorded state changes.

- [x] Record actual SDK/ATK versions, discovered tools and sanitized smoke
  evidence/outcome; mark only this gate VERIFIED or reproducibly BLOCKED.
- [x] Review all contracts and failure paths against the spec; verify no
  exchange writes and the CLI/core files have no changes.
- [x] Run `py -B -m unittest discover -s tests -v`, verify old/new counts,
  run `git diff --check`, and inspect the diff summary and changed-file list.
- [ ] Commit `feat: add runtime OKX ATK MCP market adapter` on the backend
  branch, verify clean status, report hash/evidence/debt, and stop.
