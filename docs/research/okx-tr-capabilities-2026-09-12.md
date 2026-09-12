# OKX TR capability audit — 2026-09-12

User scope [U-OKX-CAP-001]; runtime connectivity evidence [E-OKX-CAP-001].
Branch: `work/okx-capabilities`.
Worktree: `C:/Users/Serdar Arif/Desktop/Agent Trading-okx`.
Base: `9d842077581f51b8264344fb331d1123665955e7`.
This is a capability research checkpoint, not a product/private-account integration.

## Verified result

- Connected OKX TR MCP: `okx-trade-mcp-server` **1.5.0**, `hasAuth=true`,
  `readOnly=false`, `demo=false`. Account, spot and all discovered Earn modules
  report enabled. That server state was pre-existing; no settings were changed.
- Trading balance, funding balance, account configuration, SPOT fees, BTC-USDT
  open orders, fills and pending trailing orders returned **code "0"**.
- Flexible Earn balance, fixed Earn orders, USDT personal lending history,
  lending-rate catalog, Flash Earn projects and active on-chain orders also
  returned **code "0"**. Empty private lists are successful reads, not evidence
  that those capabilities are missing.
- Trading balance exposed **USDT `autoLendStatus="off"`** and
  **`autoStakingStatus="unsupported"`**. USDT Auto Lend is supported but off;
  this does not establish staking support for other currencies. The TR balance
  documentation defines these Auto Lend states.
  [TR balance documentation](https://tr.okx.com/docs-v5/en/#trading-account-rest-api-get-balance)
- Simulated flexible-Earn read returned **code "50038"**, message
  **"This feature is unavailable in demo trading"**, despite `isError=false`.
  Never treat transport success or `isError=false` as business success.
- **Zero exchange write calls**: no orders, cancellations, amendments,
  transfers, Earn subscriptions/redemptions, rate changes or Auto Earn toggles.
  Application LIVE remains disabled. No personal amounts, UID, order identifiers,
  credentials or tokens are retained in this research.

[Machine-readable evidence and full discovered names](okx-tr-capabilities-2026-09-12.json)
retain call arguments, sanitized outcomes, local input schemas and runtime metadata.
These are connectivity/capability observations, not empirical strategy validation.

## Discovery surfaces and exact naming

| Surface | Actual discovery | Authentication / scope |
|---|---|---|
| Connected OKX TR | **165** callable session tools, prefix `mcp__okx_tr__`; runtime capability call confirms server 1.5.0 | Authenticated; non-simulated; write tools exposed but never called |
| Existing market-only desktop MCP | **21** tools, prefix `mcp__okx_trade_kit__`; server 1.4.6 | `hasAuth=false`, `readOnly=true`; all private modules `MODULE_FILTERED` |
| Fresh local SDK/MCP metadata probe | **31** actual `tools/list` results from pinned ATK 1.4.6; modules `account,spot,earn`, site `tr`, empty isolated home, `--read-only --no-log` | All 31 annotate read-only; private modules report `AUTH_MISSING / requires_auth` |
| CLI metadata catalog | Installed CLI 1.4.6, `list-tools --json` reports `totalTools=166` | Command catalog, not evidence of authenticated calls or the remote catalog |

The connected session catalog is the current callable runtime metadata supplied
to this task; no remote generic `tools/list` RPC or auth-status tool is exposed.
The local probe genuinely performs SDK `tools/list` and calls only
`system_get_capabilities`. Its temporary empty home was cleaned up.
A local-tool registration alone does not mean an authenticated account call works.

Important mismatches verified through discovery:

- `mcp__okx_tr__account_get_balance_all` is **absent** in this connected catalog,
  although bare `account_get_balance_all` exists in local 1.4.6 MCP.
- `mcp__okx_tr__earn_get_fixed_earn_products` is **absent** remotely, although
  the bare name exists locally. Remote `earn_get_lending_rate_history`
  advertises fixed offers together with rates; this audit does not prove its
  supplementary fixed-offer section was retrieved.
- CLI `okx earn auto-earn status` maps to **no standalone tool name**
  (`toolName=null`). Read Auto Earn flags through `account_get_balance`.
  No `earn_auto_get` or `earn_auto_status` exists in the connected catalog.
- Spot trailing uses **`spot_place_algo_order`** with
  **`ordType="move_order_stop"`**. There is no discovered
  `spot_place_move_stop_order`. CLI `okx spot algo trail` maps to that same
  generic spot algo tool.
- Remote private schemas require **`simulatedTrading`** on the tools that
  expose it. Local 1.4.6 schemas omit that field and use server configuration
  (`--demo`/profile). Follow each discovered schema, rather than copying args
  between the two servers.
- Deprecated remote `swap_place_move_stop_order` and
  `futures_place_move_stop_order` remain exposed. Their descriptions direct
  callers to generic `swap_place_algo_order` / `futures_place_algo_order`.
  Derivative placement/regional eligibility was not verified.

## Authentication requirements and observed result

Private reads need credentials for the **TR site/account**. A complete local
API-key credential consists of API key, secret key and passphrase. Its private
requests use `OK-ACCESS-KEY`, `OK-ACCESS-SIGN`, `OK-ACCESS-TIMESTAMP` and
`OK-ACCESS-PASSPHRASE`; signing uses Base64 HMAC-SHA256 over timestamp, method,
request path and body. API-key **Read** covers account/order history; **Trade**
covers placement/cancellation, transfers and settings. Read success cannot prove
Trade permission. [TR REST authentication](https://tr.okx.com/docs-v5/en/#overview-rest-authentication)

Local ATK 1.4.6 also supports OAuth device login through `okx-auth` and sends
`Authorization: Bearer <access-token>`. A complete API key takes precedence
without fallback after key-auth failure. OAuth must be selected for site `tr`;
CLI `config init` is an API-key wizard, not OAuth login.
[Official ATK authentication skill](https://raw.githubusercontent.com/okx/agent-trade-kit/github-main/skills/okx-cex-auth/SKILL.md)
The installed package's `applyAuth` and Earn handlers were inspected to
confirm these paths and distinguish public from private reads.

Observed status checks (exit 0):

| Context | Observed auth | Remaining blocker |
|---|---|---|
| Connected TR MCP 1.5.0 | `hasAuth=true`; 13 distinct read tools returned code "0" | Credential method and exact OAuth grant scopes are not exposed |
| Runtime `account_get_config` | `perm=""`, `acctLv="1"`, `posMode="net_mode"` | Empty permission field does not identify the grant or authorize trading |
| Local CLI 1.4.6 | No configured profiles/API key; OAuth `not_logged_in`; scopes null | `site="global"` is an unauthenticated placeholder, not a chosen TR site |
| Local isolated read-only MCP | `hasAuth=false`; account/spot/Earn `AUTH_MISSING` | No self-hosted private credentials; desktop connection is not inherited |
| Existing product market client | Public, empty home; fixed TR market/read-only config | Private account adapter/API is unimplemented and intentionally absent |

No login, upgrade, dependency installation, credential-store copying or grant
change was attempted. The exact granted OAuth scope identifiers for the remote
connection and minimum working scope set for each Earn endpoint remain
**unverified**. Any future integration must explicitly establish those grants;
neither server `hasAuth` nor the empty account `perm` field fills that gap.

Matrix auth labels:
**R** = authenticated private read; provision a Read-capable TR grant (exact
least-privilege grant acceptance untested).
**T** = authenticated write requiring trading/settings permission; not granted
by this task.
**P+R** = public rate-history request plus best-effort authenticated fixed-offer
read in inspected local 1.4.6 handler. Without authentication, rates may succeed
while supplementary offers are missing.
Flash Earn, on-chain offers and DCD catalogs use **private GET** in that package,
even when their tool input has no `simulatedTrading` field.

## Capability matrix

"Exposed" establishes a discovered TR server tool, not universal OKX TR
eligibility or successful execution. "Safe for demo" here means a hackathon
demonstration restricted to reads; it does not mean simulated Earn is available.
Account data should be visible only to its owner. All product private paths
remain unimplemented.

| Exact connected tool name | Read/write | Auth | OKX TR support | Verified live | Safe for demo | Blocker |
|---|---|---|---|---|---|---|
| `mcp__okx_tr__account_get_asset_balance` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_balance` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_bills` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_bills_archive` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_config` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_max_avail_size` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_max_size` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_max_withdrawal` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_positions` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_positions_history` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_get_trade_fee` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__account_set_position_mode` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__account_transfer` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__dcd_get_currency_pairs` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__dcd_get_order_state` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing; requires an existing ordId |
| `mcp__okx_tr__dcd_get_orders` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__dcd_get_products` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__dcd_redeem` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__dcd_subscribe` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__earn_auto_set` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified; changes account settings; 24h disable restriction |
| `mcp__okx_tr__earn_fixed_purchase` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__earn_fixed_redeem` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__earn_get_fixed_order_list` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__earn_get_flash_earn_projects` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__earn_get_lending_history` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__earn_get_lending_rate_history` | READ | P+R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__earn_get_savings_balance` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__earn_savings_purchase` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__earn_savings_redeem` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__earn_set_lending_rate` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__futures_place_algo_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__futures_place_move_stop_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__onchain_earn_cancel` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__onchain_earn_get_active_orders` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__onchain_earn_get_offers` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__onchain_earn_get_order_history` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__onchain_earn_purchase` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__onchain_earn_redeem` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__spot_amend_algo_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified; no trailing callback/activation amendment fields |
| `mcp__okx_tr__spot_amend_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__spot_batch_amend` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__spot_batch_cancel` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__spot_batch_orders` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__spot_cancel_algo_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__spot_cancel_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__spot_get_algo_orders` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__spot_get_fills` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__spot_get_order` | READ | R | Exposed on TR; availability untested | No (discovery only) | Read only; private display gated | Local private auth missing; requires an existing ordId/clOrdId |
| `mcp__okx_tr__spot_get_orders` | READ | R | Read succeeded on TR | Yes (read only) | Read only; private display gated | Local private auth missing |
| `mcp__okx_tr__spot_place_algo_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__spot_place_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__spot_set_leverage` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__swap_place_algo_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |
| `mcp__okx_tr__swap_place_move_stop_order` | WRITE | T | Exposed on TR; availability untested | No (discovery only) | No | Writes excluded; grant/execution unverified |

The two metadata tools `mcp__okx_tr__system_get_capabilities` and
`mcp__okx_trade_kit__system_get_capabilities` are READ, need no account credentials,
were called successfully, and are safe for discovery demonstrations.
All unrelated discovered market/news/bot/derivative names are preserved in JSON,
without suggesting those features are approved or verified.

## Earn and trailing limits

Auto Earn status is readable and USDT Auto Lend is off. The write tool
`earn_auto_set` accepts `ccy`, `action="turn_on"|"turn_off"`, optional
`earnType="0"|"1"` and remote `simulatedTrading`. Its description warns that
disabling is unavailable within 24 hours of enabling. No enable/disable
behavior or resulting yield was verified.

Flexible holdings, fixed orders and active on-chain orders are empty in the
connected account response. USDT personal lending history and BTC-USDT fills/
pending orders are empty within the requested filters. Flash projects returned
one row and USDT lending-rate history one row; this establishes catalog access,
not suitable investments, ongoing earnings, quota, APY guarantees or purchase
eligibility. No subscription preview/write was needed.

The spot placement schema advertises market/limit/post_only/fok/ioc and attached
TP/SL. Generic spot algo placement advertises conditional/OCO/trailing, with
`callbackRatio` or `callbackSpread` and optional `activePx`. TR documentation
requires one trailing callback representation and makes activation optional.
[TR algo-order documentation](https://tr.okx.com/docs-v5/en/#order-book-trading-algo-trading-post-place-algo-order)
Pending `move_order_stop` listing was verified; placement was not.
The discovered `spot_amend_algo_order` schema exposes size and TP/SL amendment
fields but **no** `newCallbackRatio`, `newCallbackSpread` or `newActivePx`.
Do not promise trailing-parameter amendments through that wrapper.

## Safe next integration step

Under a separate approved backend task, define a private, owner-only read
contract and adapter limited initially to `account_get_balance`,
`account_get_asset_balance` and `earn_get_savings_balance`. Read Auto Earn
flags from the balance response. Establish independent TR read authentication,
pin the target server/version and rediscover its schemas. Launch with
read-only tools and an explicit client allowlist; check both MCP failures and
nonzero exchange codes, preserve Decimal strings/UTC, and sanitize private logs.
Keep these observations separate from strategy decisions and all execution.

First prove application → authenticated read-only MCP → balance/Earn status
without expanding the public market client's isolated home or adding a generic
tool route. This audit adds no adapter, private HTTP endpoint, LIVE toggle or
exchange write client. Simulated Earn remains unavailable; an honest demo can
use owner-approved real-account reads or clearly labelled offline fixtures.

## Verification / stop

Baseline: 170 existing tests passed in this worktree, zero failures/errors.
The already configured backend virtual-environment interpreter was reused
read-only, with local working directory and bytecode disabled; no dependency or
other worktree change was needed. Final suite result is recorded in HANDOFF and
PROJECT_STATE after documentation verification.
Only research/shared-memory documents change in this task. Commit message:
`research: verify OKX account earn and execution capabilities`.
No merge, push, tag or integration work follows this checkpoint.
