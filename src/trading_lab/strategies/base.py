"""Abstract strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pandas as pd


class Strategy(ABC):
    """Deterministic trading strategy producing discrete position targets."""

    name: ClassVar[str]
    default_params: ClassVar[dict[str, Any]]

    params: dict[str, Any]

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        merged = {**type(self).default_params, **(params or {})}
        self.params = merged
        self.validate_params()

    @abstractmethod
    def validate_params(self) -> None:
        """Raise ``ValueError`` (or similar) when ``self.params`` is invalid."""

    @abstractmethod
    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Return targets aligned to ``ohlcv`` with values in ``{-1, 0, +1}``.

        Args:
            ohlcv: OHLCV bars indexed like the output series.

        Returns:
            Signed discrete position per bar (same index as ``ohlcv``).
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, params={self.params!r})"


__all__ = ["Strategy"]
