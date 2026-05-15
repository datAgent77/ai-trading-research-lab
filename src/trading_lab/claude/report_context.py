"""Structured JSON payloads for Claude daily / weekly reports (SQLite-backed lab ledger)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trading_lab.data.yfinance_source import fetch_bars
from trading_lab.db.models import Fill, Order, PositionsSnapshot, StrategyRun, StrategyRunStatus
from trading_lab.execution.kill_switch_store import describe_kill_switch


def utc_calendar_day_bounds(instant_utc: datetime) -> tuple[datetime, datetime]:
    """Return ``[start, end)`` UTC bounds for the UTC calendar day of ``instant_utc``."""
    if instant_utc.tzinfo is None:
        msg = "instant_utc must be timezone-aware"
        raise ValueError(msg)
    day = instant_utc.astimezone(UTC).date()
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


def rolling_week_bounds(instant_utc: datetime) -> tuple[datetime, datetime]:
    """Return ``[start, end)`` covering the trailing seven days ending at ``instant_utc``."""
    if instant_utc.tzinfo is None:
        msg = "instant_utc must be timezone-aware"
        raise ValueError(msg)
    end = instant_utc.astimezone(UTC)
    start = end - timedelta(days=7)
    return start, end


def spy_daily_benchmark(now_utc: datetime | None = None) -> dict[str, Any]:
    """Approximate SPY daily %% vs prior close using Yahoo Finance (best-effort)."""
    clock = now_utc.astimezone(UTC) if now_utc is not None else datetime.now(UTC)
    end_d = clock.date()
    start_d = end_d - timedelta(days=14)
    try:
        frame = fetch_bars("SPY", str(start_d), str(end_d), timeframe="1d")
        if frame.empty:
            return {"symbol": "SPY", "daily_pct_vs_prior_close": None, "note": "empty_history"}
        mapping = {str(c).strip().lower(): c for c in frame.columns}
        col = mapping.get("close")
        if col is None:
            return {"symbol": "SPY", "daily_pct_vs_prior_close": None, "note": "missing_close"}
        closes = frame[col].astype(float)
        if len(closes) < 2:
            return {"symbol": "SPY", "daily_pct_vs_prior_close": None, "note": "insufficient_bars"}
        prev = float(closes.iloc[-2])
        last = float(closes.iloc[-1])
        if prev <= 0:
            return {"symbol": "SPY", "daily_pct_vs_prior_close": None, "note": "bad_prior"}
        pct = (last / prev - 1.0) * 100.0
        idx = frame.index[-1]
        ts = pd.Timestamp(idx)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return {
            "symbol": "SPY",
            "as_of_bar_utc": ts.strftime("%Y-%m-%d"),
            "daily_pct_vs_prior_close": round(pct, 4),
            "last_close": last,
        }
    except Exception as exc:
        return {"symbol": "SPY", "note": "benchmark_failed", "error": str(exc)}


def _decimal_str(value: Decimal | float | int) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _orders_window(session: Session, start: datetime, end: datetime) -> list[dict[str, Any]]:
    stmt = (
        select(Order)
        .where(Order.created_at >= start, Order.created_at < end)
        .order_by(Order.id.asc())
    )
    rows = session.scalars(stmt).all()
    return [
        {
            "id": int(o.id),
            "strategy_run_id": int(o.strategy_run_id),
            "symbol": o.symbol,
            "side": o.side.value,
            "quantity": _decimal_str(o.quantity),
            "status": o.status.value,
            "created_at": o.created_at.isoformat(),
        }
        for o in rows
    ]


def _fills_window(session: Session, start: datetime, end: datetime) -> list[dict[str, Any]]:
    stmt = (
        select(Fill, Order.symbol)
        .join(Order, Fill.order_id == Order.id)
        .where(Fill.filled_at >= start, Fill.filled_at < end)
        .order_by(Fill.id.asc())
    )
    out: list[dict[str, Any]] = []
    for fill, sym in session.execute(stmt).all():
        out.append(
            {
                "id": int(fill.id),
                "order_id": int(fill.order_id),
                "symbol": sym,
                "fill_price": _decimal_str(fill.fill_price),
                "fill_qty": _decimal_str(fill.fill_qty),
                "commission": _decimal_str(fill.commission),
                "filled_at": fill.filled_at.isoformat(),
            },
        )
    return out


def _running_strategy_runs(session: Session) -> list[dict[str, Any]]:
    stmt = select(StrategyRun).where(StrategyRun.status == StrategyRunStatus.RUNNING)
    rows = session.scalars(stmt).all()
    return [
        {
            "id": int(r.id),
            "strategy_name": r.strategy_name,
            "symbol": r.symbol,
            "started_at": r.started_at.isoformat() if r.started_at else None,
        }
        for r in rows
    ]


def _order_status_counts(session: Session, start: datetime, end: datetime) -> dict[str, int]:
    stmt = (
        select(Order.status, func.count())
        .where(Order.created_at >= start, Order.created_at < end)
        .group_by(Order.status)
    )
    out: dict[str, int] = {}
    for status, cnt in session.execute(stmt).all():
        out[status.value] = int(cnt)
    return out


def latest_positions_by_symbol(session: Session, *, limit: int = 40) -> list[dict[str, Any]]:
    """Most recent snapshot rows per symbol (by ``captured_at`` tie-break on id)."""
    stmt = select(PositionsSnapshot).order_by(
        PositionsSnapshot.captured_at.desc(),
        PositionsSnapshot.id.desc(),
    )
    rows = session.scalars(stmt).all()
    seen: set[str] = set()
    picked: list[PositionsSnapshot] = []
    for row in rows:
        sym = row.symbol.upper()
        if sym in seen:
            continue
        seen.add(sym)
        picked.append(row)
        if len(picked) >= limit:
            break
    return [
        {
            "symbol": p.symbol,
            "quantity": _decimal_str(p.quantity),
            "avg_cost": _decimal_str(p.avg_cost),
            "unrealized_pnl": _decimal_str(p.unrealized_pnl),
            "captured_at": p.captured_at.isoformat(),
            "strategy_run_id": p.strategy_run_id,
        }
        for p in picked
    ]


def kill_switch_context(session: Session) -> dict[str, Any]:
    tripped, reason = describe_kill_switch(session)
    return {"tripped": tripped, "reason": reason}


def build_daily_report_context(
    session: Session,
    *,
    now_utc: datetime | None = None,
    include_spy: bool = True,
) -> dict[str, Any]:
    """Facts for ``daily_report_markdown`` aligned to the current UTC calendar day."""
    clock = now_utc.astimezone(UTC) if now_utc is not None else datetime.now(UTC)
    day_start, day_end = utc_calendar_day_bounds(clock)
    payload: dict[str, Any] = {
        "period": "today",
        "generated_at_utc": clock.isoformat(),
        "window_utc": {"start": day_start.isoformat(), "end_exclusive": day_end.isoformat()},
        "kill_switch": kill_switch_context(session),
        "strategy_runs_running": _running_strategy_runs(session),
        "orders": _orders_window(session, day_start, day_end),
        "order_status_counts": _order_status_counts(session, day_start, day_end),
        "fills": _fills_window(session, day_start, day_end),
        "positions_latest_snapshot": latest_positions_by_symbol(session),
    }
    if include_spy:
        payload["benchmark"] = spy_daily_benchmark(clock)
    return payload


def build_weekly_report_context(
    session: Session,
    *,
    now_utc: datetime | None = None,
    include_spy: bool = True,
) -> dict[str, Any]:
    """Facts for ``weekly_report_markdown`` over the trailing seven UTC days."""
    clock = now_utc.astimezone(UTC) if now_utc is not None else datetime.now(UTC)
    start, end = rolling_week_bounds(clock)
    payload: dict[str, Any] = {
        "period": "week",
        "generated_at_utc": clock.isoformat(),
        "window_utc": {"start": start.isoformat(), "end_exclusive": end.isoformat()},
        "kill_switch": kill_switch_context(session),
        "strategy_runs_running": _running_strategy_runs(session),
        "orders": _orders_window(session, start, end),
        "order_status_counts": _order_status_counts(session, start, end),
        "fills": _fills_window(session, start, end),
        "positions_latest_snapshot": latest_positions_by_symbol(session),
    }
    if include_spy:
        payload["benchmark"] = spy_daily_benchmark(clock)
    return payload


def merge_overlay(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Shallow merge for Telegram-driven hints without mutating frozen dicts."""
    merged = dict(base)
    merged.update(dict(overlay))
    return merged


__all__ = [
    "build_daily_report_context",
    "build_weekly_report_context",
    "kill_switch_context",
    "latest_positions_by_symbol",
    "merge_overlay",
    "rolling_week_bounds",
    "spy_daily_benchmark",
    "utc_calendar_day_bounds",
]
