"""Post-backtest markdown commentary via Claude."""

from __future__ import annotations

from sqlalchemy.orm import Session

from trading_lab.claude import prompts
from trading_lab.claude.client import ClaudeClient
from trading_lab.db.models import ClaudeCallPurpose


def analyze_backtest_markdown(
    summary: str,
    *,
    client: ClaudeClient,
    max_tokens: int = 2048,
    strategy_run_id: int | None = None,
    db_session: Session | None = None,
) -> str:
    """Return qualitative markdown analysis for the supplied summary text."""
    user = prompts.build_analyze_backtest_user_message(summary)
    return client.complete_text(
        purpose=ClaudeCallPurpose.ANALYZE_BACKTEST,
        system=prompts.PROMPT_ANALYZE_BACKTEST_SYSTEM,
        user=user,
        max_tokens=max_tokens,
        strategy_run_id=strategy_run_id,
        db_session=db_session,
    )


__all__ = ["analyze_backtest_markdown"]
