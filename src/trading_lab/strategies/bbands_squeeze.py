"""Bollinger squeeze breakout strategy (long-only).

Low-volatility regime when Bollinger bands lie **inside** Keltner channels (John Carter style).
``release`` is the first bar after a squeeze where that containment breaks. Long-only entries on
release when price confirms above the Bollinger middle band (SMA); exits when price falls back
below that middle band.
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


class BBandsSqueeze(Strategy):
    """Long-only squeeze release with SMA-confirmed breakout."""

    name = "bbands_squeeze"
    default_params: ClassVar[dict[str, Any]] = {
        "bb_period": 20,
        "bb_std": 2.0,
        "keltner_mult": 1.5,
        "atr_period": 20,
    }

    def validate_params(self) -> None:
        bb_period = int(self.params["bb_period"])
        bb_std = float(self.params["bb_std"])
        keltner_mult = float(self.params["keltner_mult"])
        atr_period = int(self.params["atr_period"])

        if bb_period < 2:
            msg = "bb_period must be >= 2"
            raise ValueError(msg)
        if bb_std <= 0:
            msg = "bb_std must be > 0"
            raise ValueError(msg)
        if keltner_mult <= 0:
            msg = "keltner_mult must be > 0"
            raise ValueError(msg)
        if atr_period < 1:
            msg = "atr_period must be >= 1"
            raise ValueError(msg)

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        df = _normalize_ohlc_columns(ohlcv)
        idx = df.index
        bb_period = int(self.params["bb_period"])
        atr_period = int(self.params["atr_period"])
        bb_std = float(self.params["bb_std"])
        k_mult = float(self.params["keltner_mult"])

        close = df["close"].astype(float)
        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        c = close.to_numpy(dtype=float)
        n = len(df)

        sma = close.rolling(bb_period).mean()
        std = close.rolling(bb_period).std(ddof=1)

        bb_upper = sma + bb_std * std
        bb_lower = sma - bb_std * std

        tr = _true_range(high, low, c)
        atr = pd.Series(tr, index=idx).rolling(atr_period).mean().to_numpy(dtype=float)

        sma_np = sma.to_numpy(dtype=float)
        bb_u = bb_upper.to_numpy(dtype=float)
        bb_l = bb_lower.to_numpy(dtype=float)

        kc_upper = sma_np + k_mult * atr
        kc_lower = sma_np - k_mult * atr

        finite = (
            np.isfinite(bb_u)
            & np.isfinite(bb_l)
            & np.isfinite(kc_upper)
            & np.isfinite(kc_lower)
            & np.isfinite(sma_np)
        )
        squeeze = finite & (bb_u < kc_upper) & (bb_l > kc_lower)

        release = np.zeros(n, dtype=bool)
        if n > 1:
            release[1:] = squeeze[:-1] & (~squeeze[1:])

        signals = np.zeros(n, dtype=np.int8)
        position = 0

        for i in range(n):
            sm = sma_np[i]
            cl = c[i]
            rel = bool(release[i])

            if not np.isfinite(sm) or not np.isfinite(cl):
                signals[i] = position
                continue

            if position == 0:
                if rel and cl > sm:
                    position = 1
                    signals[i] = 1
                else:
                    signals[i] = 0
            elif cl < sm:
                position = 0
                signals[i] = 0
            else:
                signals[i] = 1

        return pd.Series(signals, index=idx, dtype=np.int8, name="signal")


BBandsSqueezeStrategy = BBandsSqueeze

__all__ = ["BBandsSqueeze", "BBandsSqueezeStrategy"]
