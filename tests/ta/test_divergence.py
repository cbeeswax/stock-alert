import pandas as pd

from src.ta.indicators.divergence import (
    find_bearish_divergence_setup,
    find_bullish_divergence_setup,
    macd_confirmation_bonus,
)


def _bullish_frame() -> tuple[pd.DataFrame, pd.Series]:
    dates = pd.date_range("2024-01-02", periods=12, freq="B")
    low = [10.0, 9.2, 8.1, 7.0, 8.0, 9.1, 8.4, 7.8, 6.5, 7.2, 8.3, 9.6]
    high = [10.8, 10.0, 8.9, 7.9, 8.9, 9.8, 9.0, 8.4, 7.4, 8.2, 9.2, 10.0]
    close = [10.4, 9.6, 8.5, 7.3, 8.4, 9.5, 8.7, 8.0, 6.9, 7.9, 9.0, 9.8]
    oscillator = pd.Series([55.0, 42.0, 33.0, 20.0, 30.0, 44.0, 37.0, 34.0, 28.0, 36.0, 48.0, 58.0], index=dates)
    return pd.DataFrame({"Low": low, "High": high, "Close": close}, index=dates), oscillator


def _bearish_frame() -> tuple[pd.DataFrame, pd.Series]:
    dates = pd.date_range("2024-01-02", periods=12, freq="B")
    low = [7.5, 8.2, 9.0, 10.1, 9.2, 8.4, 9.3, 10.0, 11.2, 10.3, 9.5, 8.7]
    high = [8.2, 9.1, 9.9, 11.0, 10.0, 9.3, 10.0, 10.8, 12.0, 11.1, 10.1, 9.2]
    close = [7.9, 8.8, 9.5, 10.7, 9.6, 8.9, 9.8, 10.4, 11.7, 10.7, 9.8, 8.9]
    oscillator = pd.Series([45.0, 55.0, 63.0, 78.0, 70.0, 58.0, 64.0, 66.0, 69.0, 60.0, 52.0, 44.0], index=dates)
    return pd.DataFrame({"Low": low, "High": high, "Close": close}, index=dates), oscillator


def test_find_bullish_divergence_setup_returns_latest_confirmable_pair():
    df, oscillator = _bullish_frame()
    macd_frame = pd.DataFrame(
        {
            "macd_line": [0.0, -0.2, -0.4, -0.8, -0.4, 0.0, -0.2, -0.3, -0.1, 0.2, 0.4, 0.6],
            "macd_signal": [0.0, -0.1, -0.2, -0.4, -0.3, -0.1, -0.2, -0.25, -0.2, 0.0, 0.2, 0.3],
            "macd_hist": [0.0, -0.1, -0.2, -0.4, -0.1, 0.1, 0.0, -0.05, 0.1, 0.2, 0.2, 0.3],
        },
        index=df.index,
    )

    setup = find_bullish_divergence_setup(
        df,
        oscillator,
        macd_frame=macd_frame,
        left_bars=1,
        right_bars=1,
        min_separation_bars=3,
        max_pivot_lookback=10,
    )

    assert setup is not None
    assert setup.direction == "LONG"
    assert setup.first_pivot_idx == 3
    assert setup.second_pivot_idx == 8
    assert setup.trigger_level == 9.2
    assert setup.invalidation_level == 6.5
    assert setup.second_price < setup.first_price
    assert setup.second_oscillator > setup.first_oscillator
    assert setup.macd_bonus > 0


def test_find_bearish_divergence_setup_returns_latest_confirmable_pair():
    df, oscillator = _bearish_frame()
    macd_frame = pd.DataFrame(
        {
            "macd_line": [0.2, 0.4, 0.6, 1.1, 0.8, 0.4, 0.5, 0.6, 0.3, 0.0, -0.2, -0.4],
            "macd_signal": [0.1, 0.2, 0.4, 0.8, 0.7, 0.5, 0.5, 0.55, 0.4, 0.1, -0.1, -0.2],
            "macd_hist": [0.1, 0.2, 0.2, 0.3, 0.1, -0.1, 0.0, 0.05, -0.1, -0.1, -0.1, -0.2],
        },
        index=df.index,
    )

    setup = find_bearish_divergence_setup(
        df,
        oscillator,
        macd_frame=macd_frame,
        left_bars=1,
        right_bars=1,
        min_separation_bars=3,
        max_pivot_lookback=10,
    )

    assert setup is not None
    assert setup.direction == "SHORT"
    assert setup.first_pivot_idx == 3
    assert setup.second_pivot_idx == 8
    assert setup.trigger_level == 9.5
    assert setup.invalidation_level == 12.0
    assert setup.second_price > setup.first_price
    assert setup.second_oscillator < setup.first_oscillator
    assert setup.macd_bonus > 0


def test_find_divergence_setup_returns_none_when_oscillator_confirms_price():
    df, oscillator = _bullish_frame()
    oscillator.iloc[8] = 15.0

    setup = find_bullish_divergence_setup(
        df,
        oscillator,
        left_bars=1,
        right_bars=1,
        min_separation_bars=3,
        max_pivot_lookback=10,
    )

    assert setup is None


def test_macd_confirmation_bonus_rewards_directional_improvement():
    macd_frame = pd.DataFrame(
        {
            "macd_line": [-0.9, -0.3, 0.2],
            "macd_signal": [-0.6, -0.4, 0.0],
            "macd_hist": [-0.3, 0.1, 0.2],
        }
    )

    bonus = macd_confirmation_bonus(macd_frame, first_idx=0, second_idx=1, direction="LONG")

    assert bonus == 20.0
