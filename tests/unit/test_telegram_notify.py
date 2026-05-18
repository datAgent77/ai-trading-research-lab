"""Telegram notify helpers (HTTP)."""

from __future__ import annotations

from typing import Any

import pytest

from trading_lab.config import Settings
from trading_lab.telegram_bot.notify import (
    send_telegram_text,
    telegram_notifier_from_settings,
)


def test_send_telegram_posts_to_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "999")

    opened: list[Any] = []

    class _Resp:
        def read(self) -> bytes:
            return b"{}"

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def _fake_urlopen(req: Any, timeout: float | None = None) -> _Resp:
        del timeout
        opened.append(req.full_url)
        return _Resp()

    monkeypatch.setattr(
        "trading_lab.telegram_bot.notify.urllib.request.urlopen",
        _fake_urlopen,
    )
    send_telegram_text(Settings(), "paper lab ping")
    assert opened and "api.telegram.org" in opened[0]


def test_telegram_notifier_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    monkeypatch.setenv("TELEGRAM_LIVE_NOTIFY_ENABLED", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "1")
    assert telegram_notifier_from_settings(Settings()) is None


def test_telegram_notifier_none_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    monkeypatch.setenv("TELEGRAM_LIVE_NOTIFY_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "1")
    assert telegram_notifier_from_settings(Settings()) is None
