# Safety

This repository is a **research lab** configured for **Interactive Brokers paper trading only**. There is **no supported live-trading path**. The rules below are enforced in code (not documentation-only).

## Non-negotiable rules

### 1. Paper broker endpoint

- **`IBKR_PORT=7496`** (live TWS) is **rejected** at `Settings` validation (`src/trading_lab/config.py`).
- Paper typically uses **`7497`** (TWS/Gateway paper).

### 2. Paper account id

- When **`IBKR_ACCOUNT` is set**, it **must start with `D`** (IBKR paper-style id).
- **`IBKR_ACCOUNT` may be empty** for offline workflows (backtests, walk-forward without broker). Broker-connected scripts require a non-empty paper id via `paper_ibkr_account_id_required()`.

### 3. Order references and linkage

- Orders submitted through `IBKRClient` are tagged with **`paper-trade-lab`** (`ORDER_REF_TAG` in `execution/ibkr_client.py`).
- Order manager paths require a **`strategy_run_id`** for audit linkage (`execution/order_manager.py`).

### 4. Position size cap

- No single order above **`MAX_POSITION_PCT_NAV`** (default 5% of NAV), enforced before submit (`execution/order_manager.py`).

### 5. Trading hours guard

- Orders outside configured US regular session (`TRADING_START_NY` / `TRADING_END_NY`) are **rejected** (`execution/risk.py`).

### 6. Daily drawdown kill switch

- When realized + unrealized PnL breaches **`MAX_DAILY_DRAWDOWN_PCT`**, new entries halt; open orders are cancelled as implemented in the risk/order path; reset via Telegram **`/reset_killswitch confirm`** and persisted state (`execution/kill_switch_store.py`, handlers).

### 7. Idempotency

- Duplicate submits with the same **`(strategy_run_id, symbol, bar_timestamp)`** key are blocked (`DuplicateOrderKeyError`).

### 8. Claude does not trade

- The Claude layer returns **text / structured JSON** only. There is **no tool-calling path** from Claude to IBKR. Parameter suggestions must be applied by you or by explicit deterministic code after validation (`claude/refine.py`, Telegram handlers).

### 9. Telegram live notifications

- Optional HTTP notifications (`telegram_bot/notify.py`) never place orders; failures are logged only.

## What would need to change for live trading (do not do here)

- Removing port/account guards would violate the purpose of this repo.
- Live introduces regulatory, operational, and capital risks this codebase explicitly avoids.

## Verify config guards locally

```bash
IBKR_PORT=7496 IBKR_ACCOUNT=DU1234567 uv run python -c "from trading_lab.config import Settings; Settings()"
# Expect: ValidationError mentioning live port blocked.

IBKR_PORT=7497 IBKR_ACCOUNT=U123456 uv run python -c "from trading_lab.config import Settings; Settings()"
# Expect: ValidationError — account must start with D when set.
```

Run **`uv run pytest tests/unit/test_config_safety.py tests/unit/test_risk.py tests/unit/test_order_manager.py`** for automated checks.
