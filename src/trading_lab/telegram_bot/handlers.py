"""Telegram command handlers (whitelist auth)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from trading_lab.backtest.engine import backtest
from trading_lab.backtest.walk_forward import walk_forward
from trading_lab.claude.client import ClaudeClient
from trading_lab.claude.refine import refinement_walk_forward
from trading_lab.claude.report import daily_report_markdown, weekly_report_markdown
from trading_lab.config import Settings
from trading_lab.db.models import Order, StrategyRun, StrategyRunStatus
from trading_lab.db.session import managed_session
from trading_lab.execution.ibkr_client import IBKRClient
from trading_lab.execution.kill_switch_store import (
    describe_kill_switch,
    persist_kill_switch_reset,
    persist_kill_switch_trip,
)
from trading_lab.strategies.base import Strategy
from trading_lab.strategies.bbands_squeeze import BBandsSqueeze
from trading_lab.strategies.donchian_breakout import DonchianBreakout
from trading_lab.strategies.rsi_mean_reversion import RSIMeanReversion

logger = logging.getLogger(__name__)

STRATEGY_CLASSES: dict[str, type[Strategy]] = {
    "rsi": RSIMeanReversion,
    "donchian": DonchianBreakout,
    "squeeze": BBandsSqueeze,
}


def _clip_message(text: str, limit: int = 3900) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 24] + "\n...(truncated)"


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return cast(Settings, context.application.bot_data["settings"])


def _session_factory(context: ContextTypes.DEFAULT_TYPE) -> sessionmaker[Session]:
    return cast(sessionmaker[Session], context.application.bot_data["session_factory"])


def ibkr_sidecar_client_id(settings: Settings) -> int:
    """Use a distinct IB API client id so the bot can run beside ``run_paper_trading``."""
    if settings.telegram_ibkr_client_id is not None:
        return settings.telegram_ibkr_client_id
    return settings.ibkr_client_id + 1


def _account_tags(ibkr: IBKRClient) -> dict[str, str]:
    rows: dict[str, str] = {}
    for row in ibkr.ib.accountSummary(ibkr.account_id):
        rows[str(row.tag)] = str(row.value)
    return rows


def ibkr_connect(settings: Settings) -> IBKRClient:
    return IBKRClient(
        host=settings.ibkr_host,
        port=settings.ibkr_port,
        client_id=ibkr_sidecar_client_id(settings),
        account_id=settings.ibkr_account,
        connect=True,
    )


def ibkr_status_lines(settings: Settings) -> str:
    ibkr = ibkr_connect(settings)
    try:
        tags = _account_tags(ibkr)
        lines = [
            f"NetLiquidation={tags.get('NetLiquidation', '?')}",
            f"DailyPnL={tags.get('DailyPnL', tags.get('PnL', '?'))}",
            f"UnrealizedPnL={tags.get('UnrealizedPnL', '?')}",
            "Positions:",
        ]
        positions = list(ibkr.ib.positions(account=ibkr.account_id))
        if not positions:
            lines.append("  (flat)")
        else:
            for pos in positions:
                sym = getattr(pos.contract, "symbol", "?")
                lines.append(f"  {sym}: qty={pos.position} avg={pos.avgCost}")
        return "\n".join(lines)
    finally:
        ibkr.disconnect()


def ibkr_pnl_lines(settings: Settings, span: str) -> str:
    ibkr = ibkr_connect(settings)
    try:
        tags = _account_tags(ibkr)
        body = (
            f"window={span}\n"
            f"DailyPnL={tags.get('DailyPnL', '?')} "
            f"RealizedPnL={tags.get('RealizedPnL', '?')} "
            f"UnrealizedPnL={tags.get('UnrealizedPnL', '?')}\n"
            "(week/month rollups need persisted ledger rows; today uses broker tags.)"
        )
        return body
    finally:
        ibkr.disconnect()


def ibkr_positions_lines(settings: Settings) -> str:
    ibkr = ibkr_connect(settings)
    try:
        tags = _account_tags(ibkr)
        lines = [
            f"NetLiquidation={tags.get('NetLiquidation', '?')}",
            "Positions:",
        ]
        positions = list(ibkr.ib.positions(account=ibkr.account_id))
        if not positions:
            lines.append("  (flat)")
        else:
            for pos in positions:
                sym = getattr(pos.contract, "symbol", "?")
                lines.append(
                    f"  {sym}: qty={pos.position} avg={pos.avgCost}",
                )
        return "\n".join(lines)
    finally:
        ibkr.disconnect()


def latest_order_summary(session: Session) -> str:
    row = session.scalars(select(Order).order_by(Order.created_at.desc()).limit(1)).first()
    if row is None:
        return "last_order=(none)"
    return (
        f"last_order id={row.id} {row.symbol} {row.side.value} "
        f"qty={row.quantity} status={row.status.value}"
    )


def create_running_strategy_run(
    session: Session,
    *,
    strategy_name: str,
    symbol: str,
    params: dict[str, Any],
) -> int:
    """Insert a ``RUNNING`` strategy row and return its id."""
    now = datetime.now(UTC)
    row = StrategyRun(
        strategy_name=strategy_name,
        symbol=symbol,
        params=params,
        status=StrategyRunStatus.RUNNING,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return int(row.id)


def stop_latest_running_strategy_run(
    session: Session,
    *,
    strategy_name: str,
    symbol: str,
) -> int | None:
    stmt = (
        select(StrategyRun)
        .where(
            StrategyRun.strategy_name == strategy_name,
            StrategyRun.symbol == symbol,
            StrategyRun.status == StrategyRunStatus.RUNNING,
        )
        .order_by(StrategyRun.id.desc())
        .limit(1)
    )
    row = session.scalars(stmt).first()
    if row is None:
        return None
    end = datetime.now(UTC)
    row.status = StrategyRunStatus.STOPPED
    row.ended_at = end
    row.updated_at = end
    return int(row.id)


TelegramHandler = Callable[
    [Update, ContextTypes.DEFAULT_TYPE],
    Coroutine[Any, Any, None],
]


def authorized(handler: TelegramHandler) -> TelegramHandler:
    """Drop updates from users outside ``allowed_user_ids`` (silent log)."""

    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        uid = update.effective_user.id if update.effective_user else None
        allowed: set[int] = context.application.bot_data["allowed_user_ids"]
        if uid not in allowed:
            logger.info("telegram_non_whitelist user_id=%s", uid)
            return
        await handler(update, context)

    return wrapped


@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    await update.effective_chat.send_message(
        "Trading lab bot online (paper only). Try /help for commands.",
    )


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    text = (
        "Commands:\n"
        "/status — kill switch + broker snapshot + last DB order\n"
        "/positions — IBKR positions table\n"
        "/pnl [today|week|month] — broker PnL tags (coarse)\n"
        "/backtest <rsi|donchian|squeeze> <SYM> <start> <end>\n"
        "/strategies — list aliases\n"
        "/start_strategy <alias> <SYM> — insert RUNNING strategy_run row\n"
        "/stop_strategy <alias> <SYM> — stop latest RUNNING row for pair\n"
        "/refine <alias> <SYM> — Claude walk-forward refinement (slow)\n"
        "/report [today|week] — Claude markdown brief\n"
        "/killswitch — trip kill switch (persisted; live loop polls)\n"
        "/reset_killswitch confirm — clear kill switch\n"
    )
    await update.effective_chat.send_message(text)


@authorized
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    settings = _settings(context)
    factory = _session_factory(context)
    with managed_session(factory) as session:
        tripped, reason = describe_kill_switch(session)
        order_line = latest_order_summary(session)
    ks = f"kill_switch={'TRIPPED' if tripped else 'ok'} reason={reason or '-'}"
    try:
        broker = await asyncio.to_thread(ibkr_status_lines, settings)
    except Exception as exc:
        logger.warning("telegram_status_ibkr_failed exc=%s", exc)
        broker = f"IBKR unavailable: {exc}"
    await update.effective_chat.send_message("\n".join([ks, order_line, broker]))


@authorized
async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    settings = _settings(context)
    try:
        body = await asyncio.to_thread(ibkr_positions_lines, settings)
    except Exception as exc:
        body = f"IBKR unavailable: {exc}"
    await update.effective_chat.send_message(body)


@authorized
async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    args = context.args or []
    span = (args[0] if args else "today").strip().lower()
    if span not in {"today", "week", "month"}:
        await update.effective_chat.send_message(
            "Usage: /pnl [today|week|month]",
        )
        return
    settings = _settings(context)
    try:
        body = await asyncio.to_thread(ibkr_pnl_lines, settings, span)
    except Exception as exc:
        body = f"IBKR unavailable: {exc}"
    await update.effective_chat.send_message(body)


@authorized
async def cmd_strategies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    keys = ", ".join(sorted(STRATEGY_CLASSES))
    await update.effective_chat.send_message(f"Strategy aliases: {keys}")


@authorized
async def cmd_backtest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    args = context.args or []
    if len(args) != 4:
        await update.effective_chat.send_message(
            "Usage: /backtest <rsi|donchian|squeeze> <SYM> <YYYY-MM-DD> <YYYY-MM-DD>",
        )
        return
    key_raw, sym_raw, start_s, end_s = args
    key = key_raw.strip().lower()
    if key not in STRATEGY_CLASSES:
        await update.effective_chat.send_message(f"Unknown strategy {key_raw!r}. /strategies")
        return
    strat_cls = STRATEGY_CLASSES[key]
    strategy = strat_cls()
    await update.effective_chat.send_message(
        f"Running backtest {strategy.name} {sym_raw.upper()} {start_s}..{end_s} …",
    )

    def work() -> Any:
        return backtest(
            strategy,
            symbols=[sym_raw.strip().upper()],
            start=start_s,
            end=end_s,
            persist=False,
        )

    try:
        result = await asyncio.to_thread(work)
    except Exception as exc:
        logger.exception("telegram_backtest_failed")
        await update.effective_chat.send_message(f"Backtest failed: {exc}")
        return
    m = result.metrics
    summary = (
        f"{strategy.name} {sym_raw.upper()}\n"
        f"total_return={m.get('total_return')} sharpe={m.get('sharpe')} "
        f"max_dd={m.get('max_dd')}\n"
        f"num_trades={m.get('num_trades')}"
    )
    await update.effective_chat.send_message(summary)


@authorized
async def cmd_start_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    args = context.args or []
    if len(args) != 2:
        await update.effective_chat.send_message(
            "Usage: /start_strategy <rsi|donchian|squeeze> <SYM>",
        )
        return
    key_raw, sym_raw = args
    key = key_raw.strip().lower()
    if key not in STRATEGY_CLASSES:
        await update.effective_chat.send_message(f"Unknown strategy {key_raw!r}. /strategies")
        return
    strat_cls = STRATEGY_CLASSES[key]
    instance = strat_cls()
    sym_u = sym_raw.strip().upper()
    factory = _session_factory(context)
    with managed_session(factory) as session:
        run_id = create_running_strategy_run(
            session,
            strategy_name=instance.name,
            symbol=sym_u,
            params=dict(instance.params),
        )
    await update.effective_chat.send_message(
        f"strategy_run id={run_id} RUNNING ({instance.name} {sym_u}). "
        f"Start runner: uv run python scripts/run_paper_trading.py {key} {sym_u} "
        f"--run-id {run_id}",
    )


@authorized
async def cmd_stop_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    args = context.args or []
    if len(args) != 2:
        await update.effective_chat.send_message(
            "Usage: /stop_strategy <rsi|donchian|squeeze> <SYM>",
        )
        return
    key_raw, sym_raw = args
    key = key_raw.strip().lower()
    if key not in STRATEGY_CLASSES:
        await update.effective_chat.send_message(f"Unknown strategy {key_raw!r}. /strategies")
        return
    strat_cls = STRATEGY_CLASSES[key]
    instance = strat_cls()
    sym_u = sym_raw.strip().upper()
    factory = _session_factory(context)
    with managed_session(factory) as session:
        stopped_id = stop_latest_running_strategy_run(
            session,
            strategy_name=instance.name,
            symbol=sym_u,
        )
    if stopped_id is None:
        await update.effective_chat.send_message(
            f"No RUNNING row for {instance.name} {sym_u}.",
        )
        return
    await update.effective_chat.send_message(
        f"Stopped strategy_run id={stopped_id} ({instance.name} {sym_u}).",
    )


@authorized
async def cmd_refine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    settings = _settings(context)
    args = context.args or []
    if len(args) != 2:
        await update.effective_chat.send_message(
            "Usage: /refine <rsi|donchian|squeeze> <SYM>",
        )
        return
    if not settings.anthropic_api_key.strip():
        await update.effective_chat.send_message("Set ANTHROPIC_API_KEY in `.env` first.")
        return
    key_raw, sym_raw = args
    key = key_raw.strip().lower()
    if key not in STRATEGY_CLASSES:
        await update.effective_chat.send_message(f"Unknown strategy {key_raw!r}. /strategies")
        return
    strat_cls = STRATEGY_CLASSES[key]
    strat = strat_cls()
    sym_u = sym_raw.strip().upper()
    await update.effective_chat.send_message(
        "Running walk-forward refinement (several backtests + Claude). This may take minutes.",
    )

    def work() -> Any:
        wf = walk_forward(
            strat,
            symbols=[sym_u],
            start="2018-01-01",
            end="2024-12-31",
            persist=False,
        )
        if not wf.slices:
            raise ValueError("walk_forward produced zero slices for 2018-01-01 .. 2024-12-31")
        client = ClaudeClient.from_settings(settings)
        return refinement_walk_forward(
            strat_cls,
            wf,
            symbols=[sym_u],
            client=client,
        )

    try:
        ref_result = await asyncio.to_thread(work)
    except Exception as exc:
        logger.exception("telegram_refine_failed")
        await update.effective_chat.send_message(f"Refine failed: {exc}")
        return
    params_txt = ", ".join(f"{k}={v}" for k, v in sorted(ref_result.final_params.items()))
    await update.effective_chat.send_message(_clip_message(f"Final params: {params_txt}"))


@authorized
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    settings = _settings(context)
    args = context.args or []
    mode = (args[0] if args else "today").strip().lower()
    if mode not in {"today", "week"}:
        await update.effective_chat.send_message("Usage: /report [today|week]")
        return
    if not settings.anthropic_api_key.strip():
        await update.effective_chat.send_message("Set ANTHROPIC_API_KEY in `.env` first.")
        return
    payload = {
        "period": mode,
        "source": "telegram_on_demand",
        "note": "Structured ledger aggregation can be wired in Stage 10 scheduler.",
    }

    def work() -> str:
        client = ClaudeClient.from_settings(settings)
        if mode == "today":
            return daily_report_markdown(payload, client=client)
        return weekly_report_markdown(payload, client=client)

    await update.effective_chat.send_message("Requesting Claude report …")
    try:
        text = await asyncio.to_thread(work)
    except Exception as exc:
        logger.exception("telegram_report_failed")
        await update.effective_chat.send_message(f"Report failed: {exc}")
        return
    await update.effective_chat.send_message(_clip_message(text))


@authorized
async def cmd_killswitch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    factory = _session_factory(context)
    with managed_session(factory) as session:
        persist_kill_switch_trip(session, "telegram_manual")
    await update.effective_chat.send_message(
        "Kill switch TRIPPED (database). Live runner syncs this flag each poll.",
    )


@authorized
async def cmd_reset_killswitch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat is not None
    args = context.args or []
    if args != ["confirm"]:
        await update.effective_chat.send_message("Send exactly: /reset_killswitch confirm")
        return
    factory = _session_factory(context)
    with managed_session(factory) as session:
        persist_kill_switch_reset(session)
    await update.effective_chat.send_message("Kill switch cleared.")


def register(application: Application) -> None:  # type: ignore[type-arg]
    """Attach command handlers."""
    pairs: tuple[tuple[str, TelegramHandler], ...] = (
        ("start", cmd_start),
        ("help", cmd_help),
        ("status", cmd_status),
        ("positions", cmd_positions),
        ("pnl", cmd_pnl),
        ("backtest", cmd_backtest),
        ("strategies", cmd_strategies),
        ("start_strategy", cmd_start_strategy),
        ("stop_strategy", cmd_stop_strategy),
        ("refine", cmd_refine),
        ("report", cmd_report),
        ("killswitch", cmd_killswitch),
        ("reset_killswitch", cmd_reset_killswitch),
    )
    for name, fn in pairs:
        application.add_handler(CommandHandler(name, fn))


__all__ = ["register", "STRATEGY_CLASSES", "ibkr_sidecar_client_id"]
