"""Position snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fake_ibkr import RecordingFakeIB, make_portfolio_item, make_position
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trading_lab.db.models import Base, PositionsSnapshot
from trading_lab.execution.ibkr_client import IBKRClient
from trading_lab.execution.position_tracker import snapshot_positions


def test_snapshot_positions_inserts_rows() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

    fake = RecordingFakeIB()
    fake.seed_positions([make_position(symbol="SPY", qty=Decimal("3"), avg_cost=Decimal("450"))])
    fake.seed_portfolio([make_portfolio_item(symbol="SPY", unrealized=Decimal("7"))])

    ibkr = IBKRClient(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        account_id="DU1234567",
        ib=fake,
        connect=False,
    )

    cap = datetime(2024, 1, 2, tzinfo=UTC)
    with factory() as session:
        inserted = snapshot_positions(ibkr, session=session, strategy_run_id=7, captured_at=cap)
        session.commit()

    assert inserted == 1

    with factory() as session:
        row = session.scalars(select(PositionsSnapshot)).one()

    assert row.symbol == "SPY"
    assert row.strategy_run_id == 7
    assert row.quantity == Decimal("3")
    assert row.avg_cost == Decimal("450")
    assert row.unrealized_pnl == Decimal("7")
