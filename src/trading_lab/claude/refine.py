"""Walk-forward aligned parameter refinement loop (Claude suggests; code validates)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from trading_lab.backtest.engine import backtest
from trading_lab.backtest.walk_forward import WalkForwardResult
from trading_lab.claude import prompts
from trading_lab.claude.client import ClaudeClient
from trading_lab.claude.schemas import parse_refine_params_response
from trading_lab.db.models import ClaudeCallPurpose
from trading_lab.strategies.base import Strategy


@dataclass(frozen=True)
class RefinementStep:
    """One refinement iteration tied to a walk-forward slice."""

    iteration: int
    in_sample_start: str
    in_sample_end: str
    out_sample_start: str
    out_sample_end: str
    params_before: dict[str, Any]
    params_after: dict[str, Any]
    in_sample_metrics: dict[str, Any]
    out_sample_metrics: dict[str, Any]
    rationale: str


@dataclass(frozen=True)
class RefinementResult:
    """Ordered refinement trail plus terminal parameter dictionary."""

    steps: tuple[RefinementStep, ...]
    final_params: dict[str, Any]


def merge_allowed_params(
    strategy_cls: type[Strategy],
    current: dict[str, Any],
    suggested: dict[str, Any],
) -> dict[str, Any]:
    """Merge ``suggested`` keys that exist on ``strategy_cls.default_params`` only."""
    allowed = strategy_cls.default_params.keys()
    merged = dict(current)
    for key, value in suggested.items():
        if key in allowed:
            merged[key] = value
    return merged


def refinement_walk_forward(
    strategy_cls: type[Strategy],
    wf: WalkForwardResult,
    *,
    symbols: list[str] | None = None,
    initial_params: dict[str, Any] | None = None,
    client: ClaudeClient,
    max_tokens: int = 2048,
    strategy_run_id: int | None = None,
    db_session: Session | None = None,
) -> RefinementResult:
    """Run one Claude refinement per walk-forward slice's in-sample window.

    For slice ``i``, backtests the in-sample range with parameters ``P_i``, asks Claude for
    ``suggested_params``, merges allowed keys to ``P_{i+1}``, then measures ``P_{i+1}`` on the
    paired out-of-sample window.

    Args:
        strategy_cls: Concrete ``Strategy`` subclass (not an instance).
        wf: Output from ``walk_forward`` supplying inclusive calendar boundaries.
        symbols: Tickers for ``backtest``; defaults to ``wf.meta["symbols"]``.
        initial_params: Optional overrides merged onto ``default_params``.
        client: ``ClaudeClient`` (real or simulated).
        max_tokens: Messages completion budget per refinement call.
        strategy_run_id: Optional FK for ``claude_calls`` rows.
        db_session: Optional SQLAlchemy session when persistence is desired.

    Returns:
        ``RefinementResult`` capturing metrics trails and the terminal parameter dict.

    Raises:
        ValueError: When ``wf`` contains zero slices or symbols cannot be resolved.
    """
    if not wf.slices:
        msg = "walk_forward result has no slices"
        raise ValueError(msg)

    sym_list = list(symbols) if symbols is not None else list(wf.meta.get("symbols") or [])
    if not sym_list:
        msg = "symbols must be provided explicitly or present in wf.meta['symbols']"
        raise ValueError(msg)

    base_defaults = dict(strategy_cls.default_params)
    current_params = {**base_defaults, **(initial_params or {})}
    _ = strategy_cls(params=current_params)

    steps: list[RefinementStep] = []

    for i, sl in enumerate(wf.slices):
        strat_before = strategy_cls(params=current_params)
        is_res = backtest(
            strat_before,
            sym_list,
            sl.in_sample_start,
            sl.in_sample_end,
        )

        user_msg = prompts.build_refine_params_user_message(
            strat_before.name,
            strat_before.params,
            dict(is_res.metrics),
        )
        assistant_raw = client.complete_text(
            purpose=ClaudeCallPurpose.REFINE_PARAMS,
            system=prompts.PROMPT_REFINE_PARAMS_SYSTEM,
            user=user_msg,
            max_tokens=max_tokens,
            strategy_run_id=strategy_run_id,
            db_session=db_session,
        )

        refined = parse_refine_params_response(assistant_raw)
        merged = merge_allowed_params(strategy_cls, current_params, refined.suggested_params)
        strat_after = strategy_cls(params=merged)

        oos_res = backtest(
            strat_after,
            sym_list,
            sl.out_sample_start,
            sl.out_sample_end,
        )

        steps.append(
            RefinementStep(
                iteration=i,
                in_sample_start=sl.in_sample_start,
                in_sample_end=sl.in_sample_end,
                out_sample_start=sl.out_sample_start,
                out_sample_end=sl.out_sample_end,
                params_before=dict(strat_before.params),
                params_after=dict(strat_after.params),
                in_sample_metrics=dict(is_res.metrics),
                out_sample_metrics=dict(oos_res.metrics),
                rationale=refined.rationale,
            ),
        )
        current_params = dict(strat_after.params)

    return RefinementResult(steps=tuple(steps), final_params=current_params)


__all__ = [
    "RefinementResult",
    "RefinementStep",
    "merge_allowed_params",
    "refinement_walk_forward",
]
