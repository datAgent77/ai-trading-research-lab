"""Risk limits and kill-switch orchestration (stub)."""


class KillSwitchState:
    """In-memory placeholder until persistence lands."""

    def __init__(self) -> None:
        self.tripped: bool = False


def evaluate_daily_drawdown_stub(*args: object, **kwargs: object) -> bool:
    """Return ``True`` when trading must halt."""
    raise NotImplementedError


__all__ = ["KillSwitchState", "evaluate_daily_drawdown_stub"]
