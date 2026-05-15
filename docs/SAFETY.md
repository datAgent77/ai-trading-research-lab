# Safety

This lab is **paper trading only**. The following rules are enforced or will be enforced in code as modules are implemented:

1. **Paper account** — IBKR live port `7496` is rejected at configuration load time. Paper accounts must use IDs starting with `D`.
2. **Position size cap** — No single order above configured `%` of NAV (planned in `execution/order_manager.py`).
3. **Daily drawdown kill switch** — Halt trading when daily PnL breaches threshold until manual reset (planned in `execution/risk.py`).
4. **Strategy-linked orders** — Every order must tie to a strategy run record (planned).
5. **Claude does not trade** — LLM output is analysis and suggestions only; no order placement from Claude (planned).
6. **Trading hours guard** — Orders outside regular US hours rejected (planned).
7. **Idempotency** — Signal-to-order keys prevent duplicates (planned).

Live trading is explicitly out of scope for this repository.
