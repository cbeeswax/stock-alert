import numpy as np
import pandas as pd
import pytest

import src.config.settings as cfg
from src.strategies.gap_reversal import GapReversalPosition


def _confirmed_long_reversal_df(n: int = 150, gap_pct: float = 0.03) -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    early = np.linspace(100, 80, n - 25, endpoint=False)
    late = np.linspace(80, 60, 25)
    base = np.concatenate([early, late]) + np.sin(np.linspace(0, 8, n)) * 0.2
    close_vals = base.copy()
    open_vals = close_vals.copy()
    high_vals = close_vals * 1.01
    low_vals = close_vals * 0.99
    volume = np.full(n, 20_000_000.0)

    gap_idx = n - 3
    prior_close = close_vals[gap_idx - 1]
    open_vals[gap_idx] = prior_close * (1 + gap_pct)
    low_vals[gap_idx] = open_vals[gap_idx] * 0.995
    high_vals[gap_idx] = open_vals[gap_idx] * 1.02
    close_vals[gap_idx] = open_vals[gap_idx] * 1.015
    volume[gap_idx] = volume[gap_idx - 1] * 3.0

    open_vals[gap_idx + 1] = close_vals[gap_idx] * 0.999
    low_vals[gap_idx + 1] = close_vals[gap_idx] * 0.998
    high_vals[gap_idx + 1] = close_vals[gap_idx] * 1.002
    close_vals[gap_idx + 1] = close_vals[gap_idx] * 1.001

    open_vals[gap_idx + 2] = close_vals[gap_idx + 1] * 1.001
    low_vals[gap_idx + 2] = close_vals[gap_idx + 1] * 0.999
    high_vals[gap_idx + 2] = high_vals[gap_idx] * 1.01
    close_vals[gap_idx + 2] = high_vals[gap_idx] * 1.006
    volume[gap_idx + 2] = volume[gap_idx + 1] * 1.3

    return pd.DataFrame(
        {
            "Open": open_vals,
            "High": high_vals,
            "Low": low_vals,
            "Close": close_vals,
            "Volume": volume,
        },
        index=dates,
    )


def _confirmed_short_reversal_df(n: int = 150, gap_pct: float = 0.03) -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    early = np.linspace(30, 100, n - 25, endpoint=False)
    late = np.linspace(100, 150, 25)
    base = np.concatenate([early, late]) + np.sin(np.linspace(0, 8, n)) * 0.2
    close_vals = base.copy()
    open_vals = close_vals.copy()
    high_vals = close_vals * 1.01
    low_vals = close_vals * 0.99
    volume = np.full(n, 20_000_000.0)

    gap_idx = n - 3
    prior_close = close_vals[gap_idx - 1]
    open_vals[gap_idx] = prior_close * (1 - gap_pct)
    high_vals[gap_idx] = open_vals[gap_idx] * 1.005
    low_vals[gap_idx] = open_vals[gap_idx] * 0.98
    close_vals[gap_idx] = open_vals[gap_idx] * 0.985
    volume[gap_idx] = volume[gap_idx - 1] * 3.0

    open_vals[gap_idx + 1] = close_vals[gap_idx] * 1.001
    high_vals[gap_idx + 1] = close_vals[gap_idx] * 1.002
    low_vals[gap_idx + 1] = close_vals[gap_idx] * 0.998
    close_vals[gap_idx + 1] = close_vals[gap_idx] * 0.999

    open_vals[gap_idx + 2] = close_vals[gap_idx + 1] * 0.999
    high_vals[gap_idx + 2] = close_vals[gap_idx + 1] * 1.001
    low_vals[gap_idx + 2] = low_vals[gap_idx] * 0.99
    close_vals[gap_idx + 2] = low_vals[gap_idx] * 0.995
    volume[gap_idx + 2] = volume[gap_idx + 1] * 1.3

    return pd.DataFrame(
        {
            "Open": open_vals,
            "High": high_vals,
            "Low": low_vals,
            "Close": close_vals,
            "Volume": volume,
        },
        index=dates,
    )


@pytest.fixture(autouse=True)
def configure_gap_reversal(monkeypatch):
    monkeypatch.setattr(cfg, "GAP_REVERSAL_WEEKLY_TF_FILTER", False)
    monkeypatch.setattr(cfg, "GAP_REVERSAL_LONG_MACRO_FILTER", False)
    monkeypatch.setattr(cfg, "GAP_REVERSAL_MIN_GAP_ATR_MULT", 0.0)
    monkeypatch.setattr(cfg, "GAP_REVERSAL_MIN_VOL_MULT", 1.0)
    monkeypatch.setattr(cfg, "GAP_REVERSAL_SHORT_REGIME_FILTER", False)
    monkeypatch.setattr(
        GapReversalPosition,
        "_load_external_settings",
        classmethod(
            lambda cls: {
                "GAP_REVERSAL_MIN_CONFIRM_CLOSE_POS": 0.60,
                "GAP_REVERSAL_MAX_COUNTER_WICK_PCT": 0.35,
                "GAP_REVERSAL_MIN_EFFECTIVE_RISK_PCT": 0.01,
            }
        ),
    )


def test_gap_reversal_rejects_same_day_long_gap_entry():
    df = _confirmed_long_reversal_df()
    df = df.iloc[:-1].copy()
    strat = GapReversalPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_reversal_generates_confirmed_long_signal():
    df = _confirmed_long_reversal_df()
    strat = GapReversalPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["Direction"] == "LONG"
    assert signal["Strategy"] == "GapReversal_Position"
    assert signal["SignalType"] == "confirmed_gap_reversal"
    assert signal["Entry"] == round(float(df["Close"].iloc[-1]), 2)
    assert signal["StopLoss"] < signal["Entry"]
    assert signal["RiskPerShare"] == round(signal["Entry"] - signal["StopLoss"], 2)
    assert signal["GapFillLevel"] < signal["Entry"]
    assert signal["GapSupport"] >= signal["GapMid"]


def test_gap_reversal_generates_confirmed_short_signal():
    df = _confirmed_short_reversal_df()
    strat = GapReversalPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["Direction"] == "SHORT"
    assert signal["Entry"] == round(float(df["Close"].iloc[-1]), 2)
    assert signal["StopLoss"] > signal["Entry"]
    assert signal["GapResistance"] <= signal["GapMid"]
    assert signal["ZoneResistance"] >= signal["GapResistance"]


def test_gap_reversal_rejects_weak_gap_bar():
    df = _confirmed_long_reversal_df()
    gap_idx = len(df) - 3
    df.iloc[gap_idx, df.columns.get_loc("Close")] = float(df["Open"].iloc[gap_idx]) * 1.002
    strat = GapReversalPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_reversal_rejects_failed_long_hold():
    df = _confirmed_long_reversal_df()
    gap_idx = len(df) - 3
    prior_close = float(df["Close"].iloc[gap_idx - 1])
    gap_mid = prior_close + ((float(df["Open"].iloc[gap_idx]) - prior_close) * 0.5)
    df.iloc[-2, df.columns.get_loc("Close")] = gap_mid * 0.995
    strat = GapReversalPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_reversal_rejects_failed_short_hold():
    df = _confirmed_short_reversal_df()
    gap_idx = len(df) - 3
    prior_close = float(df["Close"].iloc[gap_idx - 1])
    gap_mid = prior_close + ((float(df["Open"].iloc[gap_idx]) - prior_close) * 0.5)
    df.iloc[-2, df.columns.get_loc("Close")] = gap_mid * 1.005
    strat = GapReversalPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_reversal_rejects_nearby_long_resistance():
    df = _confirmed_long_reversal_df()
    broader_seller_zone_high = float(df["Close"].iloc[-1]) * 1.017
    recent_range_high = float(df["Close"].iloc[-1]) * 1.005
    df.iloc[-50, df.columns.get_loc("High")] = broader_seller_zone_high
    df.iloc[-25:-1, df.columns.get_loc("High")] = np.minimum(
        df.iloc[-25:-1]["High"].to_numpy(),
        recent_range_high,
    )
    strat = GapReversalPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_reversal_uses_minimum_practical_risk_floor():
    df = _confirmed_long_reversal_df()
    df.iloc[-2, df.columns.get_loc("Low")] = float(df["Close"].iloc[-2]) * 1.0002
    df.iloc[-2, df.columns.get_loc("High")] = float(df["Close"].iloc[-2]) * 1.0004
    df.iloc[-1, df.columns.get_loc("Low")] = float(df["Close"].iloc[-1]) * 0.9998
    df.iloc[-1, df.columns.get_loc("High")] = float(df["Close"].iloc[-1]) * 1.00005
    strat = GapReversalPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["RiskPerShare"] == round(signal["Entry"] * 0.01, 2)


def test_gap_reversal_gap_fill_stop_long():
    strat = GapReversalPosition()
    position = {"Direction": "LONG", "GapFillLevel": 95.0}
    dates = pd.date_range("2024-01-02", periods=30, freq="B")
    close_vals = np.linspace(100, 96, 30)
    low_vals = close_vals.copy()
    low_vals[-1] = 94.5
    df = pd.DataFrame(
        {
            "Open": close_vals,
            "High": close_vals * 1.01,
            "Low": low_vals,
            "Close": close_vals,
            "Volume": [1_000_000] * 30,
        },
        index=dates,
    )

    exit_cond = strat.get_exit_conditions(position, df)

    assert exit_cond is not None
    assert "gap_fill" in exit_cond["reason"]


def test_gap_reversal_zone_resistance_fail_short():
    strat = GapReversalPosition()
    position = {"Direction": "SHORT", "ZoneResistance": 99.0}
    dates = pd.date_range("2024-01-02", periods=60, freq="B")
    close_vals = np.linspace(95, 101, 60)
    df = pd.DataFrame(
        {
            "Open": close_vals,
            "High": close_vals * 1.005,
            "Low": close_vals * 0.995,
            "Close": close_vals,
            "Volume": [1_000_000] * 60,
        },
        index=dates,
    )

    exit_cond = strat.get_exit_conditions(position, df)

    assert exit_cond is not None
    assert exit_cond["reason"] == "zone_resistance_fail"
