"""Risk controls tests (Stage 7)."""

from __future__ import annotations

import pytest

from trading_lab.execution import risk


def test_drawdown_guard_stub_raises() -> None:
    with pytest.raises(NotImplementedError):
        risk.evaluate_daily_drawdown_stub()
