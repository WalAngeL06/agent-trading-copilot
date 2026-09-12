# 006 — Open-source and self-hosting first

- **Decision:** Design an open-source product that is easy to self-host locally
  or on a VPS. Telegram is optional; the deterministic core remains independently
  usable through application services/API and a normal browser. [U-PRODUCT-001]
- **Reason:** The approved copilot direction makes installation, ownership and
  useful web/API access first-class requirements rather than deployment extras.
- **Consequence:** Target one easy Docker Compose start command after explicit
  configuration, not necessarily one container. Plan persistent data, health
  checks, a clear `.env.example`, license/quickstart and READ-ONLY/SHADOW defaults.
  Avoid mandatory Telegram/LLM and unnecessary infrastructure. These are product
  requirements; no deployment files or product features are implemented by Ch.0.
- **Date:** 2026-09-12.
