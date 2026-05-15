"""Interactive Brokers connectivity (paper-only enforcement)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from ib_insync import IB, MarketOrder, Stock, Trade

from trading_lab.db.models import OrderSide
from trading_lab.execution.exceptions import PaperAccountRequiredError

ORDER_REF_TAG = "paper-trade-lab"


class IBKRClient:
    """Thin ``ib_insync`` wrapper with mandatory paper safeguards."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        client_id: int,
        account_id: str,
        ib: Any | None = None,
        connect: bool = True,
        timeout: float = 10.0,
    ) -> None:
        if port == 7496:
            msg = "Refusing IBKR live TWS port 7496"
            raise ValueError(msg)
        if not account_id.startswith("D"):
            msg = "account_id must start with 'D' (paper account)"
            raise PaperAccountRequiredError(msg)

        self._account_id = account_id
        self._ib: Any = ib if ib is not None else IB()  # type: ignore[no-untyped-call]
        if connect:
            self.connect(host, port, client_id, timeout=timeout)
        self._assert_paper_account()

    @property
    def ib(self) -> Any:
        """Underlying ``ib_insync`` handle."""
        return self._ib

    @property
    def account_id(self) -> str:
        """Configured IBKR account."""
        return self._account_id

    def connect(self, host: str, port: int, client_id: int, *, timeout: float = 10.0) -> None:
        """Open socket connection (no-op if already connected)."""
        if self._ib.isConnected():
            return
        self._ib.connect(host, port, clientId=client_id, timeout=timeout, readonly=False)

    def disconnect(self) -> None:
        """Disconnect when idle."""
        if self._ib.isConnected():
            self._ib.disconnect()

    def _assert_paper_account(self) -> None:
        """Fail fast when managed accounts look non-paper."""
        accounts = [str(a) for a in self._ib.managedAccounts()]
        upper_accounts = {a.upper() for a in accounts}
        target = self._account_id.upper()
        if target not in upper_accounts:
            msg = f"account_id {self._account_id!r} not in managedAccounts {accounts}"
            raise PaperAccountRequiredError(msg)
        if not self._account_id.upper().startswith("D"):
            raise PaperAccountRequiredError("non-paper account id blocked")

    def submit_market_order(
        self,
        *,
        symbol: str,
        quantity: Decimal,
        side: OrderSide,
        account: str | None = None,
    ) -> Trade:
        """Submit a DAY market order tagged with ``ORDER_REF_TAG``."""
        sym = symbol.strip().upper()
        contract = Stock(sym, "SMART", "USD")
        self._ib.qualifyContracts(contract)

        action = "BUY" if side == OrderSide.BUY else "SELL"
        qty = float(quantity)
        order = MarketOrder(action, qty)
        order.orderRef = ORDER_REF_TAG
        order.tif = "DAY"
        order.account = account or self._account_id

        trade = self._ib.placeOrder(contract, order)
        return cast(Trade, trade)


__all__ = ["IBKRClient", "ORDER_REF_TAG"]
