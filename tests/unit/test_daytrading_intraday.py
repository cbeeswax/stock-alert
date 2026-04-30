from zoneinfo import ZoneInfo

import pandas as pd

from src.daytrading.intraday import add_session_vwap, get_latest_regular_session


def test_get_latest_regular_session_filters_last_trading_day():
    index = pd.DatetimeIndex(
        [
            "2026-04-27 13:30:00+00:00",
            "2026-04-27 13:35:00+00:00",
            "2026-04-28 08:00:00+00:00",
            "2026-04-28 13:30:00+00:00",
            "2026-04-28 13:35:00+00:00",
        ]
    )
    df = pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104],
            "High": [101, 102, 103, 104, 105],
            "Low": [99, 100, 101, 102, 103],
            "Close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "Volume": [1000, 1100, 900, 1200, 1300],
        },
        index=index,
    )

    session = get_latest_regular_session(df)

    assert len(session) == 2
    assert session.index.tz == ZoneInfo("America/New_York")
    assert all(timestamp.date().isoformat() == "2026-04-28" for timestamp in session.index)


def test_add_session_vwap_adds_vwap_column():
    index = pd.DatetimeIndex(
        [
            "2026-04-28 09:30:00-04:00",
            "2026-04-28 09:35:00-04:00",
        ]
    )
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1000, 1000],
        },
        index=index,
    )

    result = add_session_vwap(df)

    assert "VWAP" in result.columns
    assert result["VWAP"].iloc[-1] > 0
