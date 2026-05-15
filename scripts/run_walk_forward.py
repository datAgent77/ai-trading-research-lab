"""CLI entrypoint for rolling walk-forward backtests."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from trading_lab.backtest.walk_forward import walk_forward
from trading_lab.strategies.bbands_squeeze import BBandsSqueeze
from trading_lab.strategies.donchian_breakout import DonchianBreakout
from trading_lab.strategies.rsi_mean_reversion import RSIMeanReversion

STRATEGIES = {
    "rsi": RSIMeanReversion,
    "donchian": DonchianBreakout,
    "squeeze": BBandsSqueeze,
}

_SLICE_METRICS = ("total_return", "sharpe", "max_dd", "num_trades")


def main(
    strategy_key: str = typer.Argument(..., help="Strategy alias, e.g. rsi"),
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    start: str = typer.Option(..., "--start"),
    end: str = typer.Option(..., "--end"),
    in_sample_months: int = typer.Option(24, "--is-months", help="In-sample window length"),
    out_sample_months: int = typer.Option(6, "--oos-months", help="Out-of-sample window length"),
    step_months: int | None = typer.Option(
        None,
        "--step-months",
        help="Roll step in months; defaults to out-of-sample length",
    ),
    initial_cash: float = typer.Option(100_000.0, "--cash"),
    persist: bool = typer.Option(False, "--persist", help="Save runs to SQLite"),
) -> None:
    key = strategy_key.strip().lower()
    if key not in STRATEGIES:
        typer.echo(f"Unknown strategy {strategy_key!r}. Choices: {', '.join(sorted(STRATEGIES))}")
        raise typer.Exit(code=1)

    strat_cls = STRATEGIES[key]
    strategy = strat_cls()
    sym = symbol.strip().upper()

    wf = walk_forward(
        strategy,
        symbols=[sym],
        start=start,
        end=end,
        in_sample_months=in_sample_months,
        out_sample_months=out_sample_months,
        step_months=step_months,
        initial_cash=initial_cash,
        persist=persist,
    )

    console = Console()
    typer.echo(
        f"Walk-forward {strategy.name} {sym} {start} .. {end} ({wf.meta['num_slices']} slice(s))",
    )

    if not wf.slices:
        typer.echo("No complete slices fit in the date range (extend range or shorten windows).")
        raise typer.Exit(code=0)

    for i, sl in enumerate(wf.slices, start=1):
        title = (
            f"Slice {i}: IS {sl.in_sample_start}..{sl.in_sample_end} | "
            f"OOS {sl.out_sample_start}..{sl.out_sample_end}"
        )
        table = Table(title=title)
        table.add_column("Window", style="cyan", no_wrap=True)
        for mk in _SLICE_METRICS:
            table.add_column(mk)

        is_m = sl.in_sample_result.metrics
        oos_m = sl.out_sample_result.metrics
        table.add_row(
            "IS",
            *[str(is_m.get(k)) for k in _SLICE_METRICS],
        )
        table.add_row(
            "OOS",
            *[str(oos_m.get(k)) for k in _SLICE_METRICS],
        )
        console.print(table)


if __name__ == "__main__":
    typer.run(main)
