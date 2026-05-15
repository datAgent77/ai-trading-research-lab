"""Coverage for APScheduler registration guards."""

from __future__ import annotations

from unittest.mock import MagicMock

from trading_lab.runner.report_jobs import register_scheduled_report_jobs


def test_register_skips_when_schedule_disabled() -> None:
    sched = MagicMock()
    settings = MagicMock()
    settings.reports_schedule_enabled = False
    factory = MagicMock()
    register_scheduled_report_jobs(sched, settings=settings, session_factory=factory)
    sched.add_job.assert_not_called()


def test_register_skips_when_missing_anthropic_key() -> None:
    sched = MagicMock()
    settings = MagicMock()
    settings.reports_schedule_enabled = True
    settings.anthropic_api_key = ""
    factory = MagicMock()
    register_scheduled_report_jobs(sched, settings=settings, session_factory=factory)
    sched.add_job.assert_not_called()


def test_register_adds_two_jobs_when_ready() -> None:
    sched = MagicMock()
    settings = MagicMock()
    settings.reports_schedule_enabled = True
    settings.anthropic_api_key = "sk-test"
    settings.report_timezone = "UTC"
    settings.report_daily_crontab = "0 12 * * *"
    settings.report_weekly_crontab = "30 12 * * sun"
    factory = MagicMock()
    register_scheduled_report_jobs(sched, settings=settings, session_factory=factory)
    assert sched.add_job.call_count == 2
