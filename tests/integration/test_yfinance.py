"""Recorded Yahoo Finance integration coverage.

`vcrpy` cannot replay Yahoo traffic because modern ``yfinance`` uses ``curl_cffi``, not
``urllib3``/``requests``. Instead we replay a frozen parquet snapshot captured from a live
``download_yfinance_history`` pull (see ``fixtures/yfinance_spy_week.parquet``).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trading_lab.data.yfinance_source import fetch_bars

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "yfinance_spy_week.parquet"


def test_fetch_spy_week_recorded_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorded = pd.read_parquet(FIXTURE)
    calls: list[int] = []

    def fake_download(symbol: str, start: str, end_exclusive: str, interval: str) -> pd.DataFrame:
        calls.append(1)
        assert symbol == "SPY"
        assert interval == "1d"
        del start, end_exclusive
        return recorded.copy()

    monkeypatch.setattr(
        "trading_lab.data.yfinance_source.download_yfinance_history",
        fake_download,
    )

    df = fetch_bars("SPY", "2024-01-02", "2024-01-08", timeframe="1d", cache_dir=tmp_path)

    assert df.index.tz is not None
    assert len(df) == len(recorded)
    df2 = fetch_bars("SPY", "2024-01-02", "2024-01-08", timeframe="1d", cache_dir=tmp_path)

    assert sum(calls) == 1
    pd.testing.assert_frame_equal(df, df2)

