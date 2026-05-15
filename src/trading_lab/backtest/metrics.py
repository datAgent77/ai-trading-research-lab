"""Backtest performance metrics (daily bars, 252-day year, risk-free 0)."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def compute_metrics(
    equity_curve: pd.Series,
    trades: pd.DataFrame,
    benchmark_equity: pd.Series | None = None,
    *,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
    risk_free_rate: float = 0.0,
) -> dict[str, Any]:
    """Compute summary metrics from an equity curve and closed-trade rows.

    Args:
        equity_curve: Portfolio value indexed by timestamp (daily).
        trades: Must include ``pnl`` and ``return_pct`` columns when non-empty.
        benchmark_equity: Optional buy-and-hold equity curve (same frequency).
        trading_days_per_year: Annualization factor for Sharpe/Sortino.
        risk_free_rate: Annualized risk-free rate (simple daily drift subtracted).

    Returns:
        JSON-friendly dict of floats / ints (NaNs as ``None`` where needed).
    """
    eq = equity_curve.astype(float).sort_index()
    daily_rf = risk_free_rate / float(trading_days_per_year)

    rets = eq.pct_change().dropna()
    excess = rets - daily_rf
    std = float(excess.std(ddof=1))
    mu = float(excess.mean())
    if std > 1e-16 and len(excess) > 1:
        sharpe = float(math.sqrt(trading_days_per_year) * mu / std)
    else:
        sharpe = math.nan

    downside = rets[rets < 0]
    dstd = float(downside.std(ddof=1)) if len(downside) > 1 else math.nan
    sortino = (
        float(math.sqrt(trading_days_per_year) * float(rets.mean() - daily_rf) / dstd)
        if not math.isnan(dstd) and dstd > 1e-16
        else math.nan
    )

    roll_max = eq.cummax()
    dd = eq / roll_max - 1.0
    max_dd = float(dd.min()) if len(eq) else math.nan

    if len(eq) == 0:
        total_return = math.nan
        cagr = math.nan
    else:
        v0 = float(eq.iloc[0])
        v1 = float(eq.iloc[-1])
        total_return = (v1 / v0 - 1.0) if v0 > 0 else math.nan
        n = len(eq)
        years = n / float(trading_days_per_year)
        cagr = float((v1 / v0) ** (1.0 / years) - 1.0) if v0 > 0 and years > 0 else math.nan

    calmar = float(cagr / abs(max_dd)) if max_dd < -1e-16 and not math.isnan(cagr) else math.nan

    num_trades = int(len(trades))
    if trades.empty or "pnl" not in trades.columns:
        win_rate = math.nan
        profit_factor = math.nan
        expectancy = math.nan
        avg_trade = math.nan
        avg_win = math.nan
        avg_loss = math.nan
    else:
        pnl = trades["pnl"].astype(float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        win_rate = float(len(wins) / num_trades) if num_trades else math.nan
        gross_win = float(wins.sum()) if len(wins) else 0.0
        gross_loss = float(losses.sum()) if len(losses) else 0.0
        profit_factor = float(gross_win / abs(gross_loss)) if gross_loss < -1e-12 else math.nan
        expectancy = float(pnl.mean()) if num_trades else math.nan
        avg_trade = float(pnl.mean()) if num_trades else math.nan
        avg_win = float(wins.mean()) if len(wins) else math.nan
        avg_loss = float(losses.mean()) if len(losses) else math.nan

    vs_bh = math.nan
    if benchmark_equity is not None and len(eq) and len(benchmark_equity):
        bh = benchmark_equity.astype(float).sort_index()
        common = eq.index.intersection(bh.index)
        if len(common) >= 2:
            e0 = float(eq.loc[common].iloc[0])
            e1 = float(eq.loc[common].iloc[-1])
            b0 = float(bh.loc[common].iloc[0])
            b1 = float(bh.loc[common].iloc[-1])
            if b0 > 0 and e0 > 0:
                strat_tr = e1 / e0 - 1.0
                bh_tr = b1 / b0 - 1.0
                vs_bh = float(strat_tr - bh_tr)

    raw = {
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_dd": max_dd,
        "total_return": total_return,
        "cagr": cagr,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "num_trades": num_trades,
        "avg_trade": avg_trade,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "vs_buy_and_hold": vs_bh,
    }
    return {k: (_nan_to_none(v) if isinstance(v, float) else v) for k, v in raw.items()}


def _nan_to_none(value: float) -> float | None:
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


__all__ = ["TRADING_DAYS_PER_YEAR", "compute_metrics"]
