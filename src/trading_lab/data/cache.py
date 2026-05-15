"""Generic parquet helpers for OHLCV caches."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import pandas as pd

Provider = Literal["yfinance", "polygon"]


def safe_symbol_filename(symbol: str) -> str:
    """Return a filesystem-safe token for ``symbol``."""
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in symbol.strip())


def provider_cache_path(cache_root: Path, provider: Provider, symbol: str, timeframe: str) -> Path:
    """Parquet path ``{cache_root}/{provider}/{symbol}_{timeframe}.parquet``."""
    safe = safe_symbol_filename(symbol)
    rel = f"{safe}_{timeframe}.parquet"
    return cache_root / provider / rel


def resolve_cache_directory(cache_dir: os.PathLike[str] | str | None) -> Path:
    """Resolve cache root: explicit arg, ``DATA_CACHE_DIR`` env, else project default.

    Does not load full :class:`~trading_lab.config.Settings`, so data helpers work without
    IBKR variables (e.g. ad-hoc ``fetch_bars`` smoke tests).
    """
    if cache_dir is not None:
        return Path(cache_dir)
    env_dir = os.getenv("DATA_CACHE_DIR")
    if env_dir:
        return Path(env_dir)
    from trading_lab.config import DEFAULT_DATA_CACHE_DIR

    return Path(DEFAULT_DATA_CACHE_DIR)


def ensure_parent_dir(path: Path) -> None:
    """Create parent directories for ``path`` if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)


def read_parquet_if_exists(path: Path) -> pd.DataFrame | None:
    """Load parquet at ``path`` or return ``None`` if missing."""
    if not path.is_file():
        return None
    frame = pd.read_parquet(path)
    if frame.empty:
        return None
    return normalize_index_utc(frame)


def atomic_write_parquet(frame: pd.DataFrame, path: Path) -> None:
    """Atomically write ``frame`` to ``path`` (write temp + replace)."""
    ensure_parent_dir(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(tmp)
    os.replace(tmp, path)


def normalize_index_utc(frame: pd.DataFrame, *, daily: bool = True) -> pd.DataFrame:
    """Ensure a monotonic UTC DatetimeIndex named ``timestamp``."""
    if frame.empty:
        out = frame.copy()
        out.index.name = "timestamp"
        return out
    idx = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True))
    if daily:
        idx = idx.normalize()
    out = frame.copy()
    out.index = idx
    out.sort_index(inplace=True)
    out.index.name = "timestamp"
    return out


def merge_ohlcv_frames(existing: pd.DataFrame | None, delta: pd.DataFrame) -> pd.DataFrame:
    """Concatenate OHLCV frames on index, dropping duplicate timestamps (keep last)."""
    if existing is None or existing.empty:
        return delta.sort_index() if not delta.empty else delta
    if delta.empty:
        return existing.sort_index()
    merged = pd.concat([existing, delta])
    merged = merged[~merged.index.duplicated(keep="last")]
    merged.sort_index(inplace=True)
    merged.index.name = "timestamp"
    return merged


def compute_missing_segments(
    cached: pd.DataFrame | None,
    req_start: pd.Timestamp,
    req_end: pd.Timestamp,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return inclusive UTC date segments needed to cover ``[req_start, req_end]``.

    When cache is empty, returns a single segment for the full range. Otherwise returns
    disjoint segments before the cached minimum and/or after the cached maximum.
    """
    rs = pd.Timestamp(req_start).tz_convert("UTC").normalize()
    re = pd.Timestamp(req_end).tz_convert("UTC").normalize()
    if rs > re:
        msg = f"start {rs} must be on or before end {re}"
        raise ValueError(msg)
    if cached is None or cached.empty:
        return [(rs, re)]
    cmin = cached.index.min()
    cmax = cached.index.max()
    segments: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    if rs < cmin:
        seg_end = min(re, cmin - pd.Timedelta(days=1))
        if seg_end >= rs:
            segments.append((rs, seg_end))
    if re > cmax:
        seg_start = max(rs, cmax + pd.Timedelta(days=1))
        if seg_start <= re:
            segments.append((seg_start, re))
    return segments


def slice_inclusive(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Return rows with index between ``start`` and ``end`` inclusive (UTC normalized)."""
    if frame.empty:
        return frame.copy()
    rs = pd.Timestamp(start).tz_convert("UTC").normalize()
    re = pd.Timestamp(end).tz_convert("UTC").normalize()
    idx = frame.index
    mask = (idx >= rs) & (idx <= re)
    out = frame.loc[mask].copy()
    out.index.name = "timestamp"
    return out


__all__ = [
    "Provider",
    "atomic_write_parquet",
    "compute_missing_segments",
    "ensure_parent_dir",
    "merge_ohlcv_frames",
    "normalize_index_utc",
    "provider_cache_path",
    "read_parquet_if_exists",
    "resolve_cache_directory",
    "safe_symbol_filename",
    "slice_inclusive",
]
