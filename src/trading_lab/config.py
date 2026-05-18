"""Application configuration loaded from environment variables."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATA_CACHE_DIR = "./data/cache"


class Settings(BaseSettings):
    """Runtime settings. IBKR paper-only rules are enforced here."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_ibkr_client_id: int | None = Field(
        default=None,
        description=(
            "Separate IBKR client id for Telegram-driven reads (defaults to IBKR_CLIENT_ID + 1)"
        ),
    )
    telegram_report_chat_ids: str = ""
    telegram_live_notify_enabled: bool = Field(
        default=False,
        description="Telegram alerts for live intents/submits (same recipients as reports).",
    )
    telegram_http_timeout_seconds: float = Field(
        default=30.0,
        ge=5.0,
        le=180.0,
        description="Bot API HTTP timeouts in seconds (PTB default ~5s; increase on TimedOut).",
    )
    telegram_proxy_url: str = Field(
        default="",
        description="Optional HTTP(S) proxy for Bot API if api.telegram.org is blocked.",
    )

    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 42
    ibkr_account: str = Field(
        default="",
        description=(
            "Paper account id (DU…); optional for backtests-only. "
            "Required for paper trading and Telegram IBKR reads."
        ),
    )

    max_daily_drawdown_pct: Decimal = Field(default=Decimal("-3.0"))
    max_position_pct_nav: Decimal = Field(default=Decimal("5.0"))
    trading_start_ny: str = "09:30"
    trading_end_ny: str = "16:00"

    polygon_api_key: str = ""
    data_provider: Literal["yfinance", "polygon"] = Field(
        default="yfinance",
        description="Historical/live daily bars source (Polygon requires POLYGON_API_KEY).",
    )
    data_cache_dir: str = Field(default=DEFAULT_DATA_CACHE_DIR)

    database_url: str = "sqlite:///./trading_lab.db"

    reports_schedule_enabled: bool = True
    report_timezone: str = "America/New_York"
    report_daily_crontab: str = "5 17 * * mon-fri"
    report_weekly_crontab: str = "35 17 * * fri"

    @field_validator("telegram_ibkr_client_id", mode="before")
    @classmethod
    def telegram_ibkr_client_id_empty_as_none(cls, value: object) -> object:
        """Treat blank env (``TELEGRAM_IBKR_CLIENT_ID=``) as unset."""
        if value == "":
            return None
        return value

    @field_validator("ibkr_port")
    @classmethod
    def reject_live_ibkr_port(cls, value: int) -> int:
        """Refuse the IBKR live Trader Workstation port."""
        if value == 7496:
            msg = "IBKR_PORT 7496 is the live TWS port and is blocked by policy"
            raise ValueError(msg)
        return value

    @field_validator("ibkr_account")
    @classmethod
    def require_paper_account_prefix(cls, value: str) -> str:
        """When set, require paper-style ids (DU…). Empty is allowed for offline backtests."""
        stripped = value.strip()
        if not stripped:
            return ""
        if not stripped.startswith("D"):
            msg = "IBKR_ACCOUNT must start with 'D' (paper account id)"
            raise ValueError(msg)
        return stripped

    @model_validator(mode="after")
    def polygon_requires_api_key(self) -> Settings:
        """Polygon adapter needs a non-empty API key."""
        if self.data_provider == "polygon" and not self.polygon_api_key.strip():
            msg = "POLYGON_API_KEY is required when DATA_PROVIDER=polygon"
            raise ValueError(msg)
        return self

    def telegram_user_id_list(self) -> list[int]:
        """Parse ``TELEGRAM_ALLOWED_USER_IDS`` into integers."""
        raw = self.telegram_allowed_user_ids.strip()
        if not raw:
            return []
        return [int(part.strip()) for part in raw.split(",") if part.strip()]

    def telegram_report_recipient_ids(self) -> list[int]:
        """Recipients for scheduled reports (explicit chats else whitelist fall-through)."""
        raw = self.telegram_report_chat_ids.strip()
        if raw:
            return [int(part.strip()) for part in raw.split(",") if part.strip()]
        return self.telegram_user_id_list()

    def paper_ibkr_account_id_required(self) -> str:
        """Return stripped ``DU…`` id for broker connections; raise if unset."""
        stripped = self.ibkr_account.strip()
        if not stripped:
            msg = (
                "IBKR_ACCOUNT is unset — set your paper id (DU…) in `.env` for broker scripts. "
                "Backtests omit this."
            )
            raise ValueError(msg)
        return stripped


def get_settings() -> Settings:
    """Load settings from the environment."""
    return Settings()
