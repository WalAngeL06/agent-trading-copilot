# 007 — ATK MCP in the actual product runtime

- **Decision:** The product backend must use real OKX Agent Trade Kit / MCP.
  Codex/Claude development-tool MCP access does not count as product integration.
  [U-PRODUCT-001]
- **Reason:** Runtime MCP is mandatory under the approved product direction and
  the 20% ATK integration criterion. The existing verified application adapter
  uses the official ATK CLI; that is not evidence of product-runtime MCP.
- **Consequence:** First validate application → MCP client → toolkit → actual
  ticker, 4H/1H/15m candles and orderbook → normalized core input in Ch.1. Prefer
  market-only, read-only TR public reads independent of desktop OAuth. Preserve
  CLI foundation evidence; label any fallback transport honestly. No adapter,
  dependency installation or real-data MCP smoke is performed by this closure.
- **Date:** 2026-09-12.
