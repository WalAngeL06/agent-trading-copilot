# OKX TR authenticated private reads v0.1

2026-09-12. Authority: [U-OKX-AUTH-001], explicit owner task and approved design.
Branch: `work/okx-auth`. Exact base: `adbafa485c900164c95ed0e13fce0d267da8b645`.
Uses the integrated [capability research](../research/okx-tr-capabilities-2026-09-12.md),
not Codex/Claude's connected account session.

## Hard boundary

Product Python -> pinned official MCP SDK `2.2.0` -> separately launched
official ATK MCP `1.4.6` -> authenticated OKX TR private GETs -> immutable
AccountSnapshot/EarnSnapshot. The existing public runtime stays unchanged and
credential-free. No HTTP/private endpoint, generic tool route, frontend wiring,
orders, Earn settings, transfers, purchases, redemptions, strategy/risk input,
autonomous bot or LIVE enablement is authorized or implemented here.

Exact client private-read allowlist (every invocation sends `{}`):

- `account_get_balance`: trading balances and per-currency Auto Earn flags.
- `account_get_asset_balance`: funding balances, no optional valuation request.
- `account_get_config`: account level, position mode and borrow settings.
- `earn_get_savings_balance`: Simple Earn flexible holdings only.

All other calls are rejected before transport. `tools/list` is discovery only;
even `system_get_capabilities` is not invoked. Server-discovered tools must
annotate read-only/non-destructive. Require all four exact names, bounded
pagination and pinned optional field schemas with no required arguments.
Only those four registrations are retained. No write tool can be invoked by
this client, including `earn_auto_set`.

## Owner configuration

Create/edit **`C:/Users/Serdar Arif/Desktop/Agent Trading-auth/.env`** locally,
using [.env.example](../../.env.example). Never paste credentials into chat.
Required exact fields:

```dotenv
OKX_API_KEY=
OKX_SECRET_KEY=
OKX_PASSPHRASE=
```

Provision an API key for the **TR account/site with Read permission only**;
do not grant Trade or Withdraw. Store the file with owner-only access on the
self-hosted machine. Environment values override file values, including empty
ones. Literal `KEY=VALUE`, whole-line comments and matching single/double quotes
are supported; no interpolation/escape expansion or shell execution. Duplicate
keys or malformed/unreadable files fail closed. Other valid env names are not
forwarded. `.env` and `.env.*` are ignored; `.env.example` alone is tracked.

No login wizard, OAuth token lookup, desktop session, CLI profile fallback or
credential-store copying. Missing/partial credentials stop before any process
starts. A complete key prevents ATK's OAuth branch from running. Child HOME,
USERPROFILE, APPDATA and LOCALAPPDATA are an empty temporary directory under
ignored `runs/`, removed after SDK process cleanup. Fixed TR URL/site, non-demo
account reads, `--modules account,earn --read-only --no-log` and disabled update
checks. Non-demo **reads do not enable LIVE execution**. No credential in argv.

Launch/configuration representations omit secrets. Raw child stderr is discarded;
ATK persistent logs are disabled. Exact pinned SDK stdio/client/dispatcher
logger records (including tracebacks, args and extras) are suppressed in the
private task context through shutdown; unrelated task logging is preserved.
Neither credentials, auth headers, raw provider errors nor raw responses are
written to JSONL, SQLite or product logs. The owner CLI intentionally displays
normalized **private financial data**; do not redirect/share that output publicly.

## Snapshots and failure contract

Terminal output is `{status,error_code,account,earn}`. `CONNECTED` means all
four normalized reads succeeded **and the child shut down successfully**.
`AUTH_MISSING` means incomplete local credentials or explicit provider auth
absence; `ERROR` includes bad auth (`AUTH_FAILED`), configuration, transport,
timeout, schema/scope drift and malformed responses. Only fixed categories
escape; never raw messages/suggestions/trace IDs/headers/UIDs. No retries or
write-suggested remediation. A valid account may be retained if the subsequent
savings read fails, but EarnSnapshot is null and overall status is ERROR.
Initialization/discovery/calls are individually bounded; SDK shutdown uses its
own bounded process cleanup. No promise of a single whole-workflow deadline.

Parse MCP text first without float conversion or duplicate JSON keys. Require
matching tool and endpoint, authenticated/read-only/non-demo capabilities and
success envelope. Reject nonzero business codes if surfaced even with
`is_error=false`; pinned ATK normally consumes REST codes before normalizing its
GET response. Its top-level `AuthenticationError` omits the numeric exchange
code, so it maps to fixed AUTH_FAILED. Domain validation rejects malformed
amounts, currencies, duplicate rows and future exchange timestamps.

AccountSnapshot contains separate trading/funding currency balances, total
trading equity (USD, **not all-account valuation**), selected configuration,
Auto Earn flags, UTC exchange/observation times and site. Decimal strings go
directly to Decimal and return as strings, never float. Inapplicable empty
numeric values become null, not zero. Borrow settings are observations, never
write authorization. Sequential GETs are not an atomic exchange snapshot;
observed_at records bundle normalization after the account reads, not a candle
decision cutoff. Funding/Earn have no fabricated exchange timestamp.

EarnSnapshot contains flexible savings amount/loan amount/rate/earnings when
provided, the account-derived Auto Earn states and their bundle observation
time. It does **not** claim fixed-term/on-chain/DCD holdings, APY guarantees or
investment eligibility. Successful empty lists are empty results, not missing
capabilities or proof of zero assets everywhere.

Auto Earn has **no standalone status tool in the researched toolkit**. Its source
is explicitly `account_get_balance.details`: `autoLendStatus` and
`autoStakingStatus`. Preserve `unsupported/off/pending/active`; absent, blank or
unrecognized fields are `UNKNOWN`, never assumed off. Only returned currencies
have status; balance may omit zero-balance currencies. See the
[official TR balance definitions](https://tr.okx.com/docs-v5/en/#trading-account-rest-api-get-balance)
and the integrated research for provenance/limits. Auto Earn is readable state,
not enablement or proof of earnings.

## Run and verification

From the auth worktree with the documented optional runtime dependencies:

```powershell
python -B -m agent_trading.account_read
```

Or specify `--env-file`, `--node-path`, `--server-path`, `--timeout`.
Portable dependencies remain `pip install -e '.[runtime-mcp]'`, Node and
`@okx_ai/okx-trade-mcp@1.4.6`; no auto-install/upgrade or CLI fallback.
On this host, the existing backend interpreter can be reused:

```powershell
& 'C:/Users/Serdar Arif/Desktop/Agent Trading-backend/.venv/Scripts/python.exe' -B -m agent_trading.account_read --env-file 'C:/Users/Serdar Arif/Desktop/Agent Trading-auth/.env'
```

Exit 0 only for CONNECTED; missing auth/error exits 1 with sanitized JSON.
Normal offline tests fake only the external SDK/process/network boundary and
retain real config, normalization and serialization. Real owner credentials
must be filled locally before a genuine successful private read can be proven.
No real owner key is available at this checkpoint; `.env` was not created.
The separate genuine product-runtime invalid-test-key probe returned
ERROR/AUTH_FAILED, not desktop-session success. Zero exchange write calls.
