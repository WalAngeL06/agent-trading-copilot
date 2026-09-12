# Open-source notes — actionable conclusions

Source: [R-OSS-001]. Reviewed 2026-09-12. These are engineering judgments, not
DD rules or empirical strategy validation. The existing broader
[review](open-source-kaynak-taramasi-2026-09-12.md) is retained unchanged.

- **Keep our deterministic core.** The verified replay/MTF/SHADOW path remains
  the foundation; references do not require replacing it.
- **Use smart-money-concepts as an algorithm reference, not a DD-equivalent
  implementation.** Its documented swing method uses a configurable window
  before and after an extreme, while our genuine opposing-movement definition
  remains unresolved. [Primary repository/API](https://github.com/joshyattridge/smart-money-concepts).
- **Check swing/BOS/FVG labeling for look-ahead.** Separate occurrence from
  availability: documented swing windows look forward, FVG compares previous
  and next candles, and BrokenIndex/MitigatedIndex describe later events.
  Offline labels cannot be treated as then-known inputs without causal review.
  [Primary indicator definitions](https://github.com/joshyattridge/smart-money-concepts#indicators).
- **Use Freqtrade as a backtest/lookahead reference.** Its lookahead analysis
  compares baseline and sliced backtests for changed indicators/signals.
  Borrow the validation approach; this is not a claim that the tool already
  runs against our independent core. [Official lookahead documentation](https://docs.freqtrade.io/en/latest/lookahead-analysis/).
- **Use NautilusTrader as a longer-term event/account architecture reference,
  not a hackathon migration target.** Its event-driven engines and account,
  portfolio and execution separation are relevant to later state/accounting
  design. Deferring migration is our scope decision. [Official architecture](https://nautilustrader.io/docs/latest/concepts/architecture/).
- **Lightweight Charts may help visual validation.** A replay view could show
  wick occurrence, confirmed_at and then-visible HTF context. That is a
  proposed validation use, not an implemented UI or a detector. [Official chart library](https://tradingview.github.io/lightweight-charts/).
- **Optuna is for later parameter research, not defining missing semantics.**
  Its optimization/search-space tooling can explore approved parameterized
  hypotheses; it cannot make an optimized rule a confirmed DD definition.
  [Official optimization documentation](https://optuna.readthedocs.io/en/stable/).
- **Do not integrate new frameworks during the hackathon without a clear
  need.** No dependency, framework or runtime behavior is added by this note.
