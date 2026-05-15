"""Tests for parquet cache helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trading_lab.data.cache import (
    atomic_write_parquet,
    compute_missing_segments,
    merge_ohlcv_frames,
    normalize_index_utc,
    provider_cache_path,
    read_parquet_if_exists,
    resolve_cache_directory,
    slice_inclusive,
)


def test_resolve_explicit_cache_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATA_CACHE_DIR", raising=False)
    assert resolve_cache_directory(tmp_path) == Path(tmp_path)


def test_resolve_cache_dir_env_beats_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_CACHE_DIR", str(tmp_path))
    assert resolve_cache_directory(None) == Path(tmp_path)


def test_provider_cache_path_layout(tmp_path: Path) -> None:
    p = provider_cache_path(tmp_path, "yfinance", "BRK.B", "1d")
    assert p == tmp_path / "yfinance" / "BRK_B_1d.parquet"


def test_read_parquet_miss_returns_none(tmp_path: Path) -> None:
    assert read_parquet_if_exists(tmp_path / "missing.parquet") is None


def test_atomic_write_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], tz="UTC")
    df = pd.DataFrame({"Close": [1.0, 2.0]}, index=idx)
    df = normalize_index_utc(df, daily=True)
    atomic_write_parquet(df, path)
    loaded = read_parquet_if_exists(path)
    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, df)


def test_merge_dedupes_on_index() -> None:
    idx = pd.DatetimeIndex(["2024-01-03", "2024-01-04"], tz="UTC")
    a = pd.DataFrame({"Close": [1.0, 2.0]}, index=idx)
    b = pd.DataFrame({"Close": [9.0]}, index=pd.DatetimeIndex(["2024-01-04"], tz="UTC"))
    a = normalize_index_utc(a, daily=True)
    b = normalize_index_utc(b, daily=True)
    merged = merge_ohlcv_frames(a, b)
    assert merged.loc[pd.Timestamp("2024-01-04", tz="UTC"), "Close"] == 9.0


def test_compute_missing_segments_full_miss() -> None:
    rs = pd.Timestamp("2024-01-01", tz="UTC")
    re = pd.Timestamp("2024-01-05", tz="UTC")
    assert compute_missing_segments(None, rs, re) == [(rs, re)]


def test_compute_missing_segments_cache_hit() -> None:
    idx = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=5, tz="UTC"))
    cached = pd.DataFrame({"Close": range(len(idx))}, index=idx)
    cached = normalize_index_utc(cached, daily=True)
    rs = pd.Timestamp("2024-01-01", tz="UTC")
    re = pd.Timestamp("2024-01-05", tz="UTC")
    assert compute_missing_segments(cached, rs, re) == []


def test_compute_missing_segments_tail_gap() -> None:
    idx = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=3, tz="UTC"))
    cached = pd.DataFrame({"Close": [1, 2, 3]}, index=idx)
    cached = normalize_index_utc(cached, daily=True)
    rs = pd.Timestamp("2024-01-01", tz="UTC")
    re = pd.Timestamp("2024-01-05", tz="UTC")
    assert compute_missing_segments(cached, rs, re) == [
        (pd.Timestamp("2024-01-04", tz="UTC"), pd.Timestamp("2024-01-05", tz="UTC")),
    ]


def test_slice_inclusive() -> None:
    idx = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=10, tz="UTC"))
    df = pd.DataFrame({"Close": range(len(idx))}, index=idx)
    t0 = pd.Timestamp("2024-01-03", tz="UTC")
    t1 = pd.Timestamp("2024-01-05", tz="UTC")
    sub = slice_inclusive(df, t0, t1)
    assert len(sub) == 3


def test_yfinance_partial_cache_tail_fetch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Only the missing suffix range should be downloaded when the cache covers the head."""
    from trading_lab.data import cache as cache_mod
    from trading_lab.data import yfinance_source as yf_src

    path = cache_mod.provider_cache_path(tmp_path, "yfinance", "SPY", "1d")
    cache_mod.ensure_parent_dir(path)
    head_idx = pd.DatetimeIndex(
        [
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
        ],
        tz="UTC",
    )
    head = pd.DataFrame(
        {
            "Open": 1.0,
            "High": 1.0,
            "Low": 1.0,
            "Close": 1.0,
            "Volume": 1.0,
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        },
        index=head_idx,
    )
    head = normalize_index_utc(head, daily=True)
    cache_mod.atomic_write_parquet(head, path)

    calls: list[tuple[str, str]] = []

    def fake_download(symbol: str, start: str, end_exclusive: str, interval: str) -> pd.DataFrame:
        calls.append((start, end_exclusive))
        tail_idx = pd.DatetimeIndex(["2024-01-05", "2024-01-08"], tz="UTC")
        tail = pd.DataFrame(
            {
                "Open": [2.0, 3.0],
                "High": [2.0, 3.0],
                "Low": [2.0, 3.0],
                "Close": [2.0, 3.0],
                "Volume": [2.0, 3.0],
                "Dividends": [0.0, 0.0],
                "Stock Splits": [0.0, 0.0],
            },
            index=tail_idx,
        )
        return tail

    monkeypatch.setattr(yf_src, "download_yfinance_history", fake_download)

    out = yf_src.fetch_bars(
        "SPY",
        "2024-01-02",
        "2024-01-08",
        timeframe="1d",
        cache_dir=tmp_path,
    )

    assert calls == [("2024-01-05", "2024-01-09")]
    assert len(out) == 5
    assert out.index.tz is not None

