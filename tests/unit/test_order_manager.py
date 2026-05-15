"""Order manager tests (Stage 7)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from trading_lab.execution.order_manager import place_order_stub


def test_place_order_stub_raises() -> None:
    with pytest.raises(NotImplementedError):
        place_order_stub(strategy_run_id=1, symbol="SPY", quantity=Decimal("1"))
