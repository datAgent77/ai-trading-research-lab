"""Resolve OHLCV fetchers from settings (Yahoo vs Polygon)."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from trading_lab.config import Settings
from trading_lab.data.polygon_source import fetch_bars as polygon_fetch_bars
from trading_lab.data.yfinance_source import fetch_bars as yfinance_fetch_bars

BarsFetcher = Callable[..., pd.DataFrame]


def bars_fetcher_for_settings(settings: Settings) -> BarsFetcher:
    """Return a ``fetch_bars(symbol, start, end, timeframe=...)`` compatible callable."""
    if settings.data_provider == "polygon":

        def _polygon(
            symbol: str,
            start: str,
            end: str,
            timeframe: str = "1d",
        ) -> pd.DataFrame:
            return polygon_fetch_bars(symbol, start, end, timeframe=timeframe)

        return _polygon

    def _yfinance(
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        return yfinance_fetch_bars(symbol, start, end, timeframe=timeframe)

    return _yfinance


__all__ = ["BarsFetcher", "bars_fetcher_for_settings"]
