"""Risk limits and kill-switch helpers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from trading_lab.config import Settings
from trading_lab.execution.exceptions import KillSwitchTrippedError, TradingHoursError

_NY = ZoneInfo("America/New_York")


class KillSwitchState:
    """In-memory kill switch (live runner should persist or hydrate separately)."""

    def __init__(self) -> None:
        self.tripped: bool = False
        self.reason: str = ""

    def trip(self, reason: str) -> None:
        """Latch the switch closed."""
        self.tripped = True
        self.reason = reason

    def reset(self) -> None:
        """Manual reset path (e.g. Telegram ``/reset_killswitch`` in later stages)."""
        self.tripped = False
        self.reason = ""


class RiskEngine:
    """Trading-hours guard and kill-switch coordination."""

    def __init__(self, settings: Settings, kill_switch: KillSwitchState) -> None:
        self._settings = settings
        self.kill_switch = kill_switch

    @property
    def settings(self) -> Settings:
        """Settings snapshot backing checks."""
        return self._settings

    def ensure_order_allowed(self, *, now_utc: datetime) -> None:
        """Raise when kill-switch is latched or outside regular equity hours."""
        if self.kill_switch.tripped:
            msg = f"kill switch tripped: {self.kill_switch.reason or 'unknown'}"
            raise KillSwitchTrippedError(msg)
        assert_us_regular_trading_hours(
            now_utc,
            self._settings.trading_start_ny,
            self._settings.trading_end_ny,
        )

    def evaluate_daily_drawdown(
        self,
        *,
        day_start_equity: Decimal,
        current_equity: Decimal,
    ) -> bool:
        """Trip kill switch if intraday PnL%% breaches configured floor.

        Returns:
            ``True`` when the switch was newly tripped.
        """
        if exceeds_max_daily_drawdown(
            day_start_equity,
            current_equity,
            self._settings.max_daily_drawdown_pct,
        ):
            self.kill_switch.trip("max_daily_drawdown_pct")
            return True
        return False


def parse_hhmm_local(token: str) -> tuple[int, int]:
    """Parse ``HH:MM`` into hour/minute."""
    parts = token.strip().split(":")
    if len(parts) != 2:
        msg = f"expected HH:MM, got {token!r}"
        raise ValueError(msg)
    return int(parts[0]), int(parts[1])


def _seconds_since_midnight_local(dt_local: datetime) -> int:
    return dt_local.hour * 3600 + dt_local.minute * 60 + dt_local.second


def assert_us_regular_trading_hours(at_utc: datetime, start_hhmm: str, end_hhmm: str) -> None:
    """Require NY weekday equity session ``[start, end)`` (``end`` exclusive).

    Args:
        at_utc: Timezone-aware instant (typically UTC).
        start_hhmm: Session open in America/New_York wall clock.
        end_hhmm: Session **close**, exclusive upper bound at this minute boundary.

    Raises:
        TradingHoursError: Outside configured session or weekend.
        ValueError: ``at_utc`` lacks timezone information.
    """
    if at_utc.tzinfo is None:
        msg = "now_utc must be timezone-aware"
        raise ValueError(msg)

    ny = at_utc.astimezone(_NY)
    if ny.weekday() >= 5:
        raise TradingHoursError("Weekend — regular session closed")

    sh, sm = parse_hhmm_local(start_hhmm)
    eh, em = parse_hhmm_local(end_hhmm)
    start_s = sh * 3600 + sm * 60
    end_s = eh * 3600 + em * 60
    cur = _seconds_since_midnight_local(ny)
    if not (start_s <= cur < end_s):
        raise TradingHoursError(
            f"Outside trading window {start_hhmm}-{end_hhmm} America/New_York "
            f"(now {ny.strftime('%Y-%m-%d %H:%M:%S %Z')})",
        )


def daily_return_pct(day_start_equity: Decimal, current_equity: Decimal) -> Decimal:
    """Percent change versus ``day_start_equity``."""
    if day_start_equity <= 0:
        return Decimal("0")
    return (current_equity - day_start_equity) / day_start_equity * Decimal("100")


def exceeds_max_daily_drawdown(
    day_start_equity: Decimal,
    current_equity: Decimal,
    max_daily_drawdown_pct: Decimal,
) -> bool:
    """Compare realized+unrealized drift vs a negative threshold like ``-3.0``."""
    return daily_return_pct(day_start_equity, current_equity) <= max_daily_drawdown_pct


__all__ = [
    "KillSwitchState",
    "RiskEngine",
    "assert_us_regular_trading_hours",
    "daily_return_pct",
    "exceeds_max_daily_drawdown",
    "parse_hhmm_local",
]
