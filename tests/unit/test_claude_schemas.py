"""Structured-output parsing helpers."""

from __future__ import annotations

import pytest

from trading_lab.claude.schemas import (
    RefineParamsResponse,
    extract_first_json_object,
    parse_refine_params_response,
    parse_regime_detection_response,
)


def test_extract_first_json_object_plain() -> None:
    blob = '{"a": 1, "b": "x"}'
    assert extract_first_json_object(blob) == {"a": 1, "b": "x"}


def test_extract_first_json_object_from_fence() -> None:
    text = 'Sure:\n```json\n{"regime": "range", "confidence": 0.7}\n```'
    assert extract_first_json_object(text)["regime"] == "range"


def test_parse_refine_params_response() -> None:
    raw = '{"suggested_params": {"rsi_period": 18}, "rationale": "test"}'
    obj = parse_refine_params_response(raw)
    assert isinstance(obj, RefineParamsResponse)
    assert obj.suggested_params["rsi_period"] == 18


def test_parse_regime_detection_response() -> None:
    raw = '{"regime": "high_vol", "confidence": 0.42}'
    reg = parse_regime_detection_response(raw)
    assert reg.regime == "high_vol"
    assert abs(reg.confidence - 0.42) < 1e-9


def test_extract_first_json_object_missing_raises() -> None:
    with pytest.raises(ValueError, match="JSON"):
        extract_first_json_object("no json here")
