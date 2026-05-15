"""Rolling walk-forward backtests (fixed in-sample / out-of-sample calendar windows)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from trading_lab.backtest.engine import BacktestResult, backtest
from trading_lab.strategies.base import Strategy


@dataclass(frozen=True)
class WalkForwardSlice:
    """One in-sample run paired with the following out-of-sample run."""

    in_sample_start: str
    in_sample_end: str
    out_sample_start: str
    out_sample_end: str
    in_sample_result: BacktestResult
    out_sample_result: BacktestResult


@dataclass(frozen=True)
class WalkForwardResult:
    """Full walk-forward report and bookkeeping metadata."""

    slices: tuple[WalkForwardSlice, ...]
    meta: dict[str, Any]


def walk_forward(
    strategy: Strategy,
    symbols: list[str],
    start: str,
    end: str,
    *,
    in_sample_months: int = 24,
    out_sample_months: int = 6,
    step_months: int | None = None,
    initial_cash: float = 100_000,
    commission_bps: float = 1.0,
    slippage_bps: float = 2.0,
    persist: bool = False,
) -> WalkForwardResult:
    """Roll calendar windows: optimize/train assumptions use IS metrics; OOS follows immediately.

    Each slice runs ``backtest`` on ``[in_sample_start, in_sample_end]`` inclusive, then on
    ``[out_sample_start, out_sample_end]`` inclusive. Windows advance by ``step_months`` (default:
    ``out_sample_months``). The boundary between IS and OOS is the first day of the OOS month span.

    Args:
        strategy: Concrete ``Strategy`` instance (same params for every slice).
        symbols: Symbols passed through to ``backtest``.
        start: First eligible **in-sample** start (``YYYY-MM-DD``).
        end: Last calendar day that **out-of-sample** may include (inclusive).
        in_sample_months: Length of each in-sample segment.
        out_sample_months: Length of each out-of-sample segment.
        step_months: Rolling step for the next slice start; defaults to ``out_sample_months``.
        initial_cash: Cash passed to each ``backtest`` call.
        commission_bps: Commission per ``backtest``.
        slippage_bps: Slippage per ``backtest``.
        persist: Forwarded to ``backtest`` when ``True``.

    Returns:
        ``WalkForwardResult`` with ordered slices and summary ``meta``.
    """
    if in_sample_months < 1:
        msg = "in_sample_months must be >= 1"
        raise ValueError(msg)
    if out_sample_months < 1:
        msg = "out_sample_months must be >= 1"
        raise ValueError(msg)

    step = step_months if step_months is not None else out_sample_months
    if step < 1:
        msg = "step_months must be >= 1"
        raise ValueError(msg)

    range_end = pd.Timestamp(end, tz="UTC").normalize()
    cursor = pd.Timestamp(start, tz="UTC").normalize()

    pieces: list[WalkForwardSlice] = []

    while True:
        is_start = cursor
        is_boundary = is_start + pd.DateOffset(months=in_sample_months)
        oos_boundary = is_boundary + pd.DateOffset(months=out_sample_months)

        is_last = is_boundary - pd.Timedelta(days=1)
        oos_last = oos_boundary - pd.Timedelta(days=1)

        if oos_last > range_end:
            break

        is_start_s = _fmt_day(is_start)
        is_end_s = _fmt_day(is_last)
        oos_start_s = _fmt_day(is_boundary)
        oos_end_s = _fmt_day(oos_last)

        is_res = backtest(
            strategy,
            symbols,
            is_start_s,
            is_end_s,
            initial_cash=initial_cash,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            persist=persist,
        )
        oos_res = backtest(
            strategy,
            symbols,
            oos_start_s,
            oos_end_s,
            initial_cash=initial_cash,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            persist=persist,
        )

        pieces.append(
            WalkForwardSlice(
                in_sample_start=is_start_s,
                in_sample_end=is_end_s,
                out_sample_start=oos_start_s,
                out_sample_end=oos_end_s,
                in_sample_result=is_res,
                out_sample_result=oos_res,
            ),
        )

        cursor = cursor + pd.DateOffset(months=step)

    meta: dict[str, Any] = {
        "start": start,
        "end": end,
        "symbols": list(symbols),
        "strategy_name": strategy.name,
        "in_sample_months": in_sample_months,
        "out_sample_months": out_sample_months,
        "step_months": step,
        "num_slices": len(pieces),
    }

    return WalkForwardResult(slices=tuple(pieces), meta=meta)


def _fmt_day(ts: pd.Timestamp) -> str:
    """Format ``ts`` as UTC ``YYYY-MM-DD``."""
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


__all__ = ["WalkForwardResult", "WalkForwardSlice", "walk_forward"]
