import pandas as pd

import src.strategies.relative_strength as relative_strength


def _history(start: float, daily_growth: float) -> pd.DataFrame:
    index = pd.date_range("2024-01-02", periods=252, freq="B")
    close = pd.Series(
        [start * (1 + daily_growth) ** day for day in range(len(index))],
        index=index,
    )
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close,
            "Low": close * 0.99,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=index,
    )


def test_relative_strength_ranker_emits_a_valid_leader_signal(monkeypatch):
    stock = _history(100, 0.01)
    benchmark = _history(400, 0.001)
    monkeypatch.setattr(
        relative_strength,
        "get_historical_data",
        lambda ticker: benchmark if ticker == "QQQ" else stock,
    )
    monkeypatch.setattr("src.data.universe.get_ticker_sector", lambda ticker: "Technology")

    signal = relative_strength.RelativeStrengthRanker().scan(
        "AAA", stock, as_of_date=stock.index[-1]
    )

    assert signal is not None
    assert signal["Strategy"] == "RelativeStrength_Ranker_Position"
    assert signal["Entry"] > signal["StopLoss"] > 0
    assert signal["MaxDays"] > 0
