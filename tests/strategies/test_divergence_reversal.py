import numpy as np
import pandas as pd
import pytest

import src.strategies.divergence_reversal as divergence_module
from src.analysis.zone_structure import ZoneSnapshot
from src.strategies.divergence_reversal import DivergenceReversalPosition
from src.ta.indicators.divergence import DivergenceSetup


def _base_long_df(n: int = 140) -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    base = np.linspace(135, 96, n) + np.sin(np.linspace(0, 10, n)) * 1.2
    close_vals = base.copy()
    open_vals = close_vals * 0.998
    high_vals = close_vals * 1.01
    low_vals = close_vals * 0.99
    volume = np.full(n, 2_500_000.0)

    close_vals[80] = 118.0
    high_vals[80] = 120.0
    low_vals[80] = 116.0
    close_vals[100] = 96.0
    high_vals[100] = 98.0
    low_vals[100] = 95.0
    close_vals[120] = 92.0
    high_vals[120] = 94.0
    low_vals[120] = 90.0

    for idx, price in zip(range(121, 139), np.linspace(93.0, 99.0, 18)):
        close_vals[idx] = price
        open_vals[idx] = price * 0.998
        high_vals[idx] = price * 1.01
        low_vals[idx] = price * 0.99

    open_vals[-1] = 98.0
    low_vals[-1] = 97.0
    high_vals[-1] = 101.0
    close_vals[-1] = 100.0
    volume[-1] = 3_500_000.0

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


def _base_short_df(n: int = 140) -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    base = np.linspace(75, 112, n) + np.sin(np.linspace(0, 10, n)) * 1.0
    close_vals = base.copy()
    open_vals = close_vals * 1.002
    high_vals = close_vals * 1.01
    low_vals = close_vals * 0.99
    volume = np.full(n, 2_500_000.0)

    close_vals[80] = 86.0
    high_vals[80] = 88.0
    low_vals[80] = 84.0
    close_vals[100] = 108.0
    high_vals[100] = 110.0
    low_vals[100] = 106.0
    close_vals[120] = 114.0
    high_vals[120] = 116.0
    low_vals[120] = 112.0

    for idx, price in zip(range(121, 139), np.linspace(113.0, 108.0, 18)):
        close_vals[idx] = price
        open_vals[idx] = price * 1.002
        high_vals[idx] = price * 1.01
        low_vals[idx] = price * 0.99

    open_vals[-1] = 107.0
    high_vals[-1] = 108.0
    low_vals[-1] = 103.5
    close_vals[-1] = 104.0
    volume[-1] = 3_500_000.0

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
def configure_divergence(monkeypatch):
    monkeypatch.setattr(
        DivergenceReversalPosition,
        "_load_external_settings",
        classmethod(
            lambda cls: {
                "DIVERGENCE_REVERSAL_DIRECTION": "both",
                "DIVERGENCE_REVERSAL_EMA_PERIOD": 21,
                "DIVERGENCE_REVERSAL_RSI_PERIOD": 14,
                "DIVERGENCE_REVERSAL_MACD_FAST_PERIOD": 12,
                "DIVERGENCE_REVERSAL_MACD_SLOW_PERIOD": 26,
                "DIVERGENCE_REVERSAL_MACD_SIGNAL_PERIOD": 9,
                "DIVERGENCE_REVERSAL_PIVOT_LEFT_BARS": 3,
                "DIVERGENCE_REVERSAL_PIVOT_RIGHT_BARS": 3,
                "DIVERGENCE_REVERSAL_MIN_SEPARATION_BARS": 5,
                "DIVERGENCE_REVERSAL_PIVOT_LOOKBACK_BARS": 60,
                "DIVERGENCE_REVERSAL_PRIOR_DECLINE_LOOKBACK": 40,
                "DIVERGENCE_REVERSAL_PRIOR_DECLINE_PCT": 0.12,
                "DIVERGENCE_REVERSAL_PRIOR_RALLY_LOOKBACK": 40,
                "DIVERGENCE_REVERSAL_PRIOR_RALLY_PCT": 0.12,
                "DIVERGENCE_REVERSAL_MIN_CONFIRM_CLOSE_POS": 0.60,
                "DIVERGENCE_REVERSAL_MIN_EFFECTIVE_RISK_PCT": 0.01,
                "DIVERGENCE_REVERSAL_TRAIL_MA": 21,
                "DIVERGENCE_REVERSAL_TARGET_R_MULTIPLE": 2.0,
                "DIVERGENCE_REVERSAL_LONG_MIN_ROOM_TO_RESISTANCE": 0.03,
                "DIVERGENCE_REVERSAL_SHORT_MIN_ROOM_TO_SUPPORT": 0.03,
                "DIVERGENCE_REVERSAL_ZONE_EXIT_TOLERANCE_PCT": 0.002,
                "DIVERGENCE_REVERSAL_MAX_DAYS": 90,
                "DIVERGENCE_REVERSAL_MAX_SIGNAL_AGE_DAYS": 5,
                "DIVERGENCE_REVERSAL_PRIORITY": 2,
                "DIVERGENCE_REVERSAL_MIN_HISTORY_BARS": 80,
            }
        ),
    )


def test_divergence_reversal_generates_confirmed_long_signal(monkeypatch):
    df = _base_long_df()
    monkeypatch.setattr(
        divergence_module,
        "find_bullish_divergence_setup",
        lambda *args, **kwargs: DivergenceSetup(
            direction="LONG",
            first_pivot_idx=100,
            second_pivot_idx=120,
            trigger_level=99.0,
            invalidation_level=90.0,
            first_price=95.0,
            second_price=90.0,
            first_oscillator=22.0,
            second_oscillator=31.0,
            macd_bonus=12.0,
        ),
    )
    monkeypatch.setattr(divergence_module, "find_bearish_divergence_setup", lambda *args, **kwargs: None)

    signal = DivergenceReversalPosition().scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["Direction"] == "LONG"
    assert signal["Strategy"] == "DivergenceReversal_Position"
    assert signal["SignalType"] == "confirmed_bullish_divergence"
    assert signal["Entry"] == 100.0
    assert signal["StopLoss"] < signal["Entry"]
    assert signal["ZoneSupport"] >= 90.0
    assert signal["MACDBonus"] == 12.0


def test_divergence_reversal_generates_confirmed_short_signal(monkeypatch):
    df = _base_short_df()
    monkeypatch.setattr(divergence_module, "find_bullish_divergence_setup", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        divergence_module,
        "find_bearish_divergence_setup",
        lambda *args, **kwargs: DivergenceSetup(
            direction="SHORT",
            first_pivot_idx=100,
            second_pivot_idx=120,
            trigger_level=105.0,
            invalidation_level=116.0,
            first_price=110.0,
            second_price=116.0,
            first_oscillator=79.0,
            second_oscillator=68.0,
            macd_bonus=10.0,
        ),
    )
    monkeypatch.setattr(
        divergence_module,
        "build_zone_snapshot",
        lambda *_args, **_kwargs: ZoneSnapshot(
            close=104.0,
            prior_short_high=115.0,
            prior_short_low=100.0,
            prior_long_high=118.0,
            prior_long_low=80.0,
            short_zone_width_pct=0.08,
            long_zone_width_pct=0.20,
            short_zone_position=0.30,
            long_zone_position=0.45,
            room_to_short_ceiling_pct=0.10,
            room_to_long_ceiling_pct=0.14,
            room_to_short_floor_pct=0.04,
            room_to_long_floor_pct=0.30,
            in_short_seller_zone=False,
            in_long_seller_zone=False,
            in_short_demand_zone=False,
            in_long_demand_zone=False,
        ),
    )

    signal = DivergenceReversalPosition().scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["Direction"] == "SHORT"
    assert signal["SignalType"] == "confirmed_bearish_divergence"
    assert signal["Entry"] == 104.0
    assert signal["StopLoss"] > signal["Entry"]
    assert signal["ZoneResistance"] <= 116.0


def test_divergence_reversal_rejects_without_price_confirmation(monkeypatch):
    df = _base_long_df()
    df.iloc[-1, df.columns.get_loc("Close")] = 98.8
    df.iloc[-1, df.columns.get_loc("High")] = 99.0
    monkeypatch.setattr(
        divergence_module,
        "find_bullish_divergence_setup",
        lambda *args, **kwargs: DivergenceSetup(
            direction="LONG",
            first_pivot_idx=100,
            second_pivot_idx=120,
            trigger_level=99.0,
            invalidation_level=90.0,
            first_price=95.0,
            second_price=90.0,
            first_oscillator=22.0,
            second_oscillator=31.0,
            macd_bonus=12.0,
        ),
    )
    monkeypatch.setattr(divergence_module, "find_bearish_divergence_setup", lambda *args, **kwargs: None)

    signal = DivergenceReversalPosition().scan("TEST", df, df.index[-1])

    assert signal is None


def test_divergence_reversal_rejects_nearby_long_resistance(monkeypatch):
    df = _base_long_df()
    monkeypatch.setattr(
        divergence_module,
        "find_bullish_divergence_setup",
        lambda *args, **kwargs: DivergenceSetup(
            direction="LONG",
            first_pivot_idx=100,
            second_pivot_idx=120,
            trigger_level=99.0,
            invalidation_level=90.0,
            first_price=95.0,
            second_price=90.0,
            first_oscillator=22.0,
            second_oscillator=31.0,
            macd_bonus=12.0,
        ),
    )
    monkeypatch.setattr(divergence_module, "find_bearish_divergence_setup", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        divergence_module,
        "build_zone_snapshot",
        lambda *_args, **_kwargs: ZoneSnapshot(
            close=100.0,
            prior_short_high=101.0,
            prior_short_low=96.0,
            prior_long_high=101.5,
            prior_long_low=90.0,
            short_zone_width_pct=0.05,
            long_zone_width_pct=0.10,
            short_zone_position=0.85,
            long_zone_position=0.90,
            room_to_short_ceiling_pct=0.01,
            room_to_long_ceiling_pct=0.015,
            room_to_short_floor_pct=0.04,
            room_to_long_floor_pct=0.10,
            in_short_seller_zone=True,
            in_long_seller_zone=True,
            in_short_demand_zone=False,
            in_long_demand_zone=False,
        ),
    )

    signal = DivergenceReversalPosition().scan("TEST", df, df.index[-1])

    assert signal is None


def test_divergence_reversal_uses_minimum_practical_risk_floor(monkeypatch):
    df = _base_long_df()
    monkeypatch.setattr(
        divergence_module,
        "find_bullish_divergence_setup",
        lambda *args, **kwargs: DivergenceSetup(
            direction="LONG",
            first_pivot_idx=100,
            second_pivot_idx=120,
            trigger_level=99.0,
            invalidation_level=99.6,
            first_price=95.0,
            second_price=99.6,
            first_oscillator=22.0,
            second_oscillator=31.0,
            macd_bonus=12.0,
        ),
    )
    monkeypatch.setattr(divergence_module, "find_bearish_divergence_setup", lambda *args, **kwargs: None)

    signal = DivergenceReversalPosition().scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["RiskPerShare"] == round(signal["Entry"] * 0.01, 2)


def test_divergence_reversal_exit_on_zone_support_fail():
    strat = DivergenceReversalPosition()
    df = _base_long_df()
    position = {"Direction": "LONG", "ZoneSupport": 101.0}

    exit_cond = strat.get_exit_conditions(position, df, df.index[-1])

    assert exit_cond is not None
    assert exit_cond["reason"] == "zone_support_fail"


def test_divergence_reversal_exit_on_zone_resistance_fail():
    strat = DivergenceReversalPosition()
    df = _base_short_df()
    position = {"Direction": "SHORT", "ZoneResistance": 103.0}

    exit_cond = strat.get_exit_conditions(position, df, df.index[-1])

    assert exit_cond is not None
    assert exit_cond["reason"] == "zone_resistance_fail"
