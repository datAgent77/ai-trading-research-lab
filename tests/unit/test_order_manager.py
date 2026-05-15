"""Order manager validation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fake_ibkr import RecordingFakeIB

from trading_lab.config import Settings
from trading_lab.db.models import OrderSide
from trading_lab.execution.exceptions import (
    DuplicateOrderKeyError,
    KillSwitchTrippedError,
    PositionCapExceededError,
    TradingHoursError,
)
from trading_lab.execution.ibkr_client import IBKRClient
from trading_lab.execution.order_manager import MarketOrderIntent, place_market_order
from trading_lab.execution.risk import KillSwitchState, RiskEngine


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    return Settings()


@pytest.fixture
def risk_engine(settings: Settings) -> RiskEngine:
    return RiskEngine(settings, KillSwitchState())


@pytest.fixture
def ibkr_paper() -> IBKRClient:
    fake = RecordingFakeIB()
    return IBKRClient(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        account_id="DU1234567",
        ib=fake,
        connect=False,
    )


def _monday_open_utc() -> datetime:
    ny = ZoneInfo("America/New_York")
    return datetime(2024, 6, 10, 11, 0, tzinfo=ny).astimezone(UTC)


def _intent(
    *,
    strategy_run_id: int = 99,
    symbol: str = "SPY",
    quantity: Decimal = Decimal("10"),
    side: OrderSide = OrderSide.BUY,
    nav: Decimal = Decimal("100000"),
    reference_price: Decimal = Decimal("400"),
    bar_timestamp: datetime | None = None,
) -> MarketOrderIntent:
    ts = bar_timestamp if bar_timestamp is not None else _monday_open_utc()
    return MarketOrderIntent(
        strategy_run_id=strategy_run_id,
        symbol=symbol,
        quantity=quantity,
        side=side,
        nav=nav,
        reference_price=reference_price,
        bar_timestamp=ts,
    )


def test_rejects_missing_strategy_run_id(ibkr_paper: IBKRClient, risk_engine: RiskEngine) -> None:
    intent = _intent(strategy_run_id=0)
    with pytest.raises(ValueError, match="strategy_run_id"):
        place_market_order(intent, ibkr=ibkr_paper, risk=risk_engine, now_utc=_monday_open_utc())


def test_position_cap(ibkr_paper: IBKRClient, risk_engine: RiskEngine) -> None:
    intent = _intent(quantity=Decimal("11"), reference_price=Decimal("500"))
    with pytest.raises(PositionCapExceededError):
        place_market_order(intent, ibkr=ibkr_paper, risk=risk_engine, now_utc=_monday_open_utc())


def test_trading_hours_block(ibkr_paper: IBKRClient, risk_engine: RiskEngine) -> None:
    ny = ZoneInfo("America/New_York")
    late = datetime(2024, 6, 12, 16, 5, tzinfo=ny).astimezone(UTC)
    intent = _intent()
    with pytest.raises(TradingHoursError):
        place_market_order(intent, ibkr=ibkr_paper, risk=risk_engine, now_utc=late)


def test_kill_switch_blocks(ibkr_paper: IBKRClient, settings: Settings) -> None:
    ks = KillSwitchState()
    ks.trip("test")
    risk = RiskEngine(settings, ks)
    intent = _intent()
    with pytest.raises(KillSwitchTrippedError):
        place_market_order(intent, ibkr=ibkr_paper, risk=risk, now_utc=_monday_open_utc())


def test_idempotency_registry(ibkr_paper: IBKRClient, risk_engine: RiskEngine) -> None:
    intent = _intent()
    keys: set[tuple[int, str, str]] = set()
    now = _monday_open_utc()
    place_market_order(intent, ibkr=ibkr_paper, risk=risk_engine, recent_keys=keys, now_utc=now)
    with pytest.raises(DuplicateOrderKeyError):
        place_market_order(intent, ibkr=ibkr_paper, risk=risk_engine, recent_keys=keys, now_utc=now)
    assert len(keys) == 1


def test_successful_submit(ibkr_paper: IBKRClient, risk_engine: RiskEngine) -> None:
    intent = _intent()
    trade = place_market_order(
        intent,
        ibkr=ibkr_paper,
        risk=risk_engine,
        now_utc=_monday_open_utc(),
    )
    assert trade.order.orderId >= 1
