"""Causal Strategy V1 backtest: frozen data in, production strategy, artifacts out."""
from .config import BacktestConfig, CostModel
from .dataset import Dataset, load_dataset, load_stream, discover
from .engine import BacktestResult, run
from .metrics import compute, demo_card, funnel
from .recorder import TradeRecord, SliceRecord, EquityPoint, equity_curve, record_trades
from . import report

__all__ = ['BacktestConfig', 'CostModel', 'Dataset', 'load_dataset', 'load_stream',
           'discover', 'BacktestResult', 'run', 'compute', 'demo_card', 'funnel',
           'TradeRecord', 'SliceRecord', 'EquityPoint', 'equity_curve', 'record_trades',
           'report']
