"""Pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _default_ibkr_safety_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure settings validation passes unless a test overrides IBKR env vars."""
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
