"""IBKR client paper enforcement."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fake_ibkr import RecordingFakeIB

from trading_lab.db.models import OrderSide
from trading_lab.execution.exceptions import PaperAccountRequiredError
from trading_lab.execution.ibkr_client import ORDER_REF_TAG, IBKRClient


def test_rejects_live_tws_port() -> None:
    fake = RecordingFakeIB()
    with pytest.raises(ValueError, match="7496"):
        IBKRClient(
            host="127.0.0.1",
            port=7496,
            client_id=1,
            account_id="DU1234567",
            ib=fake,
            connect=False,
        )


def test_rejects_non_paper_account_prefix() -> None:
    fake = RecordingFakeIB()
    with pytest.raises(PaperAccountRequiredError, match="paper"):
        IBKRClient(
            host="127.0.0.1",
            port=7497,
            client_id=1,
            account_id="U123456",
            ib=fake,
            connect=False,
        )


def test_requires_account_in_managed_list() -> None:
    fake = RecordingFakeIB(accounts=["DU9999999"])
    with pytest.raises(PaperAccountRequiredError, match="managedAccounts"):
        IBKRClient(
            host="127.0.0.1",
            port=7497,
            client_id=1,
            account_id="DU1234567",
            ib=fake,
            connect=False,
        )


def test_market_order_carries_audit_ref() -> None:
    fake = RecordingFakeIB()
    client = IBKRClient(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        account_id="DU1234567",
        ib=fake,
        connect=False,
    )
    trade = client.submit_market_order(symbol="SPY", quantity=Decimal("2"), side=OrderSide.BUY)
    assert trade.order.orderRef == ORDER_REF_TAG
    assert fake.placed
