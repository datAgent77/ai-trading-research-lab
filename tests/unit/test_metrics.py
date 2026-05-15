"""Performance metric unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_lab.backtest.metrics import compute_metrics


def test_compute_metrics_determinism() -> None:
    idx = pd.date_range("2024-01-01", periods=30, freq="D")
    equity = pd.Series(np.linspace(100.0, 105.0, 30), index=idx)
    trades = pd.DataFrame(
        {"pnl": [10.0, -3.0], "return_pct": [0.01, -0.002]},
    )
    first = compute_metrics(equity, trades)
    second = compute_metrics(equity, trades)
    assert first == second


def test_max_drawdown_known_curve() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    equity = pd.Series([100.0, 110.0, 99.0, 102.0], index=idx)
    trades = pd.DataFrame(columns=["pnl", "return_pct"])
    metrics = compute_metrics(equity, trades)
    expected_dd = 99.0 / 110.0 - 1.0
    assert metrics["max_dd"] is not None
    assert abs(float(metrics["max_dd"]) - expected_dd) < 1e-9


def test_win_rate_two_trades() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    equity = pd.Series([100.0, 101.0, 102.0], index=idx)
    trades = pd.DataFrame({"pnl": [5.0, -2.0], "return_pct": [0.05, -0.02]})
    metrics = compute_metrics(equity, trades)
    assert metrics["win_rate"] == 0.5


def test_sharpe_positive_for_upward_noisy_returns() -> None:
    rng = np.random.default_rng(1)
    idx = pd.date_range("2024-01-01", periods=120, freq="D")
    daily = rng.normal(0.002, 0.005, size=len(idx))
    equity = pd.Series(100 * np.cumprod(1 + daily), index=idx)
    trades = pd.DataFrame({"pnl": [1.0], "return_pct": [0.01]})
    metrics = compute_metrics(equity, trades)
    assert metrics["sharpe"] is not None
    assert float(metrics["sharpe"]) > 0.5
