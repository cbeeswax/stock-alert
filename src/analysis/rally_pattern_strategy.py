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

import pandas as pd


@dataclass(frozen=True)
class _BacktestPosition:
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: float
    entry_score: float
    best_score: float
    has_new_high: bool
    score_improved: bool
    days_held: int


class RallyPatternStrategy:
    """Cross-sectional rally-ranking strategy operating on precomputed features."""

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

    def __init__(
        self,
        *,
        strict_entry: bool = False,
        use_atr_stop: bool = False,
        use_time_stop: bool = False,
        reentry_cooldown_days: int = 3,
        time_stop_days: int = 15,
    ) -> None:
        self.strict_entry = strict_entry
        self.use_atr_stop = use_atr_stop
        self.use_time_stop = use_time_stop
        self.reentry_cooldown_days = reentry_cooldown_days
        self.time_stop_days = time_stop_days

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
        working = self._prepare_dataframe(df)
        scored = working.apply(self.score_row, axis=1, result_type="expand")
        return pd.concat([working, scored], axis=1)

    def generate_entries(self, df: pd.DataFrame) -> pd.Series:
        """Return the exact baseline entry signal for each row."""
        scored = self._ensure_scored(df)
        entry_signal = (
            (scored["score"] >= 70)
            & (scored["pattern_stage"] == "breakout_or_power_trend")
            & (scored["volume_ratio_20"] >= 1.15)
            & (scored["trend_stack_bullish"] == 1)
            & ((scored["rs_spy_20"] > 0) | (scored["rs_qqq_20"] > 0))
        )

        if self.strict_entry:
            entry_signal &= (
                (scored["rsi_14"] >= 58)
                & (scored["donchian_pos_20"] >= 0.80)
                & (scored["close_vs_ema_20"] > 0)
                & (scored["macd_hist"] > 0)
            )

        return entry_signal.rename("entry_signal")

    def generate_exits(self, df: pd.DataFrame) -> pd.Series:
        """Return the exact baseline exit signal for each row."""
        scored = self._ensure_scored(df)
        exit_signal = (
            (scored["score"] < 45)
            | ((scored["close_vs_ema_20"] < 0) & (scored["macd_hist"] < 0))
            | (
                (scored["rs_spy_20"] < 0)
                & (scored["rs_qqq_20"] < 0)
                & (scored["pct_from_20d_high"] < -0.10)
            )
        )
        return exit_signal.rename("exit_signal")

    def rank_candidates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rank baseline entry candidates for each date."""
        scored = self._ensure_scored(df).copy()
        scored["entry_signal"] = self.generate_entries(scored)
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
    ) -> dict[str, pd.DataFrame]:
        """
        Run a no-lookahead daily backtest.

        Signals are evaluated at each row's close. Exits and new entries are both
        executed at that close, and new positions participate from the next bar.
        """
        scored = self._ensure_scored(df).copy()
        scored["entry_signal"] = self.generate_entries(scored)
        scored["exit_signal"] = self.generate_exits(scored)
        scored = scored.sort_values(["Date", "ticker"]).reset_index(drop=True)

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

            ranked_candidates = self.rank_candidates(day_df)
            available_slots = max_positions - len(positions)
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

        for column, default_value in self.COLUMN_DEFAULTS.items():
            if column not in working.columns:
                working[column] = default_value
            working[column] = pd.to_numeric(working[column], errors="coerce").fillna(default_value)

        return working.sort_values(["ticker", "Date"]).reset_index(drop=True)

    def _ensure_scored(self, df: pd.DataFrame) -> pd.DataFrame:
        if {"score", "trend_points", "penalty", "pattern_stage", "label"}.issubset(df.columns):
            return self._prepare_dataframe(df)
        return self.score_dataframe(df)

    def _coerce_row(self, row: pd.Series) -> dict[str, float]:
        coerced: dict[str, float] = {}
        for column, default_value in self.COLUMN_DEFAULTS.items():
            value = row[column] if column in row.index else default_value
            coerced[column] = default_value if pd.isna(value) else float(value)
        return coerced

    def _exit_reason(self, row: pd.Series, position: _BacktestPosition) -> str | None:
        if bool(row["exit_signal"]):
            return "baseline_exit"

        if self.use_atr_stop:
            atr_stop = position.entry_price - (2.0 * float(row["atr_14"]))
            if float(row["close"]) <= atr_stop:
                return "atr_stop"

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
