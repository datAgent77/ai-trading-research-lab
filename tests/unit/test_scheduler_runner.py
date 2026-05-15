"""APScheduler wiring."""

from __future__ import annotations

import asyncio

from trading_lab.runner.scheduler import (
    build_async_scheduler,
    register_heartbeat_job,
    shutdown_scheduler,
    sleep_until,
)


def test_scheduler_registers_heartbeat_job() -> None:
    async def body() -> None:
        sched = build_async_scheduler()
        register_heartbeat_job(sched, interval_seconds=3600)
        sched.start()
        job_ids = {job.id for job in sched.get_jobs()}
        assert "trading_lab_scheduler_heartbeat" in job_ids
        shutdown_scheduler(sched, wait=False)

    asyncio.run(body())


def test_sleep_until_times_out() -> None:
    async def body() -> None:
        ev = asyncio.Event()
        fired = await sleep_until(ev, seconds=0.02)
        assert fired is False

    asyncio.run(body())
