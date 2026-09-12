# 002 — SHADOW before live

- **Decision:** Validate strategy in SHADOW before enabling real execution;
  live execution requires explicit user authorization.
- **Reason:** Real-data reasoning and operational behavior need evidence before
  exposing funds. Data-pipeline tests alone do not validate a strategy.
- **Consequence:** Current execution stays disabled/intent-only. SHADOW does
  not provide fill/PnL proof; trading validation and authorization remain
  separate gates. OAuth/CLI permissions do not bypass them.
- **Date:** 2026-09-12.
