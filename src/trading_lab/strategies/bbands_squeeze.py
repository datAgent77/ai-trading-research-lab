"""Bollinger squeeze breakout strategy (stub)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from trading_lab.strategies.base import Strategy


class BBandsSqueezeStrategy(Strategy):
    """Volatility squeeze breakout using Bollinger and Keltner (not implemented yet)."""

    name = "bbands_squeeze"

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Raise until Stage 5 implements logic."""
        raise NotImplementedError
