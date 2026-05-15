"""Database model metadata checks."""

from __future__ import annotations

from trading_lab.db.models import Base


def test_expected_tables_registered() -> None:
    tables = set(Base.metadata.tables.keys())
    assert {
        "strategy_runs",
        "backtest_results",
        "signals",
        "orders",
        "fills",
        "positions_snapshot",
        "claude_calls",
    }.issubset(tables)
