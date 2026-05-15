"""Broker execution and risk controls."""

from trading_lab.execution.exceptions import (
    DuplicateOrderKeyError,
    ExecutionError,
    KillSwitchTrippedError,
    PaperAccountRequiredError,
    PositionCapExceededError,
    TradingHoursError,
)
from trading_lab.execution.ibkr_client import ORDER_REF_TAG, IBKRClient
from trading_lab.execution.order_manager import MarketOrderIntent, place_market_order
from trading_lab.execution.position_tracker import snapshot_positions
from trading_lab.execution.risk import (
    KillSwitchState,
    RiskEngine,
    assert_us_regular_trading_hours,
    daily_return_pct,
    exceeds_max_daily_drawdown,
    parse_hhmm_local,
)

__all__ = [
    "DuplicateOrderKeyError",
    "ExecutionError",
    "IBKRClient",
    "KillSwitchState",
    "KillSwitchTrippedError",
    "MarketOrderIntent",
    "ORDER_REF_TAG",
    "PaperAccountRequiredError",
    "PositionCapExceededError",
    "RiskEngine",
    "TradingHoursError",
    "assert_us_regular_trading_hours",
    "daily_return_pct",
    "exceeds_max_daily_drawdown",
    "parse_hhmm_local",
    "place_market_order",
    "snapshot_positions",
]
