"""Vectorbt-backed backtesting (stub)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from trading_lab.strategies.base import Strategy


@dataclass(frozen=True)
class BacktestResult:
    """Container for equity path, trades, and summary metrics."""

    equity_curve: pd.Series
    trades: pd.DataFrame
    metrics: dict[str, Any]
    params: dict[str, Any]
    meta: dict[str, Any]


def backtest(
    strategy: Strategy,
    symbols: list[str],
    start: str,
    end: str,
    initial_cash: float = 100_000,
    commission_bps: float = 1.0,
    slippage_bps: float = 2.0,
) -> BacktestResult:
    """Run a backtest (not implemented until Stage 4)."""
    raise NotImplementedError


__all__ = ["BacktestResult", "backtest"]
