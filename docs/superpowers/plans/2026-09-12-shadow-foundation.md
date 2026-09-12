# Phase 1: real-market shadow foundation

Approved scope: the user's live-hackathon Phase 1 request. Work in the current
tree; preserve `foundation-v0.1`. Stop before implementing strategy rules.

1. Inspect installed Agent Trade Kit and smoke-test public ticker, candles on
   4H/1H/15m, older historical candles and order book; separately check account
   read without logging private responses.
2. Parse JSON numeric tokens directly as Decimal; test precise prices/volume.
3. Add immutable MarketSnapshot(symbol, as_of, histories) and a shared bounded
   history store. Validate closed candles, symbol/timeframe separation and
   causal ordering. Widen Detector.evaluate to snapshot; offer an explicit
   adapter for existing single-timeframe detectors.
4. Add a public-data-only CLI adapter: Node + installed official CLI,
   shell=False, allowlisted market operations, safe error messages. Normalize
   OKX opening timestamps to closing timestamps with fixed bar durations;
   reject malformed values and omit unconfirmed/future candles.
5. Bootstrap all configured series through the shared store without running
   detectors or execution. Log BOOTSTRAP_COMPLETE with counts/latest closes.
6. Run the unchanged decision/acceptance/risk placeholders against the final
   snapshot. Shadow execution only records WOULD_BUY/WOULD_SELL/NO_ACTION.
   No execution client, account credentials or order command exists in it.
7. Add bounded/continuous polling, detecting missed bars instead of silently
   accepting a gap. Default shadow example makes one evaluation and exits;
   optional cycles=0 runs until interrupted. Journal does not overwrite logs.
8. Verify focused causality, precision, bootstrap and execution tests; preserve
   existing replay behavior. Demonstrate real 3-timeframe bootstrap and
   NO_TRADE in an ignored JSONL artifact. Report limitations and stop.

No strategy thresholds, native REST/WebSocket connection, account integration,
real execution, new Git tag, commit or remote is part of this phase.
