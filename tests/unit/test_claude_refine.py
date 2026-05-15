"""Refinement orchestration with mocked Claude + backtest."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from trading_lab.backtest.engine import BacktestResult
from trading_lab.backtest.walk_forward import WalkForwardResult, WalkForwardSlice
from trading_lab.claude.client import ClaudeClient
from trading_lab.claude.refine import merge_allowed_params, refinement_walk_forward
from trading_lab.strategies.rsi_mean_reversion import RSIMeanReversion


def _stub_bt(metrics: dict[str, float]) -> BacktestResult:
    idx = pd.date_range("2020-01-01", periods=2, freq="D", tz="UTC")
    eq = pd.Series([100.0, 101.0], index=idx)
    return BacktestResult(
        equity_curve=eq,
        trades=pd.DataFrame(),
        metrics=metrics,
        params={},
        meta={},
    )


def _two_slice_wf() -> WalkForwardResult:
    stub = _stub_bt({"total_return": 0.0})
    slices = (
        WalkForwardSlice(
            "2020-01-01",
            "2020-06-30",
            "2020-07-01",
            "2020-12-31",
            stub,
            stub,
        ),
        WalkForwardSlice(
            "2021-01-01",
            "2021-06-30",
            "2021-07-01",
            "2021-12-31",
            stub,
            stub,
        ),
    )
    meta = {
        "start": "2020-01-01",
        "end": "2022-12-31",
        "symbols": ["SPY"],
        "strategy_name": RSIMeanReversion.name,
        "in_sample_months": 6,
        "out_sample_months": 6,
        "step_months": 6,
        "num_slices": len(slices),
    }
    return WalkForwardResult(slices=slices, meta=meta)


def test_merge_allowed_params_ignores_unknown_keys() -> None:
    base = RSIMeanReversion().params
    merged = merge_allowed_params(RSIMeanReversion, base, {"rsi_period": 21, "ghost": 99})
    assert merged["rsi_period"] == 21
    assert "ghost" not in merged


def test_refinement_walk_forward_updates_params_from_simulator() -> None:
    replies = iter(
        [
            '{"suggested_params": {"rsi_period": 15}, "rationale": "first"}',
            '{"suggested_params": {}, "rationale": "second"}',
        ],
    )

    def fake_bt(
        strategy: object, symbols: list[str], start: str, end: str, **_kw: object
    ) -> BacktestResult:
        _ = (strategy, symbols, start, end)
        return _stub_bt({"total_return": 0.01})

    def sim(**_kw: object) -> str:
        return next(replies)

    client = ClaudeClient(api_key="", model="stub-model", simulator=sim)
    wf = _two_slice_wf()

    with patch("trading_lab.claude.refine.backtest", side_effect=fake_bt):
        result = refinement_walk_forward(RSIMeanReversion, wf, symbols=["SPY"], client=client)

    assert len(result.steps) == 2
    assert result.steps[0].params_after["rsi_period"] == 15
    assert result.final_params["rsi_period"] == 15


def test_refinement_walk_forward_requires_slices() -> None:
    wf = WalkForwardResult(slices=(), meta={"symbols": ["SPY"], "num_slices": 0})
    client = ClaudeClient(api_key="", model="m", simulator=lambda **kw: "{}")
    with pytest.raises(ValueError, match="no slices"):
        refinement_walk_forward(RSIMeanReversion, wf, client=client)
