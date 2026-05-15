"""Pydantic schemas for Claude structured outputs."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

REGIME_LITERAL = Literal["trending_up", "trending_down", "range", "high_vol"]


class RefineParamsResponse(BaseModel):
    """Expected JSON body for parameter refinement."""

    suggested_params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class RegimeDetectionResponse(BaseModel):
    """Expected JSON body for regime labeling."""

    regime: REGIME_LITERAL
    confidence: float = Field(ge=0.0, le=1.0)


_json_fence_re = re.compile(r"```(?:json)?\s*(\{.*?})\s*```", re.DOTALL)


def extract_first_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object from ``text`` (optionally inside a fenced block).

    Raises:
        ValueError: If no object can be parsed.
    """
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fence = _json_fence_re.search(text)
    if fence:
        try:
            inner = json.loads(fence.group(1))
            if isinstance(inner, dict):
                return inner
        except json.JSONDecodeError:
            pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            sliced = json.loads(stripped[start : end + 1])
            if isinstance(sliced, dict):
                return sliced
        except json.JSONDecodeError:
            pass

    msg = "assistant response did not contain a JSON object"
    raise ValueError(msg)


def parse_refine_params_response(text: str) -> RefineParamsResponse:
    """Validate refinement JSON from assistant text."""
    return RefineParamsResponse.model_validate(extract_first_json_object(text))


def parse_regime_detection_response(text: str) -> RegimeDetectionResponse:
    """Validate regime detection JSON from assistant text."""
    return RegimeDetectionResponse.model_validate(extract_first_json_object(text))


__all__ = [
    "RefineParamsResponse",
    "RegimeDetectionResponse",
    "extract_first_json_object",
    "parse_refine_params_response",
    "parse_regime_detection_response",
]
