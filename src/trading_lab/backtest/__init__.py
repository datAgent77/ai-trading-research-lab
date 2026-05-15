"""Backtesting package."""

from trading_lab.backtest.engine import BacktestResult, backtest, save_backtest_result
from trading_lab.backtest.metrics import compute_metrics
from trading_lab.backtest.walk_forward import WalkForwardResult, WalkForwardSlice, walk_forward

__all__ = [
    "BacktestResult",
    "WalkForwardResult",
    "WalkForwardSlice",
    "backtest",
    "compute_metrics",
    "save_backtest_result",
    "walk_forward",
]
