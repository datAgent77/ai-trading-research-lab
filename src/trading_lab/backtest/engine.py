"""Vectorbt-backed portfolio simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import vectorbt as vbt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_lab.backtest.metrics import compute_metrics
from trading_lab.config import get_settings
from trading_lab.data.yfinance_source import fetch_bars
from trading_lab.db.models import BacktestResult as BacktestResultORM
from trading_lab.db.models import Base as DbBase
from trading_lab.strategies.base import Strategy


@dataclass(frozen=True)
class BacktestResult:
    """Container for equity path, trades, and summary metrics."""

    equity_curve: pd.Series
    trades: pd.DataFrame
    metrics: dict[str, Any]
    params: dict[str, Any]
    meta: dict[str, Any]


def _close_series(ohlcv: pd.DataFrame) -> pd.Series:
    mapping = {str(c).strip().lower(): c for c in ohlcv.columns}
    if "close" not in mapping:
        msg = "OHLCV frame must contain a Close/close column"
        raise ValueError(msg)
    return ohlcv[mapping["close"]].astype(float)


def _entries_exits_from_signals(signal: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Long entries on 0->1; exits on 1->0 (targets match ``RSIMeanReversion`` outputs)."""
    if signal.empty:
        empty = pd.Series(False, index=signal.index, dtype=bool)
        return empty, empty
    s = signal.astype(np.int8).to_numpy()
    prev = np.zeros_like(s, dtype=np.int8)
    prev[0] = 0
    prev[1:] = s[:-1]
    entries_arr = (s == 1) & (prev != 1)
    exits_arr = (s == 0) & (prev == 1)
    idx = signal.index
    return pd.Series(entries_arr, index=idx), pd.Series(exits_arr, index=idx)


def _buy_hold_equity(close: pd.Series, cash: float) -> pd.Series:
    if close.empty or cash <= 0:
        return pd.Series(dtype=float)
    units = cash / float(close.iloc[0])
    return units * close.astype(float)


def _trades_frame_from_portfolio(pf: vbt.Portfolio, symbol: str) -> pd.DataFrame:
    readable = pf.trades.records_readable
    if readable.empty:
        return pd.DataFrame(
            columns=["symbol", "entry_date", "exit_date", "pnl", "return_pct"],
        )
    return pd.DataFrame(
        {
            "symbol": symbol,
            "entry_date": pd.to_datetime(readable["Entry Timestamp"], utc=True),
            "exit_date": pd.to_datetime(readable["Exit Timestamp"], utc=True),
            "pnl": readable["PnL"].astype(float),
            "return_pct": readable["Return"].astype(float),
        },
    )


def _run_symbol_backtest(
    strategy: Strategy,
    symbol: str,
    start: str,
    end: str,
    cash: float,
    commission_bps: float,
    slippage_bps: float,
) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    ohlcv = fetch_bars(symbol, start, end, timeframe="1d")
    if ohlcv.empty:
        empty_trades = pd.DataFrame(
            columns=["symbol", "entry_date", "exit_date", "pnl", "return_pct"],
        )
        return pd.Series(dtype=float), empty_trades, pd.Series(dtype=float)
    close = _close_series(ohlcv)
    if close.empty:
        empty_trades = pd.DataFrame(
            columns=["symbol", "entry_date", "exit_date", "pnl", "return_pct"],
        )
        return pd.Series(dtype=float), empty_trades, pd.Series(dtype=float)
    sig = strategy.generate_signals(ohlcv).reindex(close.index).fillna(0).astype(np.int8)
    entries, exits = _entries_exits_from_signals(sig)
    fee = commission_bps / 10_000.0
    slip = slippage_bps / 10_000.0
    pf = vbt.Portfolio.from_signals(
        close,
        entries,
        exits,
        fees=fee,
        slippage=slip,
        init_cash=float(cash),
        freq="1d",
    )
    equity = pf.value()
    trades = _trades_frame_from_portfolio(pf, symbol)
    bh = _buy_hold_equity(close, cash)
    return equity.astype(float), trades, bh.astype(float)


def _combine_on_intersection(series_list: list[pd.Series]) -> pd.Series:
    if not series_list:
        return pd.Series(dtype=float)
    idx = series_list[0].index
    for s in series_list[1:]:
        idx = idx.intersection(s.index)
    idx = idx.sort_values()
    stacked = np.stack([s.loc[idx].to_numpy(dtype=float) for s in series_list], axis=0)
    return pd.Series(stacked.sum(axis=0), index=idx)


def backtest(
    strategy: Strategy,
    symbols: list[str],
    start: str,
    end: str,
    initial_cash: float = 100_000,
    commission_bps: float = 1.0,
    slippage_bps: float = 2.0,
    *,
    persist: bool = False,
) -> BacktestResult:
    """Run daily long-only signal backtests per symbol and aggregate equal-weight equity."""
    if not symbols:
        msg = "symbols must be non-empty"
        raise ValueError(msg)
    n = len(symbols)
    cash_each = float(initial_cash) / n

    equities: list[pd.Series] = []
    benchmarks: list[pd.Series] = []
    trade_parts: list[pd.DataFrame] = []

    for sym in symbols:
        eq, tr, bh = _run_symbol_backtest(
            strategy,
            sym,
            start,
            end,
            cash_each,
            commission_bps,
            slippage_bps,
        )
        equities.append(eq)
        benchmarks.append(bh)
        trade_parts.append(tr)

    combined_equity = _combine_on_intersection(equities)
    combined_bh = _combine_on_intersection(benchmarks)
    trades_all = pd.concat(trade_parts, ignore_index=True) if trade_parts else pd.DataFrame()

    metrics = compute_metrics(combined_equity, trades_all, benchmark_equity=combined_bh)

    meta: dict[str, Any] = {
        "start": start,
        "end": end,
        "symbols": list(symbols),
        "symbols_joined": ",".join(symbols),
        "strategy_name": strategy.name,
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "initial_cash": initial_cash,
    }

    params_out = dict(strategy.params)
    result = BacktestResult(
        equity_curve=combined_equity,
        trades=trades_all,
        metrics=metrics,
        params=params_out,
        meta=meta,
    )
    if persist:
        save_backtest_result(result)
    return result


def save_backtest_result(result: BacktestResult) -> int:
    """Persist ``result`` to ``backtest_results``. Returns new row id."""
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    DbBase.metadata.create_all(engine)
    created_at = datetime.now(UTC)
    row = BacktestResultORM(
        strategy_run_id=None,
        strategy_name=str(result.meta["strategy_name"]),
        symbol=str(result.meta["symbols_joined"]),
        start_date=str(result.meta["start"]),
        end_date=str(result.meta["end"]),
        metrics=_json_safe(dict(result.metrics)),
        params=_json_safe(dict(result.params)),
        meta=_json_safe(dict(result.meta)),
        created_at=created_at,
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return int(row.id)


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if np.isnan(v) or np.isinf(v) else v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


__all__ = ["BacktestResult", "backtest", "save_backtest_result"]
