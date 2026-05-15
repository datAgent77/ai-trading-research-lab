"""Live polling loop behaviour."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from fake_ibkr import RecordingFakeIB, make_position

from trading_lab.config import Settings
from trading_lab.execution.ibkr_client import IBKRClient
from trading_lab.execution.risk import KillSwitchState, RiskEngine
from trading_lab.runner.live_loop import LiveBinding, LiveLoop
from trading_lab.strategies.base import Strategy


class CountStrategy(Strategy):
    """Synthetic strategy: first tick flat, afterwards long (until optional reset tests)."""

    name = "count_strategy"
    default_params: ClassVar[dict[str, Any]] = {}

    def validate_params(self) -> None:
        return

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self._n = 0

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        self._n += 1
        target = 1 if self._n >= 2 else 0
        return pd.Series(target, index=ohlcv.index, dtype="int64")


def _ny_monday_open_utc() -> datetime:
    ny = ZoneInfo("America/New_York")
    return datetime(2024, 6, 10, 11, 0, tzinfo=ny).astimezone(UTC)


def _bars(sym: str, start: str, end: str) -> pd.DataFrame:
    _ = sym
    end_ts = pd.Timestamp(end, tz="UTC")
    idx = pd.date_range(end_ts - pd.Timedelta(days=59), periods=60, freq="D", tz="UTC")
    close = 100.0
    return pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close},
        index=idx,
    )


@pytest.fixture
def risk_bundle(monkeypatch: pytest.MonkeyPatch) -> RiskEngine:
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU1234567")
    settings = Settings()
    return RiskEngine(settings, KillSwitchState())


def test_tick_places_buy_after_second_signal(risk_bundle: RiskEngine) -> None:
    fake = RecordingFakeIB()
    ibkr = IBKRClient(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        account_id="DU1234567",
        ib=fake,
        connect=False,
    )
    strat = CountStrategy()
    loop = LiveLoop(
        ibkr=ibkr,
        risk=risk_bundle,
        bindings=[LiveBinding(strategy_run_id=5, strategy=strat, symbol="SPY")],
        bars_fetcher=_bars,
    )
    now = _ny_monday_open_utc()
    loop.tick_once(now_utc=now)
    assert fake.placed == []
    loop.tick_once(now_utc=now)
    assert len(fake.placed) == 1
    assert fake.placed[0][1].action == "BUY"


def test_tick_places_sell_when_flattening(risk_bundle: RiskEngine) -> None:
    fake = RecordingFakeIB()
    fake.seed_positions([make_position(symbol="SPY", qty=Decimal("10"), avg_cost=Decimal("100"))])
    ibkr = IBKRClient(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        account_id="DU1234567",
        ib=fake,
        connect=False,
    )

    class AlwaysFlat(Strategy):
        name = "always_flat"
        default_params: ClassVar[dict[str, Any]] = {}

        def validate_params(self) -> None:
            return

        def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
            return pd.Series(0, index=ohlcv.index, dtype="int64")

    strat = AlwaysFlat()
    loop = LiveLoop(
        ibkr=ibkr,
        risk=risk_bundle,
        bindings=[LiveBinding(strategy_run_id=6, strategy=strat, symbol="SPY")],
        bars_fetcher=_bars,
    )
    loop.prime_previous_signal(6, "SPY", 1)
    loop.tick_once(now_utc=_ny_monday_open_utc())
    sells = [t for t in fake.placed if t[1].action == "SELL"]
    assert sells and sells[-1][1].totalQuantity == 10.0


def test_run_forever_stops_on_event(risk_bundle: RiskEngine) -> None:
    fake = RecordingFakeIB()
    ibkr = IBKRClient(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        account_id="DU1234567",
        ib=fake,
        connect=False,
    )
    strat = CountStrategy()
    loop = LiveLoop(
        ibkr=ibkr,
        risk=risk_bundle,
        bindings=[LiveBinding(strategy_run_id=7, strategy=strat, symbol="SPY")],
        bars_fetcher=_bars,
    )

    async def body() -> None:
        stop = asyncio.Event()

        async def fire() -> None:
            await asyncio.sleep(0.05)
            stop.set()

        asyncio.create_task(fire())
        await loop.run_forever(poll_seconds=0.05, stop_event=stop)

    asyncio.run(body())
