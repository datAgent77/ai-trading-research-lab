"""Configuration-level safety enforcement."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from trading_lab.config import Settings


def test_settings_rejects_live_ibkr_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7496")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "7496" in str(exc.value)


def test_settings_rejects_non_paper_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "U123456")
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "IBKR_ACCOUNT" in str(exc.value)


def test_settings_accepts_paper_port_and_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    settings = Settings()
    assert settings.ibkr_port == 7497
    assert settings.ibkr_account == "DU1234567"
