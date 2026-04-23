import numpy as np
import pandas as pd
import pytest

import src.config.settings as cfg
from src.strategies.gap_continuation import GapContinuationPosition


def _gap_continuation_df(n: int = 150, gap_pct: float = 0.05, close_pos: float = 0.8) -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    base = 100 + np.linspace(0, 25, n) + np.sin(np.linspace(0, 10, n)) * 2
    close_vals = base.copy()
    open_vals = close_vals.copy()
    high_vals = close_vals * 1.01
    low_vals = close_vals * 0.99
    volume = np.full(n, 20_000_000.0)

    prior_close = close_vals[-2]
    open_vals[-1] = prior_close * (1 + gap_pct)
    intraday_range = open_vals[-1] * 0.04
    low_vals[-1] = open_vals[-1] - intraday_range
    high_vals[-1] = open_vals[-1] + intraday_range
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


def _post_gap_shelf_df(n: int = 150, gap_pct: float = 0.08) -> pd.DataFrame:
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
    low_vals[gap_idx] = open_vals[gap_idx] * 0.985
    high_vals[gap_idx] = open_vals[gap_idx] * 1.02
    close_vals[gap_idx] = open_vals[gap_idx] * 0.992
    volume[gap_idx] = volume[gap_idx - 1] * 3.0

    open_vals[gap_idx + 1] = close_vals[gap_idx] * 0.998
    low_vals[gap_idx + 1] = close_vals[gap_idx] * 0.988
    high_vals[gap_idx + 1] = close_vals[gap_idx] * 1.008
    close_vals[gap_idx + 1] = close_vals[gap_idx] * 1.002

    open_vals[gap_idx + 2] = close_vals[gap_idx + 1] * 1.001
    low_vals[gap_idx + 2] = close_vals[gap_idx + 1] * 0.995
    high_vals[gap_idx + 2] = close_vals[gap_idx] * 1.025
    close_vals[gap_idx + 2] = close_vals[gap_idx] * 1.01

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


def test_gap_continuation_generates_long_signal():
    df = _gap_continuation_df()
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["Direction"] == "LONG"
    assert signal["Strategy"] == "GapContinuation_Position"


def test_gap_continuation_can_enter_post_gap_shelf():
    df = _post_gap_shelf_df()
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["SignalType"] == "post_gap_shelf"


def test_gap_continuation_rejects_weak_close():
    df = _gap_continuation_df(close_pos=0.35)
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_continuation_rejects_low_volume_gap(monkeypatch):
    monkeypatch.setattr(cfg, "GAP_CONTINUATION_MIN_VOL_MULT", 4.0)
    df = _gap_continuation_df()
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_continuation_rejects_gap_into_nearby_seller_zone():
    df = _gap_continuation_df()
    seller_zone_high = float(df["Close"].iloc[-1]) * 1.01
    df.iloc[-30, df.columns.get_loc("High")] = seller_zone_high
    strat = GapContinuationPosition()

    signal = strat.scan("TEST", df, df.index[-1])

    assert signal is None


def test_gap_continuation_exit_on_gap_support_fail():
    strat = GapContinuationPosition()
    df = _gap_continuation_df()
    position = {"Direction": "LONG", "GapLow": float(df["Low"].iloc[-1])}

    exit_df = df.copy()
    exit_df.iloc[-1, exit_df.columns.get_loc("Low")] = float(df["Low"].iloc[-1]) - 1.0

    exit_cond = strat.get_exit_conditions(position, exit_df, exit_df.index[-1])

    assert exit_cond is not None
    assert exit_cond["reason"] == "gap_support_fail"


def test_gap_continuation_exit_on_zone_support_fail():
    strat = GapContinuationPosition()
    df = _gap_continuation_df()
    position = {"Direction": "LONG", "ZoneSupport": float(df["Close"].iloc[-1]) + 1.0}

    exit_cond = strat.get_exit_conditions(position, df, df.index[-1])

    assert exit_cond is not None
    assert exit_cond["reason"] == "zone_support_fail"
