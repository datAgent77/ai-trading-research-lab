"""Integration coverage for end-to-end backtests (Stage 4)."""

from __future__ import annotations

import pytest

from trading_lab.backtest.engine import backtest
from trading_lab.strategies.rsi_mean_reversion import RSIMeanReversionStrategy


@pytest.mark.skip(reason="Engine not implemented until Stage 4")
def test_backtest_flow_placeholder() -> None:
    strat = RSIMeanReversionStrategy()
    backtest(strat, symbols=["SPY"], start="2020-01-01", end="2020-06-01")
