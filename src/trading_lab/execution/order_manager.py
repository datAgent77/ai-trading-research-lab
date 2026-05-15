"""Order routing and validation (stub)."""

from __future__ import annotations

from decimal import Decimal


def place_order_stub(strategy_run_id: int, symbol: str, quantity: Decimal) -> None:
    """Validate caps and submit orders (not implemented)."""
    raise NotImplementedError


__all__ = ["place_order_stub"]
