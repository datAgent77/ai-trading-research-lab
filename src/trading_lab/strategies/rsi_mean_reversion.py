"""RSI mean reversion strategy (long-only).

Bu modül Wilder yumuşatmalı RSI ve ATR kullanır; harici ``ta`` kütüphanesi yoktur.

Implementation notes
--------------------
- **RSI**: İlk ortalama kazanç/kayıp, ilk ``rsi_period`` günlük fiyat değişiminin ortalamasıdır;
  sonrasında Wilder RMA: ``avg_t = (avg_{t-1} * (n-1) + x_t) / n``.
- **ATR**: True range üzerinde aynı Wilder yumuşatması; giriş **kapanışta** sayılır, stop giriş
  çubuğunda **kontrol edilmez** (mean reversion’da dip genelde o günün low’unda oluşur). Stop,
  girişten sonraki çubuklarda önce ``low <= stop``, sonra ``RSI > 50`` ile denetlenir.
- **Giriş filtresi**: Oversold yukarı kesişiminde ``RSI > 50`` ise (tek barda aşırı toparlanma)
  pozisyon açılmaz.
- **Long-only**: Pozisyon hedefi yalnızca ``0`` (nakit) veya ``+1`` (uzun); kısa satış yoktur.
- **OHLCV sütunları**: Yahoo kaynaklı büyük harf başlıklar küçük harfe normalize edilir.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd

from trading_lab.strategies.base import Strategy


def _wilder_step(previous_avg: float, value: float, period: int) -> float:
    return (previous_avg * (period - 1) + value) / period


def _rsi_wilder(close: np.ndarray, period: int) -> np.ndarray:
    """Wilder RSI; ilk geçerli değer indeksi ``period`` (0 tabanlı)."""
    n = len(close)
    rsi = np.full(n, np.nan)
    if n <= period:
        return rsi
    deltas = np.diff(close)
    gains = np.clip(deltas, 0.0, None)
    losses = np.clip(-deltas, 0.0, None)

    avg_g = float(gains[0:period].mean())
    avg_l = float(losses[0:period].mean())

    def _point(ag: float, al: float) -> float:
        if al == 0.0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    rsi[period] = _point(avg_g, avg_l)

    for bar in range(period + 1, n):
        avg_g = _wilder_step(avg_g, float(gains[bar - 1]), period)
        avg_l = _wilder_step(avg_l, float(losses[bar - 1]), period)
        rsi[bar] = _point(avg_g, avg_l)

    return rsi


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


def _atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Wilder ATR; ilk geçerli değer indeksi ``period - 1``."""
    n = len(close)
    atr = np.full(n, np.nan)
    if n < period:
        return atr
    tr = _true_range(high, low, close)
    atr[period - 1] = float(tr[0:period].mean())
    for i in range(period, n):
        atr[i] = _wilder_step(float(atr[i - 1]), float(tr[i]), period)
    return atr


def _normalize_ohlc_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.copy()
    renamed.columns = [str(c).strip().lower() for c in renamed.columns]
    required = {"open", "high", "low", "close"}
    missing = required - set(renamed.columns)
    if missing:
        msg = f"ohlcv missing columns {sorted(missing)} after normalization"
        raise ValueError(msg)
    return renamed


class RSIMeanReversion(Strategy):
    """Uzun yönlü RSI aşırı satım dönüşü + ATR stop + RSI > 50 çıkışı."""

    name = "rsi_mean_reversion"
    default_params: ClassVar[dict[str, Any]] = {
        "rsi_period": 14,
        "oversold": 30,
        "overbought": 70,
        "atr_stop_mult": 2.0,
    }

    def validate_params(self) -> None:
        rsi_period = int(self.params["rsi_period"])
        oversold = float(self.params["oversold"])
        overbought = float(self.params["overbought"])
        atr_stop_mult = float(self.params["atr_stop_mult"])

        if rsi_period < 2:
            msg = "rsi_period must be >= 2"
            raise ValueError(msg)
        if not (0 < oversold < overbought < 100):
            msg = "require 0 < oversold < overbought < 100"
            raise ValueError(msg)
        if atr_stop_mult <= 0:
            msg = "atr_stop_mult must be > 0"
            raise ValueError(msg)

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        df = _normalize_ohlc_columns(ohlcv)
        idx = df.index
        period = int(self.params["rsi_period"])
        oversold = float(self.params["oversold"])
        atr_stop_mult = float(self.params["atr_stop_mult"])

        close = df["close"].to_numpy(dtype=float)
        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)

        rsi_arr = _rsi_wilder(close, period)
        atr_arr = _atr_wilder(high, low, close, period)

        signals = np.zeros(len(df), dtype=np.int8)
        position = 0
        stop_price = np.nan

        for i in range(len(df)):
            r_now = rsi_arr[i]

            if position == 0:
                sig_here = 0
                if i > 0 and not np.isnan(r_now) and not np.isnan(rsi_arr[i - 1]):
                    prev_r = rsi_arr[i - 1]
                    if prev_r <= oversold and r_now > oversold:
                        atr_here = atr_arr[i]
                        if not np.isnan(atr_here):
                            if r_now > 50:
                                sig_here = 0
                            else:
                                stop_price = float(close[i]) - atr_stop_mult * float(atr_here)
                                position = 1
                                sig_here = 1

                signals[i] = sig_here
                continue

            # long — önce stop (intrabar low), sonra RSI çıkışı
            if not np.isnan(stop_price) and float(low[i]) <= stop_price:
                position = 0
                stop_price = np.nan
                signals[i] = 0
            elif not np.isnan(r_now) and r_now > 50:
                position = 0
                stop_price = np.nan
                signals[i] = 0
            else:
                signals[i] = 1

        return pd.Series(signals, index=idx, dtype=np.int8, name="signal")


RSIMeanReversionStrategy = RSIMeanReversion

__all__ = ["RSIMeanReversion", "RSIMeanReversionStrategy"]
