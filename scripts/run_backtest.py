"""CLI entrypoint for running historical backtests."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from trading_lab.backtest.engine import backtest
from trading_lab.strategies.bbands_squeeze import BBandsSqueeze
from trading_lab.strategies.donchian_breakout import DonchianBreakout
from trading_lab.strategies.rsi_mean_reversion import RSIMeanReversion

STRATEGIES = {
    "rsi": RSIMeanReversion,
    "donchian": DonchianBreakout,
    "squeeze": BBandsSqueeze,
}


def main(
    strategy_key: str = typer.Argument(..., help="Strategy alias, e.g. rsi"),
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    start: str = typer.Option(..., "--start"),
    end: str = typer.Option(..., "--end"),
    persist: bool = typer.Option(False, "--persist", help="Save row to SQLite"),
    initial_cash: float = typer.Option(100_000.0, "--cash"),
) -> None:
    key = strategy_key.strip().lower()
    if key not in STRATEGIES:
        typer.echo(f"Unknown strategy {strategy_key!r}. Choices: {', '.join(sorted(STRATEGIES))}")
        raise typer.Exit(code=1)
    strat_cls = STRATEGIES[key]
    strategy = strat_cls()
    result = backtest(
        strategy,
        symbols=[symbol.strip().upper()],
        start=start,
        end=end,
        initial_cash=initial_cash,
        persist=persist,
    )

    console = Console()
    table = Table(title=f"Backtest {strategy.name} {symbol.upper()} {start} .. {end}")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value")
    for metric_key in sorted(result.metrics.keys()):
        table.add_row(metric_key, str(result.metrics[metric_key]))
    console.print(table)
    typer.echo(f"Trades logged: {len(result.trades)}")


if __name__ == "__main__":
    typer.run(main)
