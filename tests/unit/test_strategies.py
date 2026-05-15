"""Strategy unit tests (expanded in Stage 3)."""

from __future__ import annotations

import pandas as pd
import pytest

from trading_lab.strategies.rsi_mean_reversion import RSIMeanReversionStrategy


def test_rsi_strategy_stub_raises() -> None:
    strat = RSIMeanReversionStrategy()
    frame = pd.DataFrame({"close": [1, 2, 3]})
    with pytest.raises(NotImplementedError):
        strat.generate_signals(frame)
