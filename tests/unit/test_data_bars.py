"""Bars fetcher routing from settings."""

from __future__ import annotations

import pandas as pd
import pytest

from trading_lab.config import Settings
from trading_lab.data.bars import bars_fetcher_for_settings


def test_bars_fetcher_routes_to_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    monkeypatch.setenv("DATA_PROVIDER", "polygon")
    monkeypatch.setenv("POLYGON_API_KEY", "k")

    calls: list[str] = []

    def fake_polygon(
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        calls.extend([symbol, start, end, timeframe])
        return pd.DataFrame()

    monkeypatch.setattr("trading_lab.data.bars.polygon_fetch_bars", fake_polygon)
    fn = bars_fetcher_for_settings(Settings())
    fn("QQQ", "2024-01-01", "2024-06-01", timeframe="1d")
    assert calls == ["QQQ", "2024-01-01", "2024-06-01", "1d"]


def test_bars_fetcher_routes_to_yfinance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")

    calls: list[str] = []

    def fake_yf(
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        calls.extend([symbol, start, end, timeframe])
        return pd.DataFrame()

    monkeypatch.setattr("trading_lab.data.bars.yfinance_fetch_bars", fake_yf)
    fn = bars_fetcher_for_settings(Settings())
    fn("SPY", "2024-01-01", "2024-06-01")
    assert calls == ["SPY", "2024-01-01", "2024-06-01", "1d"]
