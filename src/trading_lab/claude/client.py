"""Anthropic Messages API wrapper with optional audit rows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from anthropic import Anthropic
from anthropic.types import TextBlock
from sqlalchemy.orm import Session

from trading_lab.config import Settings
from trading_lab.db.models import ClaudeCall, ClaudeCallPurpose

AssistantSimulator = Callable[..., str]


class ClaudeClient:
    """Invoke Claude with consistent auditing hooks.

    Pass ``simulator`` in tests to bypass HTTP entirely; it receives keyword arguments
    ``model``, ``system``, ``user``, ``max_tokens`` and must return assistant text.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        simulator: AssistantSimulator | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._simulator = simulator
        self._anthropic: Anthropic | None = None

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs: Any) -> ClaudeClient:
        """Build a client using ``anthropic_api_key`` and ``anthropic_model``."""
        return cls(api_key=settings.anthropic_api_key, model=settings.anthropic_model, **kwargs)

    def complete_text(
        self,
        *,
        purpose: ClaudeCallPurpose,
        system: str,
        user: str,
        max_tokens: int = 4096,
        strategy_run_id: int | None = None,
        db_session: Session | None = None,
    ) -> str:
        """Return assistant plain-text output for system/user prompts."""
        request_payload: dict[str, Any] = {
            "system": system,
            "user": user,
            "max_tokens": max_tokens,
        }
        tokens_used: int | None = None

        if self._simulator is not None:
            assistant_text = self._simulator(
                model=self._model,
                system=system,
                user=user,
                max_tokens=max_tokens,
            )
            response_payload: dict[str, Any] | None = {"text": assistant_text}
        else:
            if not self._api_key:
                msg = "ANTHROPIC_API_KEY is required when no simulator is configured"
                raise RuntimeError(msg)
            if self._anthropic is None:
                self._anthropic = Anthropic(api_key=self._api_key)
            resp = self._anthropic.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            assistant_text = "".join(blk.text for blk in resp.content if isinstance(blk, TextBlock))
            usage = getattr(resp, "usage", None)
            if usage is not None:
                inp = getattr(usage, "input_tokens", None)
                out = getattr(usage, "output_tokens", None)
                if inp is not None and out is not None:
                    tokens_used = int(inp) + int(out)
            response_payload = {"text": assistant_text}

        _persist_claude_call_row(
            db_session,
            purpose=purpose,
            model=self._model,
            strategy_run_id=strategy_run_id,
            request_payload=request_payload,
            response_payload=response_payload,
            tokens_used=tokens_used,
            input_summary=user[:512],
        )

        return assistant_text


def _persist_claude_call_row(
    session: Session | None,
    *,
    purpose: ClaudeCallPurpose,
    model: str,
    strategy_run_id: int | None,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any] | None,
    tokens_used: int | None,
    input_summary: str | None,
) -> None:
    if session is None:
        return
    row = ClaudeCall(
        strategy_run_id=strategy_run_id,
        purpose=purpose,
        model=model,
        input_summary=input_summary,
        request_payload=request_payload,
        response_payload=response_payload,
        tokens_used=tokens_used,
        created_at=datetime.now(UTC),
    )
    session.add(row)


__all__ = ["ClaudeClient"]
