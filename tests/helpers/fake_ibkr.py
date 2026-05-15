"""Test doubles for ``ib_insync`` without a broker."""

from __future__ import annotations

from decimal import Decimal

from ib_insync import MarketOrder, Trade


class RecordingFakeIB:
    """Minimal ``IB`` surface used by ``IBKRClient`` in unit tests."""

    def __init__(self, *, accounts: list[str] | None = None) -> None:
        self._accounts = list(accounts or ["DU1234567"])
        self.connected = False
        self.placed: list[tuple[object, MarketOrder]] = []
        self._portfolio_items: list[object] = []
        self._position_items: list[object] = []
        self.net_liquidation: str = "100000"

    # --- IB API subset -------------------------------------------------

    def isConnected(self) -> bool:
        return self.connected

    def connect(self, *_args: object, **_kwargs: object) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def managedAccounts(self) -> list[str]:
        return list(self._accounts)

    def qualifyContracts(self, contract: object) -> list[object]:
        contract.conId = int(getattr(contract, "conId", 0) or 123456)
        return [contract]

    def placeOrder(self, contract: object, order: MarketOrder) -> Trade:
        self.placed.append((contract, order))
        order.orderId = len(self.placed)
        trade = Trade(contract, order)
        return trade

    def portfolio(self, account: str = "") -> list[object]:
        _ = account
        return list(self._portfolio_items)

    def positions(self, account: str = "") -> list[object]:
        _ = account
        return list(self._position_items)

    def accountSummary(self, account: str = "") -> list[object]:
        """Minimal tags for NAV reads in ``LiveLoop``."""
        from types import SimpleNamespace

        acct = account or (self._accounts[0] if self._accounts else "")
        return [
            SimpleNamespace(
                tag="NetLiquidation",
                account=acct,
                value=self.net_liquidation,
                currency="USD",
            ),
        ]

    # --- Test hooks ----------------------------------------------------

    def seed_portfolio(self, items: list[object]) -> None:
        self._portfolio_items = items

    def seed_positions(self, items: list[object]) -> None:
        self._position_items = items


def make_portfolio_item(*, symbol: str, unrealized: Decimal) -> object:
    """Build a duck-typed portfolio row."""
    from types import SimpleNamespace

    return SimpleNamespace(
        contract=SimpleNamespace(symbol=symbol),
        unrealizedPNL=float(unrealized),
    )


def make_position(*, symbol: str, qty: Decimal, avg_cost: Decimal) -> object:
    """Build a duck-typed position row."""
    from types import SimpleNamespace

    return SimpleNamespace(
        contract=SimpleNamespace(symbol=symbol),
        position=float(qty),
        avgCost=float(avg_cost),
    )


__all__ = ["RecordingFakeIB", "make_portfolio_item", "make_position"]
