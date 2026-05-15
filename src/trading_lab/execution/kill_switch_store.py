"""Persisted kill-switch flag shared between Telegram and the live runner."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from trading_lab.db.models import KillSwitchRecord
from trading_lab.execution.risk import KillSwitchState

GLOBAL_KILL_SWITCH_KEY = "global"


def apply_kill_switch_from_db(session: Session, state: KillSwitchState) -> None:
    """Mirror ``kill_switch_record`` into an in-memory ``KillSwitchState``.

    When no row exists yet, the in-memory latch is left unchanged so purely local trips
    remain visible until a row is written.
    """
    row = session.get(KillSwitchRecord, GLOBAL_KILL_SWITCH_KEY)
    if row is None:
        return
    if row.tripped:
        state.trip(row.reason or "kill_switch")
    else:
        state.reset()


def persist_kill_switch_trip(session: Session, reason: str) -> None:
    """Latch kill switch on with reason text."""
    now = datetime.now(UTC)
    text = reason.strip()[:512]
    row = session.get(KillSwitchRecord, GLOBAL_KILL_SWITCH_KEY)
    if row is None:
        session.add(
            KillSwitchRecord(
                singleton_key=GLOBAL_KILL_SWITCH_KEY,
                tripped=True,
                reason=text,
                updated_at=now,
            ),
        )
        return
    row.tripped = True
    row.reason = text
    row.updated_at = now


def persist_kill_switch_reset(session: Session) -> None:
    """Clear kill switch (manual reset path)."""
    now = datetime.now(UTC)
    row = session.get(KillSwitchRecord, GLOBAL_KILL_SWITCH_KEY)
    if row is None:
        session.add(
            KillSwitchRecord(
                singleton_key=GLOBAL_KILL_SWITCH_KEY,
                tripped=False,
                reason="",
                updated_at=now,
            ),
        )
        return
    row.tripped = False
    row.reason = ""
    row.updated_at = now


def describe_kill_switch(session: Session) -> tuple[bool, str]:
    """Return ``(tripped, reason)`` for operator-facing messages."""
    row = session.get(KillSwitchRecord, GLOBAL_KILL_SWITCH_KEY)
    if row is None:
        return False, ""
    return bool(row.tripped), str(row.reason or "")


__all__ = [
    "GLOBAL_KILL_SWITCH_KEY",
    "apply_kill_switch_from_db",
    "describe_kill_switch",
    "persist_kill_switch_reset",
    "persist_kill_switch_trip",
]
