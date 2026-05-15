"""Persist broker positions for auditing."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from trading_lab.db.models import PositionsSnapshot
from trading_lab.execution.ibkr_client import IBKRClient


def snapshot_positions(
    ibkr: IBKRClient,
    *,
    session: Session,
    strategy_run_id: int | None,
    captured_at: datetime | None = None,
) -> int:
    """Insert ``positions_snapshot`` rows mirroring IBKR holdings."""
    ib = ibkr.ib
    cap = captured_at if captured_at is not None else datetime.now(UTC)
    if cap.tzinfo is None:
        msg = "captured_at must be timezone-aware"
        raise ValueError(msg)

    unreal_map: dict[str, Decimal] = {}
    for item in ib.portfolio(account=ibkr.account_id):
        sym = item.contract.symbol.upper()
        unreal_map[sym] = Decimal(str(item.unrealizedPNL))

    rows = 0
    for pos in ib.positions(account=ibkr.account_id):
        sym = pos.contract.symbol.upper()
        qty = Decimal(str(pos.position))
        avg = Decimal(str(pos.avgCost))
        unreal = unreal_map.get(sym, Decimal("0"))
        session.add(
            PositionsSnapshot(
                captured_at=cap,
                symbol=sym,
                quantity=qty,
                avg_cost=avg,
                unrealized_pnl=unreal,
                strategy_run_id=strategy_run_id,
            ),
        )
        rows += 1
    return rows


__all__ = ["snapshot_positions"]
