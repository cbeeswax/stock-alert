"""
Standalone daily ranking strategy for rally-pattern detection.

The strategy expects one row per ticker-date with precomputed technical columns.
It scores each row using the exact six-bucket model from the spec, derives labels
and pattern stages, emits entry/exit signals, ranks candidates cross-sectionally,
and runs a no-lookahead daily portfolio backtest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class _BacktestPosition:
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: float
    entry_score: float
    best_score: float
    highest_close: float
    has_new_high: bool
    score_improved: bool
    days_held: int


class RallyPatternStrategy:
    """Cross-sectional rally-ranking strategy operating on precomputed or raw features."""

    COLUMN_DEFAULTS: dict[str, float] = {
        "close": 0.0,
        "close_vs_sma_10": 0.0,
        "close_vs_sma_20": 0.0,
        "close_vs_sma_50": 0.0,
        "close_vs_ema_10": 0.0,
        "close_vs_ema_20": 0.0,
        "close_vs_ema_50": 0.0,
        "trend_stack_bullish": 0.0,
        "trend_stack_bearish": 0.0,
        "pct_from_20d_high": -1.0,
        "pct_from_20d_low": 0.0,
        "donchian_pos_20": 0.0,
        "bb_pct_b_20": 0.0,
        "rsi_14": 0.0,
        "rsi_21": 0.0,
        "smoothed_rsi_ema21_rsi10": 0.0,
        "macd_line": 0.0,
        "macd_signal": 0.0,
        "macd_hist": 0.0,
        "stoch_k_14": 0.0,
        "stoch_d_3": 0.0,
        "williams_r_14": -100.0,
        "cci_20": 0.0,
        "adx_14": 0.0,
        "plus_di_14": 0.0,
        "minus_di_14": 0.0,
        "pct_chg": 0.0,
        "close_pos": 0.0,
        "body": 0.0,
        "tr": 0.0,
        "atr_14": 0.0,
        "atr_pct_14": 0.0,
        "realized_vol_20": 0.0,
        "volume_ratio_20": 0.0,
        "volume_ratio_50": 0.0,
        "volume_zscore_20": 0.0,
        "cmf_20": 0.0,
        "mfi_14": 0.0,
        "rs_spy_20": 0.0,
        "rs_spy_50": 0.0,
        "rs_qqq_20": 0.0,
        "rs_qqq_50": 0.0,
    }
    FEATURE_COLUMNS: tuple[str, ...] = tuple(COLUMN_DEFAULTS.keys())
    RAW_PRICE_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")

    def __init__(
        self,
        *,
        strict_entry: bool = False,
        use_atr_stop: bool = False,
        use_time_stop: bool = False,
        reentry_cooldown_days: int = 3,
        time_stop_days: int = 15,
        setup_score_threshold: float = 70.0,
        trigger_window_days: int = 5,
        trigger_volume_ratio: float = 1.15,
    ) -> None:
        self.strict_entry = strict_entry
        self.use_atr_stop = use_atr_stop
        self.use_time_stop = use_time_stop
        self.reentry_cooldown_days = reentry_cooldown_days
        self.time_stop_days = time_stop_days
        self.setup_score_threshold = setup_score_threshold
        self.trigger_window_days = trigger_window_days
        self.trigger_volume_ratio = trigger_volume_ratio

    def build_feature_dataframe(
        self,
        df: pd.DataFrame,
        *,
        spy_df: pd.DataFrame | None = None,
        qqq_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """
        Build the full feature set from raw OHLCV input.

        Input can be a multi-ticker frame. If `spy_df` / `qqq_df` are not passed,
        SPY/QQQ rows will be taken from the same input when available.
        """
        working = self._standardize_dataframe(df)
        self._require_columns(working, ("Date", "ticker", *self.RAW_PRICE_COLUMNS))
        working = self._coerce_numeric_columns(working, self.RAW_PRICE_COLUMNS)

        spy_series = self._resolve_benchmark_close(working, "SPY", spy_df)
        qqq_series = self._resolve_benchmark_close(working, "QQQ", qqq_df)

        feature_frames: list[pd.DataFrame] = []
        for _, ticker_df in working.groupby("ticker", sort=False):
            feature_frames.append(
                self._build_single_ticker_features(
                    ticker_df.copy(),
                    spy_close=spy_series,
                    qqq_close=qqq_series,
                )
            )

        if not feature_frames:
            return working.copy()
        return pd.concat(feature_frames, ignore_index=True)

    def score_row(self, row: pd.Series) -> dict[str, Any]:
        """Score a single ticker-date row using the exact bucket rules."""
        values = self._coerce_row(row)

        trend_points = self._clamp(
            (2 if values["close_vs_sma_10"] > 0 else 0)
            + (4 if values["close_vs_sma_20"] > 0 else 0)
            + (2 if values["close_vs_sma_50"] > 0 else 0)
            + (2 if values["close_vs_ema_10"] > 0 else 0)
            + (4 if values["close_vs_ema_20"] > 0 else 0)
            + (2 if values["close_vs_ema_50"] > 0 else 0)
            + (4 if values["trend_stack_bullish"] == 1 else 0)
            - (6 if values["trend_stack_bearish"] == 1 else 0),
            0,
            22,
        )

        breakout_points = self._clamp(
            (5 if -0.12 <= values["pct_from_20d_high"] <= -0.01 else 0)
            + (6 if values["pct_from_20d_high"] > -0.01 else 0)
            + (2 if values["pct_from_20d_low"] > 0.05 else 0)
            + (4 if values["donchian_pos_20"] >= 0.55 else 0)
            + (2 if values["donchian_pos_20"] >= 0.80 else 0)
            + (3 if values["bb_pct_b_20"] >= 0.55 else 0)
            + (2 if values["bb_pct_b_20"] >= 0.85 else 0),
            0,
            18,
        )

        momentum_points = self._clamp(
            (3 if values["rsi_14"] >= 52 else 0)
            + (3 if values["rsi_14"] >= 58 else 0)
            + (2 if values["rsi_14"] >= 65 else 0)
            + (1 if values["rsi_21"] >= 55 else 0)
            + (1 if values["smoothed_rsi_ema21_rsi10"] >= 55 else 0)
            + (3 if values["macd_hist"] > 0 else 0)
            + (2 if values["macd_line"] > values["macd_signal"] else 0)
            + (1 if values["stoch_k_14"] >= 65 else 0)
            + (1 if values["stoch_k_14"] >= 80 else 0)
            + (1 if values["stoch_d_3"] >= 60 else 0)
            + (1 if values["williams_r_14"] >= -25 else 0)
            + (1 if values["cci_20"] >= 50 else 0)
            + (1 if values["plus_di_14"] > values["minus_di_14"] else 0)
            + (1 if values["adx_14"] >= 20 else 0),
            0,
            18,
        )

        flow_points = self._clamp(
            (2 if values["volume_ratio_20"] >= 0.95 else 0)
            + (3 if values["volume_ratio_20"] >= 1.15 else 0)
            + (1 if values["volume_ratio_50"] >= 1.00 else 0)
            + (1 if values["volume_zscore_20"] >= 0 else 0)
            + (1 if values["volume_zscore_20"] >= 1 else 0)
            + (3 if values["cmf_20"] >= 0 else 0)
            + (2 if values["cmf_20"] >= 0.05 else 0)
            + (1 if values["mfi_14"] >= 50 else 0)
            + (1 if values["pct_chg"] > 0 else 0)
            + (1 if values["close_pos"] >= 0.60 else 0),
            0,
            16,
        )

        rs_points = self._clamp(
            (4 if values["rs_spy_20"] > 0 else 0)
            + (2 if values["rs_spy_50"] > 0 else 0)
            + (4 if values["rs_qqq_20"] > 0 else 0)
            + (2 if values["rs_qqq_50"] > 0 else 0)
            + (2 if values["rs_spy_20"] > 0.03 else 0)
            + (2 if values["rs_qqq_20"] > 0.03 else 0),
            0,
            16,
        )

        body_over_tr = (values["body"] / values["tr"]) if values["tr"] > 0 else 0.0
        volatility_points = self._clamp(
            (4 if 0.012 <= values["atr_pct_14"] <= 0.040 else 0)
            + (2 if 0.040 < values["atr_pct_14"] <= 0.070 else 0)
            + (3 if values["tr"] > 0 and body_over_tr >= 0.45 else 0)
            + (2 if values["close_pos"] >= 0.70 else 0)
            + (1 if values["realized_vol_20"] > 0 else 0),
            0,
            10,
        )

        penalty = (
            (8 if values["trend_stack_bearish"] == 1 else 0)
            + (5 if values["minus_di_14"] > values["plus_di_14"] and values["rsi_14"] < 50 else 0)
            + (
                8
                if values["pct_from_20d_high"] < -0.15
                and values["rs_spy_20"] < 0
                and values["rs_qqq_20"] < 0
                else 0
            )
            + (4 if values["volume_ratio_20"] < 0.75 and values["cmf_20"] < 0 else 0)
            + (
                6
                if values["macd_line"] < values["macd_signal"]
                and values["macd_hist"] < 0
                and values["rsi_14"] < 50
                else 0
            )
        )

        score = self._clamp(
            trend_points
            + breakout_points
            + momentum_points
            + flow_points
            + rs_points
            + volatility_points
            - penalty,
            0,
            100,
        )

        if score >= 75:
            label = "A"
        elif score >= 60:
            label = "B"
        elif score >= 45:
            label = "C"
        else:
            label = "D"

        if score >= 60 and values["pct_chg"] <= 0.01:
            pattern_stage = "launchpad_or_early_trigger"
        elif score >= 60 and values["pct_chg"] > 0.01:
            pattern_stage = "breakout_or_power_trend"
        else:
            pattern_stage = "non_signal"

        return {
            "trend_points": trend_points,
            "breakout_points": breakout_points,
            "momentum_points": momentum_points,
            "flow_points": flow_points,
            "rs_points": rs_points,
            "volatility_points": volatility_points,
            "penalty": penalty,
            "score": score,
            "label": label,
            "pattern_stage": pattern_stage,
        }

    def score_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a scored DataFrame with debug bucket columns."""
        working = self._standardize_dataframe(df)
        if not self._has_feature_columns(working):
            if self._has_raw_price_columns(working):
                working = self.build_feature_dataframe(working)
            else:
                working = self._fill_feature_defaults(working)
        else:
            working = self._fill_feature_defaults(working)
        scored = working.apply(self.score_row, axis=1, result_type="expand")
        return pd.concat([working, scored], axis=1)

    def generate_entries(self, df: pd.DataFrame) -> pd.Series:
        """Return stateful setup-trigger entry signals."""
        scored = self._augment_entry_support_columns(self._ensure_scored(df))
        return scored["entry_signal"].rename("entry_signal")

    def generate_exits(self, df: pd.DataFrame) -> pd.Series:
        """Return confirmed trend-failure exits, excluding entry-aware trailing stops."""
        scored = self._augment_exit_support_columns(self._ensure_scored(df))
        exit_signal = (
            scored["soft_score_fail_2d"]
            | scored["close_below_ema20_2d"]
            | scored["close_below_sma50"]
            | scored["relative_weak_2d"]
        )
        return exit_signal.rename("exit_signal")

    def rank_candidates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rank baseline entry candidates for each date."""
        scored = self._augment_entry_support_columns(self._ensure_scored(df).copy())
        candidates = scored[scored["entry_signal"]].copy()
        if candidates.empty:
            return candidates

        candidates = candidates.sort_values(
            ["Date", "score", "rs_spy_20", "volume_ratio_20", "ticker"],
            ascending=[True, False, False, False, True],
        ).reset_index(drop=True)
        candidates["candidate_rank"] = candidates.groupby("Date").cumcount() + 1
        return candidates

    def backtest(
        self,
        df: pd.DataFrame,
        max_positions: int = 5,
        initial_capital: float = 100_000.0,
        start_date: str | pd.Timestamp | None = None,
        end_date: str | pd.Timestamp | None = None,
        trade_start_date: str | pd.Timestamp | None = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Run a no-lookahead daily backtest.

        Signals are evaluated at each row's close. Exits and new entries are both
        executed at that close, and new positions participate from the next bar.
        """
        scored = self._ensure_scored(df).copy()
        if start_date is not None:
            scored = scored[scored["Date"] >= pd.Timestamp(start_date)].copy()
        if end_date is not None:
            scored = scored[scored["Date"] <= pd.Timestamp(end_date)].copy()
        scored = self._augment_entry_support_columns(scored)
        scored = self._augment_exit_support_columns(scored)
        scored["exit_signal"] = self.generate_exits(scored)
        scored = scored.sort_values(["Date", "ticker"]).reset_index(drop=True)
        trade_start_ts = pd.Timestamp(trade_start_date) if trade_start_date is not None else None
        ranked_all = self.rank_candidates(scored)

        positions: dict[str, _BacktestPosition] = {}
        last_exit_date_index: dict[str, int] = {}
        cash = float(initial_capital)
        trades: list[dict[str, Any]] = []
        holdings_rows: list[dict[str, Any]] = []
        equity_rows: list[dict[str, Any]] = []

        grouped = list(scored.groupby("Date", sort=True))
        for date_index, (current_date, day_df) in enumerate(grouped):
            day_df = day_df.sort_values(["score", "rs_spy_20", "volume_ratio_20", "ticker"], ascending=[False, False, False, True])
            day_rows = {row["ticker"]: row for _, row in day_df.iterrows()}

            for ticker, position in list(positions.items()):
                row = day_rows.get(ticker)
                if row is None:
                    continue

                updated_position = _BacktestPosition(
                    ticker=position.ticker,
                    entry_date=position.entry_date,
                    entry_price=position.entry_price,
                    shares=position.shares,
                    entry_score=position.entry_score,
                    best_score=max(position.best_score, float(row["score"])),
                    highest_close=max(position.highest_close, float(row["close"])),
                    has_new_high=position.has_new_high or float(row["pct_from_20d_high"]) >= 0,
                    score_improved=position.score_improved or float(row["score"]) > position.entry_score,
                    days_held=position.days_held + 1,
                )
                positions[ticker] = updated_position

                exit_reason = self._exit_reason(row, updated_position)
                if exit_reason is None:
                    continue

                exit_price = float(row["close"])
                cash += updated_position.shares * exit_price
                trades.append(
                    {
                        "ticker": ticker,
                        "entry_date": updated_position.entry_date,
                        "exit_date": current_date,
                        "entry_price": updated_position.entry_price,
                        "exit_price": exit_price,
                        "shares": updated_position.shares,
                        "entry_score": updated_position.entry_score,
                        "exit_score": float(row["score"]),
                        "holding_days": updated_position.days_held,
                        "return_pct": (exit_price / updated_position.entry_price) - 1.0
                        if updated_position.entry_price > 0
                        else 0.0,
                        "pnl": updated_position.shares * (exit_price - updated_position.entry_price),
                        "exit_reason": exit_reason,
                    }
                )
                last_exit_date_index[ticker] = date_index
                del positions[ticker]

            ranked_candidates = ranked_all[ranked_all["Date"] == current_date].copy()
            available_slots = max_positions - len(positions)
            if trade_start_ts is not None and current_date < trade_start_ts:
                ranked_candidates = ranked_candidates.iloc[0:0]

            if available_slots > 0 and not ranked_candidates.empty:
                total_equity = cash + sum(
                    positions[ticker].shares * float(day_rows[ticker]["close"])
                    for ticker in positions
                    if ticker in day_rows
                )
                target_position_value = total_equity / max_positions if max_positions > 0 else 0.0

                for _, row in ranked_candidates.iterrows():
                    ticker = row["ticker"]
                    if ticker in positions:
                        continue
                    if available_slots <= 0:
                        break

                    last_exit_idx = last_exit_date_index.get(ticker)
                    if (
                        last_exit_idx is not None
                        and (date_index - last_exit_idx) <= self.reentry_cooldown_days
                        and float(row["score"]) < 75
                    ):
                        continue

                    price = float(row["close"])
                    if price <= 0:
                        continue

                    allocation = min(cash, target_position_value)
                    if allocation <= 0:
                        break

                    shares = allocation / price
                    if shares <= 0:
                        continue

                    cash -= allocation
                    positions[ticker] = _BacktestPosition(
                        ticker=ticker,
                        entry_date=current_date,
                        entry_price=price,
                        shares=shares,
                        entry_score=float(row["score"]),
                        best_score=float(row["score"]),
                        highest_close=price,
                        has_new_high=float(row["pct_from_20d_high"]) >= 0,
                        score_improved=False,
                        days_held=0,
                    )
                    available_slots -= 1

            invested_value = 0.0
            holding_snapshots: list[dict[str, Any]] = []
            for ticker, position in positions.items():
                row = day_rows.get(ticker)
                if row is None:
                    continue
                market_value = position.shares * float(row["close"])
                invested_value += market_value
                holding_snapshots.append(
                    {
                        "Date": current_date,
                        "ticker": ticker,
                        "shares": position.shares,
                        "close": float(row["close"]),
                        "market_value": market_value,
                        "entry_date": position.entry_date,
                        "entry_price": position.entry_price,
                        "entry_score": position.entry_score,
                        "current_score": float(row["score"]),
                        "days_held": position.days_held,
                    }
                )

            total_equity = cash + invested_value
            for snapshot in holding_snapshots:
                snapshot["weight"] = (
                    snapshot["market_value"] / total_equity if total_equity > 0 else 0.0
                )
                holdings_rows.append(snapshot)
            equity_rows.append(
                {
                    "Date": current_date,
                    "cash": cash,
                    "invested_value": invested_value,
                    "total_equity": total_equity,
                    "num_positions": len(positions),
                }
            )

        return {
            "trades": pd.DataFrame(trades),
            "daily_holdings": pd.DataFrame(holdings_rows),
            "equity_curve": pd.DataFrame(equity_rows),
            "scored_data": scored,
        }

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        return self._fill_feature_defaults(self._standardize_dataframe(df))

    def _ensure_scored(self, df: pd.DataFrame) -> pd.DataFrame:
        if {"score", "trend_points", "penalty", "pattern_stage", "label"}.issubset(df.columns):
            return self._prepare_dataframe(df)
        return self.score_dataframe(df)

    def _augment_exit_support_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        working = self._prepare_dataframe(df).copy()
        low_source = "low" if "low" in working.columns else "close"

        working["roll_low_10"] = (
            working.groupby("ticker", sort=False)[low_source]
            .transform(lambda series: series.rolling(10, min_periods=1).min())
        )
        working["soft_score_fail"] = working["score"] < 35
        working["close_below_ema20"] = working["close_vs_ema_20"] < 0
        working["close_below_sma50"] = working["close_vs_sma_50"] < 0
        working["relative_weak"] = (working["rs_spy_20"] < 0) & (working["rs_qqq_20"] < 0)

        for source, target in (
            ("soft_score_fail", "soft_score_fail_2d"),
            ("close_below_ema20", "close_below_ema20_2d"),
            ("relative_weak", "relative_weak_2d"),
        ):
            working[target] = (
                working.groupby("ticker", sort=False)[source]
                .transform(lambda series: series.astype(int).rolling(2, min_periods=2).sum() >= 2)
            )

        return working

    def _augment_entry_support_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        working = self._prepare_dataframe(df).copy()
        base_setup_signal = self._base_setup_signal(working)

        working["setup_signal"] = False
        working["setup_active"] = False
        working["setup_age"] = 0
        working["setup_high"] = np.nan
        working["entry_signal"] = False
        working["setup_cancelled"] = False
        working["setup_expired"] = False

        for _, index_group in working.groupby("ticker", sort=False).groups.items():
            active = False
            setup_age = 0
            setup_high = np.nan

            for idx in index_group:
                row = working.loc[idx]
                entry_triggered = False
                cancelled = False
                expired = False

                if active:
                    setup_age += 1
                    if float(row["close_vs_ema_20"]) < 0:
                        active = False
                        cancelled = True
                    elif setup_age > self.trigger_window_days:
                        active = False
                        expired = True
                    elif (
                        setup_age >= 1
                        and float(row["close"]) > float(setup_high)
                        and float(row["volume_ratio_20"]) >= self.trigger_volume_ratio
                        and float(row["close_vs_ema_20"]) >= 0
                    ):
                        working.at[idx, "entry_signal"] = True
                        entry_triggered = True
                        active = False

                working.at[idx, "setup_cancelled"] = cancelled
                working.at[idx, "setup_expired"] = expired

                if base_setup_signal.loc[idx] and not entry_triggered:
                    active = True
                    setup_age = 0
                    setup_high = (
                        float(row["high"])
                        if "high" in working.columns and pd.notna(row.get("high"))
                        else float(row["close"])
                    )
                    working.at[idx, "setup_signal"] = True

                if active:
                    working.at[idx, "setup_active"] = True
                    working.at[idx, "setup_age"] = setup_age
                    working.at[idx, "setup_high"] = setup_high
                else:
                    working.at[idx, "setup_age"] = 0
                    if not pd.isna(working.at[idx, "setup_high"]):
                        working.at[idx, "setup_high"] = np.nan

        return working

    def _base_setup_signal(self, scored: pd.DataFrame) -> pd.Series:
        setup_signal = (
            (scored["score"] >= self.setup_score_threshold)
            & (scored["trend_stack_bullish"] == 1)
            & ((scored["rs_spy_20"] > 0) | (scored["rs_qqq_20"] > 0))
        )

        if self.strict_entry:
            setup_signal &= (
                (scored["rsi_14"] >= 58)
                & (scored["donchian_pos_20"] >= 0.80)
                & (scored["close_vs_ema_20"] > 0)
                & (scored["macd_hist"] > 0)
            )

        return setup_signal

    def _standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df.copy()

        working = df.copy()
        rename_map = {}
        for column in working.columns:
            if column == "Date":
                rename_map[column] = "Date"
            else:
                rename_map[column] = self._normalize_name(column)
        working = working.rename(columns=rename_map)

        if "date" in working.columns and "Date" not in working.columns:
            working = working.rename(columns={"date": "Date"})
        if "symbol" in working.columns and "ticker" not in working.columns:
            working = working.rename(columns={"symbol": "ticker"})

        if "Date" not in working.columns:
            raise ValueError("Input DataFrame must include a Date column.")
        if "ticker" not in working.columns:
            raise ValueError("Input DataFrame must include a ticker column.")

        working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
        working = working[working["Date"].notna()].copy()
        working["ticker"] = working["ticker"].astype(str).str.upper()
        return working.sort_values(["ticker", "Date"]).reset_index(drop=True)

    def _fill_feature_defaults(self, df: pd.DataFrame) -> pd.DataFrame:
        working = df.copy()
        for column, default_value in self.COLUMN_DEFAULTS.items():
            if column not in working.columns:
                working[column] = default_value
            working[column] = pd.to_numeric(working[column], errors="coerce").fillna(default_value)
        return working.sort_values(["ticker", "Date"]).reset_index(drop=True)

    def _has_feature_columns(self, df: pd.DataFrame) -> bool:
        return all(column in df.columns for column in self.FEATURE_COLUMNS)

    def _has_raw_price_columns(self, df: pd.DataFrame) -> bool:
        return all(column in df.columns for column in self.RAW_PRICE_COLUMNS)

    def _require_columns(self, df: pd.DataFrame, columns: tuple[str, ...]) -> None:
        missing = [column for column in columns if column not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    def _coerce_numeric_columns(self, df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
        working = df.copy()
        for column in columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")
        return working

    def _resolve_benchmark_close(
        self,
        working: pd.DataFrame,
        benchmark_ticker: str,
        benchmark_df: pd.DataFrame | None,
    ) -> pd.Series | None:
        if benchmark_df is not None:
            benchmark = self._standardize_dataframe(benchmark_df)
            self._require_columns(benchmark, ("Date", "ticker", "close"))
            benchmark = self._coerce_numeric_columns(benchmark, ("close",))
            benchmark = benchmark[benchmark["ticker"] == benchmark_ticker]
            if benchmark.empty:
                return None
            return benchmark.set_index("Date")["close"].sort_index()

        embedded = working[working["ticker"] == benchmark_ticker]
        if embedded.empty or "close" not in embedded.columns:
            return None
        embedded = self._coerce_numeric_columns(embedded, ("close",))
        return embedded.set_index("Date")["close"].sort_index()

    def _build_single_ticker_features(
        self,
        ticker_df: pd.DataFrame,
        *,
        spy_close: pd.Series | None,
        qqq_close: pd.Series | None,
    ) -> pd.DataFrame:
        ticker_df = ticker_df.sort_values("Date").reset_index(drop=True)
        ticker_df = self._coerce_numeric_columns(ticker_df, self.RAW_PRICE_COLUMNS)

        close = ticker_df["close"]
        open_ = ticker_df["open"]
        high = ticker_df["high"]
        low = ticker_df["low"]
        volume = ticker_df["volume"]
        typical_price = (high + low + close) / 3.0

        ticker_df["avg_vol_20"] = volume.rolling(20, min_periods=1).mean()
        ticker_df["avg_vol_50"] = volume.rolling(50, min_periods=1).mean()

        for period in (10, 20, 50):
            sma_series = close.rolling(period, min_periods=1).mean()
            ema_series = close.ewm(span=period, adjust=False).mean()
            ticker_df[f"sma_{period}"] = sma_series
            ticker_df[f"ema_{period}"] = ema_series
            ticker_df[f"close_vs_sma_{period}"] = self._safe_divide(close - sma_series, sma_series, 0.0)
            ticker_df[f"close_vs_ema_{period}"] = self._safe_divide(close - ema_series, ema_series, 0.0)

        ticker_df["trend_stack_bullish"] = (
            (close > ticker_df["ema_10"])
            & (ticker_df["ema_10"] > ticker_df["ema_20"])
            & (ticker_df["ema_20"] > ticker_df["ema_50"])
        ).astype(int)
        ticker_df["trend_stack_bearish"] = (
            (close < ticker_df["ema_10"])
            & (ticker_df["ema_10"] < ticker_df["ema_20"])
            & (ticker_df["ema_20"] < ticker_df["ema_50"])
        ).astype(int)

        ticker_df["roll_high_20"] = high.rolling(20, min_periods=1).max()
        ticker_df["roll_low_20"] = low.rolling(20, min_periods=1).min()
        ticker_df["pct_from_20d_high"] = self._safe_divide(
            close - ticker_df["roll_high_20"],
            ticker_df["roll_high_20"],
            0.0,
        )
        ticker_df["pct_from_20d_low"] = self._safe_divide(
            close - ticker_df["roll_low_20"],
            ticker_df["roll_low_20"],
            0.0,
        )

        ticker_df["donchian_high_20"] = high.rolling(20, min_periods=1).max()
        ticker_df["donchian_low_20"] = low.rolling(20, min_periods=1).min()
        ticker_df["donchian_pos_20"] = self._safe_divide(
            close - ticker_df["donchian_low_20"],
            ticker_df["donchian_high_20"] - ticker_df["donchian_low_20"],
            0.5,
        )

        ticker_df["bb_mid_20"] = close.rolling(20, min_periods=1).mean()
        bb_std_20 = close.rolling(20, min_periods=1).std()
        ticker_df["bb_upper_20"] = ticker_df["bb_mid_20"] + (2.0 * bb_std_20)
        ticker_df["bb_lower_20"] = ticker_df["bb_mid_20"] - (2.0 * bb_std_20)
        ticker_df["bb_pct_b_20"] = self._safe_divide(
            close - ticker_df["bb_lower_20"],
            ticker_df["bb_upper_20"] - ticker_df["bb_lower_20"],
            0.5,
        )

        ticker_df["rsi_14"] = self._rsi(close, 14)
        ticker_df["rsi_21"] = self._rsi(close, 21)
        ticker_df["smoothed_rsi_ema21_rsi10"] = self._rsi(
            close.ewm(span=21, adjust=False).mean(),
            10,
        )

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        ticker_df["macd_line"] = ema12 - ema26
        ticker_df["macd_signal"] = ticker_df["macd_line"].ewm(span=9, adjust=False).mean()
        ticker_df["macd_hist"] = ticker_df["macd_line"] - ticker_df["macd_signal"]

        rolling_low_14 = low.rolling(14, min_periods=1).min()
        rolling_high_14 = high.rolling(14, min_periods=1).max()
        stochastic_range = rolling_high_14 - rolling_low_14
        ticker_df["stoch_k_14"] = 100.0 * self._safe_divide(close - rolling_low_14, stochastic_range, 0.0)
        ticker_df["stoch_d_3"] = ticker_df["stoch_k_14"].rolling(3, min_periods=1).mean()
        ticker_df["williams_r_14"] = -100.0 * self._safe_divide(rolling_high_14 - close, stochastic_range, 0.0)

        typical_sma_20 = typical_price.rolling(20, min_periods=1).mean()
        mean_deviation = typical_price.rolling(20, min_periods=1).apply(
            lambda values: np.mean(np.abs(values - values.mean())),
            raw=True,
        )
        ticker_df["cci_20"] = self._safe_divide(
            typical_price - typical_sma_20,
            0.015 * mean_deviation,
            0.0,
        )

        prev_close = close.shift(1)
        ticker_df["tr"] = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        ticker_df["atr_14"] = ticker_df["tr"].rolling(14, min_periods=1).mean()
        ticker_df["atr_pct_14"] = self._safe_divide(ticker_df["atr_14"], close, 0.0)

        plus_di, minus_di, adx = self._directional_indicators(high, low, close, 14)
        ticker_df["plus_di_14"] = plus_di
        ticker_df["minus_di_14"] = minus_di
        ticker_df["adx_14"] = adx

        ticker_df["pct_chg"] = close.pct_change().fillna(0.0)
        ticker_df["close_pos"] = self._safe_divide(close - low, high - low, 0.0)
        ticker_df["body"] = (close - open_).abs()
        ticker_df["realized_vol_20"] = close.pct_change().rolling(20, min_periods=1).std(ddof=0) * np.sqrt(252)

        ticker_df["volume_ratio_20"] = self._safe_divide(volume, ticker_df["avg_vol_20"], 0.0)
        ticker_df["volume_ratio_50"] = self._safe_divide(volume, ticker_df["avg_vol_50"], 0.0)
        volume_std_20 = volume.rolling(20, min_periods=1).std(ddof=0)
        ticker_df["volume_zscore_20"] = self._safe_divide(
            volume - ticker_df["avg_vol_20"],
            volume_std_20,
            0.0,
        )

        money_flow_multiplier = self._safe_divide(
            ((close - low) - (high - close)),
            (high - low),
            0.0,
        )
        money_flow_volume = money_flow_multiplier * volume
        ticker_df["cmf_20"] = self._safe_divide(
            money_flow_volume.rolling(20, min_periods=1).sum(),
            volume.rolling(20, min_periods=1).sum(),
            0.0,
        )

        raw_money_flow = typical_price * volume
        positive_flow = raw_money_flow.where(typical_price > typical_price.shift(1), 0.0)
        negative_flow = raw_money_flow.where(typical_price < typical_price.shift(1), 0.0)
        ticker_df["mfi_14"] = 100.0 - (
            100.0
            / (
                1.0
                + self._safe_divide(
                    positive_flow.rolling(14, min_periods=1).sum(),
                    negative_flow.rolling(14, min_periods=1).sum(),
                    0.0,
                )
            )
        )

        self._add_relative_strength_features(ticker_df, "spy", spy_close)
        self._add_relative_strength_features(ticker_df, "qqq", qqq_close)

        ticker_df = self._fill_feature_defaults(ticker_df)
        return ticker_df.sort_values(["ticker", "Date"]).reset_index(drop=True)

    def _add_relative_strength_features(
        self,
        ticker_df: pd.DataFrame,
        benchmark_name: str,
        benchmark_close: pd.Series | None,
    ) -> None:
        if benchmark_close is None:
            ticker_df[f"price_to_{benchmark_name}"] = 0.0
            ticker_df[f"rs_{benchmark_name}_20"] = 0.0
            ticker_df[f"rs_{benchmark_name}_50"] = 0.0
            return

        aligned = benchmark_close.reindex(ticker_df["Date"]).ffill()
        aligned = pd.Series(aligned.values, index=ticker_df.index, dtype=float)
        price_to_benchmark = self._safe_divide(ticker_df["close"], aligned, 0.0)
        ticker_df[f"price_to_{benchmark_name}"] = price_to_benchmark
        ticker_df[f"rs_{benchmark_name}_20"] = price_to_benchmark.pct_change(20).fillna(0.0)
        ticker_df[f"rs_{benchmark_name}_50"] = price_to_benchmark.pct_change(50).fillna(0.0)

    def _coerce_row(self, row: pd.Series) -> dict[str, float]:
        coerced: dict[str, float] = {}
        for column, default_value in self.COLUMN_DEFAULTS.items():
            value = row[column] if column in row.index else default_value
            coerced[column] = default_value if pd.isna(value) else float(value)
        return coerced

    def _exit_reason(self, row: pd.Series, position: _BacktestPosition) -> str | None:
        trailing_stop = position.highest_close - (2.5 * float(row["atr_14"]))
        if float(row["close"]) <= trailing_stop:
            return "atr_trailing_stop"

        if float(row.get("roll_low_10", 0.0)) > 0 and float(row["close"]) <= float(row["roll_low_10"]):
            return "break_10d_low"

        if bool(row.get("close_below_sma50", False)):
            return "structure_sma50_fail"

        if bool(row.get("close_below_ema20_2d", False)):
            return "structure_ema20_fail"

        if bool(row.get("soft_score_fail_2d", False)):
            return "soft_score_fail"

        if bool(row.get("relative_weak_2d", False)):
            return "relative_weakness"

        if self.use_atr_stop:
            atr_stop = position.entry_price - (2.0 * float(row["atr_14"]))
            if float(row["close"]) <= atr_stop:
                return "legacy_atr_stop"

        if self.use_time_stop:
            if (
                position.days_held >= self.time_stop_days
                and not position.has_new_high
                and not position.score_improved
            ):
                return "time_stop"

        return None

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return float(max(low, min(high, value)))

    @staticmethod
    def _normalize_name(name: str) -> str:
        return (
            str(name)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

    @staticmethod
    def _safe_divide(
        numerator: pd.Series | float,
        denominator: pd.Series | float,
        default: float,
    ) -> pd.Series | float:
        if isinstance(denominator, pd.Series):
            denominator_clean = denominator.replace(0, np.nan)
            result = numerator / denominator_clean
            return result.replace([np.inf, -np.inf], np.nan).fillna(default)
        if denominator == 0 or pd.isna(denominator):
            return default
        result = numerator / denominator
        if pd.isna(result) or result in (np.inf, -np.inf):
            return default
        return result

    @staticmethod
    def _rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return (100 - (100 / (1 + rs))).fillna(0.0)

    @staticmethod
    def _directional_indicators(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = pd.Series(
            np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
            index=high.index,
        )
        minus_dm = pd.Series(
            np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
            index=high.index,
        )
        true_range = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        smoothed_tr = true_range.rolling(period, min_periods=1).mean()
        plus_di = (100.0 * plus_dm.rolling(period, min_periods=1).mean() / smoothed_tr.replace(0, np.nan)).fillna(0.0)
        minus_di = (100.0 * minus_dm.rolling(period, min_periods=1).mean() / smoothed_tr.replace(0, np.nan)).fillna(0.0)
        dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0.0)
        adx = dx.rolling(period, min_periods=1).mean().fillna(0.0)
        return plus_di, minus_di, adx
