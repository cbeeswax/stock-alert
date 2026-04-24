import numpy as np
import pandas as pd
import pytest

import src.config.settings as cfg
from src.strategies.gap_continuation import GapContinuationPosition


def _gap_day_only_df(n: int = 150, gap_pct: float = 0.05, close_pos: float = 0.8) -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    base = 100 + np.linspace(0, 25, n) + np.sin(np.linspace(0, 10, n)) * 2
    close_vals = base.copy()
    open_vals = close_vals.copy()
    high_vals = close_vals * 1.01
    low_vals = close_vals * 0.99
    volume = np.full(n, 20_000_000.0)

    prior_close = close_vals[-2]
    open_vals[-1] = prior_close * (1 + gap_pct)
    low_vals[-1] = open_vals[-1] * 0.995
    high_vals[-1] = open_vals[-1] * 1.025
    close_vals[-1] = low_vals[-1] + (high_vals[-1] - low_vals[-1]) * close_pos
    volume[-1] = volume[-2] * 3.0

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
def disable_weekly_filter(monkeypatch):
    monkeypatch.setattr(cfg, "GAP_CONTINUATION_WEEKLY_TF_FILTER", False)
    monkeypatch.setattr(cfg, "GAP_CONTINUATION_MIN_RS_20", -1.0)
    monkeypatch.setattr(cfg, "GAP_CONTINUATION_RSI_MAX", 100)
    monkeypatch.setattr(cfg, "GAP_CONTINUATION_MIN_SHELF_CLOSE_POS", 0.45)
    monkeypatch.setattr(
        GapContinuationPosition,
        "_load_external_settings",
        classmethod(
            lambda cls: {
                "GAP_CONTINUATION_MIN_BREAKOUT_CLOSE_POS": 0.60,
                "GAP_CONTINUATION_MAX_GAP_DAY_UPPER_WICK_PCT": 0.35,
                "GAP_CONTINUATION_MIN_EFFECTIVE_RISK_PCT": 0.01,
            }
        ),
    )


def _confirmed_gap_breakout_df(n: int = 150, gap_pct: float = 0.08) -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    base = 100 + np.linspace(0, 20, n) + np.sin(np.linspace(0, 8, n)) * 1.2
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

    open_vals[gap_idx + 1] = close_vals[gap_idx] * 0.998
    low_vals[gap_idx + 1] = close_vals[gap_idx] * 0.992
    high_vals[gap_idx + 1] = close_vals[gap_idx] * 1.004
    close_vals[gap_idx + 1] = close_vals[gap_idx] * 1.001

    open_vals[gap_idx + 2] = close_vals[gap_idx + 1] * 1.001
    low_vals[gap_idx + 2] = close_vals[gap_idx + 1] * 0.998
    high_vals[gap_idx + 2] = high_vals[gap_idx] * 1.01
    close_vals[gap_idx + 2] = high_vals[gap_idx] * 1.006
    volume[gap_idx + 2] = volume[gap_idx + 1] * 1.4

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


def test_gap_continuation_rejects_same_day_gap_entry():
    df = _gap_day_only_df()
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_continuation_generates_confirmed_breakout_signal():
    df = _confirmed_gap_breakout_df()
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["Direction"] == "LONG"
    assert signal["Strategy"] == "GapContinuation_Position"
    assert signal["SignalType"] == "confirmed_gap_breakout"
    assert signal["Entry"] == round(float(df["Close"].iloc[-1]), 2)
    assert signal["GapSupport"] > float(df["Close"].iloc[-4])
    assert signal["StopLoss"] <= signal["GapSupport"]
    assert signal["RiskPerShare"] == round(signal["Entry"] - signal["StopLoss"], 2)


def test_gap_continuation_rejects_weak_breakout_close():
    df = _confirmed_gap_breakout_df()
    df.iloc[-1, df.columns.get_loc("Close")] = float(df["Low"].iloc[-1]) + (
        float(df["High"].iloc[-1]) - float(df["Low"].iloc[-1])
    ) * 0.2
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_continuation_rejects_low_volume_gap(monkeypatch):
    monkeypatch.setattr(cfg, "GAP_CONTINUATION_MIN_VOL_MULT", 4.0)
    df = _confirmed_gap_breakout_df()
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_continuation_rejects_gap_into_nearby_seller_zone():
    df = _confirmed_gap_breakout_df()
    seller_zone_high = float(df["Close"].iloc[-1]) * 1.01
    df.iloc[-30, df.columns.get_loc("High")] = seller_zone_high
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_continuation_rejects_gap_mid_hold_failure():
    df = _confirmed_gap_breakout_df()
    gap_idx = len(df) - 3
    prior_close = float(df["Close"].iloc[gap_idx - 1])
    gap_mid = prior_close + ((float(df["Open"].iloc[gap_idx]) - prior_close) * 0.5)
    df.iloc[-2, df.columns.get_loc("Close")] = gap_mid * 0.995
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_continuation_uses_minimum_practical_risk_floor():
    df = _confirmed_gap_breakout_df()
    df.iloc[-2, df.columns.get_loc("Low")] = float(df["Close"].iloc[-2]) * 0.9998
    df.iloc[-2, df.columns.get_loc("High")] = float(df["Close"].iloc[-2]) * 1.0001
    df.iloc[-1, df.columns.get_loc("Low")] = float(df["Close"].iloc[-1]) * 0.9996
    df.iloc[-1, df.columns.get_loc("High")] = float(df["Close"].iloc[-1]) * 1.0002
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["RiskPerShare"] == round(signal["Entry"] * 0.01, 2)


def test_gap_continuation_exit_on_gap_support_fail():
    strat = GapContinuationPosition()
    df = _confirmed_gap_breakout_df()
    signal = strat.scan("TEST", df, df.index[-1])
    position = {"Direction": "LONG", "GapSupport": signal["GapSupport"]}

    exit_df = df.copy()
    exit_df.iloc[-1, exit_df.columns.get_loc("Low")] = signal["GapSupport"] - 1.0

    exit_cond = strat.get_exit_conditions(position, exit_df, exit_df.index[-1])

    assert exit_cond is not None
    assert exit_cond["reason"] == "gap_support_fail"


def test_gap_continuation_exit_on_zone_support_fail():
    strat = GapContinuationPosition()
    df = _confirmed_gap_breakout_df()
    position = {"Direction": "LONG", "ZoneSupport": float(df["Close"].iloc[-1]) + 1.0}

    exit_cond = strat.get_exit_conditions(position, df, df.index[-1])

    assert exit_cond is not None
    assert exit_cond["reason"] == "zone_support_fail"
