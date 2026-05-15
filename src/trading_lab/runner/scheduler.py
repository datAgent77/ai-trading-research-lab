"""APScheduler helpers for auxiliary periodic tasks (reports hook later)."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


def build_async_scheduler(*, timezone: str = "UTC") -> AsyncIOScheduler:
    """Construct an asyncio-backed scheduler (start inside a running event loop)."""
    from zoneinfo import ZoneInfo

    return AsyncIOScheduler(timezone=ZoneInfo(timezone))


def register_heartbeat_job(scheduler: AsyncIOScheduler, *, interval_seconds: int = 300) -> None:
    """Emit a lightweight heartbeat log on a fixed cadence."""

    def ping() -> None:
        logger.info("scheduler_heartbeat")

    scheduler.add_job(
        ping,
        "interval",
        seconds=interval_seconds,
        id="trading_lab_scheduler_heartbeat",
        replace_existing=True,
    )


def shutdown_scheduler(scheduler: AsyncIOScheduler | None, *, wait: bool = True) -> None:
    """Best-effort shutdown."""
    if scheduler is None:
        return
    try:
        scheduler.shutdown(wait=wait)
    except Exception:
        logger.exception("scheduler_shutdown_failed")


async def sleep_until(stop_event: asyncio.Event, seconds: float) -> bool:
    """Wait up to ``seconds`` for ``stop_event``. Returns ``True`` if event fired."""
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        return True
    except TimeoutError:
        return False


__all__ = [
    "build_async_scheduler",
    "register_heartbeat_job",
    "shutdown_scheduler",
    "sleep_until",
]
