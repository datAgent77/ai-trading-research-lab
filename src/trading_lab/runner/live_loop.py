"""Paper-trading polling loop: OHLCV → deterministic signals → validated broker orders."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Any, cast

import pandas as pd
from sqlalchemy.orm import Session, sessionmaker

from trading_lab.data.yfinance_source import fetch_bars as default_fetch_bars
from trading_lab.db.models import OrderSide
from trading_lab.execution.exceptions import (
    DuplicateOrderKeyError,
    KillSwitchTrippedError,
    PositionCapExceededError,
    TradingHoursError,
)
from trading_lab.execution.ibkr_client import IBKRClient
from trading_lab.execution.kill_switch_store import apply_kill_switch_from_db
from trading_lab.execution.order_manager import MarketOrderIntent, place_market_order
from trading_lab.execution.risk import RiskEngine
from trading_lab.strategies.base import Strategy

logger = logging.getLogger(__name__)

BarsFetcher = Callable[[str, str, str], pd.DataFrame]


@dataclass(frozen=True)
class LiveBinding:
    """One running strategy instance mapped to a symbol and persisted ``strategy_run`` row."""

    strategy_run_id: int
    strategy: Strategy
    symbol: str


class LiveLoop:
    """Poll daily bars, detect position-target transitions, route orders through ``risk`` guards."""

    def __init__(
        self,
        ibkr: IBKRClient,
        risk: RiskEngine,
        bindings: list[LiveBinding],
        *,
        bars_fetcher: BarsFetcher | None = None,
        history_calendar_days: int = 450,
        dry_run: bool = False,
        recent_keys: set[tuple[int, str, str]] | None = None,
        kill_switch_session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._ibkr = ibkr
        self._risk = risk
        self._bindings = list(bindings)
        self._bars_fetcher = bars_fetcher if bars_fetcher is not None else default_fetch_bars
        self._history_days = int(history_calendar_days)
        self._dry_run = dry_run
        rk = recent_keys if recent_keys is not None else set()
        self._recent_keys = rk
        self._prev_targets: dict[tuple[int, str], int] = {}
        self._kill_switch_session_factory = kill_switch_session_factory

    def prime_previous_signal(self, strategy_run_id: int, symbol: str, target: int) -> None:
        """Hydrate remembered targets (tests + controlled restarts)."""
        key = (strategy_run_id, symbol.strip().upper())
        self._prev_targets[key] = max(-1, min(1, int(target)))

    def _sync_kill_switch_from_db(self) -> None:
        factory = self._kill_switch_session_factory
        if factory is None:
            return
        session = factory()
        try:
            apply_kill_switch_from_db(session, self._risk.kill_switch)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @property
    def recent_keys(self) -> set[tuple[int, str, str]]:
        """Shared idempotency registry for placed orders."""
        return self._recent_keys

    def tick_once(self, *, now_utc: datetime | None = None) -> None:
        """Execute a single polling cycle for every binding (synchronous)."""
        clock = now_utc if now_utc is not None else datetime.now(UTC)
        self._sync_kill_switch_from_db()
        for binding in self._bindings:
            try:
                self._process_binding(binding, now_utc=clock)
            except Exception:
                logger.exception(
                    "live_binding_tick_failed run_id=%s symbol=%s",
                    binding.strategy_run_id,
                    binding.symbol,
                )

    async def run_forever(
        self,
        poll_seconds: float = 60.0,
        *,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Poll until ``stop_event`` is set (or forever when omitted)."""
        stop = stop_event if stop_event is not None else asyncio.Event()
        try:
            while not stop.is_set():
                self.tick_once()
                try:
                    await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
                except TimeoutError:
                    continue
        finally:
            logger.info("live_loop_stopped")

    def _process_binding(self, binding: LiveBinding, *, now_utc: datetime) -> None:
        sym_u = binding.symbol.strip().upper()
        key_state = (binding.strategy_run_id, sym_u)

        end_d = now_utc.astimezone(UTC).date()
        start_d = end_d - timedelta(days=self._history_days)
        frame = self._bars_fetcher(sym_u, str(start_d), str(end_d))
        if frame.empty:
            logger.warning(
                "live_binding_empty_ohlcv run_id=%s symbol=%s",
                binding.strategy_run_id,
                sym_u,
            )
            return

        sig_series = binding.strategy.generate_signals(frame).reindex(frame.index).fillna(0)
        raw_last = sig_series.iloc[-1]
        curr_target = max(-1, min(1, int(raw_last)))

        prev_target = self._prev_targets.get(key_state, 0)

        bar_ts = _bar_timestamp_utc(sig_series.index[-1])

        prev_long = prev_target > 0
        curr_long = curr_target > 0

        nav = _net_liquidation_decimal(self._ibkr.ib, self._ibkr.account_id)
        px = _last_close_decimal(frame)

        intent: MarketOrderIntent | None = None

        if curr_long and not prev_long:
            max_pct = self._risk.settings.max_position_pct_nav
            qty = _buy_quantity(nav=nav, reference_price=px, max_pct=max_pct)
            if qty is None or qty < 1:
                logger.info(
                    "live_binding_skip_buy_qty run_id=%s symbol=%s qty=%s",
                    binding.strategy_run_id,
                    sym_u,
                    qty,
                )
            else:
                intent = MarketOrderIntent(
                    strategy_run_id=binding.strategy_run_id,
                    symbol=sym_u,
                    quantity=qty,
                    side=OrderSide.BUY,
                    nav=nav,
                    reference_price=px,
                    bar_timestamp=bar_ts,
                )
        elif prev_long and not curr_long:
            sell_qty = _position_quantity(self._ibkr.ib, self._ibkr.account_id, sym_u)
            if sell_qty is None or sell_qty <= 0:
                logger.warning(
                    "live_binding_exit_without_position run_id=%s symbol=%s",
                    binding.strategy_run_id,
                    sym_u,
                )
            else:
                intent = MarketOrderIntent(
                    strategy_run_id=binding.strategy_run_id,
                    symbol=sym_u,
                    quantity=sell_qty,
                    side=OrderSide.SELL,
                    nav=nav,
                    reference_price=px,
                    bar_timestamp=bar_ts,
                )

        self._prev_targets[key_state] = curr_target

        if intent is None:
            return

        if self._dry_run:
            logger.info(
                "live_dry_run_order run_id=%s symbol=%s side=%s qty=%s ref=%s",
                intent.strategy_run_id,
                intent.symbol,
                intent.side,
                intent.quantity,
                intent.reference_price,
            )
            return

        try:
            trade = place_market_order(
                intent,
                ibkr=self._ibkr,
                risk=self._risk,
                recent_keys=self._recent_keys,
                now_utc=now_utc,
            )
            logger.info(
                "live_order_submitted run_id=%s symbol=%s order_id=%s",
                binding.strategy_run_id,
                sym_u,
                getattr(trade.order, "orderId", None),
            )
        except (
            DuplicateOrderKeyError,
            KillSwitchTrippedError,
            TradingHoursError,
            PositionCapExceededError,
        ) as exc:
            logger.warning(
                "live_order_blocked run_id=%s symbol=%s reason=%s",
                binding.strategy_run_id,
                sym_u,
                exc,
            )
        except Exception:
            logger.exception(
                "live_order_submit_failed run_id=%s symbol=%s",
                binding.strategy_run_id,
                sym_u,
            )


def _bar_timestamp_utc(idx_val: object) -> datetime:
    ts = pd.Timestamp(cast(Any, idx_val))
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    out = ts.to_pydatetime()
    if out.tzinfo is None:
        msg = "internal error: bar timestamp lacks timezone"
        raise RuntimeError(msg)
    return out


def _last_close_decimal(frame: pd.DataFrame) -> Decimal:
    mapping = {str(c).strip().lower(): c for c in frame.columns}
    col = mapping.get("close")
    if col is None:
        msg = "OHLCV frame missing close column"
        raise ValueError(msg)
    val = float(frame[col].iloc[-1])
    return Decimal(str(val))


def _net_liquidation_decimal(ib: Any, account_id: str) -> Decimal:
    rows = ib.accountSummary(account_id)
    for row in rows:
        if getattr(row, "tag", "") == "NetLiquidation":
            return Decimal(str(row.value))
    logger.warning("NetLiquidation missing on account summary; defaulting NAV to 0")
    return Decimal("0")


def _position_quantity(ib: Any, account_id: str, symbol: str) -> Decimal | None:
    sym_u = symbol.upper()
    for pos in ib.positions(account=account_id):
        if getattr(pos.contract, "symbol", "").upper() == sym_u:
            return Decimal(str(abs(float(pos.position))))
    return None


def _buy_quantity(
    *,
    nav: Decimal,
    reference_price: Decimal,
    max_pct: Decimal,
) -> Decimal | None:
    if nav <= 0 or reference_price <= 0:
        return None
    max_notional = nav * max_pct / Decimal("100")
    shares = (max_notional / reference_price).quantize(Decimal("1"), rounding=ROUND_DOWN)
    return shares


__all__ = ["LiveBinding", "LiveLoop"]
