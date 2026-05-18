# Architecture

Design overview for the AI-assisted trading research lab: **deterministic strategies**, **vectorbt backtests**, optional **IBKR paper execution**, **Claude for analysis only**, and **Telegram** as the control plane.

## Goals

- Same strategy code drives backtests and (optional) paper execution.
- Claude never submits broker orders; it produces structured suggestions and narrative reports.
- SQLite holds audit rows (strategy runs, orders, Claude calls); schema is compatible with PostgreSQL via `DATABASE_URL`.

## Component map

```mermaid
graph LR
  subgraph Data
    YF[yfinance]
    PG[Polygon.io]
    BAR[bars_fetcher_for_settings]
  end
  subgraph Core
    ST[strategies/*]
    ENG[backtest/engine.py]
    WF[backtest/walk_forward.py]
  end
  subgraph AI
    CL[claude/*]
  end
  subgraph Broker
    IB[execution/ibkr_client.py]
    OM[execution/order_manager.py]
    RK[execution/risk.py]
  end
  subgraph Control
    TG[telegram_bot/*]
    SCH[runner/scheduler.py]
    LL[runner/live_loop.py]
    RJ[runner/report_jobs.py]
  end
  DB[(SQLite / Postgres)]

  YF --> BAR
  PG --> BAR
  BAR --> ST
  ST --> ENG
  ST --> LL
  ENG --> WF
  ENG --> CL
  WF --> CL
  LL --> OM
  OM --> RK
  OM --> IB
  TG --> ENG
  TG --> IB
  TG --> CL
  SCH --> RJ
  RJ --> CL
  RJ --> TG
  OM --> DB
  ENG --> DB
  CL --> DB
```

## Sequence: backtest (CLI or Telegram)

```mermaid
sequenceDiagram
  participant U as User / Telegram
  participant E as backtest.engine
  participant D as data/bars.py
  participant S as Strategy
  participant V as vectorbt

  U->>E: backtest(strategy, symbols, start, end)
  E->>D: bars_fetcher(symbol, start, end)
  D-->>E: OHLCV DataFrame
  E->>S: generate_signals(ohlcv)
  S-->>E: signal Series
  E->>V: Portfolio.from_signals(...)
  V-->>E: equity, trades
  E->>E: metrics.compute_metrics
  E-->>U: BacktestResult
```

## Sequence: live loop (paper)

```mermaid
sequenceDiagram
  participant LL as live_loop.LiveLoop
  participant D as bars_fetcher
  participant S as Strategy
  participant R as RiskEngine
  participant OM as order_manager
  participant IB as IBKRClient

  LL->>D: daily OHLCV window
  D-->>LL: DataFrame
  LL->>S: generate_signals
  S-->>LL: target long/flat
  LL->>R: kill_switch + limits (from DB/session)
  alt intent and not dry_run
    LL->>OM: place_market_order(intent)
    OM->>R: validate hours, size, kill switch, idempotency
    OM->>IB: submit order (paper)
    IB-->>OM: Trade
  end
```

## Sequence: Claude refinement (walk-forward)

```mermaid
sequenceDiagram
  participant U as User
  participant WF as walk_forward / refine
  participant E as backtest.engine
  participant C as ClaudeClient
  participant P as claude/prompts.py

  U->>WF: refinement job (in-sample window)
  WF->>E: backtest current params
  E-->>WF: metrics
  WF->>C: prompt + metrics (from P only)
  C-->>WF: JSON suggested_params (validated)
  WF->>E: backtest suggested params (next window)
  E-->>WF: OOS metrics
```

## Sequence: scheduled reports

```mermaid
sequenceDiagram
  participant SCH as APScheduler
  participant RJ as report_jobs
  participant DB as SQLite
  participant CL as ClaudeClient
  participant TG as Telegram API

  SCH->>RJ: cron trigger (daily/weekly)
  RJ->>DB: report_context / overlays
  RJ->>CL: daily_report_markdown / weekly_report_markdown
  CL-->>RJ: Markdown
  RJ->>TG: broadcast_scheduled_report (split chunks)
```

## Runnable entrypoints

| Script | Role |
|--------|------|
| `scripts/run_backtest.py` | Single-symbol backtest table |
| `scripts/run_walk_forward.py` | Rolling walk-forward |
| `scripts/run_paper_trading.py` | Async polling loop + IBKR paper |
| `scripts/run_telegram_bot.py` | Telegram command bot |
| `scripts/run_scheduled_reports.py` | APScheduler + Claude reports |

## Configuration highlights

- `DATA_PROVIDER=yfinance|polygon` selects historical/live bar fetcher (`src/trading_lab/data/bars.py`).
- `IBKR_ACCOUNT` may be empty for **backtest-only**; broker scripts call `Settings.paper_ibkr_account_id_required()`.
- Telegram live fills use `telegram_bot/notify.py` (HTTP `sendMessage`) when `TELEGRAM_LIVE_NOTIFY_ENABLED=true`.

See [SAFETY.md](SAFETY.md) for enforced trading guards.
