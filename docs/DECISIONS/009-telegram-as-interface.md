# 009 — Telegram as an optional interface

- **Decision:** Telegram Bot/Mini App is an important UX channel, but the domain
  core must not depend on Telegram. Reuse one shared web frontend where practical.
  [U-PRODUCT-001]
- **Reason:** The copilot must remain useful to self-hosters, browser users, API
  clients and future agents without requiring a messaging platform.
- **Consequence:** Claude owns the thin bot/interface and shared Mini App/web UX;
  Codex owns application services/API. Define the shared API contract before
  parallel work. Keep identity/theme/launcher details at the interface boundary;
  validate Telegram identity server-side and plan reachable HTTPS. The initial
  UX has Analysis and History screens. No bot/frontend is implemented at Ch.0.
- **Date:** 2026-09-12.
