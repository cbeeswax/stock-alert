import numpy as np
import pandas as pd

from src.scanning import scanner


def _history_df(periods: int = 320) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=periods, freq="B")
    close = np.linspace(100.0, 150.0, periods)
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.full(periods, 2_000_000.0),
        },
        index=dates,
    )


def test_run_scan_as_of_checks_strategy_enablement_for_all_hardcoded_branches(monkeypatch):
    history = _history_df()
    checked = []

    monkeypatch.setattr(scanner, "get_historical_data", lambda _ticker: history)
    monkeypatch.setattr(scanner, "_get_active_registry_strategies", lambda: [])
    monkeypatch.setattr(scanner, "_is_strategy_enabled", lambda name: checked.append(name) or False)

    signals = scanner.run_scan_as_of(pd.Timestamp("2025-03-05"), ["AAA"])

    assert signals == []
    assert set(checked) >= {
        "EMA_Crossover_Position",
        "%B_MeanReversion_Position",
        "High52_Position",
        "BigBase_Breakout_Position",
        "TrendContinuation_Position",
        "RelativeStrength_Ranker_Position",
        "ShortWeakRS_Retrace_Position",
        "LeaderPullback_Short_Position",
        "GapReversal_Position",
        "GapContinuation_Position",
        "ConsumerDisc_Ranker_Position",
    }
