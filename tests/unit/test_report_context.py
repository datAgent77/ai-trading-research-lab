"""Unit coverage for Claude report JSON payloads."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from trading_lab.claude.report_context import (
    build_daily_report_context,
    build_weekly_report_context,
    merge_overlay,
    spy_daily_benchmark,
    utc_calendar_day_bounds,
)
from trading_lab.db.models import (
    Base,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    PositionsSnapshot,
    StrategyRun,
    StrategyRunStatus,
)


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def test_utc_calendar_day_bounds_mid_month() -> None:
    inst = datetime(2025, 6, 15, 3, 4, 5, tzinfo=UTC)
    start, end = utc_calendar_day_bounds(inst)
    assert start == datetime(2025, 6, 15, tzinfo=UTC)
    assert end == datetime(2025, 6, 16, tzinfo=UTC)


def test_daily_payload_contains_orders_and_fill(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
) -> None:
    def fake_fetch(
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        del symbol, start, end, timeframe
        idx = pd.date_range("2025-06-09", periods=2, freq="D", tz="UTC")
        return pd.DataFrame({"Close": [100.0, 102.0]}, index=idx)

    monkeypatch.setattr("trading_lab.claude.report_context.fetch_bars", fake_fetch)

    session = session_factory()
    try:
        now = datetime(2025, 6, 10, 18, 0, tzinfo=UTC)
        sr = StrategyRun(
            strategy_name="rsi_mean_reversion",
            symbol="SPY",
            params={},
            status=StrategyRunStatus.RUNNING,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(sr)
        session.flush()
        o = Order(
            strategy_run_id=sr.id,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=Decimal("10"),
            status=OrderStatus.FILLED,
            created_at=now,
            updated_at=now,
        )
        session.add(o)
        session.flush()
        session.add(
            Fill(
                order_id=o.id,
                fill_price=Decimal("500"),
                fill_qty=Decimal("10"),
                commission=Decimal("1"),
                filled_at=now,
            ),
        )
        session.add(
            PositionsSnapshot(
                captured_at=now,
                symbol="SPY",
                quantity=Decimal("10"),
                avg_cost=Decimal("500"),
                unrealized_pnl=Decimal("0"),
                strategy_run_id=sr.id,
            ),
        )
        session.commit()

        payload = build_daily_report_context(session, now_utc=now, include_spy=True)
        assert payload["period"] == "today"
        assert len(payload["orders"]) == 1
        assert len(payload["fills"]) == 1
        assert payload["fills"][0]["symbol"] == "SPY"
        bench = payload.get("benchmark") or {}
        assert bench.get("daily_pct_vs_prior_close") == pytest.approx(2.0)
    finally:
        session.close()


def test_weekly_payload_roll(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
) -> None:
    monkeypatch.setattr(
        "trading_lab.claude.report_context.fetch_bars",
        lambda symbol, start, end, timeframe="1d": pd.DataFrame(),
    )

    session = session_factory()
    try:
        now = datetime(2025, 6, 15, 22, 0, tzinfo=UTC)
        mid = datetime(2025, 6, 10, 10, 0, tzinfo=UTC)
        sr = StrategyRun(
            strategy_name="rsi_mean_reversion",
            symbol="QQQ",
            params={},
            status=StrategyRunStatus.STOPPED,
            started_at=mid,
            ended_at=mid,
            created_at=mid,
            updated_at=mid,
        )
        session.add(sr)
        session.flush()
        o = Order(
            strategy_run_id=sr.id,
            symbol="QQQ",
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            status=OrderStatus.SUBMITTED,
            created_at=mid,
            updated_at=mid,
        )
        session.add(o)
        session.commit()
        payload = build_weekly_report_context(session, now_utc=now, include_spy=False)
        assert payload["period"] == "week"
        assert len(payload["orders"]) == 1
    finally:
        session.close()


def test_merge_overlay_smoke() -> None:
    merged = merge_overlay({"period": "today"}, {"source": "unit"})
    assert merged["period"] == "today"
    assert merged["source"] == "unit"


def test_spy_benchmark_handles_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(symbol: str, start: str, end: str, timeframe: str = "1d") -> pd.DataFrame:
        del symbol, start, end, timeframe
        raise RuntimeError("offline")

    monkeypatch.setattr("trading_lab.claude.report_context.fetch_bars", boom)
    out = spy_daily_benchmark(datetime(2025, 6, 1, tzinfo=UTC))
    assert out.get("note") == "benchmark_failed"
