"""Structured logging setup (structlog wiring comes in a later stage)."""

from __future__ import annotations

import logging


def configure_logging(json_output: bool = True, level: int = logging.INFO) -> None:
    """Configure stdlib logging.

    Args:
        json_output: When ``True``, emit JSON-shaped records where practical (placeholder).
        level: Root log level.
    """
    _ = json_output
    logging.basicConfig(level=level)
