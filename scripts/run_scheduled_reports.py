"""Long-running scheduler: heartbeat logs + cron-fired Claude daily/weekly reports."""

from __future__ import annotations

import asyncio
import logging

import typer
from pydantic import ValidationError

from trading_lab.config import Settings, get_settings
from trading_lab.db.session import create_session_factory, ensure_schema
from trading_lab.logging_setup import configure_logging
from trading_lab.runner.report_jobs import register_scheduled_report_jobs
from trading_lab.runner.scheduler import (
    build_async_scheduler,
    register_heartbeat_job,
    shutdown_scheduler,
)

logger = logging.getLogger(__name__)


async def _async_main(settings: Settings) -> None:
    ensure_schema(settings.database_url)
    factory = create_session_factory(settings)
    scheduler = build_async_scheduler(timezone="UTC")
    register_heartbeat_job(scheduler, interval_seconds=300)
    register_scheduled_report_jobs(scheduler, settings=settings, session_factory=factory)
    scheduler.start()
    logger.info("scheduled_reports_daemon_started")
    try:
        await asyncio.Future()
    finally:
        shutdown_scheduler(scheduler)


def main() -> None:
    configure_logging(json_output=False)
    try:
        settings = get_settings()
    except ValidationError as exc:
        typer.echo("Configuration error — check `.env` (see `.env.example`).", err=True)
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", ()))
            typer.echo(f"  {loc}: {err.get('msg')}", err=True)
        raise typer.Exit(code=1) from exc
    asyncio.run(_async_main(settings))


if __name__ == "__main__":
    typer.run(main)
