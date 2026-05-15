"""Run the Telegram control bot (whitelist auth, paper-only tooling)."""

from __future__ import annotations

import logging

import typer
from pydantic import ValidationError

from trading_lab.config import get_settings
from trading_lab.db.session import create_session_factory, ensure_schema
from trading_lab.logging_setup import configure_logging
from trading_lab.telegram_bot.bot import build_application

logger = logging.getLogger(__name__)


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

    if not settings.telegram_bot_token.strip():
        typer.echo("TELEGRAM_BOT_TOKEN is required.", err=True)
        raise typer.Exit(code=1)
    allowed = settings.telegram_user_id_list()
    if not allowed:
        typer.echo(
            "TELEGRAM_ALLOWED_USER_IDS must list at least one Telegram user id (comma-separated).",
            err=True,
        )
        raise typer.Exit(code=1)

    ensure_schema(settings.database_url)
    factory = create_session_factory(settings)
    application = build_application(settings, factory)
    logger.info("telegram_bot_start allowed_users=%s", sorted(allowed))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    typer.run(main)
