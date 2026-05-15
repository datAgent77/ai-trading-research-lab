"""Bollinger squeeze breakout strategy (stub)."""

from __future__ import annotations

from typing import Any, ClassVar

import pandas as pd

from trading_lab.strategies.base import Strategy


class BBandsSqueezeStrategy(Strategy):
    """Volatility squeeze breakout using Bollinger and Keltner (not implemented yet)."""

    name = "bbands_squeeze"
    default_params: ClassVar[dict[str, Any]] = {}

    def validate_params(self) -> None:
        """Deferred until Stage 5."""

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Raise until Stage 5 implements logic."""
        raise NotImplementedError
