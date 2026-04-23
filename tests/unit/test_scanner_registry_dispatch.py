import pandas as pd

from src.scanning import scanner


class _FakeRegistryStrategy:
    def run(self, tickers, as_of_date=None):
        return [
            {
                "Ticker": "AAA",
                "Strategy": "RallyPattern_Position",
                "Entry": 100.0,
                "StopLoss": 95.0,
                "Target": 110.0,
                "Score": 90.0,
                "Volume": 1_000_000,
                "Date": pd.Timestamp("2024-03-05"),
                "Priority": 3,
                "MaxDays": 120,
            }
        ]


def test_run_scan_as_of_includes_registry_strategy_signals(monkeypatch):
    monkeypatch.setattr(scanner, "_get_active_registry_strategies", lambda: [("RallyPattern_Position", _FakeRegistryStrategy())])
    monkeypatch.setattr(scanner, "get_historical_data", lambda ticker: pd.DataFrame())

    signals = scanner.run_scan_as_of(pd.Timestamp("2024-03-05"), ["AAA"])

    assert len(signals) == 1
    assert signals[0]["Strategy"] == "RallyPattern_Position"
    assert signals[0]["Ticker"] == "AAA"
