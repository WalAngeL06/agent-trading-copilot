# Product consolidation

Authority: the user's PRODUCT CONSOLIDATION request, 2026-09-16.
This supersedes the old Ch.0 stop boundary for this task.

## Integration design

Use only the canonical root. Preserve nested folders and registered worktrees.
Import committed product code from work/final-demo (1e4356f), strategy and
backtest code/specs/tests from work/backtest-v1 (baa77e9), and the existing
working UI design from Agent Trading-final-ui/src. Preserve uncommitted work
in the source folders; do not import its experimental live exchange path.

React/Vite src → FastAPI → BotService → existing StrategyV1 → read-only ATK MCP.
PAPER only. The existing strategy profile owns all algorithm validation.
No new trading rules. Break-even stays enabled; only its trigger is editable.
No daily loss or max-position input, since no corresponding policy is enforced.

## Work sequence and checks

1. Establish baseline tests and consolidate the existing source into the root.
2. Add GET/PUT /api/v1/strategy/config with strict fields, decimal strings,
   engine validation and atomic config/strategy.json persistence. Serialize
   settings saves and lifecycle actions; reject saves while running.
   Test restart persistence, invalid values, unsupported settings, write failure.
3. Make BotService instantiate the persisted strategy, fetch all configured
   timeframes through MCP and process closed candles chronologically, highest
   timeframe first at equal close times. Stop and await task cleanup before
   accepting another start. Test configured roles and actual engine consumption.
4. Preserve the current UI design, connect config and runtime reads/actions,
   remove browser-only persistence and obsolete inputs, show real errors and
   refresh state. Keep Lira Auto Earn explicitly unavailable via API.
5. Replace embedded /dashboard with a redirect to WEBAPP_URL; document optional
   Telegram HTTPS setup. Add setup.ps1/run.ps1 and product README/root policy.
6. Run full Python suite, frontend tests/build, browser save/reload/restore,
   backend restart persistence and real MCP start/stop. Record actual evidence
   and blockers. Commit the requested message; no push in this task.

## Limits

Imported strategy hypotheses remain hypotheses. Passing tests and fresh market
reads establish integration, not profitability. Historical paper bootstrap is
identified in activity; no exchange orders are available. Backtest history is
preserved without inventing a WebApp backtest endpoint.
