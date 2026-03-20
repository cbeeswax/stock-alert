"""
Unit tests for the GapReversalPosition strategy.

Tests cover:
- Signal generation (long / short / filtered-out cases)
- Exit condition logic (gap fill stop + EMA21 trailing)
- Edge cases (insufficient data, NaN guards, liquidity filters)
"""
import pandas as pd
import numpy as np
import pytest

from src.strategies.gap_reversal import GapReversalPosition
import src.config.settings as cfg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _declining_df(n=150, final_gap_up=True, gap_pct=0.015):
    """
    Build n rows of declining price ending in a gap-up (long setup) or
    gap-down (short setup) on the last bar.

    Returns a properly DatetimeIndexed OHLCV DataFrame.
    """
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    close_vals = 100 - np.linspace(0, 40, n)   # declining → drives RSI very low

    open_vals = close_vals.copy()
    if final_gap_up:
        open_vals[-1] = close_vals[-2] * (1 + gap_pct)   # gap up on last bar
    else:
        open_vals[-1] = close_vals[-2] * (1 - gap_pct)   # gap down on last bar

    return pd.DataFrame(
        {
            "Open":   open_vals,
            "High":   np.maximum(open_vals, close_vals) * 1.005,
            "Low":    np.minimum(open_vals, close_vals) * 0.995,
            "Close":  close_vals,
            "Volume": [50_000_000] * n,
        },
        index=dates,
    )


def _rallying_df(n=150, final_gap_down=True, gap_pct=0.015):
    """Build n rows of rising price ending in a gap-down (short setup)."""
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    close_vals = 60 + np.linspace(0, 40, n)   # rallying → drives RSI very high

    open_vals = close_vals.copy()
    if final_gap_down:
        open_vals[-1] = close_vals[-2] * (1 - gap_pct)

    return pd.DataFrame(
        {
            "Open":   open_vals,
            "High":   np.maximum(open_vals, close_vals) * 1.005,
            "Low":    np.minimum(open_vals, close_vals) * 0.995,
            "Close":  close_vals,
            "Volume": [50_000_000] * n,
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def disable_weekly_filter(monkeypatch):
    """Disable weekly TF filter so tests don't need network access."""
    monkeypatch.setattr(cfg, "GAP_REVERSAL_WEEKLY_TF_FILTER", False)


# ---------------------------------------------------------------------------
# Signal generation — LONG
# ---------------------------------------------------------------------------

class TestLongSignal:
    def test_gap_up_low_rsi_generates_long_signal(self):
        df = _declining_df(n=150, final_gap_up=True, gap_pct=0.015)
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])

        assert signal is not None
        assert signal["Direction"] == "LONG"
        assert signal["Ticker"] == "TEST"
        assert signal["Strategy"] == "GapReversal_Position"

    def test_signal_entry_is_open_price(self):
        df = _declining_df(n=150, final_gap_up=True, gap_pct=0.015)
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])

        expected_entry = round(float(df["Open"].iloc[-1]), 2)
        assert signal["Entry"] == pytest.approx(expected_entry, abs=0.01)

    def test_signal_stop_is_prior_close(self):
        df = _declining_df(n=150, final_gap_up=True, gap_pct=0.015)
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])

        expected_stop = round(float(df["Close"].iloc[-2]), 2)
        assert signal["StopLoss"] == pytest.approx(expected_stop, abs=0.01)

    def test_signal_contains_required_keys(self):
        df = _declining_df(n=150, final_gap_up=True)
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])

        required = {
            "Ticker", "Strategy", "Direction", "Entry", "StopLoss",
            "GapFillLevel", "SmoothedRSI", "GapPct", "Score", "MaxDays",
        }
        assert required.issubset(signal.keys())

    def test_no_signal_when_gap_below_threshold(self):
        """0.1% gap up — below 0.5% minimum. Should be filtered out."""
        df = _declining_df(n=150, final_gap_up=True, gap_pct=0.001)
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])
        assert signal is None

    def test_no_signal_when_rsi_not_oversold(self):
        """Flat price (RSI ~50) with a gap up — RSI condition not met."""
        n = 150
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        close_vals = np.full(n, 100.0)
        open_vals = close_vals.copy()
        open_vals[-1] = close_vals[-2] * 1.02   # 2% gap up
        df = pd.DataFrame(
            {
                "Open":   open_vals,
                "High":   close_vals * 1.003,
                "Low":    close_vals * 0.997,
                "Close":  close_vals,
                "Volume": [50_000_000] * n,
            },
            index=dates,
        )
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])
        # Smoothed RSI on flat price is near 50 — should not fire < 10
        assert signal is None

    def test_no_signal_insufficient_data(self):
        """Only 20 bars — not enough for EMA21 + RSI10 warmup."""
        df = _declining_df(n=20, final_gap_up=True)
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])
        assert signal is None

    def test_direction_long_only_no_short(self, monkeypatch):
        """When GAP_REVERSAL_DIRECTION='long', short signals are suppressed."""
        monkeypatch.setattr(cfg, "GAP_REVERSAL_DIRECTION", "long")
        df = _rallying_df(n=150, final_gap_down=True, gap_pct=0.015)
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])
        # No long setup here (rallying df with gap down) — signal should be None
        assert signal is None


# ---------------------------------------------------------------------------
# Signal generation — SHORT
# ---------------------------------------------------------------------------

class TestShortSignal:
    def test_gap_down_high_rsi_generates_short_signal(self):
        df = _rallying_df(n=150, final_gap_down=True, gap_pct=0.015)
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])

        assert signal is not None
        assert signal["Direction"] == "SHORT"

    def test_no_short_when_direction_set_to_long_only(self, monkeypatch):
        monkeypatch.setattr(cfg, "GAP_REVERSAL_DIRECTION", "long")
        df = _rallying_df(n=150, final_gap_down=True, gap_pct=0.015)
        strat = GapReversalPosition()
        signal = strat.scan("TEST", df, df.index[-1])
        assert signal is None


# ---------------------------------------------------------------------------
# Exit conditions
# ---------------------------------------------------------------------------

class TestExitConditions:
    def _make_position(self, direction="LONG", gap_fill=95.0):
        return {
            "Direction": direction,
            "GapFillLevel": gap_fill,
            "entry_price": 102.0,
            "risk_amount": 7.0,
        }

    def _df_at_price(self, price, ema_above=True, n=60):
        """DataFrame where the last close is 'price' and EMA21 is either above or below."""
        # Build a run of prices that sets up EMA, then the final bar
        dates = pd.date_range("2024-01-02", periods=n, freq="B")
        if ema_above:
            # Declining: EMA21 > last close (triggers exit for LONG)
            close_vals = np.linspace(110, price, n)
        else:
            # Stable: last close > EMA21 (no exit for LONG)
            close_vals = np.linspace(95, price, n)
        return pd.DataFrame(
            {
                "Open": close_vals,
                "High": close_vals * 1.005,
                "Low":  close_vals * 0.995,
                "Close": close_vals,
                "Volume": [10_000_000] * n,
            },
            index=dates,
        )

    def test_gap_fill_stop_long(self):
        """Long position: Low drops to gap fill level → exit."""
        strat = GapReversalPosition()
        position = self._make_position("LONG", gap_fill=95.0)

        # Build df where last Low = 94.5 (below gap fill)
        n = 30
        dates = pd.date_range("2024-01-02", periods=n, freq="B")
        close_vals = np.linspace(100, 96, n)
        low_vals = close_vals.copy()
        low_vals[-1] = 94.5   # below gap fill

        df = pd.DataFrame(
            {"Open": close_vals, "High": close_vals * 1.01,
             "Low": low_vals, "Close": close_vals, "Volume": [1_000_000]*n},
            index=dates,
        )
        exit_cond = strat.get_exit_conditions(position, df)
        assert exit_cond is not None
        assert "gap_fill" in exit_cond["reason"]

    def test_ema_trailing_exit_long(self):
        """Long position: close < EMA21 → trailing exit triggered."""
        strat = GapReversalPosition()
        position = self._make_position("LONG", gap_fill=50.0)  # gap fill far below
        df = self._df_at_price(price=90, ema_above=True)   # EMA above close
        exit_cond = strat.get_exit_conditions(position, df)
        assert exit_cond is not None
        assert "trailing_ema" in exit_cond["reason"]

    def test_no_exit_when_trade_is_healthy(self):
        """Long position above EMA21 and above gap fill → no exit."""
        strat = GapReversalPosition()
        position = self._make_position("LONG", gap_fill=50.0)  # gap fill far below
        df = self._df_at_price(price=110, ema_above=False)   # rising: close > EMA21
        exit_cond = strat.get_exit_conditions(position, df)
        assert exit_cond is None

    def test_gap_fill_stop_short(self):
        """Short position: close returns to/above gap fill → exit."""
        strat = GapReversalPosition()
        position = self._make_position("SHORT", gap_fill=110.0)

        n = 30
        dates = pd.date_range("2024-01-02", periods=n, freq="B")
        close_vals = np.linspace(100, 111, n)  # rallying back above gap fill

        df = pd.DataFrame(
            {"Open": close_vals, "High": close_vals * 1.01,
             "Low": close_vals * 0.99, "Close": close_vals, "Volume": [1_000_000]*n},
            index=dates,
        )
        exit_cond = strat.get_exit_conditions(position, df)
        assert exit_cond is not None
        assert "gap_fill" in exit_cond["reason"]
