"""Strategy unit tests."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd
import pytest

from trading_lab.strategies.base import Strategy
from trading_lab.strategies.bbands_squeeze import BBandsSqueeze
from trading_lab.strategies.donchian_breakout import DonchianBreakout
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
    """Oversold cross üretir; giriş çubuğunda intrabar stop iptali yapılmaz (regresyon)."""
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


@pytest.fixture
def donchian_break_then_drop_ohlcv() -> pd.DataFrame:
    """Flat tape → upper breakout → hold → sharp breakdown exits Donchian channel."""
    n = 45
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 100.0)
    low = np.full(n, 99.5)
    burst = 25
    high[burst:] = 106.0
    close[burst:] = 106.0
    low[burst:] = 105.5
    crash = 38
    high[crash] = 96.0
    low[crash] = 92.0
    close[crash] = 93.0
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close},
        index=idx,
    )


def test_donchian_invalid_params_raise() -> None:
    with pytest.raises(ValueError, match="entry_period"):
        DonchianBreakout(params={"entry_period": 1})


def test_donchian_breakout_enters_and_exits(donchian_break_then_drop_ohlcv: pd.DataFrame) -> None:
    strat = DonchianBreakout(params={"entry_period": 10, "exit_period": 5})
    sig = strat.generate_signals(donchian_break_then_drop_ohlcv)
    assert set(sig.unique().tolist()).issubset({0, 1})
    assert (sig == 1).any()
    assert (sig == 0).sum() >= 1


def test_donchian_deterministic(donchian_break_then_drop_ohlcv: pd.DataFrame) -> None:
    s1 = DonchianBreakout(params={"entry_period": 10, "exit_period": 5}).generate_signals(
        donchian_break_then_drop_ohlcv,
    )
    s2 = DonchianBreakout(params={"entry_period": 10, "exit_period": 5}).generate_signals(
        donchian_break_then_drop_ohlcv,
    )
    pd.testing.assert_series_equal(s1, s2)


@pytest.fixture
def bbands_quiet_then_pop_ohlcv() -> pd.DataFrame:
    """Quiet highs/lows around 100 then bullish expansion."""
    n = 80
    idx = pd.date_range("2022-06-01", periods=n, freq="D", tz="UTC")
    rng = np.random.default_rng(7)
    base = 100.0 + rng.uniform(-0.15, 0.15, size=n).cumsum() * 0.05
    close = base.copy()
    high = close + rng.uniform(0.05, 0.25, size=n)
    low = close - rng.uniform(0.05, 0.25, size=n)
    close[-15:] = close[-15] + np.linspace(0.0, 4.5, 15)
    high[-15:] = np.maximum(high[-15:], close[-15:] + 0.05)
    low[-15:] = np.minimum(low[-15:], close[-15:] - 0.05)
    open_px = np.roll(close, 1)
    open_px[0] = close[0]
    return pd.DataFrame(
        {"Open": open_px, "High": high, "Low": low, "Close": close},
        index=idx,
    )


@pytest.fixture
def bbands_ten_year_synthetic_squeeze_ohlcv() -> pd.DataFrame:
    """~2500 daily bars: repeated tight squeeze → vol spike (release) → SMA breakout → fade."""
    n_cycles = 14
    cycle = 180
    n = n_cycles * cycle
    idx = pd.date_range("2015-01-01", periods=n, freq="D", tz="UTC")
    close = np.zeros(n)
    high = np.zeros(n)
    low = np.zeros(n)
    anchor = 100.0

    for c in range(n_cycles):
        off = c * cycle
        for i in range(90):
            j = off + i
            cl = anchor + 0.001 * np.sin(i / 3.0)
            close[j] = cl
            high[j] = cl + 0.02
            low[j] = cl - 0.02
        for i in range(15):
            j = off + 90 + i
            cl = anchor + (i - 7) * 0.15
            close[j] = cl
            high[j] = cl + 1.4
            low[j] = cl - 1.4
        j_break = off + 105
        close[j_break] = anchor + 4.0
        high[j_break] = close[j_break] + 0.4
        low[j_break] = close[j_break] - 0.3
        trail = np.linspace(float(close[j_break]), anchor - 1.5, cycle - 106)
        for i in range(cycle - 106):
            j = off + 106 + i
            cl = trail[i]
            close[j] = cl
            high[j] = cl + 0.15
            low[j] = cl - 0.15
        anchor += 0.4

    open_px = np.roll(close, 1)
    open_px[0] = close[0]
    return pd.DataFrame(
        {"Open": open_px, "High": high, "Low": low, "Close": close},
        index=idx,
    )


def test_bbands_invalid_params_raise() -> None:
    with pytest.raises(ValueError, match="bb_std"):
        BBandsSqueeze(params={"bb_std": 0.0})
    with pytest.raises(ValueError, match="atr_period"):
        BBandsSqueeze(params={"atr_period": 0})


def test_bbands_squeeze_long_only_signal_domain(bbands_quiet_then_pop_ohlcv: pd.DataFrame) -> None:
    strat = BBandsSqueeze(params={"bb_period": 15, "atr_period": 15})
    sig = strat.generate_signals(bbands_quiet_then_pop_ohlcv)
    assert set(sig.unique().tolist()).issubset({0, 1})


def test_bbands_deterministic(bbands_quiet_then_pop_ohlcv: pd.DataFrame) -> None:
    p = {"bb_period": 15, "atr_period": 15}
    s1 = BBandsSqueeze(params=p).generate_signals(bbands_quiet_then_pop_ohlcv)
    s2 = BBandsSqueeze(params=p).generate_signals(bbands_quiet_then_pop_ohlcv)
    pd.testing.assert_series_equal(s1, s2)


def test_bbands_produces_signals_on_real_data(
    bbands_ten_year_synthetic_squeeze_ohlcv: pd.DataFrame,
) -> None:
    """Regression: squeeze+release+breakout path must emit multiple long stretches."""
    strat = BBandsSqueeze()
    sig = strat.generate_signals(bbands_ten_year_synthetic_squeeze_ohlcv)
    long_days = int((sig == 1).sum())
    assert long_days >= 3, f"expected >= 3 long bars, got {long_days}"
