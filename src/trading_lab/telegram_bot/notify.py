"""Synchronous Telegram notifications (HTTP) for live trading events."""

from __future__ import annotations

import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from trading_lab.config import Settings

logger = logging.getLogger(__name__)


def send_telegram_text(settings: Settings, text: str) -> None:
    """POST ``sendMessage`` for each configured recipient (same list as scheduled reports)."""
    token = settings.telegram_bot_token.strip()
    recipients = settings.telegram_report_recipient_ids()
    if not token or not recipients:
        logger.debug("telegram_notify_skip missing_token_or_recipients")
        return

    body = text.strip()
    if len(body) > 4000:
        body = body[:3980] + "\n...(truncated)"

    for chat_id in recipients:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = urllib.parse.urlencode(
                {"chat_id": str(chat_id), "text": body},
            ).encode()
            req = urllib.request.Request(url, data=payload, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                _ = resp.read()
        except urllib.error.HTTPError as exc:
            logger.warning(
                "telegram_notify_http_error chat_id=%s code=%s",
                chat_id,
                exc.code,
            )
        except Exception:
            logger.exception("telegram_notify_failed chat_id=%s", chat_id)


def telegram_notifier_from_settings(settings: Settings) -> Callable[[str], None] | None:
    """Return a one-arg notifier closure, or ``None`` when disabled or misconfigured."""
    if not settings.telegram_live_notify_enabled:
        return None
    if not settings.telegram_bot_token.strip():
        return None
    if not settings.telegram_report_recipient_ids():
        return None

    def _notify(text: str) -> None:
        send_telegram_text(settings, text)

    return _notify


__all__ = ["send_telegram_text", "telegram_notifier_from_settings"]
