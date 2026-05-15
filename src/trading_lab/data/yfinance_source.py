"""Yahoo Finance OHLCV downloads with parquet caching."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd
import yfinance as yf

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

_TIMEFRAME_TO_INTERVAL: Mapping[str, str] = {
    "1d": "1d",
    "1wk": "1wk",
    "1mo": "1mo",
}


def _normalize_yfinance_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Flatten optional MultiIndex columns and keep dividend / split fields."""
    out = frame.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.droplevel(1)
    for col in ("Dividends", "Stock Splits"):
        if col not in out.columns:
            out[col] = 0.0
    return out


def download_yfinance_history(
    symbol: str,
    start: str,
    end_exclusive: str,
    interval: str,
) -> pd.DataFrame:
    """Download raw history from Yahoo (used by ``fetch_bars``; patchable in tests)."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(
        start=start,
        end=end_exclusive,
        interval=interval,
        auto_adjust=False,
        actions=True,
    )
    return _normalize_yfinance_columns(hist)


def _daily(end_exclusive: pd.Timestamp) -> str:
    return end_exclusive.strftime("%Y-%m-%d")


def _fetch_segments_daily(
    symbol: str,
    segments: list[tuple[pd.Timestamp, pd.Timestamp]],
    interval: str,
) -> pd.DataFrame:
    """Fetch inclusive daily segments via Yahoo; ``end`` passed to Yahoo is exclusive."""
    chunks: list[pd.DataFrame] = []
    for seg_start, seg_end in segments:
        start_s = _daily(seg_start)
        end_exc = seg_end + pd.Timedelta(days=1)
        end_s = _daily(end_exc)
        raw = download_yfinance_history(symbol, start_s, end_s, interval)
        if raw.empty:
            continue
        chunks.append(normalize_index_utc(raw, daily=True))
    if not chunks:
        return pd.DataFrame()
    merged_chunks = pd.concat(chunks)
    merged_chunks = merged_chunks[~merged_chunks.index.duplicated(keep="last")]
    merged_chunks.sort_index(inplace=True)
    merged_chunks.index.name = "timestamp"
    return merged_chunks


def fetch_bars(
    symbol: str,
    start: str,
    end: str,
    timeframe: str = "1d",
    *,
    cache_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Load OHLCV (+ dividends / splits when present) with UTC DatetimeIndex.

    Bars are cached under ``{DATA_CACHE_DIR}/yfinance/{symbol}_{timeframe}.parquet``.
    When the cache partially covers the requested window, only missing leading/trailing
    ranges are downloaded and merged (typical incremental \"tail\" refresh).

    Yahoo's ``history`` API treats ``end`` as exclusive; ``end`` here is **inclusive**.
    """
    if timeframe not in _TIMEFRAME_TO_INTERVAL:
        supported = ", ".join(sorted(_TIMEFRAME_TO_INTERVAL))
        msg = f"Unsupported timeframe {timeframe!r}; choose one of: {supported}"
        raise ValueError(msg)
    interval = _TIMEFRAME_TO_INTERVAL[timeframe]

    root = resolve_cache_directory(cache_dir)
    path = provider_cache_path(root, "yfinance", symbol, timeframe)

    req_start = pd.Timestamp(start, tz="UTC").normalize()
    req_end = pd.Timestamp(end, tz="UTC").normalize()

    cached = read_parquet_if_exists(path)
    segments = compute_missing_segments(cached, req_start, req_end)

    delta = (
        _fetch_segments_daily(symbol, segments, interval)
        if segments
        else pd.DataFrame()
    )

    merged = merge_ohlcv_frames(cached, delta)
    if not delta.empty:
        atomic_write_parquet(merged, path)

    return slice_inclusive(merged, req_start, req_end)


__all__ = ["download_yfinance_history", "fetch_bars"]
