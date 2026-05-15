"""Donchian channel breakout strategy (long-only).

Trading idea: go long when price closes above the highest high of the prior ``entry_period``
sessions; exit when price closes below the lowest low of the prior ``exit_period`` sessions.
Levels use shifted rolling windows to avoid lookahead.

Volatility-targeting parameters ``risk_per_trade`` and ``atr_stop_mult`` are validated and
documented for execution sizing; the vectorbt backtest engine currently allocates full cash per
entry like other long-only strategies in this lab.
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


class DonchianBreakout(Strategy):
    """Long-only Donchian breakout with independent entry and exit channel lengths."""

    name = "donchian_breakout"
    default_params: ClassVar[dict[str, Any]] = {
        "entry_period": 20,
        "exit_period": 10,
        "atr_period": 20,
        "risk_per_trade": 2_000.0,
        "atr_stop_mult": 2.0,
    }

    def validate_params(self) -> None:
        entry_period = int(self.params["entry_period"])
        exit_period = int(self.params["exit_period"])
        atr_period = int(self.params["atr_period"])
        risk_per_trade = float(self.params["risk_per_trade"])
        atr_stop_mult = float(self.params["atr_stop_mult"])

        if entry_period < 2:
            msg = "entry_period must be >= 2"
            raise ValueError(msg)
        if exit_period < 2:
            msg = "exit_period must be >= 2"
            raise ValueError(msg)
        if atr_period < 2:
            msg = "atr_period must be >= 2"
            raise ValueError(msg)
        if risk_per_trade <= 0:
            msg = "risk_per_trade must be > 0"
            raise ValueError(msg)
        if atr_stop_mult <= 0:
            msg = "atr_stop_mult must be > 0"
            raise ValueError(msg)

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        df = _normalize_ohlc_columns(ohlcv)
        idx = df.index
        ep = int(self.params["entry_period"])
        xp = int(self.params["exit_period"])

        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)

        entry_bound = high.rolling(ep).max().shift(1)
        exit_bound = low.rolling(xp).min().shift(1)

        signals = np.zeros(len(df), dtype=np.int8)
        position = 0

        for i in range(len(df)):
            eb = entry_bound.iloc[i]
            xb = exit_bound.iloc[i]
            c = float(close.iloc[i])

            if position == 0:
                if not np.isnan(eb) and not np.isnan(xb) and c > eb:
                    position = 1
                    signals[i] = 1
                else:
                    signals[i] = 0
                continue

            if not np.isnan(xb) and c < xb:
                position = 0
                signals[i] = 0
            else:
                signals[i] = 1

        return pd.Series(signals, index=idx, dtype=np.int8, name="signal")


DonchianBreakoutStrategy = DonchianBreakout

__all__ = ["DonchianBreakout", "DonchianBreakoutStrategy"]
