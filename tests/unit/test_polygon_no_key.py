"""Polygon credential enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from trading_lab.data.exceptions import DataSourceUnavailable
from trading_lab.data.polygon_source import fetch_bars


def test_polygon_raises_when_api_key_missing(tmp_path: Path) -> None:
    with pytest.raises(DataSourceUnavailable, match="POLYGON_API_KEY"):
        fetch_bars(
            "SPY",
            "2024-01-02",
            "2024-01-08",
            timeframe="1d",
            cache_dir=tmp_path,
            api_key="",
        )


def test_polygon_raises_when_api_key_whitespace_only(tmp_path: Path) -> None:
    with pytest.raises(DataSourceUnavailable):
        fetch_bars(
            "SPY",
            "2024-01-02",
            "2024-01-08",
            timeframe="1d",
            cache_dir=tmp_path,
            api_key="   ",
        )
