"""Integration coverage for end-to-end backtests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_lab.backtest.engine import backtest
from trading_lab.strategies.rsi_mean_reversion import RSIMeanReversion


@pytest.fixture
def monkeypatched_yfinance_ohlcv(monkeypatch: pytest.MonkeyPatch) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=120, freq="D", tz="UTC")
    rng = np.random.default_rng(7)
    close = np.concatenate([np.linspace(100.0, 62.0, 55), np.linspace(62.0, 105.0, 65)])
    noise = rng.normal(0.0, 0.2, size=len(close))
    close = np.maximum(close + noise, 1.0)
    open_px = np.roll(close, 1)
    open_px[0] = close[0]
    high = np.maximum(open_px, close) + 0.5
    low = np.minimum(open_px, close) - 0.5
    frame = pd.DataFrame(
        {"Open": open_px, "High": high, "Low": low, "Close": close},
        index=idx,
    )

    def _fake_fetch(symbol: str, start: str, end: str, timeframe: str = "1d") -> pd.DataFrame:
        del symbol, start, end, timeframe
        return frame.copy()

    monkeypatch.setattr("trading_lab.backtest.engine.fetch_bars", _fake_fetch)
    return frame


def test_rsi_backtest_computes_metrics(monkeypatched_yfinance_ohlcv: pd.DataFrame) -> None:
    assert len(monkeypatched_yfinance_ohlcv) == 120
    result = backtest(
        RSIMeanReversion(),
        symbols=["SYN"],
        start="2020-01-01",
        end="2020-12-31",
        persist=False,
    )
    assert len(result.equity_curve) > 0
    expected_keys = {
        "sharpe",
        "sortino",
        "calmar",
        "max_dd",
        "total_return",
        "cagr",
        "win_rate",
        "profit_factor",
        "expectancy",
        "num_trades",
        "avg_trade",
        "avg_win",
        "avg_loss",
        "vs_buy_and_hold",
    }
    assert set(result.metrics.keys()) == expected_keys
    assert result.metrics["num_trades"] is not None
    assert int(result.metrics["num_trades"]) >= 0


def test_backtest_empty_price_window(monkeypatch: pytest.MonkeyPatch) -> None:
    def _empty_fetch(
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        del symbol, start, end, timeframe
        return pd.DataFrame()

    monkeypatch.setattr("trading_lab.backtest.engine.fetch_bars", _empty_fetch)
    result = backtest(
        RSIMeanReversion(),
        symbols=["SYN"],
        start="2025-01-01",
        end="2025-01-05",
        persist=False,
    )
    assert result.equity_curve.empty
    assert result.trades.empty
