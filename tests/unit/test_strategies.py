"""Strategy unit tests."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd
import pytest

from trading_lab.strategies.base import Strategy
from trading_lab.strategies.rsi_mean_reversion import RSIMeanReversion


class _DummyStrategy(Strategy):
    """Minimal concrete strategy for base-class behaviour."""

    name = "dummy"
    default_params: ClassVar[dict[str, Any]] = {"k": 1}

    def validate_params(self) -> None:
        if int(self.params["k"]) <= 0:
            msg = "k must be positive"
            raise ValueError(msg)

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        pat = np.array([1, 0, -1], dtype=np.int8)
        vals = np.tile(pat, int(np.ceil(len(ohlcv) / 3)))[: len(ohlcv)]
        return pd.Series(vals, index=ohlcv.index, dtype=np.int8)


@pytest.fixture
def rsi_oversold_scenario_ohlcv() -> pd.DataFrame:
    """~100 günlük sentetik seri: keskin düşüş + toparlanma → RSI oversold ve yukarı kesişim."""
    idx = pd.date_range("2020-01-01", periods=100, freq="D", tz="UTC")
    rng = np.random.default_rng(42)
    # Önce güçlü düşüş (RSI çukuru), sonra toparlanma
    close = np.concatenate(
        [
            np.linspace(120.0, 72.0, 45),
            np.linspace(72.0, 118.0, 55),
        ],
    )
    noise = rng.normal(0.0, 0.35, size=len(close))
    close = np.maximum(close + noise, 1.0)
    open_px = np.roll(close, 1)
    open_px[0] = close[0]
    high = np.maximum(open_px, close) + rng.uniform(0.05, 0.6, size=len(close))
    low = np.minimum(open_px, close) - rng.uniform(0.05, 0.6, size=len(close))
    return pd.DataFrame(
        {"Open": open_px, "High": high, "Low": low, "Close": close},
        index=idx,
    )


def test_strategy_base_validates_params() -> None:
    with pytest.raises(ValueError, match="positive"):
        _DummyStrategy(params={"k": -1})


def test_strategy_base_signals_correct_index() -> None:
    idx = pd.date_range("2024-01-01", periods=7, freq="D", tz="UTC")
    ohlcv = pd.DataFrame({"close": range(7)}, index=idx)
    sig = _DummyStrategy().generate_signals(ohlcv)
    pd.testing.assert_index_equal(sig.index, ohlcv.index)


def test_strategy_base_signals_in_valid_range() -> None:
    idx = pd.date_range("2024-01-01", periods=12, freq="D", tz="UTC")
    ohlcv = pd.DataFrame({"close": np.linspace(1, 12, 12)}, index=idx)
    sig = _DummyStrategy().generate_signals(ohlcv)
    assert set(sig.unique().tolist()).issubset({-1, 0, 1})


def test_rsi_default_params() -> None:
    s = RSIMeanReversion()
    assert s.params == {
        "rsi_period": 14,
        "oversold": 30,
        "overbought": 70,
        "atr_stop_mult": 2.0,
    }


@pytest.mark.parametrize(
    "bad",
    [
        {"rsi_period": 1},
        {"oversold": 35, "overbought": 30},
        {"atr_stop_mult": 0.0},
    ],
)
def test_rsi_invalid_params_raise(bad: dict[str, Any]) -> None:
    base = dict(RSIMeanReversion.default_params)
    base.update(bad)
    with pytest.raises(ValueError):
        RSIMeanReversion(params=base)


def test_rsi_oversold_triggers_long(rsi_oversold_scenario_ohlcv: pd.DataFrame) -> None:
    strat = RSIMeanReversion()
    sig = strat.generate_signals(rsi_oversold_scenario_ohlcv)
    assert (sig == 1).any()


def test_rsi_signal_index_matches_input(rsi_oversold_scenario_ohlcv: pd.DataFrame) -> None:
    strat = RSIMeanReversion()
    sig = strat.generate_signals(rsi_oversold_scenario_ohlcv)
    pd.testing.assert_index_equal(sig.index, rsi_oversold_scenario_ohlcv.index)


def test_rsi_signal_values_long_only(rsi_oversold_scenario_ohlcv: pd.DataFrame) -> None:
    strat = RSIMeanReversion()
    sig = strat.generate_signals(rsi_oversold_scenario_ohlcv)
    assert set(sig.unique().tolist()).issubset({0, 1})
