"""
GapReversal_Position Strategy
==============================
Confirmed reversal-gap strategy on daily charts.

The gap bar is treated as setup evidence, not the executable entry itself.
Entries require post-gap confirmation after a qualified reversal gap:
    - Long: bullish gap after a strong decline, then confirmation above the setup range
    - Short: bearish gap after a strong rally, then confirmation below the setup range

Stops use structural invalidation with a minimum practical breathing distance.
Exits keep gap-fill awareness, zone-failure checks, and an EMA21 trailing exit.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from src.analysis.zone_structure import (
    build_zone_snapshot,
    long_zone_broken,
    long_zone_entry_ok,
    short_zone_broken,
    short_zone_entry_ok,
)
from src.storage.gcs import download_file
from src.strategies.base import BaseStrategy
from src.ta.indicators.gaps import gap_fill_level, gap_pct, is_gap_down, is_gap_up
from src.ta.indicators.momentum import smoothed_rsi
from src.ta.indicators.moving_averages import ema
from src.ta.indicators.volatility import atr_latest


class GapReversalPosition(BaseStrategy):
    """Confirmed reversal-gap strategy."""

    name = "GapReversal_Position"
    description = "Confirmed reversal gap with smoothed RSI extremes and structural confirmation"
    EXTERNAL_SETTINGS_PATH = Path("config\\settings.json")
    REQUIRED_EXTERNAL_KEYS = {
        "GAP_REVERSAL_MIN_CONFIRM_CLOSE_POS",
        "GAP_REVERSAL_MAX_COUNTER_WICK_PCT",
        "GAP_REVERSAL_MIN_EFFECTIVE_RISK_PCT",
    }
    LONG_MIN_ROOM_TO_RESISTANCE = 0.02
    SHORT_MIN_ROOM_TO_SUPPORT = 0.02
    ZONE_EXIT_TOLERANCE_PCT = 0.002

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        as_of_date=None,
    ) -> Optional[Dict[str, Any]]:
        from src.config.settings import (
            GAP_REVERSAL_DIRECTION,
            GAP_REVERSAL_EMA_PERIOD,
            GAP_REVERSAL_LONG_MACRO_FILTER,
            GAP_REVERSAL_MAX_DAYS,
            GAP_REVERSAL_MAX_GAP_AGE_DAYS,
            GAP_REVERSAL_MIN_GAP_ATR_MULT,
            GAP_REVERSAL_MIN_GAP_PCT,
            GAP_REVERSAL_MIN_VOL_MULT,
            GAP_REVERSAL_PRIOR_DECLINE_LOOKBACK,
            GAP_REVERSAL_PRIOR_DECLINE_PCT,
            GAP_REVERSAL_PRIORITY,
            GAP_REVERSAL_RSI_OVERBOUGHT,
            GAP_REVERSAL_RSI_OVERSOLD,
            GAP_REVERSAL_RSI_PERIOD,
            GAP_REVERSAL_SHORT_PRIOR_RALLY_PCT,
            GAP_REVERSAL_SHORT_REGIME_FILTER,
            GAP_REVERSAL_SHORT_REQUIRE_RISK_OFF,
            GAP_REVERSAL_TARGET_R_MULTIPLE,
            GAP_REVERSAL_WEEKLY_TF_FILTER,
            MIN_LIQUIDITY_USD,
            MIN_PRICE,
        )

        external_settings = self._load_external_settings()
        min_confirm_close_pos = float(external_settings["GAP_REVERSAL_MIN_CONFIRM_CLOSE_POS"])
        max_counter_wick_pct = float(external_settings["GAP_REVERSAL_MAX_COUNTER_WICK_PCT"])
        min_effective_risk_pct = float(external_settings["GAP_REVERSAL_MIN_EFFECTIVE_RISK_PCT"])

        try:
            min_bars = GAP_REVERSAL_EMA_PERIOD + GAP_REVERSAL_RSI_PERIOD + 30
            if len(df) < min_bars or "Open" not in df.columns:
                return None

            if as_of_date is not None:
                as_of_ts = pd.Timestamp(as_of_date)
                if (as_of_ts - pd.Timestamp(df.index[-1])).days > GAP_REVERSAL_MAX_GAP_AGE_DAYS:
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

            srsi = smoothed_rsi(close, GAP_REVERSAL_EMA_PERIOD, GAP_REVERSAL_RSI_PERIOD)
            if srsi.isna().all():
                return None

            direction_mode = GAP_REVERSAL_DIRECTION
            zone_snapshot = build_zone_snapshot(df)

            candidate = self._find_recent_reversal_gap(
                ticker=ticker,
                df=df,
                srsi=srsi,
                direction_mode=direction_mode,
                min_gap_pct=GAP_REVERSAL_MIN_GAP_PCT,
                min_gap_atr_mult=GAP_REVERSAL_MIN_GAP_ATR_MULT,
                min_vol_mult=GAP_REVERSAL_MIN_VOL_MULT,
                rsi_oversold=GAP_REVERSAL_RSI_OVERSOLD,
                rsi_overbought=GAP_REVERSAL_RSI_OVERBOUGHT,
                lookback=GAP_REVERSAL_PRIOR_DECLINE_LOOKBACK,
                prior_decline_pct=GAP_REVERSAL_PRIOR_DECLINE_PCT,
                short_prior_rally_pct=GAP_REVERSAL_SHORT_PRIOR_RALLY_PCT,
                short_regime_filter=GAP_REVERSAL_SHORT_REGIME_FILTER,
                short_require_risk_off=GAP_REVERSAL_SHORT_REQUIRE_RISK_OFF,
                long_macro_filter=GAP_REVERSAL_LONG_MACRO_FILTER,
                weekly_tf_filter=GAP_REVERSAL_WEEKLY_TF_FILTER,
                max_gap_age_days=GAP_REVERSAL_MAX_GAP_AGE_DAYS,
                min_confirm_close_pos=min_confirm_close_pos,
                max_counter_wick_pct=max_counter_wick_pct,
                as_of_date=as_of_date,
            )
            if candidate is None:
                return None

            gap_idx = int(candidate["gap_idx"])
            gap_bar = df.iloc[gap_idx]
            gap_high = float(gap_bar["High"])
            gap_low = float(gap_bar["Low"])
            gap_fill = float(candidate["gap_fill_level"])
            gap_mid = float(candidate["gap_mid"])
            trade_direction = str(candidate["direction"])
            gap_srsi = float(candidate["gap_srsi"])
            days_since_gap = (len(df) - 1) - gap_idx
            if days_since_gap < 1:
                return None

            shelf_slice = df.iloc[gap_idx + 1 : len(df) - 1]
            post_gap_slice = df.iloc[gap_idx + 1 :]
            if post_gap_slice.empty:
                return None

            current_close_pos = self._close_position_for_bar(df.iloc[-1])
            if trade_direction == "LONG":
                if not shelf_slice.empty and float(shelf_slice["Close"].min()) <= gap_mid:
                    return None
                breakout_level = max(gap_high, float(shelf_slice["High"].max()) if not shelf_slice.empty else gap_high)
                if last_close <= breakout_level or last_high <= breakout_level:
                    return None
                if last_close <= last_open or current_close_pos < min_confirm_close_pos:
                    return None

                structural_support = max(gap_mid, float(post_gap_slice["Low"].min()))
                effective_risk = max(
                    last_close - structural_support,
                    last_close * min_effective_risk_pct,
                )
                if effective_risk <= 0:
                    return None
                stop_loss = last_close - effective_risk
                min_room = max(
                    self.LONG_MIN_ROOM_TO_RESISTANCE,
                    GAP_REVERSAL_TARGET_R_MULTIPLE * (effective_risk / last_close),
                )
                if zone_snapshot is not None and not long_zone_entry_ok(
                    zone_snapshot,
                    min_room_to_resistance=min_room,
                    require_near_term_check=True,
                ):
                    return None

                zone_support = structural_support
                if (
                    zone_snapshot is not None
                    and 0 < float(zone_snapshot.prior_short_low) < last_close
                ):
                    zone_support = max(zone_support, float(zone_snapshot.prior_short_low))
                target_price = round(last_close + GAP_REVERSAL_TARGET_R_MULTIPLE * effective_risk, 2)
                gap_support = structural_support
                zone_resistance = None
                gap_resistance = None
                room_to_target = (
                    float(zone_snapshot.room_to_long_ceiling_pct) * 100
                    if zone_snapshot is not None
                    else None
                )
            else:
                if not shelf_slice.empty and float(shelf_slice["Close"].max()) >= gap_mid:
                    return None
                breakdown_level = min(gap_low, float(shelf_slice["Low"].min()) if not shelf_slice.empty else gap_low)
                if last_close >= breakdown_level or last_low >= breakdown_level:
                    return None
                if last_close >= last_open or current_close_pos > (1.0 - min_confirm_close_pos):
                    return None

                structural_resistance = min(gap_mid, float(post_gap_slice["High"].max()))
                effective_risk = max(
                    structural_resistance - last_close,
                    last_close * min_effective_risk_pct,
                )
                if effective_risk <= 0:
                    return None
                stop_loss = last_close + effective_risk
                min_room = max(
                    self.SHORT_MIN_ROOM_TO_SUPPORT,
                    GAP_REVERSAL_TARGET_R_MULTIPLE * (effective_risk / last_close),
                )
                if zone_snapshot is not None and not short_zone_entry_ok(
                    zone_snapshot,
                    min_room_to_support=min_room,
                    require_near_term_check=True,
                ):
                    return None

                zone_resistance = structural_resistance
                if (
                    zone_snapshot is not None
                    and float(zone_snapshot.prior_short_high) > last_close
                ):
                    zone_resistance = min(zone_resistance, float(zone_snapshot.prior_short_high))
                target_price = round(last_close - GAP_REVERSAL_TARGET_R_MULTIPLE * effective_risk, 2)
                gap_resistance = structural_resistance
                zone_support = None
                gap_support = None
                room_to_target = (
                    float(zone_snapshot.room_to_long_floor_pct) * 100
                    if zone_snapshot is not None
                    else None
                )

            if stop_loss <= 0:
                return None

            gap = float(gap_pct(df.iloc[: gap_idx + 1]).iloc[-1])
            score_extreme = (
                max(0.0, (GAP_REVERSAL_RSI_OVERSOLD - gap_srsi) * 5)
                if trade_direction == "LONG"
                else max(0.0, (gap_srsi - GAP_REVERSAL_RSI_OVERBOUGHT) * 5)
            )
            confirmation_bonus = current_close_pos * 20 if trade_direction == "LONG" else (1.0 - current_close_pos) * 20
            score = round(min(100.0, score_extreme + confirmation_bonus), 1)

            signal = {
                "Ticker": ticker,
                "Strategy": self.name,
                "Direction": trade_direction,
                "Priority": GAP_REVERSAL_PRIORITY,
                "Close": round(last_close, 2),
                "Price": round(last_close, 2),
                "Entry": round(last_close, 2),
                "StopLoss": round(stop_loss, 2),
                "StopPrice": round(stop_loss, 2),
                "GapFillLevel": round(gap_fill, 2),
                "GapHigh": round(gap_high, 2),
                "GapLow": round(gap_low, 2),
                "GapMid": round(gap_mid, 2),
                "Target": target_price,
                "RiskPerShare": round(effective_risk, 2),
                "SmoothedRSI": round(gap_srsi, 2),
                "GapPct": round(gap * 100, 2),
                "Score": score,
                "Volume": int(volume.iloc[gap_idx]),
                "Date": as_of_date if as_of_date is not None else df.index[-1],
                "AsOfDate": as_of_date if as_of_date is not None else df.index[-1],
                "MaxDays": GAP_REVERSAL_MAX_DAYS,
                "SignalType": "confirmed_gap_reversal",
            }
            if trade_direction == "LONG":
                signal["GapSupport"] = round(gap_support, 2)
                signal["ZoneSupport"] = round(zone_support, 2)
                signal["RoomToResistancePct"] = round(room_to_target, 2) if room_to_target is not None else None
            else:
                signal["GapResistance"] = round(gap_resistance, 2)
                signal["ZoneResistance"] = round(zone_resistance, 2)
                signal["RoomToSupportPct"] = round(room_to_target, 2) if room_to_target is not None else None
            return signal

        except Exception:
            return None

    def get_exit_conditions(
        self,
        position: Dict[str, Any],
        df: pd.DataFrame,
        current_date=None,
    ) -> Optional[Dict[str, Any]]:
        from src.config.settings import GAP_REVERSAL_TRAIL_MA

        try:
            close = df["Close"]
            low = df["Low"]
            last_close = float(close.iloc[-1])
            last_low = float(low.iloc[-1])
            last_high = float(df["High"].iloc[-1])

            direction = position.get("Direction", "LONG")
            metadata = position.get("metadata", {})

            gap_fill = (
                position.get("GapFillLevel")
                or position.get("gap_fill_level")
                or metadata.get("GapFillLevel")
                or position.get("stop_loss")
            )
            if gap_fill is not None:
                if direction == "LONG" and last_low <= float(gap_fill):
                    return {"reason": "gap_fill_stop", "exit_price": float(gap_fill)}
                if direction == "SHORT" and last_high >= float(gap_fill):
                    return {"reason": "gap_fill_stop", "exit_price": float(gap_fill)}

            zone_support = position.get("ZoneSupport") or position.get("zone_support") or metadata.get("ZoneSupport")
            zone_resistance = (
                position.get("ZoneResistance")
                or position.get("zone_resistance")
                or metadata.get("ZoneResistance")
            )
            if direction == "LONG" and zone_support is not None and long_zone_broken(
                last_close,
                float(zone_support),
                self.ZONE_EXIT_TOLERANCE_PCT,
            ):
                return {"reason": "zone_support_fail", "exit_price": last_close}
            if direction == "SHORT" and zone_resistance is not None and short_zone_broken(
                last_close,
                float(zone_resistance),
                self.ZONE_EXIT_TOLERANCE_PCT,
            ):
                return {"reason": "zone_resistance_fail", "exit_price": last_close}

            trail_ema = ema(close, GAP_REVERSAL_TRAIL_MA)
            last_ema = float(trail_ema.iloc[-1])
            if direction == "LONG" and last_close < last_ema:
                return {"reason": f"trailing_ema{GAP_REVERSAL_TRAIL_MA}", "exit_price": last_close}
            if direction == "SHORT" and last_close > last_ema:
                return {"reason": f"trailing_ema{GAP_REVERSAL_TRAIL_MA}", "exit_price": last_close}
        except Exception:
            pass

        return None

    def _find_recent_reversal_gap(
        self,
        *,
        ticker: str,
        df: pd.DataFrame,
        srsi: pd.Series,
        direction_mode: str,
        min_gap_pct: float,
        min_gap_atr_mult: float,
        min_vol_mult: float,
        rsi_oversold: float,
        rsi_overbought: float,
        lookback: int,
        prior_decline_pct: float,
        short_prior_rally_pct: float,
        short_regime_filter: bool,
        short_require_risk_off: bool,
        long_macro_filter: bool,
        weekly_tf_filter: bool,
        max_gap_age_days: int,
        min_confirm_close_pos: float,
        max_counter_wick_pct: float,
        as_of_date,
    ) -> dict[str, Any] | None:
        last_index = len(df) - 2
        if last_index < 1:
            return None

        first_index = max(1, len(df) - 1 - max_gap_age_days)
        for gap_idx in range(last_index, first_index - 1, -1):
            gap_date = pd.Timestamp(df.index[gap_idx])
            current_date = pd.Timestamp(df.index[-1])
            if (current_date - gap_date).days > max_gap_age_days:
                continue

            candidate = self._qualify_gap_bar(
                ticker=ticker,
                df=df,
                gap_idx=gap_idx,
                srsi=srsi,
                direction_mode=direction_mode,
                min_gap_pct=min_gap_pct,
                min_gap_atr_mult=min_gap_atr_mult,
                min_vol_mult=min_vol_mult,
                rsi_oversold=rsi_oversold,
                rsi_overbought=rsi_overbought,
                lookback=lookback,
                prior_decline_pct=prior_decline_pct,
                short_prior_rally_pct=short_prior_rally_pct,
                short_regime_filter=short_regime_filter,
                short_require_risk_off=short_require_risk_off,
                long_macro_filter=long_macro_filter,
                weekly_tf_filter=weekly_tf_filter,
                min_confirm_close_pos=min_confirm_close_pos,
                max_counter_wick_pct=max_counter_wick_pct,
                as_of_date=as_of_date,
            )
            if candidate is not None:
                return candidate
        return None

    def _qualify_gap_bar(
        self,
        *,
        ticker: str,
        df: pd.DataFrame,
        gap_idx: int,
        srsi: pd.Series,
        direction_mode: str,
        min_gap_pct: float,
        min_gap_atr_mult: float,
        min_vol_mult: float,
        rsi_oversold: float,
        rsi_overbought: float,
        lookback: int,
        prior_decline_pct: float,
        short_prior_rally_pct: float,
        short_regime_filter: bool,
        short_require_risk_off: bool,
        long_macro_filter: bool,
        weekly_tf_filter: bool,
        min_confirm_close_pos: float,
        max_counter_wick_pct: float,
        as_of_date,
    ) -> dict[str, Any] | None:
        if gap_idx < 1:
            return None

        window = df.iloc[: gap_idx + 1].copy()
        gap_bar = window.iloc[-1]
        gap_open = float(gap_bar["Open"])
        gap_high = float(gap_bar["High"])
        gap_low = float(gap_bar["Low"])
        gap_close = float(gap_bar["Close"])
        prior_close = float(window["Close"].iloc[-2])
        gap_fill = float(gap_fill_level(window).iloc[-1])
        gap_mid = prior_close + ((gap_open - prior_close) * 0.5)
        gap_srsi = float(srsi.iloc[gap_idx])
        if pd.isna(gap_srsi):
            return None

        gap_up = bool(is_gap_up(window, min_gap_pct).iloc[-1])
        gap_down = bool(is_gap_down(window, min_gap_pct).iloc[-1])
        is_long = gap_up and gap_srsi < rsi_oversold
        is_short = gap_down and gap_srsi > rsi_overbought
        if direction_mode == "long":
            is_short = False
        elif direction_mode == "short":
            is_long = False
        if not (is_long or is_short):
            return None

        gap_size = abs(gap_open - prior_close)
        if gap_size < atr_latest(window, 20) * min_gap_atr_mult:
            return None

        if len(window["Volume"]) >= 20:
            avg_vol_20 = float(window["Volume"].iloc[-21:-1].mean())
            gap_day_vol = float(window["Volume"].iloc[-1])
            if avg_vol_20 > 0 and gap_day_vol < avg_vol_20 * min_vol_mult:
                return None

        if is_long and long_macro_filter and not self._macro_ok(pd.Timestamp(window.index[-1])):
            return None

        prior_close_series = window["Close"].iloc[max(0, len(window) - lookback - 1) : -1]
        if len(prior_close_series) >= 5:
            prior_close_val = float(prior_close_series.iloc[-1])
            if is_long:
                recent_high = float(prior_close_series.max())
                if recent_high > 0 and (prior_close_val / recent_high) > (1 - prior_decline_pct):
                    return None
            if is_short:
                recent_low = float(prior_close_series.min())
                if recent_low > 0 and (prior_close_val / recent_low) < (1 + short_prior_rally_pct):
                    return None

        if is_short and short_regime_filter and not self._short_regime_ok(
            as_of_date=pd.Timestamp(window.index[-1]),
            require_risk_off=short_require_risk_off,
        ):
            return None

        if weekly_tf_filter and not self._weekly_trend_ok(
            ticker=ticker,
            gap_bar_date=pd.Timestamp(window.index[-1]),
            is_long=is_long,
            is_short=is_short,
        ):
            return None

        gap_close_pos = self._close_position_for_bar(gap_bar)
        if is_long:
            if gap_close <= gap_open or gap_close <= gap_mid:
                return None
            if gap_close_pos < min_confirm_close_pos:
                return None
            if self._upper_wick_fraction_for_bar(gap_bar) > max_counter_wick_pct:
                return None
            return {
                "gap_idx": gap_idx,
                "direction": "LONG",
                "gap_fill_level": gap_fill,
                "gap_mid": gap_mid,
                "gap_srsi": gap_srsi,
            }

        if gap_close >= gap_open or gap_close >= gap_mid:
            return None
        if gap_close_pos > (1.0 - min_confirm_close_pos):
            return None
        if self._lower_wick_fraction_for_bar(gap_bar) > max_counter_wick_pct:
            return None
        return {
            "gap_idx": gap_idx,
            "direction": "SHORT",
            "gap_fill_level": gap_fill,
            "gap_mid": gap_mid,
            "gap_srsi": gap_srsi,
        }

    @staticmethod
    def _macro_ok(gap_bar_date: pd.Timestamp) -> bool:
        try:
            cache_path = Path("data/predictor/macro_risk_cache") / f"macro_risk_{gap_bar_date.strftime('%Y-%m-%d')}.json"
            if cache_path.exists():
                macro = json.loads(cache_path.read_text())
                return macro.get("level", "LOW") not in ("HIGH", "EXTREME")
        except Exception:
            return True
        return True

    @staticmethod
    def _short_regime_ok(*, as_of_date: pd.Timestamp, require_risk_off: bool) -> bool:
        try:
            from src.analysis.market_regime import PositionRegime, get_position_regime

            regime = get_position_regime(as_of_date)
            if require_risk_off:
                return regime == PositionRegime.RISK_OFF
            return regime != PositionRegime.RISK_ON
        except Exception:
            return True

    @staticmethod
    def _weekly_trend_ok(*, ticker: str, gap_bar_date: pd.Timestamp, is_long: bool, is_short: bool) -> bool:
        try:
            from src.ta.timeframes import get_weekly_trend

            weekly_trend = get_weekly_trend(ticker, gap_bar_date)
            if is_long and weekly_trend == "DOWN":
                return False
            if is_short and weekly_trend == "UP":
                return False
        except Exception:
            return True
        return True

    @staticmethod
    def _close_position_for_bar(bar: pd.Series) -> float:
        high = float(bar["High"])
        low = float(bar["Low"])
        close = float(bar["Close"])
        if high <= low:
            return 0.0
        return (close - low) / (high - low)

    @staticmethod
    def _upper_wick_fraction_for_bar(bar: pd.Series) -> float:
        high = float(bar["High"])
        low = float(bar["Low"])
        open_price = float(bar["Open"])
        close = float(bar["Close"])
        if high <= low:
            return 0.0
        return max(0.0, high - max(open_price, close)) / (high - low)

    @staticmethod
    def _lower_wick_fraction_for_bar(bar: pd.Series) -> float:
        high = float(bar["High"])
        low = float(bar["Low"])
        open_price = float(bar["Open"])
        close = float(bar["Close"])
        if high <= low:
            return 0.0
        return max(0.0, min(open_price, close) - low) / (high - low)

    @classmethod
    def _load_external_settings(cls) -> dict[str, Any]:
        if cls.EXTERNAL_SETTINGS_PATH.exists():
            with cls.EXTERNAL_SETTINGS_PATH.open("r", encoding="utf-8") as handle:
                settings = json.load(handle)
        else:
            with tempfile.TemporaryDirectory(prefix="gap-reversal-settings-") as tmp_dir:
                local_path = Path(tmp_dir) / "settings.json"
                if not download_file("config/settings.json", local_path):
                    raise FileNotFoundError(
                        "Missing required settings file: config\\settings.json "
                        "(expected locally or in GCS)."
                    )
                with local_path.open("r", encoding="utf-8") as handle:
                    settings = json.load(handle)

        missing = sorted(key for key in cls.REQUIRED_EXTERNAL_KEYS if key not in settings)
        if missing:
            raise ValueError(f"Gap reversal config missing required settings keys: {missing}")
        return settings

