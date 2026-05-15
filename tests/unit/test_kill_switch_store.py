"""Tests for persisted kill-switch syncing."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from trading_lab.db.models import Base
from trading_lab.db.session import managed_session
from trading_lab.execution.kill_switch_store import (
    apply_kill_switch_from_db,
    describe_kill_switch,
    persist_kill_switch_reset,
    persist_kill_switch_trip,
)
from trading_lab.execution.risk import KillSwitchState


@pytest.fixture
def ks_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def test_apply_without_db_row_preserves_memory_state(ks_factory: sessionmaker[Session]) -> None:
    state = KillSwitchState()
    state.trip("local_only")
    with managed_session(ks_factory) as session:
        apply_kill_switch_from_db(session, state)
    assert state.tripped


def test_trip_in_db_forces_memory_latch(ks_factory: sessionmaker[Session]) -> None:
    state = KillSwitchState()
    with managed_session(ks_factory) as session:
        persist_kill_switch_trip(session, "telegram_manual")
    with managed_session(ks_factory) as session:
        apply_kill_switch_from_db(session, state)
    assert state.tripped
    assert "telegram_manual" in state.reason


def test_reset_in_db_clears_memory_latch(ks_factory: sessionmaker[Session]) -> None:
    state = KillSwitchState()
    with managed_session(ks_factory) as session:
        persist_kill_switch_trip(session, "x")
    with managed_session(ks_factory) as session:
        apply_kill_switch_from_db(session, state)
    assert state.tripped
    with managed_session(ks_factory) as session:
        persist_kill_switch_reset(session)
    with managed_session(ks_factory) as session:
        apply_kill_switch_from_db(session, state)
    assert not state.tripped


def test_describe_before_insert_returns_disabled(ks_factory: sessionmaker[Session]) -> None:
    with managed_session(ks_factory) as session:
        tripped, reason = describe_kill_switch(session)
    assert tripped is False
    assert reason == ""
