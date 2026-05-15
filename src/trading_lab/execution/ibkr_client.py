"""Interactive Brokers client wrapper (stub)."""


class IBKRClient:
    """Enforces paper connectivity rules (implementation in Stage 7)."""

    def __init__(self, host: str, port: int, client_id: int, account_id: str) -> None:
        """Connect to IBKR Gateway/TWS (not implemented)."""
        raise NotImplementedError


__all__ = ["IBKRClient"]
