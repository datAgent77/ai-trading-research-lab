"""Validated broker submissions (paper account only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from ib_insync import Trade

from trading_lab.db.models import OrderSide
from trading_lab.execution.exceptions import DuplicateOrderKeyError, PositionCapExceededError
from trading_lab.execution.ibkr_client import IBKRClient
from trading_lab.execution.risk import RiskEngine


@dataclass(frozen=True)
class MarketOrderIntent:
    """User/strategy intent for a single market order."""

    strategy_run_id: int
    symbol: str
    quantity: Decimal
    side: OrderSide
    nav: Decimal
    reference_price: Decimal
    bar_timestamp: datetime


def _idempotency_key(intent: MarketOrderIntent) -> tuple[int, str, str]:
    if intent.bar_timestamp.tzinfo is None:
        msg = "bar_timestamp must be timezone-aware"
        raise ValueError(msg)
    ts = intent.bar_timestamp.astimezone(UTC).isoformat()
    return (intent.strategy_run_id, intent.symbol.strip().upper(), ts)


def _order_notional(intent: MarketOrderIntent) -> Decimal:
    return abs(intent.reference_price * intent.quantity)


def _max_allowed_notional(nav: Decimal, max_position_pct_nav: Decimal) -> Decimal:
    return nav * max_position_pct_nav / Decimal("100")


def place_market_order(
    intent: MarketOrderIntent,
    *,
    ibkr: IBKRClient,
    risk: RiskEngine,
    recent_keys: set[tuple[int, str, str]] | None = None,
    now_utc: datetime | None = None,
) -> Trade:
    """Validate guards then submit a market order tagged for auditability.

    Enforces:
        - Positive ``strategy_run_id`` (must correspond to an existing DB row upstream).
        - Kill-switch / NY regular-hours guards via ``risk``.
        - ``MAX_POSITION_PCT_NAV`` versus supplied NAV × reference price.
        - Optional idempotency registry keyed by ``(strategy_run_id, symbol, bar UTC iso)``.
    """
    if intent.strategy_run_id < 1:
        msg = "strategy_run_id must reference a persisted strategy run row"
        raise ValueError(msg)
    if intent.quantity <= 0:
        msg = "quantity must be positive"
        raise ValueError(msg)
    if intent.nav <= 0:
        msg = "nav must be positive"
        raise ValueError(msg)
    if intent.reference_price <= 0:
        msg = "reference_price must be positive"
        raise ValueError(msg)

    key = _idempotency_key(intent)
    if recent_keys is not None and key in recent_keys:
        msg = f"duplicate order key for strategy_run_id={key[0]} symbol={key[1]} ts={key[2]}"
        raise DuplicateOrderKeyError(msg)

    clock = now_utc if now_utc is not None else datetime.now(UTC)
    risk.ensure_order_allowed(now_utc=clock)

    notion = _order_notional(intent)
    ceiling = _max_allowed_notional(intent.nav, risk.settings.max_position_pct_nav)
    if notion > ceiling:
        msg = (
            f"order notional {notion} exceeds cap {ceiling} "
            f"({risk.settings.max_position_pct_nav}% of NAV {intent.nav})"
        )
        raise PositionCapExceededError(msg)

    trade = ibkr.submit_market_order(
        symbol=intent.symbol,
        quantity=intent.quantity,
        side=intent.side,
    )
    if recent_keys is not None:
        recent_keys.add(key)
    return trade


__all__ = ["MarketOrderIntent", "place_market_order"]
