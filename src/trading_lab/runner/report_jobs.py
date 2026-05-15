"""Scheduled Claude reports and optional Telegram delivery."""

from __future__ import annotations

import asyncio
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session, sessionmaker

from trading_lab.claude.client import ClaudeClient
from trading_lab.claude.report import daily_report_markdown, weekly_report_markdown
from trading_lab.claude.report_context import (
    build_daily_report_context,
    build_weekly_report_context,
)
from trading_lab.config import Settings
from trading_lab.db.session import managed_session

logger = logging.getLogger(__name__)


def _clip(text: str, limit: int = 3900) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 24] + "\n...(truncated)"


async def broadcast_scheduled_report(settings: Settings, markdown: str) -> None:
    """Best-effort push to Telegram chat ids (``telegram_report_chat_ids`` or whitelist)."""
    token = settings.telegram_bot_token.strip()
    recipients = settings.telegram_report_recipient_ids()
    if not token or not recipients:
        logger.info(
            "scheduled_report_skip_delivery has_token=%s recipient_count=%s",
            bool(token),
            len(recipients),
        )
        return

    from telegram import Bot

    body = "Scheduled Claude report\n\n" + _clip(markdown)
    bot = Bot(token)
    async with bot:
        for cid in recipients:
            await bot.send_message(chat_id=int(cid), text=body[:4096])


def generate_daily_markdown(settings: Settings, session_factory: sessionmaker[Session]) -> str:
    """Blocking Claude invocation."""
    with managed_session(session_factory) as session:
        payload = build_daily_report_context(session)
    overlayed = dict(payload)
    overlayed["delivery"] = "scheduled_daily"
    client = ClaudeClient.from_settings(settings)
    return daily_report_markdown(overlayed, client=client)


def generate_weekly_markdown(settings: Settings, session_factory: sessionmaker[Session]) -> str:
    """Blocking Claude invocation."""
    with managed_session(session_factory) as session:
        payload = build_weekly_report_context(session)
    overlayed = dict(payload)
    overlayed["delivery"] = "scheduled_weekly"
    client = ClaudeClient.from_settings(settings)
    return weekly_report_markdown(overlayed, client=client)


async def run_scheduled_daily_report(
    settings: Settings,
    factory: sessionmaker[Session],
) -> None:
    logger.info("scheduled_daily_report_job_start")
    try:
        md = await asyncio.to_thread(generate_daily_markdown, settings, factory)
        logger.info("scheduled_daily_report_job_done chars=%s", len(md))
        await broadcast_scheduled_report(settings, md)
    except Exception:
        logger.exception("scheduled_daily_report_job_failed")


async def run_scheduled_weekly_report(
    settings: Settings,
    factory: sessionmaker[Session],
) -> None:
    logger.info("scheduled_weekly_report_job_start")
    try:
        md = await asyncio.to_thread(generate_weekly_markdown, settings, factory)
        logger.info("scheduled_weekly_report_job_done chars=%s", len(md))
        await broadcast_scheduled_report(settings, md)
    except Exception:
        logger.exception("scheduled_weekly_report_job_failed")


def register_scheduled_report_jobs(
    scheduler: AsyncIOScheduler,
    *,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    """Attach cron-fired Claude reporters when scheduling + API prerequisites exist."""
    if not settings.reports_schedule_enabled:
        logger.info("reports_schedule_disabled_config")
        return
    if not settings.anthropic_api_key.strip():
        logger.warning("reports_schedule_skipped_missing_anthropic_api_key")
        return

    tz_name = settings.report_timezone.strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        logger.exception("reports_schedule_bad_timezone name=%s", tz_name)
        return

    try:
        daily_trigger = CronTrigger.from_crontab(
            settings.report_daily_crontab.strip(),
            timezone=tz,
        )
        weekly_trigger = CronTrigger.from_crontab(
            settings.report_weekly_crontab.strip(),
            timezone=tz,
        )
    except Exception:
        logger.exception(
            "reports_schedule_bad_crontab daily=%r weekly=%r",
            settings.report_daily_crontab,
            settings.report_weekly_crontab,
        )
        return

    scheduler.add_job(
        run_scheduled_daily_report,
        trigger=daily_trigger,
        kwargs={"settings": settings, "factory": session_factory},
        id="trading_lab_daily_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_weekly_report,
        trigger=weekly_trigger,
        kwargs={"settings": settings, "factory": session_factory},
        id="trading_lab_weekly_report",
        replace_existing=True,
    )
    logger.info(
        "reports_schedule_registered timezone=%s daily=%s weekly=%s",
        tz_name,
        settings.report_daily_crontab.strip(),
        settings.report_weekly_crontab.strip(),
    )


__all__ = [
    "broadcast_scheduled_report",
    "generate_daily_markdown",
    "generate_weekly_markdown",
    "register_scheduled_report_jobs",
    "run_scheduled_daily_report",
    "run_scheduled_weekly_report",
]
