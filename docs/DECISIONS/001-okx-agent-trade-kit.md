# 001 — OKX Agent Trade Kit

- **Decision:** OKX Agent Trade Kit is the primary exchange integration layer.
- **Reason:** The user selected the official kit; Phase 1's public data path is
  already verified through its CLI. Avoid exchange coupling inside strategy.
- **Consequence:** Keep exchange normalization behind the adapter and prefer
  the kit before introducing alternative/native integrations. Current adapter
  remains public-read-only; broader CLI/MCP tools are not application features.
- **Date:** 2026-09-12.
