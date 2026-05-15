"""Metrics tests (Stage 4)."""

from __future__ import annotations

import pytest

from trading_lab.backtest import metrics


def test_metrics_stubs_raise() -> None:
    with pytest.raises(NotImplementedError):
        metrics.sharpe_ratio_stub(object())
