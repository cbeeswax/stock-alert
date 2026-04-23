import pandas as pd

from src.analysis.zone_structure import (
    add_zone_columns,
    build_zone_snapshot,
    long_zone_broken,
    short_zone_broken,
)


def test_add_zone_columns_and_snapshot_capture_shared_structure_levels():
    df = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=5, freq="B"),
            "ticker": ["AAA"] * 5,
            "high": [11.0, 12.0, 13.0, 14.0, 15.0],
            "low": [9.0, 10.0, 11.0, 12.0, 13.0],
            "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        }
    )

    zoned = add_zone_columns(
        df,
        high_col="high",
        low_col="low",
        close_col="close",
        group_col="ticker",
        windows=(3, 4),
    )
    snapshot = build_zone_snapshot(
        df.rename(columns={"Date": "date", "close": "Close", "high": "High", "low": "Low"}),
        close_col="Close",
        high_col="High",
        low_col="Low",
        short_window=3,
        long_window=4,
    )

    assert float(zoned.iloc[-1]["prior_3bar_high"]) == 14.0
    assert float(zoned.iloc[-1]["prior_3bar_low"]) == 10.0
    assert bool(zoned.iloc[-1]["in_3bar_seller_zone"])
    assert snapshot is not None
    assert snapshot.prior_short_high == 14.0
    assert snapshot.prior_short_low == 10.0
    assert snapshot.prior_long_high == 14.0
    assert snapshot.prior_long_low == 9.0
    assert snapshot.in_short_seller_zone


def test_zone_break_helpers_respect_tolerance():
    assert long_zone_broken(98.0, 100.0, 0.01)
    assert not long_zone_broken(99.5, 100.0, 0.01)
    assert short_zone_broken(102.5, 100.0, 0.01)
    assert not short_zone_broken(100.5, 100.0, 0.01)
