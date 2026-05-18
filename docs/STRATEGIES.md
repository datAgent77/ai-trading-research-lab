# Strategies

All strategies subclass `strategies.base.Strategy`, validate params at construction, and emit a **`pd.Series`** aligned with OHLCV index with values in **`{-1, 0, +1}`** (short / flat / long). Phase-1 implementations are **long-only** in practice (signals use flat vs long).

Implementation files:

| Alias (CLI / Telegram) | Module | Class |
|------------------------|--------|--------|
| `rsi` | `strategies/rsi_mean_reversion.py` | `RSIMeanReversion` |
| `donchian` | `strategies/donchian_breakout.py` | `DonchianBreakout` |
| `squeeze` | `strategies/bbands_squeeze.py` | `BBandsSqueeze` |

## RSI mean reversion

- **Idea:** Fade short-term oversold conditions; exit on strength or volatility stop.
- **Defaults:** `rsi_period=14`, `oversold=30`, `overbought=70`, `atr_stop_mult=2.0`.
- **Long entry:** RSI crosses **up** through `oversold`.
- **Exit:** RSI > 50 (target) or price hits **ATR-based stop** below entry.
- **Regime weakness:** Strong one-way trends (buy-and-hold dominates); can sit out extended rallies.

## Donchian breakout

- **Idea:** Breakout above rolling highs captures trend legs (Turtle-style).
- **Defaults:** `entry_period=20`, `exit_period=10`, `atr_period=20`.
- **Long entry:** Close > highest high over `entry_period`.
- **Exit:** Close < lowest low over `exit_period`.
- **Regime weakness:** Choppy ranges produce false breaks and drawdown.

## Bollinger / Keltner squeeze breakout

- **Idea:** Compress volatility (BB inside Keltner) then trade breakout direction.
- **Defaults:** `bb_period=20`, `bb_std=2.0`, `squeeze_pct=0.5`, `keltner_mult=1.5`.
- **Regime weakness:** Low-quality breakouts when squeeze signal is noisy; needs trending follow-through.

## Backtest methodology (shared)

- Daily bars via **`DATA_PROVIDER`** (`yfinance` default or `polygon`).
- Costs: configurable **commission_bps** and **slippage_bps** in `backtest/engine.py`.
- Metrics: Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor, expectancy, vs buy-and-hold, etc. (`backtest/metrics.py`).

## Example commands

```bash
uv run python scripts/run_backtest.py rsi SPY --start 2020-01-01 --end 2024-12-31
uv run python scripts/run_backtest.py donchian ASELS.IS --start 2020-01-01 --end 2024-12-31
uv run python scripts/run_walk_forward.py squeeze QQQ --start 2018-01-01 --end 2024-12-31
```

## Sample snapshot (SPY, 2020–2024, engine defaults)

Illustrative only — **not** a promise of future performance. See `README.md` for the published comparison table.

## Known limitations

- **US session assumptions** for risk/trading-hours guards — adapt before automating non-US sessions.
- **Data quality** for non-US symbols (e.g. `.IS`) depends on Yahoo/Polygon; validate manually for decisions.
