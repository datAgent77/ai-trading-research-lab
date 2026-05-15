"""Bollinger squeeze breakout strategy (long-only).

Identifies low-volatility regimes where Bollinger bandwidth is narrow relative to Keltner
channel width. After the squeeze *releases* (bandwidth expands past the ratio threshold),
enters long on bullish breakout (close above the upper Bollinger band).

Exits when price falls back to the Bollinger middle band or when Bollinger width reaches or
exceeds Keltner width (volatility expansion exit).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd

from trading_lab.strategies.base import Strategy


def _normalize_ohlc_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.copy()
    renamed.columns = [str(c).strip().lower() for c in renamed.columns]
    required = {"high", "low", "close"}
    missing = required - set(renamed.columns)
    if missing:
        msg = f"ohlcv missing columns {sorted(missing)} after normalization"
        raise ValueError(msg)
    return renamed


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    n = len(close)
    tr = np.zeros(n)
    tr[0] = float(high[0] - low[0])
    for i in range(1, n):
        hl = float(high[i] - low[i])
        hc = abs(float(high[i] - close[i - 1]))
        lc = abs(float(low[i] - close[i - 1]))
        tr[i] = max(hl, hc, lc)
    return tr


def _wilder_step(previous_avg: float, value: float, period: int) -> float:
    return (previous_avg * (period - 1) + value) / period


def _atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Wilder ATR; first valid index ``period - 1`` (0-based)."""
    n = len(close)
    atr = np.full(n, np.nan)
    if n < period:
        return atr
    tr = _true_range(high, low, close)
    atr[period - 1] = float(tr[0:period].mean())
    for i in range(period, n):
        atr[i] = _wilder_step(float(atr[i - 1]), float(tr[i]), period)
    return atr


class BBandsSqueeze(Strategy):
    """Long-only squeeze release with bullish Bollinger breakout."""

    name = "bbands_squeeze"
    default_params: ClassVar[dict[str, Any]] = {
        "bb_period": 20,
        "bb_std": 2.0,
        "squeeze_pct": 0.5,
        "keltner_mult": 1.5,
    }

    def validate_params(self) -> None:
        bb_period = int(self.params["bb_period"])
        bb_std = float(self.params["bb_std"])
        squeeze_pct = float(self.params["squeeze_pct"])
        keltner_mult = float(self.params["keltner_mult"])

        if bb_period < 2:
            msg = "bb_period must be >= 2"
            raise ValueError(msg)
        if bb_std <= 0:
            msg = "bb_std must be > 0"
            raise ValueError(msg)
        if squeeze_pct <= 0:
            msg = "squeeze_pct must be > 0"
            raise ValueError(msg)
        if keltner_mult <= 0:
            msg = "keltner_mult must be > 0"
            raise ValueError(msg)

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        df = _normalize_ohlc_columns(ohlcv)
        idx = df.index
        period = int(self.params["bb_period"])
        bb_std = float(self.params["bb_std"])
        squeeze_pct = float(self.params["squeeze_pct"])
        k_mult = float(self.params["keltner_mult"])

        close = df["close"].astype(float)
        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        c = close.to_numpy(dtype=float)

        middle = close.rolling(period).mean()
        roll_std = close.rolling(period).std(ddof=0)
        upper_bb = middle + bb_std * roll_std
        lower_bb = middle - bb_std * roll_std
        bb_width = (upper_bb - lower_bb).abs()

        atr_arr = _atr_wilder(high, low, c, period)
        upper_k = middle.to_numpy(dtype=float) + k_mult * atr_arr
        lower_k = middle.to_numpy(dtype=float) - k_mult * atr_arr
        kc_width = upper_k - lower_k

        bb_w = bb_width.to_numpy(dtype=float)
        squeeze_ok = pd.Series(
            (bb_w <= squeeze_pct * kc_width) & ~np.isnan(kc_width) & ~np.isnan(bb_w),
            index=idx,
        )

        prev_sq = squeeze_ok.shift(1).fillna(False).astype(bool)
        released = prev_sq & (~squeeze_ok)

        signals = np.zeros(len(df), dtype=np.int8)
        position = 0

        for i in range(len(df)):
            mid = middle.iloc[i]
            ub = upper_bb.iloc[i]
            bw = bb_width.iloc[i]
            kw = kc_width[i]
            cl = float(close.iloc[i])

            if position == 0:
                rel = bool(released.iloc[i])
                if (
                    rel
                    and not np.isnan(ub)
                    and not np.isnan(cl)
                    and cl > float(ub)
                    and not np.isnan(kw)
                ):
                    position = 1
                    signals[i] = 1
                else:
                    signals[i] = 0
                continue

            exit_mid = not np.isnan(mid) and cl <= float(mid)
            exit_expand = not np.isnan(bw) and not np.isnan(kw) and bw >= kw
            if exit_mid or exit_expand:
                position = 0
                signals[i] = 0
            else:
                signals[i] = 1

        return pd.Series(signals, index=idx, dtype=np.int8, name="signal")


BBandsSqueezeStrategy = BBandsSqueeze

__all__ = ["BBandsSqueeze", "BBandsSqueezeStrategy"]
