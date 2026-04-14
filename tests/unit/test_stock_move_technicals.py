import pandas as pd

from src.analysis.stock_move_technicals import (
    analyze_single_event,
    build_technical_frame,
    normalize_event_file,
    save_analysis_results,
)


def _sample_history() -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=320, freq="B")
    close = pd.Series(range(len(dates)), index=dates, dtype=float) * 0.4 + 100.0
    close += pd.Series(
        [0.8 if i % 7 == 0 else -0.3 if i % 11 == 0 else 0.0 for i in range(len(dates))],
        index=dates,
        dtype=float,
    )

    frame = pd.DataFrame(index=dates)
    frame["Open"] = close - 0.5
    frame["High"] = close + 1.0
    frame["Low"] = close - 1.2
    frame["Close"] = close
    frame["Volume"] = 1_000_000 + (pd.Series(range(len(dates)), index=dates) * 2_500)
    return frame


def test_normalize_event_file_accepts_time_range_aliases():
    raw = pd.DataFrame(
        {
            "Stock Name": ["AAPL"],
            "Time Range": ["2024-01-08 to 2024-01-31"],
            "Rally or Down": ["Run Up"],
        }
    )

    normalized = normalize_event_file(raw)

    assert list(normalized.columns) == [
        "event_id",
        "ticker",
        "start_date",
        "end_date",
        "move_type",
        "source_row",
    ]
    assert normalized.loc[0, "ticker"] == "AAPL"
    assert normalized.loc[0, "move_type"] == "rally"
    assert str(normalized.loc[0, "start_date"].date()) == "2024-01-08"
    assert str(normalized.loc[0, "end_date"].date()) == "2024-01-31"


def test_build_technical_frame_adds_broad_indicator_set():
    technicals = build_technical_frame(_sample_history())

    expected_columns = {
        "rsi_14",
        "macd_hist",
        "stoch_k_14",
        "williams_r_14",
        "cci_20",
        "adx_14",
        "atr_pct_14",
        "bb_pct_b_20",
        "mfi_14",
        "obv",
        "cmf_20",
        "donchian_pos_20",
        "gap_pct",
        "trend_stack_bullish",
    }
    assert expected_columns.issubset(set(technicals.columns))


def test_analyze_events_returns_summary_and_daily_outputs(tmp_path):
    history = _sample_history()
    event_date_start = pd.Timestamp("2024-01-08")
    event_date_end = pd.Timestamp("2024-02-09")

    technical_frame = build_technical_frame(history)
    event = pd.DataFrame(
        [
            {
                "event_id": "AAPL_move_1",
                "ticker": "AAPL",
                "start_date": event_date_start,
                "end_date": event_date_end,
                "move_type": "rally",
                "source_row": 1,
            }
        ]
    )

    summary_df, daily_df = analyze_events_from_cache(event, {"AAPL": technical_frame})

    assert summary_df.loc[0, "status"] == "ok"
    assert summary_df.loc[0, "event_id"] == "AAPL_move_1"
    assert "start_rsi_14" in summary_df.columns
    assert "end_macd_hist" in summary_df.columns
    assert "delta_cmf_20" in summary_df.columns
    assert not daily_df.empty
    assert {"event_id", "ticker", "move_type", "date", "event_day", "event_return_pct"}.issubset(
        set(daily_df.columns)
    )

    summary_path, daily_path = save_analysis_results(
        summary_df,
        daily_df,
        output_dir=tmp_path,
        base_name="sample_moves",
    )

    assert summary_path.exists()
    assert daily_path.exists()


def analyze_events_from_cache(
    events_df: pd.DataFrame,
    cache: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    daily_frames = []
    for event in events_df.to_dict("records"):
        summary, daily = analyze_single_event(cache[event["ticker"]], event)
        summary_rows.append(summary)
        daily_frames.append(daily)
    return pd.DataFrame(summary_rows), pd.concat(daily_frames, ignore_index=True)
