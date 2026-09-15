"""Causal replay driver.

The only thing this module decides is the ORDER in which already-closed candles
are handed to the production `StrategyV1`. Every bias, range, manipulation,
entry, stop, break-even, trailing, partial and runner decision is made inside
the shipped strategy, which this engine never reimplements or overrides.
"""
from dataclasses import dataclass

from ..strategy_v1 import StrategyV1
from .dataset import load_dataset
from .metrics import compute, demo_card, funnel
from .recorder import equity_curve, record_trades


@dataclass(frozen=True)
class BacktestResult:
    config: object
    dataset: object
    strategy: StrategyV1
    trades: tuple
    curve: tuple
    summary: dict

    @property
    def events(self):
        return self.strategy.events

    def summary_document(self):
        return {'schema_version': 'strategy-v1-backtest-v0.1',
                'symbol': self.config.symbol,
                'label': self.config.label,
                'dataset': self.dataset.as_dict(),
                'costs': self.config.costs.as_dict(),
                'metrics': self.summary,
                'funnel': funnel(self.strategy),
                'demo': demo_card(self.config, self.dataset, self.summary),
                'limitations': list(self.strategy.report()['limitations'])
                               + ['REALISED_EQUITY_CURVE_ONLY',
                                  'COSTS_APPLIED_POST_HOC',
                                  'ONE_RANGE_ONE_SETUP_PER_RUN']}


def run(config, dataset=None):
    """Replay one frozen dataset through the production strategy."""
    dataset = dataset if dataset is not None else load_dataset(config)
    strategy = StrategyV1(config.symbol, config.profile)
    roles = config.timeframes
    previous = None
    for candle in dataset.candles(roles):
        # Ordering is asserted here, not trusted: the strategy also enforces it.
        key = (candle.close_time, roles.rank(candle.timeframe))
        if previous is not None and key < previous:
            raise ValueError('replay order regressed; dataset is not causal')
        previous = key
        strategy.process(candle)
    trades = record_trades(strategy, config.costs, config.symbol)
    opened = dataset.candles(roles)[0].close_time
    curve = equity_curve(trades, config.starting_equity, opened)
    summary = compute(strategy, trades, curve, config.starting_equity)
    return BacktestResult(config, dataset, strategy, trades, curve, summary)
