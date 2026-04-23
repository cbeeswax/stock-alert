"""
GapContinuation_Position Strategy
=================================
Bullish gap-and-go / earnings gap continuation strategy on daily charts.

Long setup:
    - meaningful gap up with high relative volume
    - close holds near high of day
    - smoothed RSI stays in a strength band (not oversold reversal)
    - price remains above EMA21 / SMA50 with optional weekly trend alignment

Stop loss:
    - gap day low (institutional gap support)

Exit:
    - gap day support fails
    - trailing EMA21
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any
import json

import pandas as pd

from src.strategies.base import BaseStrategy
from src.ta.indicators.gaps import gap_pct, is_gap_up
from src.ta.indicators.momentum import smoothed_rsi
from src.ta.indicators.moving_averages import ema
from src.ta.indicators.volatility import atr_latest
from src.analysis.zone_structure import build_zone_snapshot, long_zone_broken


class GapContinuationPosition(BaseStrategy):
    """Bullish earnings-gap continuation strategy."""

    name = "GapContinuation_Position"
    description = "Bullish gap continuation with trend, volume, and close-strength filters"
    GAP_DAY_MIN_ROOM_TO_RESISTANCE = 0.02
    POST_SHELF_MIN_ROOM_TO_RESISTANCE = 0.03
    ZONE_EXIT_TOLERANCE_PCT = 0.002

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        as_of_date=None,
    ) -> Optional[Dict[str, Any]]:
        from src.config.settings import (
            GAP_CONTINUATION_MIN_GAP_PCT,
            GAP_CONTINUATION_MIN_GAP_ATR_MULT,
            GAP_CONTINUATION_MIN_VOL_MULT,
            GAP_CONTINUATION_EMA_PERIOD,
            GAP_CONTINUATION_RSI_PERIOD,
            GAP_CONTINUATION_RSI_MIN,
            GAP_CONTINUATION_RSI_MAX,
            GAP_CONTINUATION_MIN_CLOSE_POS,
            GAP_CONTINUATION_WEEKLY_TF_FILTER,
            GAP_CONTINUATION_MAX_DAYS,
            GAP_CONTINUATION_TARGET_R_MULTIPLE,
            GAP_CONTINUATION_MAX_GAP_AGE_DAYS,
            GAP_CONTINUATION_PRIORITY,
            GAP_CONTINUATION_MIN_RS_20,
            GAP_CONTINUATION_LONG_MACRO_FILTER,
            GAP_CONTINUATION_MAX_SHELF_DAYS,
            GAP_CONTINUATION_MAX_SHELF_RANGE_PCT,
            GAP_CONTINUATION_MIN_SHELF_CLOSE_POS,
            MIN_LIQUIDITY_USD,
            MIN_PRICE,
        )

        try:
            min_bars = max(GAP_CONTINUATION_EMA_PERIOD + GAP_CONTINUATION_RSI_PERIOD + 30, 65)
            if len(df) < min_bars:
                return None
            if "Open" not in df.columns:
                return None

            if as_of_date is not None:
                gap_bar_date = df.index[-1]
                as_of_ts = pd.Timestamp(as_of_date)
                if (as_of_ts - gap_bar_date).days > GAP_CONTINUATION_MAX_GAP_AGE_DAYS:
                    return None

            close = df["Close"]
            open_ = df["Open"]
            high = df["High"]
            low = df["Low"]
            volume = df["Volume"]

            last_close = float(close.iloc[-1])
            last_open = float(open_.iloc[-1])
            last_high = float(high.iloc[-1])
            last_low = float(low.iloc[-1])

            if last_close < MIN_PRICE:
                return None
            avg_vol = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else 0.0
            if avg_vol * last_close < MIN_LIQUIDITY_USD:
                return None

            srsi = smoothed_rsi(close, GAP_CONTINUATION_EMA_PERIOD, GAP_CONTINUATION_RSI_PERIOD)
            current_srsi = float(srsi.iloc[-1])
            if pd.isna(current_srsi):
                return None

            if GAP_CONTINUATION_LONG_MACRO_FILTER:
                try:
                    if as_of_date is not None:
                        date_str = pd.Timestamp(as_of_date).strftime("%Y-%m-%d")
                        cache_path = Path("data/predictor/macro_risk_cache") / f"macro_risk_{date_str}.json"
                        if cache_path.exists():
                            macro = json.loads(cache_path.read_text())
                            if macro.get("level", "LOW") in ("HIGH", "EXTREME"):
                                return None
                except Exception:
                    pass

            ema21 = ema(close, GAP_CONTINUATION_EMA_PERIOD)
            sma50 = close.rolling(50, min_periods=1).mean()
            last_ema = float(ema21.iloc[-1])
            last_sma50 = float(sma50.iloc[-1])
            if last_close <= last_ema or last_close <= last_sma50:
                return None

            if not (GAP_CONTINUATION_RSI_MIN <= current_srsi <= GAP_CONTINUATION_RSI_MAX):
                return None

            if GAP_CONTINUATION_WEEKLY_TF_FILTER:
                try:
                    from src.ta.timeframes import get_weekly_trend

                    gap_bar_date = df.index[-1]
                    weekly_trend = get_weekly_trend(ticker, gap_bar_date)
                    if weekly_trend == "DOWN":
                        return None
                except Exception:
                    pass

            rs_20 = self._relative_strength_vs_benchmarks(df)
            if rs_20 is not None and rs_20 < GAP_CONTINUATION_MIN_RS_20:
                return None
            zone_snapshot = build_zone_snapshot(df)

            signal_type = "gap_day"
            gap_idx = len(df) - 1
            if not self._qualified_gap_up_bar(
                df,
                gap_idx,
                min_gap_pct=GAP_CONTINUATION_MIN_GAP_PCT,
                min_gap_atr_mult=GAP_CONTINUATION_MIN_GAP_ATR_MULT,
                min_vol_mult=GAP_CONTINUATION_MIN_VOL_MULT,
            ):
                gap_idx = self._find_recent_gap_up_bar(
                    df,
                    max_shelf_days=GAP_CONTINUATION_MAX_SHELF_DAYS,
                    min_gap_pct=GAP_CONTINUATION_MIN_GAP_PCT,
                    min_gap_atr_mult=GAP_CONTINUATION_MIN_GAP_ATR_MULT,
                    min_vol_mult=GAP_CONTINUATION_MIN_VOL_MULT,
                )
                signal_type = "post_gap_shelf"
            if gap_idx is None:
                return None

            gap_bar = df.iloc[gap_idx]
            prior_close = float(close.iloc[gap_idx - 1]) if gap_idx >= 1 else float(gap_bar["Open"])
            gap_mid = prior_close + ((float(gap_bar["Open"]) - prior_close) * 0.5)
            close_pos = ((last_close - last_low) / (last_high - last_low)) if last_high > last_low else 0.0

            if signal_type == "gap_day":
                if close_pos < GAP_CONTINUATION_MIN_CLOSE_POS:
                    return None
                if last_close <= last_open:
                    return None
                entry_price = last_open
                stop_loss = float(gap_bar["Low"])
            else:
                days_since_gap = (len(df) - 1) - gap_idx
                shelf_slice = df.iloc[gap_idx : len(df)]
                shelf_range = (
                    (float(shelf_slice["High"].max()) - float(shelf_slice["Low"].min())) / last_close
                    if last_close > 0
                    else 0.0
                )
                prior_shelf_closes = shelf_slice["Close"].iloc[:-1]
                prior_shelf_max_close = float(prior_shelf_closes.max()) if not prior_shelf_closes.empty else 0.0
                if days_since_gap < 1 or days_since_gap > GAP_CONTINUATION_MAX_SHELF_DAYS:
                    return None
                if shelf_range > GAP_CONTINUATION_MAX_SHELF_RANGE_PCT:
                    return None
                if close_pos < GAP_CONTINUATION_MIN_SHELF_CLOSE_POS:
                    return None
                if last_close <= gap_mid:
                    return None
                if prior_shelf_max_close > 0 and last_close < prior_shelf_max_close:
                    return None
                entry_price = last_close
                stop_loss = gap_mid

            min_room_to_resistance = (
                self.POST_SHELF_MIN_ROOM_TO_RESISTANCE
                if signal_type == "post_gap_shelf"
                else self.GAP_DAY_MIN_ROOM_TO_RESISTANCE
            )
            if zone_snapshot is not None and not self._long_zone_entry_ok(
                zone_snapshot,
                min_room_to_resistance=min_room_to_resistance,
            ):
                return None

            risk = abs(entry_price - stop_loss)
            if risk <= 0:
                return None
            zone_support = (
                max(float(stop_loss), float(zone_snapshot.prior_short_low))
                if zone_snapshot is not None
                else float(stop_loss)
            )

            target_price = round(entry_price + GAP_CONTINUATION_TARGET_R_MULTIPLE * risk, 2)
            gap = float(gap_pct(df).iloc[-1])
            score = round(
                min(
                    100.0,
                    (gap * 100 * 4)
                    + (max(current_srsi - GAP_CONTINUATION_RSI_MIN, 0) * 0.8)
                    + (close_pos * 20),
                ),
                1,
            )

            return {
                "Ticker": ticker,
                "Strategy": self.name,
                "Direction": "LONG",
                "Priority": GAP_CONTINUATION_PRIORITY,
                "Close": round(last_close, 2),
                "Price": round(last_close, 2),
                "Entry": round(entry_price, 2),
                "StopLoss": round(stop_loss, 2),
                "StopPrice": round(stop_loss, 2),
                "GapLow": round(float(gap_bar["Low"]), 2),
                "GapSupport": round(stop_loss, 2),
                "ZoneSupport": round(zone_support, 2),
                "RoomToResistancePct": round(
                    float(zone_snapshot.room_to_long_ceiling_pct) * 100,
                    2,
                ) if zone_snapshot is not None else None,
                "SignalType": signal_type,
                "GapPct": round(gap * 100, 2),
                "Target": target_price,
                "SmoothedRSI": round(current_srsi, 2),
                "ClosePos": round(close_pos, 2),
                "Score": score,
                "Volume": int(volume.iloc[-1]),
                "Date": as_of_date if as_of_date is not None else df.index[-1],
                "AsOfDate": as_of_date if as_of_date is not None else df.index[-1],
                "MaxDays": GAP_CONTINUATION_MAX_DAYS,
            }
        except Exception:
            return None

    def get_exit_conditions(
        self,
        position: Dict[str, Any],
        df: pd.DataFrame,
        current_date=None,
    ) -> Optional[Dict[str, Any]]:
        from src.config.settings import GAP_CONTINUATION_TRAIL_MA

        try:
            close = df["Close"]
            low = df["Low"]
            last_close = float(close.iloc[-1])
            last_low = float(low.iloc[-1])

            gap_support = position.get("GapSupport") or position.get("GapLow") or position.get("stop_loss")
            if gap_support is None:
                metadata = position.get("metadata", {})
                gap_support = metadata.get("GapSupport") or metadata.get("GapLow")

            if gap_support is not None and last_low <= float(gap_support):
                return {"reason": "gap_support_fail", "exit_price": float(gap_support)}

            zone_support = position.get("ZoneSupport")
            if zone_support is None:
                metadata = position.get("metadata", {})
                zone_support = metadata.get("ZoneSupport")
            if zone_support is not None and long_zone_broken(
                last_close,
                float(zone_support),
                self.ZONE_EXIT_TOLERANCE_PCT,
            ):
                return {"reason": "zone_support_fail", "exit_price": last_close}

            trail_ema = ema(close, GAP_CONTINUATION_TRAIL_MA)
            last_ema = float(trail_ema.iloc[-1])
            if last_close < last_ema:
                return {"reason": f"trailing_ema{GAP_CONTINUATION_TRAIL_MA}", "exit_price": last_close}
        except Exception:
            pass

        return None

    def _relative_strength_vs_benchmarks(self, df: pd.DataFrame) -> float | None:
        """Return the best 20-bar relative-strength delta vs SPY/QQQ when benchmark data exists."""
        try:
            from src.data.market import get_historical_data
        except Exception:
            return None

        benchmark_strengths: list[float] = []
        ticker_ret = float(df["Close"].pct_change(20).iloc[-1]) if len(df) > 20 else None
        if ticker_ret is None or pd.isna(ticker_ret):
            return None

        for benchmark in ("SPY", "QQQ"):
            try:
                bench_df = get_historical_data(benchmark)
                if bench_df is None or bench_df.empty or "Close" not in bench_df.columns:
                    continue
                bench_df = bench_df.copy()
                if not isinstance(bench_df.index, pd.DatetimeIndex):
                    bench_df.index = pd.to_datetime(bench_df.index, errors="coerce")
                    bench_df = bench_df[bench_df.index.notna()]
                aligned = bench_df.reindex(df.index).ffill()
                if "Close" not in aligned.columns or len(aligned) <= 20:
                    continue
                bench_ret = float(aligned["Close"].pct_change(20).iloc[-1])
                if pd.isna(bench_ret):
                    continue
                benchmark_strengths.append(ticker_ret - bench_ret)
            except Exception:
                continue

        if not benchmark_strengths:
            return None
        return max(benchmark_strengths)

    @staticmethod
    def _qualified_gap_up_bar(
        df: pd.DataFrame,
        gap_idx: int,
        *,
        min_gap_pct: float,
        min_gap_atr_mult: float,
        min_vol_mult: float,
    ) -> bool:
        if gap_idx < 1:
            return False
        window = df.iloc[: gap_idx + 1].copy()
        if not bool(is_gap_up(window, min_gap_pct).iloc[-1]):
            return False
        gap_open = float(window["Open"].iloc[-1])
        prior_close = float(window["Close"].iloc[-2])
        gap_size = abs(gap_open - prior_close)
        if gap_size < atr_latest(window, 20) * min_gap_atr_mult:
            return False
        if len(window["Volume"]) >= 20:
            avg_vol_20 = float(window["Volume"].iloc[-21:-1].mean())
            if avg_vol_20 > 0 and float(window["Volume"].iloc[-1]) < avg_vol_20 * min_vol_mult:
                return False
        return True

    def _find_recent_gap_up_bar(
        self,
        df: pd.DataFrame,
        *,
        max_shelf_days: int,
        min_gap_pct: float,
        min_gap_atr_mult: float,
        min_vol_mult: float,
    ) -> int | None:
        last_index = len(df) - 2
        first_index = max(1, len(df) - 1 - max_shelf_days)
        for gap_idx in range(last_index, first_index - 1, -1):
            if self._qualified_gap_up_bar(
                df,
                gap_idx,
                min_gap_pct=min_gap_pct,
                min_gap_atr_mult=min_gap_atr_mult,
                min_vol_mult=min_vol_mult,
            ):
                return gap_idx
        return None

    @staticmethod
    def _long_zone_entry_ok(zone_snapshot, *, min_room_to_resistance: float) -> bool:
        broader_overhead_supply = zone_snapshot.prior_long_high > (zone_snapshot.prior_short_high * 1.01)
        return (
            zone_snapshot.prior_long_high <= 0
            or not broader_overhead_supply
            or zone_snapshot.close >= zone_snapshot.prior_long_high
            or (
                zone_snapshot.room_to_long_ceiling_pct >= min_room_to_resistance
                and not zone_snapshot.in_long_seller_zone
            )
        )
