import pandas as pd

import src.scanning.validator as validator


def test_pre_buy_check_logs_short_direction(monkeypatch, capsys):
    dates = pd.date_range("2024-01-02", periods=60, freq="B")
    price = 100.0
    df = pd.DataFrame(
        {
            "Open": [price] * len(dates),
            "High": [price * 1.01] * len(dates),
            "Low": [price * 0.99] * len(dates),
            "Close": [price] * len(dates),
            "Volume": [1_000_000] * len(dates),
        },
        index=dates,
    )

    monkeypatch.setattr(validator, "get_historical_data", lambda _ticker: df)

    trades = validator.pre_buy_check(
        [
            {
                "Ticker": "WYNN",
                "Strategy": "DivergenceReversal_Position",
                "Entry": 80.39,
                "StopLoss": 98.66,
                "Target": 43.84,
                "Score": 55.0,
                "Volume": 1_500_000,
                "Date": dates[-1],
                "Direction": "SHORT",
            }
        ]
    )

    output = capsys.readouterr().out

    assert not trades.empty
    assert "[DivergenceReversal_Position SHORT]" in output
