"""Donchian breakout strategy (stub)."""

from __future__ import annotations

from typing import Any, ClassVar

import pandas as pd

from trading_lab.strategies.base import Strategy


class DonchianBreakoutStrategy(Strategy):
    """Donchian channel breakout (not implemented yet)."""

    name = "donchian_breakout"
    default_params: ClassVar[dict[str, Any]] = {}

    def validate_params(self) -> None:
        """Deferred until Stage 5."""

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Raise until Stage 5 implements logic."""
        raise NotImplementedError
