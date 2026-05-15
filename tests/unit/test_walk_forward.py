"""Walk-forward harness tests."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from trading_lab.backtest.engine import BacktestResult
from trading_lab.backtest.walk_forward import walk_forward
from trading_lab.strategies.donchian_breakout import DonchianBreakout


def _dummy_result(end_day: str) -> BacktestResult:
    idx = pd.date_range(end_day, periods=2, freq="D", tz="UTC")
    eq = pd.Series([100.0, 100.0], index=idx)
    return BacktestResult(
        equity_curve=eq,
        trades=pd.DataFrame(),
        metrics={"total_return": 0.0},
        params={},
        meta={},
    )


def test_walk_forward_runs_is_then_oos_per_slice() -> None:
    """Each slice triggers two ``backtest`` calls with inclusive Yahoo-style dates."""
    pair_dates: list[tuple[str, str]] = []

    def fake_backtest(
        strategy: object,
        symbols: object,
        start: str,
        end: str,
        **_: object,
    ) -> BacktestResult:
        pair_dates.append((start, end))
        return _dummy_result(end)

    with patch("trading_lab.backtest.walk_forward.backtest", side_effect=fake_backtest):
        wf = walk_forward(
            DonchianBreakout(),
            ["SPY"],
            "2020-01-01",
            "2022-12-31",
            in_sample_months=12,
            out_sample_months=6,
            step_months=6,
        )

    assert len(wf.slices) >= 1
    assert len(pair_dates) == len(wf.slices) * 2
    assert wf.meta["num_slices"] == len(wf.slices)


def test_walk_forward_returns_empty_when_range_too_short() -> None:
    def boom(*_: object, **__: object) -> BacktestResult:
        raise AssertionError("backtest should not run")

    with patch("trading_lab.backtest.walk_forward.backtest", side_effect=boom):
        wf = walk_forward(
            DonchianBreakout(),
            ["SPY"],
            "2020-01-01",
            "2020-03-01",
            in_sample_months=24,
            out_sample_months=6,
        )

    assert wf.slices == ()
    assert wf.meta["num_slices"] == 0
