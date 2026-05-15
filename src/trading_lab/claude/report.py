"""Claude-authored markdown reports and regime JSON helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from trading_lab.claude import prompts
from trading_lab.claude.client import ClaudeClient
from trading_lab.claude.schemas import RegimeDetectionResponse, parse_regime_detection_response
from trading_lab.db.models import ClaudeCallPurpose


def daily_report_markdown(
    context: Mapping[str, Any],
    *,
    client: ClaudeClient,
    max_tokens: int = 2048,
    strategy_run_id: int | None = None,
    db_session: Session | None = None,
) -> str:
    """Return markdown brief for the supplied factual JSON context."""
    user = prompts.build_daily_report_user_message(context)
    return client.complete_text(
        purpose=ClaudeCallPurpose.DAILY_REPORT,
        system=prompts.PROMPT_DAILY_REPORT_ROLE,
        user=user,
        max_tokens=max_tokens,
        strategy_run_id=strategy_run_id,
        db_session=db_session,
    )


def weekly_report_markdown(
    context: Mapping[str, Any],
    *,
    client: ClaudeClient,
    max_tokens: int = 3072,
    strategy_run_id: int | None = None,
    db_session: Session | None = None,
) -> str:
    """Return markdown weekly summary for structured facts."""
    user = prompts.build_weekly_report_user_message(context)
    return client.complete_text(
        purpose=ClaudeCallPurpose.WEEKLY_REPORT,
        system=prompts.PROMPT_WEEKLY_REPORT_ROLE,
        user=user,
        max_tokens=max_tokens,
        strategy_run_id=strategy_run_id,
        db_session=db_session,
    )


def regime_detection(
    payload: dict[str, Any],
    *,
    client: ClaudeClient,
    max_tokens: int = 512,
    strategy_run_id: int | None = None,
    db_session: Session | None = None,
) -> RegimeDetectionResponse:
    """Parse structured regime JSON from Claude."""
    user = prompts.build_regime_detection_user_message(payload)
    raw = client.complete_text(
        purpose=ClaudeCallPurpose.REGIME_DETECTION,
        system=prompts.PROMPT_REGIME_DETECTION_SYSTEM,
        user=user,
        max_tokens=max_tokens,
        strategy_run_id=strategy_run_id,
        db_session=db_session,
    )
    return parse_regime_detection_response(raw)


__all__ = ["daily_report_markdown", "regime_detection", "weekly_report_markdown"]
