# Product consolidation evidence

**Fresh 2026-09-16 follow-up supersedes the market FAIL/BLOCKED below:** all public
product-runtime layers and Dashboard CONNECTED now pass without runtime changes.
The original verification table is historical. The prior broad network-blocked
attribution is withdrawn. See [fresh diagnosis](fresh-atk-runtime-diagnosis.md).

2026-09-16, local Windows verification. Authority: [U-PRODUCT-CONSOLIDATION-001].

| Requested check | Result |
|---|---|
| Canonical frontend | C:/Users/Serdar Arif/Desktop/Agent Trading/src |
| Emergency dashboard removed | YES in canonical runtime; old source folders preserved |
| Frontend URL | http://localhost:5173 |
| Backend URL | http://localhost:8000 |
| Real backend wired | PASS |
| Strategy GET | PASS |
| Strategy SAVE | PASS |
| Persistence | PASS, page reload and actual backend process restart |
| Start Agent | PASS, backend-confirmed process lifecycle; live market feed blocked |
| Stop Agent | PASS, cancellation drains before restart/save |
| Settings locked while running | PASS, browser and HTTP 409 |
| OKX ATK live market | FAIL/BLOCKED, transport reset from tr.okx.com |
| Account | AUTH_MISSING; successful private read unverified |
| Lira Auto Earn | Status unavailable via API; no generic autoLend mapping |
| Frontend tests | 10 passed |
| Frontend production build | PASS |
| Python tests | 590 passed |
| README / root policy | Updated |
| Launcher | PASS; both services opened in separate visible windows |
| Push | Not performed |

## Implementation evidence

Backend tests cover domain timeframes, duplicate R levels, allocations, invalid
numbers, unsupported fields/modes, write-failure rollback, restart persistence,
real strategy consumption of configured roles, delayed higher-frame publication,
exact paper-ledger summaries, and repeated start/stop/settings-lock cycles.
Frontend tests cover backend read/write/readback, error propagation, state
refresh after actions, no default/browser fallback, and incompatible runtime
state rejection. Existing strategy/backtest tests were preserved.

Read-only code review identified cross-poll timeframe ordering and stale untouched
settings after another client's save. Both were fixed and verified. Trading
engine algorithms were imported unchanged from their existing implementation.

## Browser walkthrough

The existing terminal-style screens were visually preserved. Verified desktop
1280px and mobile 390px without horizontal overflow. Saved risk 0.75%, reloaded,
confirmed persistence, restarted the backend process, confirmed 0.75% again,
then restored 1.00%. Verified external settings changes refresh an untouched
form. Real Start/Stop actions and disabled Save while running passed.

Local screenshots are in ignored `output/playwright/`; logs in ignored `runs/`.
The main Python verification log is `runs/python-tests.txt`. Browser restart
produced expected temporary connection-refused errors while the backend was
intentionally offline; the UI recovered via polling. An initial favicon 404 was
fixed. No mock backend was used in the browser walkthrough.

## External integration evidence and limits

Pinned Python MCP SDK 2.2.0 and ATK 1.4.6 are installed and package-validated.
Actual public MCP process initialization and tool discovery succeed. A real
market_get_candles BTC-USDT/4H call returns NetworkError/MCP_TOOL_ERROR. An
independent Node fetch and PowerShell HTTPS request to tr.okx.com both fail with
connection reset (ECONNRESET). No successful live market result is claimed.
Start failure correctly yields STOPPED/ERROR and a failure activity event.

The canonical .env contains empty optional credentials and local URL defaults.
AUTH_MISSING is real; connected-account verification and Telegram delivery need
owner configuration. No exchange order/transfer/earn action was called.

## Source and Git preservation

Imported the committed product runtime at work/final-demo 1e4356f and strategy/
backtest at work/backtest-v1 baa77e9. Preserved the existing uncommitted UI design
by copying only Agent Trading-final-ui/src into the canonical src. Its original
files remain untouched. Did not import experimental uncommitted live-smoke code
from Agent Trading-final. Root branch remains strategy-v0.1. No worktrees were
created, repaired, pruned, moved or deleted; existing stale paths remain listed.

Pre-existing nested projects and user media folders remain untracked and outside
the requested consolidation commit. See HANDOFF for their list. The complete
working tree is therefore not clean, even though authored product work is committed.

## Settings API contract

GET and PUT `/api/v1/strategy/config` use `schemaVersion: strategy-config-v1`.
Wire fields match the UI: timeframes (bias/range/entry), entry (level and
secondaryFvgSupport), risk (riskPct/minimumRR), management (breakEvenEnabled=true,
breakEvenTriggerR, trailingEnabled/trailingBuffer), exits (partialTakeProfits
with id/rMultiple/closePct and runnerPct), executionMode=PAPER/profileId.
Financial values are strings. Domain rules come from StrategyProfile and
TimeframeRoles; percentages are converted with Decimal at the server boundary.
Extra fields are forbidden. PUT returns 422 for invalid values, 409 while running,
and 503 if persistence fails. GET exposes the last successful active settings.
Saved changes apply on next Start. config/strategy.json is atomically replaced;
an invalid existing file blocks startup rather than silently resetting it.
