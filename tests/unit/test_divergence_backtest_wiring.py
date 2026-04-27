import pandas as pd

from src.backtesting.engine import WalkForwardBacktester
from src.strategies.divergence_reversal import DivergenceReversalPosition


def _history_df() -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=120, freq="B")
    close = pd.Series(range(120), index=dates, dtype=float) * 0.1 + 95.0
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": [1_500_000] * len(close),
        },
        index=dates,
    )


def test_backtester_routes_divergence_strategy_exit(monkeypatch):
    history = _history_df()
    current_date = history.index[-1]
    today_data = history.loc[current_date]
    backtester = WalkForwardBacktester(["AAA"])
    position = {
        "ticker": "AAA",
        "strategy": "DivergenceReversal_Position",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_price": 90.0,
        "risk_amount": 10.0,
        "days_held": 5,
        "max_days": 90,
        "current_shares": 10,
        "initial_shares": 10,
        "pyramid_adds": [],
        "partial_exited": False,
        "closes_below_trail": 0,
        "zone_support": 95.0,
        "zone_resistance": None,
        "highest_price": 107.0,
        "entry_date": history.index[-10],
    }

    monkeypatch.setattr(
        DivergenceReversalPosition,
        "get_exit_conditions",
        lambda self, position_payload, df, current_dt: {
            "reason": "zone_support_fail",
            "exit_price": 94.0,
        },
    )

    result = backtester._evaluate_exit_conditions(
        position,
        current_date,
        today_data,
        float(today_data["Close"]),
        (float(today_data["Close"]) - position["entry_price"]) / position["risk_amount"],
        history,
    )

    assert result is not None
    assert result["Strategy"] == "DivergenceReversal_Position"
    assert result["ExitReason"] == "zone_support_fail"
    assert result["Exit"] == 94.0
