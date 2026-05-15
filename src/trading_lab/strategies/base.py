"""Abstract strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class Strategy(ABC):
    """Deterministic trading strategy producing discrete signals."""

    name: str
    params: dict[str, Any]

    @abstractmethod
    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Return a ``Series`` aligned to ``ohlcv`` with values in ``{-1, 0, +1}``.

        Args:
            ohlcv: OHLCV bars indexed by timestamp.

        Returns:
            Signed discrete position targets per bar.
        """
        raise NotImplementedError
