# Telegram trading control shell v0.1

Authority: current user instruction [U-WEBAPP-SHELL-001], 2026-09-12.
Worktree: Agent Trading-webapp; branch: work/webapp.
Base: 9d842077581f51b8264344fb331d1123665955e7.

Build only Dashboard and Strategy Settings with React/Vite/TypeScript.
This explicit instruction authorizes frontend work and local UI configuration,
including confirmed LIVE preview, without execution or trading algorithms.

Dashboard: local RUNNING/STOPPED, BTC-USDT, Sweep Reversal, labeled demo decision,
intended OKX ATK MCP source (disconnected), UNKNOWN Auto Earn, local activity.
Start/stop only change in-memory demo state. No polling, paper fills or trades.

Strategy: Sweep Reversal/Custom; four timeframe roles with 1m/5m/15m/30m/1H/4H;
six confirmation modules; percentage risk/daily loss and max open positions;
Swing Based/ATR Based/Off trailing; ANALYZE/PAPER/LIVE. Three module switches
configure the local preview only. Manipulation, Premium/Discount and Range
are disabled and labeled unavailable. All algorithms remain unintegrated;
preset/risk defaults are UI examples, not approved trading definitions.
LIVE has warning/confirmation and is always blocked at bot startup.

TradingControlApi is injected into components. Mock saves only validated
strategy config in localStorage; session status/events reset on reload.
Storage errors are shown. Financial/risk fields remain strings.
Existing analysis-v0.2 semantics are unchanged; the current backend
NO_TRADE/STRATEGY_NOT_CONFIGURED must never be mapped to NO SETUP.

Telegram: official optional WebApp SDK, detection/ready/expand, CSS safe area;
browser fallback. No authentication, identity storage, bot or credentials.

Design: graphite #101214, panel #191c20, raised #22262b, text #f1f3f5,
muted #a3abb5; restrained mint/amber/red. System Segoe UI, left alignment.
Mobile 390x844 primary; desktop two columns. No chart/gradients.
Native labeled controls, keyboard focus, busy/error feedback, dirty-navigation
guard and focus-managed confirmation dialog.

Verify npm install/build, small Node tests for API gates/validation/storage/
Telegram fallback, mobile/desktop browser flows. Only requested final commit;
no merge/push/tag. No edits outside this worktree.
