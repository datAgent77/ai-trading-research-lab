"""All Claude prompt prose lives here (assembled via helpers below).

Call sites must not embed additional instruction text—only pass structured facts
(metrics JSON, OHLCV summaries, etc.) through the builders in this module.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

# --- Refinement -------------------------------------------------------------

PROMPT_REFINE_PARAMS_SYSTEM = """You are a quantitative research assistant for a deterministic \
backtesting lab. You suggest strategy parameter updates based ONLY on in-sample summary \
metrics. You never recommend trades or broker actions.

Respond with a single JSON object (no markdown fences, no commentary outside JSON) matching \
this schema:
{"suggested_params": {<parameter_name>: <number or string>, ...}, "rationale": "<short text>"}

Rules:
- Only suggest keys that already exist in CURRENT PARAMETERS; omit unknown keys by using \
empty suggested_params if unsure.
- Values must be physically plausible for the strategy (e.g. RSI periods integers >= 2, \
thresholds between 0 and 100 where applicable).
- If metrics are weak, propose modest adjustments; avoid extreme parameter jumps unless \
metrics justify them.
"""

PROMPT_REFINE_PARAMS_INPUT_HEADER = (
    "=== STRATEGY ===\n"
    "{strategy_name}\n\n"
    "=== CURRENT PARAMETERS (JSON) ===\n"
    "{params_json}\n\n"
    "=== IN-SAMPLE METRICS (JSON) ===\n"
    "{metrics_json}\n"
)

PROMPT_REFINE_PARAMS = PROMPT_REFINE_PARAMS_SYSTEM


def build_refine_params_user_message(
    strategy_name: str,
    params: dict[str, Any],
    metrics: dict[str, Any],
) -> str:
    """User turn for parameter refinement."""
    return PROMPT_REFINE_PARAMS_INPUT_HEADER.format(
        strategy_name=strategy_name,
        params_json=json.dumps(params, sort_keys=True, default=str),
        metrics_json=json.dumps(metrics, sort_keys=True, default=str),
    )


# --- Backtest analysis --------------------------------------------------------

PROMPT_ANALYZE_BACKTEST_ROLE = """You write short institutional-style markdown commentary on \
deterministic backtests. Focus on drawdowns, stability of returns, and plausible regime \
weaknesses. Do not invent trades or metrics not given in the summary."""

PROMPT_ANALYZE_BACKTEST_FORMAT = """Output 1–2 paragraphs of markdown only (no JSON)."""

PROMPT_ANALYZE_BACKTEST_SYSTEM = (
    f"{PROMPT_ANALYZE_BACKTEST_ROLE}\n\n{PROMPT_ANALYZE_BACKTEST_FORMAT}"
)


def build_analyze_backtest_user_message(summary: str) -> str:
    """User turn for qualitative backtest commentary."""
    return f"=== BACKTEST SUMMARY ===\n{summary.strip()}\n"


PROMPT_ANALYZE_BACKTEST = PROMPT_ANALYZE_BACKTEST_SYSTEM


# --- Reports -----------------------------------------------------------------

PROMPT_DAILY_REPORT_ROLE = """You produce a concise daily trading desk brief in markdown \
based ONLY on the structured facts provided. Tone: neutral institutional. No trade \
recommendations or broker instructions."""

PROMPT_WEEKLY_REPORT_ROLE = """You produce a weekly operations summary in markdown from \
the structured facts provided. Highlight win/loss mix and notable outliers. No trade \
recommendations or broker instructions."""


def build_daily_report_user_message(context: Mapping[str, Any]) -> str:
    """Structured facts JSON section only (instructions belong in system prompt)."""
    payload = json.dumps(dict(context), sort_keys=True, default=str)
    return f"=== CONTEXT (JSON) ===\n{payload}\n"


def build_weekly_report_user_message(context: Mapping[str, Any]) -> str:
    """Structured facts JSON section only (instructions belong in system prompt)."""
    payload = json.dumps(dict(context), sort_keys=True, default=str)
    return f"=== CONTEXT (JSON) ===\n{payload}\n"


PROMPT_DAILY_REPORT = PROMPT_DAILY_REPORT_ROLE
PROMPT_WEEKLY_REPORT = PROMPT_WEEKLY_REPORT_ROLE


# --- Regime detection ---------------------------------------------------------

PROMPT_REGIME_DETECTION_SYSTEM = """You classify the recent US equity regime using ONLY the \
numeric summaries provided (you do not fetch external data).

Respond with one JSON object (no markdown fences, no extra text) exactly like:
{"regime": "trending_up" | "trending_down" | "range" | "high_vol", "confidence": <number 0-1>}

Use:
- trending_up / trending_down when directional drift dominates recent closes vs earlier window.
- range when mean-reverting chop dominates with bounded breadth.
- high_vol when realized volatility or range expansion dominates vs its recent baseline."""

PROMPT_REGIME_DETECTION_INPUT = """=== MARKET SUMMARY (JSON) ===\n{payload_json}\n"""


def build_regime_detection_user_message(payload: dict[str, Any]) -> str:
    """User turn for regime JSON classification."""
    body = json.dumps(payload, sort_keys=True, default=str)
    return PROMPT_REGIME_DETECTION_INPUT.format(payload_json=body)


PROMPT_REGIME_DETECTION = PROMPT_REGIME_DETECTION_SYSTEM


__all__ = [
    "PROMPT_ANALYZE_BACKTEST",
    "PROMPT_ANALYZE_BACKTEST_SYSTEM",
    "PROMPT_DAILY_REPORT",
    "PROMPT_REFINE_PARAMS",
    "PROMPT_REGIME_DETECTION",
    "PROMPT_WEEKLY_REPORT",
    "PROMPT_ANALYZE_BACKTEST_ROLE",
    "PROMPT_DAILY_REPORT_ROLE",
    "PROMPT_REFINE_PARAMS_SYSTEM",
    "PROMPT_REGIME_DETECTION_SYSTEM",
    "PROMPT_WEEKLY_REPORT_ROLE",
    "build_analyze_backtest_user_message",
    "build_daily_report_user_message",
    "build_refine_params_user_message",
    "build_regime_detection_user_message",
    "build_weekly_report_user_message",
]
