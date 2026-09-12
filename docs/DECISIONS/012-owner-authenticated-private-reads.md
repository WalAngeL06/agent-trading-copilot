# ADR 012 — separate owner-authenticated private read runtime

2026-09-12. Accepted for [U-OKX-AUTH-001] only on work/okx-auth.

## Context

Integrated OKX TR research distinguishes connected desktop account access from
product-runtime credentials. The public MCP runtime intentionally launches in
an empty home and has no private auth. Reusing a desktop session would not be
self-hosted authentication; widening public analysis could leak account data.

## Decision

Keep public analysis unchanged. Add a separate owner-local product read command
and function using the pinned SDK/ATK, literal owner env authentication and an
isolated temporary home. Server read-only mode plus the client's exact four-tool
allowlist enforce the approved balance/funding/config/savings GET boundary.
No generic dispatch route, private HTTP endpoint or persistent financial log.
Normalize immutable Decimal/UTC AccountSnapshot/EarnSnapshot and fixed terminal
CONNECTED/AUTH_MISSING/ERROR. Suppress raw child and SDK private diagnostics.

Auto Earn is observed only from balance currency flags, not a fabricated status
tool or any enable/disable operation. Flexible savings holdings do not imply a
complete Earn portfolio. Unknown flags/inapplicable values remain unknown/null.

## Consequences

Owner must provide a Read-only TR key, secret and passphrase locally. Current
real owner success remains blocked by missing credentials; invalid-key runtime
failure and offline normalized success are verified separately. No desktop
fallback, OAuth enrollment, exchange write client, LIVE authorization, account
API/UI integration or full portfolio management is introduced. Future private
web display requires separately approved owner access controls.

Authoritative [setup/state contract](../specs/okx-private-read-v0.1.md).
