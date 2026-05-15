"""Application configuration loaded from environment variables."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, field_validator
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
            "Separate IBKR client id for Telegram-driven reads "
            "(defaults to IBKR_CLIENT_ID + 1)"
        ),
    )

    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 42
    ibkr_account: str = Field(default="", description="Paper account id; must start with D")

    max_daily_drawdown_pct: Decimal = Field(default=Decimal("-3.0"))
    max_position_pct_nav: Decimal = Field(default=Decimal("5.0"))
    trading_start_ny: str = "09:30"
    trading_end_ny: str = "16:00"

    polygon_api_key: str = ""
    data_cache_dir: str = Field(default=DEFAULT_DATA_CACHE_DIR)

    database_url: str = "sqlite:///./trading_lab.db"

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
        """Require paper-style account ids (Interactive Brokers paper accounts start with D)."""
        stripped = value.strip()
        if not stripped:
            msg = (
                "IBKR_ACCOUNT is unset or empty — set your paper account id in `.env` "
                "(must start with 'D', e.g. DU1234567). See `.env.example`."
            )
            raise ValueError(msg)
        if not stripped.startswith("D"):
            msg = "IBKR_ACCOUNT must start with 'D' (paper account id)"
            raise ValueError(msg)
        return stripped

    def telegram_user_id_list(self) -> list[int]:
        """Parse ``TELEGRAM_ALLOWED_USER_IDS`` into integers."""
        raw = self.telegram_allowed_user_ids.strip()
        if not raw:
            return []
        return [int(part.strip()) for part in raw.split(",") if part.strip()]


def get_settings() -> Settings:
    """Load settings from the environment."""
    return Settings()
