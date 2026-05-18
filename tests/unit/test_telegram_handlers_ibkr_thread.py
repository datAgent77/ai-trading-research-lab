"""Telegram handlers: IBKR calls from asyncio thread pool."""

from __future__ import annotations

import asyncio

from trading_lab.telegram_bot.handlers import _run_ibkr_sync_in_thread


def test_ibkr_sync_worker_runs_under_to_thread() -> None:
    async def main() -> str:
        return await asyncio.to_thread(_run_ibkr_sync_in_thread, lambda: "ok")

    assert asyncio.run(main()) == "ok"
