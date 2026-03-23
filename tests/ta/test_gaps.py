"""
Unit tests for src/ta/indicators/gaps.py

All tests use synthetic DataFrames with DatetimeIndex to mirror real OHLCV data.
"""
import pandas as pd
import numpy as np
import pytest

from src.ta.indicators.gaps import gap_pct, is_gap_up, is_gap_down, gap_fill_level


def _make_df(closes, opens=None, n_rows=None):
    """Build a minimal OHLCV DataFrame with DatetimeIndex."""
    n = n_rows or len(closes)
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    close_arr = np.array(closes, dtype=float)
    open_arr = np.array(opens, dtype=float) if opens is not None else close_arr.copy()
    return pd.DataFrame(
        {
            "Open": open_arr,
            "High": np.maximum(open_arr, close_arr) * 1.002,
            "Low": np.minimum(open_arr, close_arr) * 0.998,
            "Close": close_arr,
            "Volume": [1_000_000] * n,
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# gap_pct
# ---------------------------------------------------------------------------

class TestGapPct:
    def test_flat_open_equals_close(self):
        """When open = prior close, gap pct should be ~0."""
        df = _make_df([100, 100, 100], opens=[100, 100, 100])
        result = gap_pct(df)
        assert abs(result.iloc[-1]) < 1e-9

    def test_gap_up_1pct(self):
        """Open 1% above prior close → gap_pct ≈ 0.01."""
        closes = [100.0, 100.0]
        opens  = [100.0, 101.0]   # last open = prior_close(100) * 1.01 = exactly 1%
        df = _make_df(closes, opens)
        result = gap_pct(df)
        assert pytest.approx(result.iloc[-1], abs=1e-4) == 0.01

    def test_gap_down_1pct(self):
        """Open 1% below prior close → gap_pct ≈ -0.01."""
        closes = [100.0, 100.0]
        opens  = [100.0, 99.0]    # last open = prior_close(100) * 0.99 = exactly -1%
        df = _make_df(closes, opens)
        result = gap_pct(df)
        assert result.iloc[-1] < -0.009

    def test_first_row_is_nan(self):
        """First row must be NaN — no prior close exists."""
        df = _make_df([100, 102], opens=[100, 103])
        result = gap_pct(df)
        assert pd.isna(result.iloc[0])

    def test_returns_series(self):
        df = _make_df([100, 102, 104])
        assert isinstance(gap_pct(df), pd.Series)

    def test_large_dataset(self):
        """Works correctly on a 250-row dataset (no NaN on last rows)."""
        n = 250
        closes = 100 - np.linspace(0, 30, n)
        opens = closes.copy()
        opens[-1] = closes[-2] * 1.015    # 1.5% gap up on last bar
        df = _make_df(closes.tolist(), opens.tolist())
        result = gap_pct(df)
        assert not pd.isna(result.iloc[-1])
        assert pytest.approx(result.iloc[-1], abs=1e-4) == 0.015


# ---------------------------------------------------------------------------
# is_gap_up
# ---------------------------------------------------------------------------

class TestIsGapUp:
    def test_gap_up_detected(self):
        closes = [100.0, 100.0]
        opens  = [100.0, 101.0]   # 1% gap up
        df = _make_df(closes, opens)
        assert bool(is_gap_up(df, 0.005).iloc[-1]) is True

    def test_gap_up_below_threshold(self):
        closes = [100.0, 100.0]
        opens  = [100.0, 100.3]   # 0.3% — below 0.5% threshold
        df = _make_df(closes, opens)
        assert bool(is_gap_up(df, 0.005).iloc[-1]) is False

    def test_flat_open_not_gap_up(self):
        df = _make_df([100, 100], opens=[100, 100])
        assert bool(is_gap_up(df).iloc[-1]) is False

    def test_gap_down_not_gap_up(self):
        closes = [100.0, 100.0]
        opens  = [100.0, 99.0]   # gap down
        df = _make_df(closes, opens)
        assert bool(is_gap_up(df).iloc[-1]) is False

    def test_custom_threshold(self):
        """Exact threshold boundary: 2% gap with 2% threshold should be True."""
        closes = [100.0, 100.0]
        opens  = [100.0, 102.0]
        df = _make_df(closes, opens)
        assert bool(is_gap_up(df, 0.02).iloc[-1]) is True

    def test_returns_bool_series(self):
        df = _make_df([100, 101, 102], opens=[100, 101, 104])
        result = is_gap_up(df)
        assert result.dtype == bool


# ---------------------------------------------------------------------------
# is_gap_down
# ---------------------------------------------------------------------------

class TestIsGapDown:
    def test_gap_down_detected(self):
        closes = [100.0, 100.0]
        opens  = [100.0, 99.0]   # 1% gap down
        df = _make_df(closes, opens)
        assert bool(is_gap_down(df, 0.005).iloc[-1]) is True

    def test_gap_down_below_threshold(self):
        closes = [100.0, 100.0]
        opens  = [100.0, 99.8]   # 0.2% — below 0.5% threshold
        df = _make_df(closes, opens)
        assert bool(is_gap_down(df, 0.005).iloc[-1]) is False

    def test_gap_up_not_gap_down(self):
        closes = [100.0, 100.0]
        opens  = [100.0, 101.0]
        df = _make_df(closes, opens)
        assert bool(is_gap_down(df).iloc[-1]) is False


# ---------------------------------------------------------------------------
# gap_fill_level
# ---------------------------------------------------------------------------

class TestGapFillLevel:
    def test_fill_level_is_prior_close(self):
        closes = [95.0, 100.0, 102.0]
        df = _make_df(closes)
        result = gap_fill_level(df)
        assert result.iloc[-1] == pytest.approx(100.0)
        assert result.iloc[1] == pytest.approx(95.0)

    def test_first_row_is_nan(self):
        df = _make_df([100, 102])
        assert pd.isna(gap_fill_level(df).iloc[0])

    def test_stop_loss_equals_fill_level(self):
        """For a gap-up long trade, stop should be at prior close."""
        closes = [100.0, 100.0]
        opens  = [100.0, 102.0]   # gap up
        df = _make_df(closes, opens)
        stop = float(gap_fill_level(df).iloc[-1])
        assert stop == pytest.approx(100.0)   # prior close
