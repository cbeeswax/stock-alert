import pandas as pd

from src.analysis.rally_pattern_strategy import RallyPatternStrategy


def _strong_row(date: str, ticker: str, close: float = 100.0) -> dict:
    return {
        "ticker": ticker,
        "Date": pd.Timestamp(date),
        "close": close,
        "close_vs_sma_10": 0.01,
        "close_vs_sma_20": 0.02,
        "close_vs_sma_50": 0.03,
        "close_vs_ema_10": 0.01,
        "close_vs_ema_20": 0.02,
        "close_vs_ema_50": 0.03,
        "trend_stack_bullish": 1,
        "trend_stack_bearish": 0,
        "pct_from_20d_high": -0.005,
        "pct_from_20d_low": 0.10,
        "donchian_pos_20": 0.85,
        "bb_pct_b_20": 0.90,
        "rsi_14": 66.0,
        "rsi_21": 56.0,
        "smoothed_rsi_ema21_rsi10": 60.0,
        "macd_line": 1.50,
        "macd_signal": 0.50,
        "macd_hist": 1.00,
        "stoch_k_14": 85.0,
        "stoch_d_3": 65.0,
        "williams_r_14": -20.0,
        "cci_20": 55.0,
        "adx_14": 25.0,
        "plus_di_14": 30.0,
        "minus_di_14": 15.0,
        "pct_chg": 0.015,
        "close_pos": 0.80,
        "body": 1.50,
        "tr": 3.00,
        "atr_14": 3.00,
        "atr_pct_14": 0.03,
        "realized_vol_20": 0.20,
        "volume_ratio_20": 1.20,
        "volume_ratio_50": 1.05,
        "volume_zscore_20": 1.20,
        "cmf_20": 0.06,
        "mfi_14": 55.0,
        "rs_spy_20": 0.05,
        "rs_spy_50": 0.02,
        "rs_qqq_20": 0.05,
        "rs_qqq_50": 0.02,
    }


def _moderate_entry_row(date: str, ticker: str, close: float = 100.0) -> dict:
    row = _strong_row(date, ticker, close)
    row.update(
        {
            "close_vs_sma_50": -0.01,
            "close_vs_ema_50": -0.01,
            "pct_from_20d_high": -0.05,
            "donchian_pos_20": 0.56,
            "bb_pct_b_20": 0.56,
            "rsi_14": 58.0,
            "rsi_21": 55.0,
            "smoothed_rsi_ema21_rsi10": 55.0,
            "stoch_k_14": 70.0,
            "stoch_d_3": 50.0,
            "williams_r_14": -30.0,
            "cci_20": 40.0,
            "adx_14": 19.0,
            "volume_ratio_20": 1.16,
            "volume_zscore_20": 0.10,
            "cmf_20": 0.01,
            "mfi_14": 49.0,
            "rs_spy_20": 0.01,
            "rs_spy_50": 0.0,
            "rs_qqq_20": 0.01,
            "rs_qqq_50": 0.0,
            "atr_pct_14": 0.045,
        }
    )
    return row


def _exit_row(date: str, ticker: str, close: float = 95.0) -> dict:
    row = _strong_row(date, ticker, close)
    row.update(
        {
            "close_vs_sma_10": -0.02,
            "close_vs_sma_20": -0.03,
            "close_vs_sma_50": -0.05,
            "close_vs_ema_10": -0.02,
            "close_vs_ema_20": -0.03,
            "close_vs_ema_50": -0.05,
            "trend_stack_bullish": 0,
            "trend_stack_bearish": 1,
            "pct_from_20d_high": -0.20,
            "pct_from_20d_low": -0.05,
            "donchian_pos_20": 0.20,
            "bb_pct_b_20": 0.20,
            "rsi_14": 40.0,
            "rsi_21": 45.0,
            "smoothed_rsi_ema21_rsi10": 40.0,
            "macd_line": -1.00,
            "macd_signal": -0.50,
            "macd_hist": -0.50,
            "stoch_k_14": 30.0,
            "stoch_d_3": 35.0,
            "williams_r_14": -80.0,
            "cci_20": -50.0,
            "adx_14": 18.0,
            "plus_di_14": 12.0,
            "minus_di_14": 28.0,
            "pct_chg": -0.03,
            "close_pos": 0.20,
            "body": 0.50,
            "tr": 2.50,
            "atr_14": 2.50,
            "atr_pct_14": 0.025,
            "realized_vol_20": 0.15,
            "volume_ratio_20": 0.60,
            "volume_ratio_50": 0.80,
            "volume_zscore_20": -1.00,
            "cmf_20": -0.10,
            "mfi_14": 35.0,
            "rs_spy_20": -0.05,
            "rs_spy_50": -0.02,
            "rs_qqq_20": -0.05,
            "rs_qqq_50": -0.02,
        }
    )
    return row


def test_score_row_matches_bucket_spec():
    strategy = RallyPatternStrategy()

    scored = strategy.score_row(pd.Series(_strong_row("2024-01-02", "AAA")))

    assert scored["trend_points"] == 20
    assert scored["breakout_points"] == 18
    assert scored["momentum_points"] == 18
    assert scored["flow_points"] == 16
    assert scored["rs_points"] == 16
    assert scored["volatility_points"] == 10
    assert scored["penalty"] == 0
    assert scored["score"] == 98
    assert scored["label"] == "A"
    assert scored["pattern_stage"] == "breakout_or_power_trend"


def test_score_dataframe_uses_neutral_defaults_for_missing_fields():
    strategy = RallyPatternStrategy()
    df = pd.DataFrame([{"ticker": "AAA", "Date": "2024-01-02"}])

    scored = strategy.score_dataframe(df)

    assert scored.loc[0, "pct_from_20d_high"] == -1.0
    assert scored.loc[0, "williams_r_14"] == -100.0
    assert scored.loc[0, "score"] == 0.0
    assert scored.loc[0, "label"] == "D"
    assert scored.loc[0, "pattern_stage"] == "non_signal"


def test_generate_entries_and_exits_follow_exact_rules():
    strategy = RallyPatternStrategy()
    df = pd.DataFrame(
        [
            _strong_row("2024-01-02", "AAA"),
            _exit_row("2024-01-02", "BBB"),
        ]
    )

    scored = strategy.score_dataframe(df)
    entries = strategy.generate_entries(scored)
    exits = strategy.generate_exits(scored)

    assert entries.tolist() == [True, False]
    assert exits.tolist() == [False, True]


def test_rank_candidates_uses_score_then_rs_then_volume():
    strategy = RallyPatternStrategy()
    leader = _strong_row("2024-01-02", "AAA")
    tie_breaker = _strong_row("2024-01-02", "BBB")
    third = _strong_row("2024-01-02", "CCC")

    leader["rs_spy_20"] = 0.08
    tie_breaker["rs_spy_20"] = 0.05
    third["rs_spy_20"] = 0.05
    third["volume_ratio_20"] = 1.30

    ranked = strategy.rank_candidates(pd.DataFrame([tie_breaker, third, leader]))

    assert ranked["ticker"].tolist() == ["AAA", "CCC", "BBB"]
    assert ranked["candidate_rank"].tolist() == [1, 2, 3]


def test_backtest_enforces_cooldown_but_allows_score_75_override():
    strategy = RallyPatternStrategy()
    dates = pd.date_range("2024-01-02", periods=6, freq="B")

    rows = [
        _strong_row(str(dates[0].date()), "AAA", 100.0),
        _exit_row(str(dates[1].date()), "AAA", 95.0),
        _moderate_entry_row(str(dates[2].date()), "AAA", 96.0),
        _moderate_entry_row(str(dates[3].date()), "AAA", 97.0),
        _strong_row(str(dates[4].date()), "AAA", 105.0),
        _exit_row(str(dates[5].date()), "AAA", 102.0),
    ]

    results = strategy.backtest(pd.DataFrame(rows), max_positions=1, initial_capital=100_000.0)
    trades = results["trades"]
    equity_curve = results["equity_curve"]
    daily_holdings = results["daily_holdings"]

    assert len(trades) == 2
    assert trades["entry_date"].dt.normalize().tolist() == [dates[0], dates[4]]
    assert trades["exit_date"].dt.normalize().tolist() == [dates[1], dates[5]]
    assert not daily_holdings.empty
    assert not equity_curve.empty
    assert equity_curve["num_positions"].max() == 1
