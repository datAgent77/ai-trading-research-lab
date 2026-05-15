"""Execution-layer errors (paper-only trading lab)."""


class ExecutionError(Exception):
    """Base class for broker routing failures."""


class KillSwitchTrippedError(ExecutionError):
    """Raised when the kill switch blocks new risk."""


class TradingHoursError(ExecutionError):
    """Raised for submissions outside configured US regular hours."""


class PositionCapExceededError(ExecutionError):
    """Raised when an order exceeds ``MAX_POSITION_PCT_NAV`` vs NAV."""


class DuplicateOrderKeyError(ExecutionError):
    """Raised when idempotency key was already used in-process."""


class PaperAccountRequiredError(ExecutionError):
    """Raised when IBKR account context is not paper-safe."""


__all__ = [
    "DuplicateOrderKeyError",
    "ExecutionError",
    "KillSwitchTrippedError",
    "PaperAccountRequiredError",
    "PositionCapExceededError",
    "TradingHoursError",
]
