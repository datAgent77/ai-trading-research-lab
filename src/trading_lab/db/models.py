"""Database models."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class StrategyRunStatus(enum.StrEnum):
    """Lifecycle state for a strategy run."""

    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class OrderSide(enum.StrEnum):
    """Order direction."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(enum.StrEnum):
    """Broker-facing order status."""

    NEW = "new"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class ClaudeCallPurpose(enum.StrEnum):
    """High-level reason for a Claude API request."""

    REFINE_PARAMS = "refine_params"
    ANALYZE_BACKTEST = "analyze_backtest"
    DAILY_REPORT = "daily_report"
    WEEKLY_REPORT = "weekly_report"
    REGIME_DETECTION = "regime_detection"
    TELEGRAM_REPLY = "telegram_reply"


class StrategyRun(Base):
    """Single live or research invocation of a named strategy."""

    __tablename__ = "strategy_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    params: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[StrategyRunStatus] = mapped_column(
        Enum(StrategyRunStatus, native_enum=False, length=32),
        nullable=False,
        default=StrategyRunStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    signals: Mapped[list[Signal]] = relationship(back_populates="strategy_run")
    orders: Mapped[list[Order]] = relationship(back_populates="strategy_run")
    claude_calls: Mapped[list[ClaudeCall]] = relationship(back_populates="strategy_run")


class BacktestResult(Base):
    """Persisted summary of a backtest execution."""

    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_run_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_runs.id"), index=True)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[str] = mapped_column(String(32), nullable=False)
    end_date: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    params: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    meta: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Signal(Base):
    """Discrete strategy signal on a bar."""

    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_signals_idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_run_id: Mapped[int] = mapped_column(ForeignKey("strategy_runs.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    bar_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signal_value: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    strategy_run: Mapped[StrategyRun] = relationship(back_populates="signals")
    orders: Mapped[list[Order]] = relationship(back_populates="signal")


class Order(Base):
    """Order intent submitted to the broker (paper only)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_run_id: Mapped[int] = mapped_column(ForeignKey("strategy_runs.id"), nullable=False)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"))
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide, native_enum=False, length=16))
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=32),
        nullable=False,
        default=OrderStatus.NEW,
    )
    ibkr_order_id: Mapped[str | None] = mapped_column(String(64))
    order_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="paper-trade-lab")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    strategy_run: Mapped[StrategyRun] = relationship(back_populates="orders")
    signal: Mapped[Signal | None] = relationship(back_populates="orders")
    fills: Mapped[list[Fill]] = relationship(back_populates="order")


class Fill(Base):
    """Execution fill against an order."""

    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    fill_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    fill_qty: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    commission: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
        default=Decimal("0"),
    )
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    order: Mapped[Order] = relationship(back_populates="fills")


class PositionsSnapshot(Base):
    """Point-in-time positions snapshot."""

    __tablename__ = "positions_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    strategy_run_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_runs.id"))


class KillSwitchRecord(Base):
    """Singleton kill-switch row (Telegram manual trip / reset + live-loop polling sync)."""

    __tablename__ = "kill_switch_record"

    singleton_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    tripped: Mapped[bool] = mapped_column(nullable=False, default=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClaudeCall(Base):
    """Audit row for Claude API usage."""

    __tablename__ = "claude_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_run_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_runs.id"))
    purpose: Mapped[ClaudeCallPurpose] = mapped_column(
        Enum(ClaudeCallPurpose, native_enum=False, length=32),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_summary: Mapped[str | None] = mapped_column(Text())
    request_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    response_payload: Mapped[dict[str, object] | None] = mapped_column(JSON)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    strategy_run: Mapped[StrategyRun | None] = relationship(back_populates="claude_calls")
