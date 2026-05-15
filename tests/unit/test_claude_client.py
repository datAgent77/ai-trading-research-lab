"""Claude client persistence hooks."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from trading_lab.claude.analyze import analyze_backtest_markdown
from trading_lab.claude.client import ClaudeClient
from trading_lab.claude.report import regime_detection
from trading_lab.db.models import Base, ClaudeCall, ClaudeCallPurpose


def test_claude_call_row_written_when_session_provided() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    client = ClaudeClient(api_key="", model="stub-model", simulator=lambda **kw: '{"ok": true}')

    with Session(bind=engine) as session:
        client.complete_text(
            purpose=ClaudeCallPurpose.REGIME_DETECTION,
            system="sys",
            user="usr",
            max_tokens=64,
            db_session=session,
        )
        session.commit()

    with Session(bind=engine) as session:
        rows = session.scalars(select(ClaudeCall)).all()

    assert len(rows) == 1
    assert rows[0].purpose == ClaudeCallPurpose.REGIME_DETECTION
    assert rows[0].response_payload is not None


def test_analyze_backtest_markdown_uses_simulator() -> None:
    client = ClaudeClient(api_key="", model="stub", simulator=lambda **kw: "## Summary\nok")
    md = analyze_backtest_markdown("Sharpe 1.2", client=client)
    assert "## Summary" in md


def test_regime_detection_parses_simulator_json() -> None:
    client = ClaudeClient(
        api_key="",
        model="stub",
        simulator=lambda **kw: '{"regime": "range", "confidence": 0.55}',
    )
    out = regime_detection({"spy_last_return": 0.001}, client=client)
    assert out.regime == "range"
