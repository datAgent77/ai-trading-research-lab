"""Risk helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from trading_lab.config import Settings
from trading_lab.execution.exceptions import KillSwitchTrippedError, TradingHoursError
from trading_lab.execution.risk import (
    KillSwitchState,
    RiskEngine,
    assert_us_regular_trading_hours,
    daily_return_pct,
    exceeds_max_daily_drawdown,
    parse_hhmm_local,
)


def test_parse_hhmm_local() -> None:
    assert parse_hhmm_local("09:30") == (9, 30)


def test_weekend_trading_blocked() -> None:
    ny = ZoneInfo("America/New_York")
    saturday = datetime(2024, 6, 8, 12, 0, tzinfo=ny).astimezone(UTC)
    with pytest.raises(TradingHoursError, match="Weekend"):
        assert_us_regular_trading_hours(saturday, "09:30", "16:00")


def test_after_close_blocked() -> None:
    ny = ZoneInfo("America/New_York")
    wed = datetime(2024, 6, 12, 16, 5, tzinfo=ny).astimezone(UTC)
    with pytest.raises(TradingHoursError, match="Outside"):
        assert_us_regular_trading_hours(wed, "09:30", "16:00")


def test_regular_session_opens(monday_mid_morning_ny: datetime) -> None:
    assert_us_regular_trading_hours(monday_mid_morning_ny, "09:30", "16:00")


@pytest.fixture
def monday_mid_morning_ny() -> datetime:
    ny = ZoneInfo("America/New_York")
    return datetime(2024, 6, 10, 11, 0, tzinfo=ny).astimezone(UTC)


def test_naive_timestamp_rejected() -> None:
    naive = datetime(2024, 6, 10, 11, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        assert_us_regular_trading_hours(naive, "09:30", "16:00")


def test_daily_drawdown_threshold() -> None:
    assert exceeds_max_daily_drawdown(
        Decimal("100000"),
        Decimal("96999"),
        Decimal("-3.0"),
    )
    assert not exceeds_max_daily_drawdown(
        Decimal("100000"),
        Decimal("97001"),
        Decimal("-3.0"),
    )


def test_daily_return_pct() -> None:
    assert daily_return_pct(Decimal("100"), Decimal("103")) == Decimal("3")


def test_risk_engine_trips_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    settings = Settings()
    ks = KillSwitchState()
    risk = RiskEngine(settings, ks)
    tripped = risk.evaluate_daily_drawdown(
        day_start_equity=Decimal("100000"),
        current_equity=Decimal("96900"),
    )
    assert tripped is True
    assert ks.tripped is True


def test_risk_engine_blocks_orders_when_tripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    settings = Settings()
    ks = KillSwitchState()
    ks.trip("manual")
    risk = RiskEngine(settings, ks)
    ny = ZoneInfo("America/New_York")
    now = datetime(2024, 6, 10, 11, 0, tzinfo=ny).astimezone(UTC)
    with pytest.raises(KillSwitchTrippedError):
        risk.ensure_order_allowed(now_utc=now)
