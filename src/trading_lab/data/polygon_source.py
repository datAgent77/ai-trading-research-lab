"""Polygon.io aggregates with parquet caching."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pandas as pd
from polygon import RESTClient

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
from trading_lab.data.exceptions import DataSourceUnavailable

_TIMEFRAME_TO_POLYGON: Mapping[str, tuple[int, str]] = {
    "1d": (1, "day"),
    "1wk": (1, "week"),
    "1mo": (1, "month"),
}


def resolve_polygon_api_key(api_key: str | None) -> str:
    """Resolve API key from the argument, ``POLYGON_API_KEY``, or settings."""
    if api_key is not None:
        return api_key.strip()
    env_key = os.getenv("POLYGON_API_KEY", "").strip()
    if env_key:
        return env_key
    from trading_lab.config import get_settings

    return get_settings().polygon_api_key.strip()


def _agg_float(obj: object, field: str) -> float:
    raw = getattr(obj, field, None)
    return float(raw or 0.0)


def _aggs_to_frame(aggs: list[object]) -> pd.DataFrame:
    """Convert Polygon ``Agg`` objects to an OHLCV DataFrame (+ zero div/split cols)."""
    indices: list[pd.Timestamp] = []
    records: list[dict[str, float]] = []
    for a in aggs:
        ts = getattr(a, "timestamp", None)
        if ts is None:
            continue
        idx = pd.to_datetime(int(ts), unit="ms", utc=True).normalize()
        indices.append(idx)
        records.append(
            {
                "Open": _agg_float(a, "open"),
                "High": _agg_float(a, "high"),
                "Low": _agg_float(a, "low"),
                "Close": _agg_float(a, "close"),
                "Volume": _agg_float(a, "volume"),
            },
        )
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records, index=pd.DatetimeIndex(indices, name="timestamp"))
    frame.sort_index(inplace=True)
    frame["Dividends"] = 0.0
    frame["Stock Splits"] = 0.0
    frame.index.name = "timestamp"
    return normalize_index_utc(frame, daily=True)


def download_polygon_aggs(
    symbol: str,
    start: str,
    end: str,
    timeframe: str,
    *,
    api_key: str,
) -> pd.DataFrame:
    """Fetch aggregates from Polygon (patchable in tests)."""
    mult, span = _TIMEFRAME_TO_POLYGON[timeframe]
    client = RESTClient(api_key=api_key)
    aggs = client.get_aggs(symbol, mult, span, start, end, adjusted=True, sort="asc", limit=50000)
    return _aggs_to_frame(list(aggs))


def fetch_bars(
    symbol: str,
    start: str,
    end: str,
    timeframe: str = "1d",
    *,
    cache_dir: Path | str | None = None,
    api_key: str | None = None,
) -> pd.DataFrame:
    """Same contract as :func:`trading_lab.data.yfinance_source.fetch_bars`.

    Cached under ``{DATA_CACHE_DIR}/polygon/{symbol}_{timeframe}.parquet``.
    Polygon ``from`` / ``to`` dates are treated as **inclusive** calendar dates.
    """
    key = resolve_polygon_api_key(api_key)
    if not key:
        raise DataSourceUnavailable(
            "Polygon.io requires POLYGON_API_KEY (non-empty) or api_key=...; provider unavailable.",
        )

    if timeframe not in _TIMEFRAME_TO_POLYGON:
        supported = ", ".join(sorted(_TIMEFRAME_TO_POLYGON))
        msg = f"Unsupported timeframe {timeframe!r}; choose one of: {supported}"
        raise ValueError(msg)

    root = resolve_cache_directory(cache_dir)
    path = provider_cache_path(root, "polygon", symbol, timeframe)

    req_start = pd.Timestamp(start, tz="UTC").normalize()
    req_end = pd.Timestamp(end, tz="UTC").normalize()

    cached = read_parquet_if_exists(path)
    if cached is not None and cached.empty:
        cached = None

    segments = compute_missing_segments(cached, req_start, req_end)

    delta_frames: list[pd.DataFrame] = []
    for seg_start, seg_end in segments:
        start_s = seg_start.strftime("%Y-%m-%d")
        end_s = seg_end.strftime("%Y-%m-%d")
        part = download_polygon_aggs(symbol, start_s, end_s, timeframe, api_key=key)
        if not part.empty:
            delta_frames.append(part)

    delta = pd.concat(delta_frames) if delta_frames else pd.DataFrame()
    if not delta.empty:
        delta = delta[~delta.index.duplicated(keep="last")]
        delta.sort_index(inplace=True)

    merged = merge_ohlcv_frames(cached, delta)
    if not delta.empty:
        atomic_write_parquet(merged, path)

    return slice_inclusive(merged, req_start, req_end)


__all__ = ["download_polygon_aggs", "fetch_bars", "resolve_polygon_api_key"]
