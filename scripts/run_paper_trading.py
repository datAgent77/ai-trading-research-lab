"""Run paper-trading loop against IBKR Gateway/TWS (7497)."""

from __future__ import annotations

import asyncio
import logging

import typer
from pydantic import ValidationError

from trading_lab.config import Settings, get_settings
from trading_lab.db.session import create_session_factory, ensure_schema
from trading_lab.execution.ibkr_client import IBKRClient
from trading_lab.execution.risk import KillSwitchState, RiskEngine
from trading_lab.logging_setup import configure_logging
from trading_lab.runner.live_loop import LiveBinding, LiveLoop
from trading_lab.runner.scheduler import (
    build_async_scheduler,
    register_heartbeat_job,
    shutdown_scheduler,
)
from trading_lab.strategies.bbands_squeeze import BBandsSqueeze
from trading_lab.strategies.donchian_breakout import DonchianBreakout
from trading_lab.strategies.rsi_mean_reversion import RSIMeanReversion

STRATEGIES = {
    "rsi": RSIMeanReversion,
    "donchian": DonchianBreakout,
    "squeeze": BBandsSqueeze,
}

logger = logging.getLogger(__name__)


async def _run_async(
    settings: Settings,
    *,
    strategy_key: str,
    symbol: str,
    run_id: int,
    poll_seconds: float,
    dry_run: bool,
    heartbeat_seconds: int,
) -> None:
    ensure_schema(settings.database_url)
    kill_sw_factory = create_session_factory(settings)

    ibkr = IBKRClient(
        host=settings.ibkr_host,
        port=settings.ibkr_port,
        client_id=settings.ibkr_client_id,
        account_id=settings.ibkr_account,
        connect=True,
    )
    risk = RiskEngine(settings, KillSwitchState())
    strat_cls = STRATEGIES[strategy_key]
    strat = strat_cls()
    bindings = [LiveBinding(strategy_run_id=run_id, strategy=strat, symbol=symbol.strip().upper())]
    loop = LiveLoop(
        ibkr=ibkr,
        risk=risk,
        bindings=bindings,
        dry_run=dry_run,
        kill_switch_session_factory=kill_sw_factory,
    )

    scheduler = build_async_scheduler()
    register_heartbeat_job(scheduler, interval_seconds=heartbeat_seconds)
    scheduler.start()
    logger.info(
        "paper_trading_start strategy=%s symbol=%s run_id=%s dry_run=%s",
        strategy_key,
        symbol.upper(),
        run_id,
        dry_run,
    )
    try:
        await loop.run_forever(poll_seconds=poll_seconds)
    finally:
        shutdown_scheduler(scheduler)
        ibkr.disconnect()


def main(
    strategy_key: str = typer.Argument(..., help="Strategy alias: rsi | donchian | squeeze"),
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    run_id: int = typer.Option(..., "--run-id", help="Existing strategy_runs.id for audit linkage"),
    poll_seconds: float = typer.Option(60.0, "--poll", help="Seconds between polling cycles"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log orders without submitting"),
    heartbeat_seconds: int = typer.Option(300, "--heartbeat", help="Scheduler heartbeat interval"),
) -> None:
    configure_logging(json_output=False)
    key = strategy_key.strip().lower()
    if key not in STRATEGIES:
        typer.echo(f"Unknown strategy {strategy_key!r}. Choices: {', '.join(sorted(STRATEGIES))}")
        raise typer.Exit(code=1)
    if run_id < 1:
        typer.echo("--run-id must be >= 1")
        raise typer.Exit(code=1)

    try:
        settings = get_settings()
    except ValidationError as exc:
        typer.secho(
            "Configuration error — check `.env` (see `.env.example`).",
            fg=typer.colors.RED,
            err=True,
        )
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", ()))
            typer.secho(f"  {loc}: {err.get('msg')}", err=True)
        typer.secho(
            "Paper trading requires IBKR_ACCOUNT (id starting with D), e.g. IBKR_ACCOUNT=DU1234567",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    asyncio.run(
        _run_async(
            settings,
            strategy_key=key,
            symbol=symbol,
            run_id=run_id,
            poll_seconds=poll_seconds,
            dry_run=dry_run,
            heartbeat_seconds=heartbeat_seconds,
        ),
    )


if __name__ == "__main__":
    typer.run(main)
