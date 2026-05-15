"""Data-layer errors."""


class DataSourceUnavailable(RuntimeError):
    """Raised when a market data provider cannot be used (missing credentials, etc.)."""


__all__ = ["DataSourceUnavailable"]
