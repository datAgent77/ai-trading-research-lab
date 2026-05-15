"""RSI mean reversion strategy (stub)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from trading_lab.strategies.base import Strategy


class RSIMeanReversionStrategy(Strategy):
    """Long-only mean reversion around RSI extremes (not implemented yet)."""

    name = "rsi_mean_reversion"

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Raise until Stage 3 implements logic."""
        raise NotImplementedError
