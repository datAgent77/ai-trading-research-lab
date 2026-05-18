# AI Trading Research Lab

> Paper-only trading research platform combining deterministic Python strategies, Claude-powered analysis, and Interactive Brokers paper execution. Built to study mean reversion, trend following, and volatility breakout regimes in equity markets — safely.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org)
[![Type Checked: mypy strict](https://img.shields.io/badge/mypy-strict-success)](http://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/tests-102%20passing-success)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Paper Trading Only](https://img.shields.io/badge/trading-paper%20only-orange)](#safety)

---

## What this is

A research-grade backtesting and paper-trading system that:

- **Runs three quantitative strategies** across mean reversion, trend following, and volatility breakout regimes.
- **Backtests with realistic costs** — basis-point commission and slippage, Wilder-smoothed indicators, walk-forward out-of-sample validation.
- **Uses Claude for analysis, not for trading decisions** — strategy refinement, regime detection, and post-trade reports. Order execution is fully deterministic.
- **Executes on IBKR paper accounts only** — multi-layer safety enforcement makes a live-account misfire structurally impossible.
- **Controlled via Telegram** — kill switch, status queries, on-demand backtests, scheduled reports.

This is a **portfolio project** demonstrating production patterns for financial automation: type-safe Python, audited LLM calls, structural safety guards, walk-forward optimization, and async live loops.

---

## Sample backtest results

Real backtests on SPY, 2020-01-01 → 2024-12-31, 1bp commission + 2bp slippage, no leverage:

| Strategy | Trades | Total Return | Sharpe | Max Drawdown | Win Rate | vs Buy & Hold |
|---|---:|---:|---:|---:|---:|---:|
| **Donchian Breakout** | 13 | +22.4% | 0.73 | -9.1% | 54% | -0.3pp |
| **RSI Mean Reversion** | 5 | +1.4% | 0.11 | -8.8% | 60% | -21.3pp |
| **BBands Squeeze** | 6 | -1.9% | -0.12 | -8.9% | 33% | -24.6pp |

**Reading the results:** Donchian captured the 2020-2024 trend regime, keeping pace with buy-and-hold at a third of the time in market. The mean reversion and squeeze strategies underperformed during this period — exactly the regime mismatch that motivates the Claude-driven regime detection layer.

> **No strategy here is meant to be profitable in production.** The point is the infrastructure: deterministic signals, validated execution, audited LLM calls, full walk-forward validation, and structural safety.

---

## Architecture

```mermaid
graph TD
    subgraph Data["Data Layer"]
        YF[Yahoo Finance]
        PG[Polygon.io]
        CACHE[(Parquet Cache)]
    end

    subgraph Strategies["Strategies (deterministic)"]
        RSI[RSI Mean Reversion]
        DON[Donchian Breakout]
        BB[BBands Squeeze]
    end

    subgraph Backtest["Backtest Engine"]
        ENG[vectorbt engine]
        MET[11 metrics suite]
        WF[Walk-Forward]
    end

    subgraph Claude["Claude AI (analysis only)"]
        REF[Param Refinement]
        REP[Daily/Weekly Reports]
        REG[Regime Detection]
    end

    subgraph Execution["Paper Execution"]
        IBKR[IBKR Client]
        OM[Order Manager]
        RISK[Risk Engine]
        KS[Kill Switch]
    end

    subgraph Control["Control Plane"]
        TG[Telegram Bot]
        SCH[Scheduler]
        LL[Live Loop]
    end

    YF --> CACHE
    PG --> CACHE
    CACHE --> Strategies
    Strategies --> ENG
    ENG --> MET
    ENG --> WF
    MET --> Claude
    Claude -.suggestions.-> Strategies
    Strategies --> LL
    LL --> RISK
    RISK --> OM
    OM --> IBKR
    KS -.halts.-> OM
    TG --> LL
    TG --> Claude
    SCH --> Claude
    SCH --> LL
```

---

## Safety

Trading systems that touch live brokerage accounts must be **structurally** safe, not just intentionally safe. The repo enforces these guarantees:

| Guarantee | Enforcement |
|---|---|
| Paper account only | Config rejects IBKR port `7496` (live TWS) at validation time, before client construction. |
| Verified paper account | When `IBKR_ACCOUNT` is set, it must start with `D`. Empty is allowed for **backtests-only**; paper trading and Telegram IBKR reads require `DU…` (`paper_ibkr_account_id_required()`). |
| Position sizing cap | Order manager rejects any single order > 5% of paper NAV. |
| Daily drawdown kill switch | If realized + unrealized PnL drops below threshold, all open orders cancel and new entries halt until manually reset via Telegram `/reset_killswitch`. |
| Trading hours guard | Orders outside US regular hours are rejected at validation. |
| Idempotency | Each strategy tick produces 0 or 1 signal; signal-to-order conversion uses `(strategy_id, symbol, bar_timestamp)` as a unique key. |
| Claude never trades | LLM module has no function-calling tool that touches IBKR. Returns structured JSON only; deterministic code validates and acts. |

These are not documentation promises — they are **code paths verified by tests**.

```bash
# Verify the live-port guard:
$ IBKR_PORT=7496 IBKR_ACCOUNT=DU1234567 uv run python -c "from trading_lab.config import Settings; Settings()"
ValidationError: IBKR_PORT 7496 is the live TWS port and is blocked by policy
```

---

## Quick start

Requires Python 3.13 and [`uv`](https://github.com/astral-sh/uv).

```bash
# 1. Clone and enter
git clone <your-repo-url>
cd trading-lab

# 2. Install dependencies
uv sync

# 3. Copy environment template
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY (reports/refine), TELEGRAM_* if using the bot,
# IBKR_* for paper execution / Telegram broker reads (optional for backtests-only).

# 4. Run a backtest (works without IBKR_ACCOUNT)
uv run python scripts/run_backtest.py donchian SPY --start 2020-01-01 --end 2024-12-31

# 5. Run walk-forward optimization
uv run python scripts/run_walk_forward.py rsi SPY --start 2018-01-01 --end 2024-12-31

# 6. Run tests
uv run pytest -v
```

For paper trading, Telegram, scheduled reports, full architecture and safety detail, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/SAFETY.md](docs/SAFETY.md), and [docs/STRATEGIES.md](docs/STRATEGIES.md). Demo asset placeholders: [docs/demo/README.md](docs/demo/README.md).

---

## Docker

Requires [Docker](https://docs.docker.com/get-docker/) and a `.env` file in the project root (Compose refuses to start if `env_file` is missing — run `cp .env.example .env` or `touch .env` first).

```bash
docker compose build
docker compose run --rm app python scripts/run_backtest.py donchian SPY --start 2020-01-01 --end 2024-12-31
```

The default service command prints `run_backtest.py --help`. Override the command as needed. Running **TWS/IBKR Gateway** against `host.docker.internal` is platform-specific — for paper trading and the Telegram bot, running scripts **on the host** with `uv` is usually simpler.

---

## Strategies

Three strategies are implemented as concrete subclasses of `Strategy`. Each is long-only initially, with explicit entry/exit logic and parameter validation at construction time.

### RSI Mean Reversion
- **Idea:** Buy oversold reversals; markets overshoot and mean-revert.
- **Entry:** RSI(14) crosses up through 30.
- **Exit:** RSI > 50 (target) or ATR(14)-based stop loss.
- **Smoothing:** Wilder's RMA (industry standard, not SMA).
- **Best regime:** Range-bound or oversold rebound markets.

### Donchian Breakout
- **Idea:** Markets trend after breaking out of consolidation ranges (Turtle Trader school).
- **Entry:** Close > 20-day high.
- **Exit:** Close < 10-day low.
- **Best regime:** Sustained directional trends.

### BBands Squeeze
- **Idea:** Volatility compression (BB inside Keltner) precedes directional expansion.
- **Entry:** Squeeze release with close above SMA(20).
- **Exit:** Close drops back below SMA(20).
- **Best regime:** Post-consolidation breakouts.

Each strategy validates its parameters at instantiation, returns a deterministic `pd.Series` of `{-1, 0, +1}` signals, and is fully tested in `tests/unit/test_strategies.py`.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.13 | Modern typing, structural pattern matching |
| Package manager | `uv` | Fast, reproducible, locks the dev group |
| Backtest engine | `vectorbt` | Vectorized, fast, realistic cost modeling |
| Live execution | `ib_insync` | Async IBKR API wrapper |
| Market data | `yfinance` + `polygon-api-client` | Free start, paid upgrade path |
| Database | SQLite (Postgres-ready) | Schema works for both |
| AI layer | `anthropic` SDK, Claude Sonnet 4.6 | Structured outputs + tool use |
| Telegram | `python-telegram-bot` v20+ | Async API |
| Scheduler | `APScheduler` | Async-native jobs |
| Validation | `pydantic-settings` | Refuses unsafe configurations at startup |
| Tests | `pytest` | 102 tests (see CI / local run) |
| Type check | `mypy --strict` | No untyped public functions |
| Lint/format | `ruff` | Single-tool replacement for flake8 + isort + black |

---

## Project structure

```
src/trading_lab/
├── config.py              # pydantic-settings; refuses live ports; optional IBKR for backtests
├── logging_setup.py       # structlog JSON
├── data/                  # yfinance + polygon + bars_fetcher + parquet cache
├── strategies/            # Strategy base + 3 implementations
├── backtest/              # vectorbt engine, metrics, walk-forward
├── claude/                # client, prompts, refinement, reports, regime detection
├── execution/             # IBKR client, order manager, risk engine, kill switch
├── runner/                # live loop, APScheduler hooks, scheduled report jobs
├── telegram_bot/          # bot, handlers, notify (HTTP)
└── db/                    # SQLAlchemy models + migrations

docs/
├── ARCHITECTURE.md
├── SAFETY.md
├── STRATEGIES.md
└── demo/README.md         # optional screenshots / GIFs

tests/
├── unit/
└── integration/

scripts/
├── run_backtest.py
├── run_walk_forward.py
├── run_paper_trading.py
├── run_telegram_bot.py
└── run_scheduled_reports.py
```

---

## Testing

```bash
uv run pytest -v          # unit + integration (~102 tests)
uv run ruff check src tests scripts
uv run mypy src/trading_lab
```

Key invariants verified by tests:
- Config rejects live ports; non-paper account IDs when `IBKR_ACCOUNT` is set.
- Empty `IBKR_ACCOUNT` allowed for offline backtests; broker scripts require paper id.
- Strategies produce deterministic signals; same input → same output.
- Backtest metrics are deterministic and handle 0-trade cases.
- Walk-forward windows are computed correctly and disjoint.
- Order manager rejects oversized orders and out-of-hours submissions.
- Kill switch trips at threshold and blocks subsequent orders.
- Claude client emits a DB audit row for every call (token count, latency, purpose).

---

## Roadmap

This is Phase 1. Possible extensions:

- **Options support** — Black-Scholes pricing, Greeks, multi-leg orders, IV surface.
- **More strategies** — pairs trading, statistical arbitrage, vol selling with risk caps.
- **Regime overlay** — Claude-driven detector switches active strategy by market regime.
- **Better data** — paid Polygon tier, intraday bars, fundamentals.
- **Multi-asset portfolios** — equal weight, vol target, Kelly fraction.
- **Live monitoring** — Grafana dashboard, alert routing, anomaly detection.
- **Strategy parameter optimization at scale** — full grid search with parallel windows.

---

## Disclaimer

This software is for research and educational purposes only. It is configured to operate exclusively on Interactive Brokers paper-trading accounts. It is not investment advice. Backtest performance does not predict future returns. Past results in the sample table above demonstrate the engine's correctness, not strategy profitability.

If you adapt this code for live trading, you accept full responsibility for capital risk, regulatory compliance, and operational soundness. The safety guards in this repo defend against accidental live execution but cannot substitute for diligent code review.

---

## License

MIT — see [LICENSE](LICENSE) for full text.