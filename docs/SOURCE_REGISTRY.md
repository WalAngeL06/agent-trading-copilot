# Source registry

Updated: 2026-09-12. **Source and validation are separate concepts.** A source
ID identifies provenance; its confirmation status is not proof of performance.
Agent-authored summaries and external libraries do not become DD strategy truth.

| Source ID | Type | Topic | Status | Empirical Validation | Notes |
|---|---|---|---|---|---|
| [D-DD-MSB-001] | [D] DD Finance | Market Structure | SOURCE CONFIRMED | PENDING | User-attested 21 DD rules captured in [market-structure-v0.1](specs/market-structure-v0.1.md). Original DD recording/transcript is not in this repository; no independent source verification or own-data/backtest validation. N-1–N-7 unresolved. |
| [U-PD-001] | [U] User clarification | Premium / Discount | CONFIRMED PROJECT RULE | PENDING | Premium/Discount is context/confirmation, not an independent entry trigger. EQ reaction/reclaim is not mandatory unless a specific approved setup requires it. Separate from DD's ordinary side blocks; see [ADR 003](DECISIONS/003-premium-discount-context.md). |
| [R-OSS-001] | [R] External research | Open-source ecosystem review | RESEARCH REFERENCE | N/A | smart-money-concepts, Freqtrade, NautilusTrader, Backtesting.py, Lightweight Charts, Optuna, etc. Actionable summary: [open-source-notes](research/open-source-notes.md). Earlier broader [review](research/open-source-kaynak-taramasi-2026-09-12.md) is retained. Libraries are references, not strategy truth; no dependencies were added or framework compatibility/performance validated. |

Tag vocabulary: [D] DD Finance; [U] user hypothesis/clarification; [G] ChatGPT;
[C] Claude; [R] external research; [E] empirical validation evidence.

For future records, keep topic, source artifact/locator, confirmation status,
unresolved definitions and validation evidence distinct. A user hypothesis
stays a hypothesis until explicitly clarified/confirmed; do not automatically
give every [U] record CONFIRMED PROJECT RULE status. Record a supporting [E]
artifact and its methodology/limitations before asserting empirical validation.

No confirmed Range source is registered yet. The next task collects it; no
placeholder source ID here asserts that unreceived DD material was reviewed.
