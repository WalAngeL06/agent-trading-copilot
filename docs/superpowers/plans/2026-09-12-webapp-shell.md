# Trading Web App Shell Implementation Plan

**Goal:** user-authorized two-screen local trading control shell.
**Architecture:** typed TradingControlApi injected into React; mock owns local
session bot state, bounded events and browser-only strategy storage.
**Tech Stack:** React/Vite/TypeScript; Node built-in tests.
**Spec:** docs/specs/webapp-shell-v0.1.md

Execute inline in work/webapp. Current detailed instruction authorizes the
design and final commit; keep process small and do not add approval pauses.

- [x] Write failing API tests: local start/stop, string risk/profile saves,
      invalid modules/risk, LIVE blocked, running-bot save blocked, storage
      error/corruption. Write Telegram fallback/init tests.
- [x] Implement src/types/control.ts; src/api/control.ts, validation.ts,
      mock.ts, index.ts; getDashboard/getStrategy/saveStrategy/startBot/stopBot
      promise methods. No backend networking or execution.
- [x] Implement src/telegram/webapp.ts; optional ready/expand and safe fallback.
- [x] Install React, Vite, TypeScript, React plugin and React type packages;
      add index.html, vite.config.ts and tsconfig.json. Generate lockfile.
- [x] Build reusable components, Dashboard, StrategySettings, App/main and
      mobile-first styles; validated save, dirty-navigation guard, LIVE modal.
- [x] Run npm test/build; mobile and desktop browser checks of navigation,
      start/stop, local persistence, unavailable modules and LIVE blocking.
- [x] Document exact integration contract gaps and update worktree state docs.
- [ ] Final commit and branch/clean verification follow this document freeze;
      report and stop. No merge/push/tag.
