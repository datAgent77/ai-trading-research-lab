"""Telegram Application bootstrap."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application
from telegram.request import HTTPXRequest

from trading_lab.config import Settings
from trading_lab.telegram_bot.handlers import register


def build_application(
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> Application:  # type: ignore[type-arg]
    """Construct ``python-telegram-bot`` ``Application`` with trading-lab handlers."""
    token = settings.telegram_bot_token.strip()
    timeout = float(settings.telegram_http_timeout_seconds)
    proxy = settings.telegram_proxy_url.strip() or None
    request = HTTPXRequest(
        connect_timeout=timeout,
        read_timeout=timeout,
        write_timeout=timeout,
        pool_timeout=max(timeout, 10.0),
        proxy=proxy,
    )
    application = Application.builder().token(token).request(request).build()
    application.bot_data["settings"] = settings
    application.bot_data["session_factory"] = session_factory
    application.bot_data["allowed_user_ids"] = set(settings.telegram_user_id_list())
    register(application)
    return application


__all__ = ["build_application"]
