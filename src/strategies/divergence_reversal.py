from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Optional

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
from src.ta.indicators.divergence import (
    DivergenceSetup,
    find_bearish_divergence_setup,
    find_bullish_divergence_setup,
    macd,
)
from src.ta.indicators.momentum import rsi
from src.ta.indicators.moving_averages import ema


class DivergenceReversalPosition(BaseStrategy):
    """Confirmation-first RSI divergence reversal strategy."""

    name = "DivergenceReversal_Position"
    description = "Confirmed RSI divergence reversal with MACD score bonus and zone-aware risk control"
    MIN_DIRECTIONAL_ORDER_FLOW_SCORE = 15.0
    EXTERNAL_SETTINGS_PATH = Path("config\\settings.json")
    REQUIRED_EXTERNAL_KEYS = {
        "DIVERGENCE_REVERSAL_DIRECTION",
        "DIVERGENCE_REVERSAL_EMA_PERIOD",
        "DIVERGENCE_REVERSAL_RSI_PERIOD",
        "DIVERGENCE_REVERSAL_MACD_FAST_PERIOD",
        "DIVERGENCE_REVERSAL_MACD_SLOW_PERIOD",
        "DIVERGENCE_REVERSAL_MACD_SIGNAL_PERIOD",
        "DIVERGENCE_REVERSAL_PIVOT_LEFT_BARS",
        "DIVERGENCE_REVERSAL_PIVOT_RIGHT_BARS",
        "DIVERGENCE_REVERSAL_MIN_SEPARATION_BARS",
        "DIVERGENCE_REVERSAL_PIVOT_LOOKBACK_BARS",
        "DIVERGENCE_REVERSAL_PRIOR_DECLINE_LOOKBACK",
        "DIVERGENCE_REVERSAL_PRIOR_DECLINE_PCT",
        "DIVERGENCE_REVERSAL_PRIOR_RALLY_LOOKBACK",
        "DIVERGENCE_REVERSAL_PRIOR_RALLY_PCT",
        "DIVERGENCE_REVERSAL_MIN_CONFIRM_CLOSE_POS",
        "DIVERGENCE_REVERSAL_MIN_EFFECTIVE_RISK_PCT",
        "DIVERGENCE_REVERSAL_TRAIL_MA",
        "DIVERGENCE_REVERSAL_TARGET_R_MULTIPLE",
        "DIVERGENCE_REVERSAL_LONG_MIN_ROOM_TO_RESISTANCE",
        "DIVERGENCE_REVERSAL_SHORT_MIN_ROOM_TO_SUPPORT",
        "DIVERGENCE_REVERSAL_ZONE_EXIT_TOLERANCE_PCT",
        "DIVERGENCE_REVERSAL_MAX_DAYS",
        "DIVERGENCE_REVERSAL_MAX_SIGNAL_AGE_DAYS",
        "DIVERGENCE_REVERSAL_PRIORITY",
        "DIVERGENCE_REVERSAL_MIN_HISTORY_BARS",
    }

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        as_of_date: pd.Timestamp = None,
    ) -> Optional[dict[str, Any]]:
        from src.config.settings import MIN_LIQUIDITY_USD, MIN_PRICE

        settings = self._load_external_settings()
        direction_mode = str(settings["DIVERGENCE_REVERSAL_DIRECTION"]).strip().lower()
        ema_period = int(settings["DIVERGENCE_REVERSAL_EMA_PERIOD"])
        rsi_period = int(settings["DIVERGENCE_REVERSAL_RSI_PERIOD"])
        macd_fast_period = int(settings["DIVERGENCE_REVERSAL_MACD_FAST_PERIOD"])
        macd_slow_period = int(settings["DIVERGENCE_REVERSAL_MACD_SLOW_PERIOD"])
        macd_signal_period = int(settings["DIVERGENCE_REVERSAL_MACD_SIGNAL_PERIOD"])
        pivot_left_bars = int(settings["DIVERGENCE_REVERSAL_PIVOT_LEFT_BARS"])
        pivot_right_bars = int(settings["DIVERGENCE_REVERSAL_PIVOT_RIGHT_BARS"])
        min_separation_bars = int(settings["DIVERGENCE_REVERSAL_MIN_SEPARATION_BARS"])
        pivot_lookback_bars = int(settings["DIVERGENCE_REVERSAL_PIVOT_LOOKBACK_BARS"])
        prior_decline_lookback = int(settings["DIVERGENCE_REVERSAL_PRIOR_DECLINE_LOOKBACK"])
        prior_decline_pct = float(settings["DIVERGENCE_REVERSAL_PRIOR_DECLINE_PCT"])
        prior_rally_lookback = int(settings["DIVERGENCE_REVERSAL_PRIOR_RALLY_LOOKBACK"])
        prior_rally_pct = float(settings["DIVERGENCE_REVERSAL_PRIOR_RALLY_PCT"])
        min_confirm_close_pos = float(settings["DIVERGENCE_REVERSAL_MIN_CONFIRM_CLOSE_POS"])
        min_effective_risk_pct = float(settings["DIVERGENCE_REVERSAL_MIN_EFFECTIVE_RISK_PCT"])
        target_r_multiple = float(settings["DIVERGENCE_REVERSAL_TARGET_R_MULTIPLE"])
        max_days = int(settings["DIVERGENCE_REVERSAL_MAX_DAYS"])
        max_signal_age_days = int(settings["DIVERGENCE_REVERSAL_MAX_SIGNAL_AGE_DAYS"])
        priority = int(settings["DIVERGENCE_REVERSAL_PRIORITY"])
        min_history_bars = int(settings["DIVERGENCE_REVERSAL_MIN_HISTORY_BARS"])
        long_min_room_to_resistance = float(settings["DIVERGENCE_REVERSAL_LONG_MIN_ROOM_TO_RESISTANCE"])
        short_min_room_to_support = float(settings["DIVERGENCE_REVERSAL_SHORT_MIN_ROOM_TO_SUPPORT"])

        required_columns = {"Open", "High", "Low", "Close", "Volume"}
        if df is None or df.empty or not required_columns.issubset(df.columns):
            return None

        min_bars = max(
            pivot_lookback_bars + pivot_right_bars + 5,
            macd_slow_period + macd_signal_period + 20,
            ema_period + rsi_period + 20,
            min_history_bars,
        )
        if len(df) < min_bars:
            return None

        if as_of_date is not None:
            as_of_ts = pd.Timestamp(as_of_date)
            bar_age_days = (as_of_ts - pd.Timestamp(df.index[-1])).days
            if bar_age_days > max_signal_age_days:
                return None

        close = pd.to_numeric(df["Close"], errors="coerce")
        open_ = pd.to_numeric(df["Open"], errors="coerce")
        high = pd.to_numeric(df["High"], errors="coerce")
        low = pd.to_numeric(df["Low"], errors="coerce")
        volume = pd.to_numeric(df["Volume"], errors="coerce")
        if close.isna().iloc[-1] or open_.isna().iloc[-1] or high.isna().iloc[-1] or low.isna().iloc[-1]:
            return None

        last_close = float(close.iloc[-1])
        last_open = float(open_.iloc[-1])
        last_high = float(high.iloc[-1])
        last_low = float(low.iloc[-1])
        if last_close < MIN_PRICE:
            return None

        avg_vol = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else 0.0
        if avg_vol * last_close < MIN_LIQUIDITY_USD:
            return None

        rsi_series = rsi(close, rsi_period)
        macd_frame = macd(
            close,
            fast_period=macd_fast_period,
            slow_period=macd_slow_period,
            signal_period=macd_signal_period,
        )
        ema_series = ema(close, ema_period)
        current_ema = float(ema_series.iloc[-1])
        if pd.isna(rsi_series.iloc[-1]) or pd.isna(current_ema):
            return None

        zone_snapshot = build_zone_snapshot(df)
        candidates: list[dict[str, Any]] = []

        if direction_mode in {"both", "long"}:
            long_setup = find_bullish_divergence_setup(
                df,
                rsi_series,
                macd_frame=macd_frame,
                left_bars=pivot_left_bars,
                right_bars=pivot_right_bars,
                min_separation_bars=min_separation_bars,
                max_pivot_lookback=pivot_lookback_bars,
            )
            long_signal = self._build_long_signal(
                ticker=ticker,
                df=df,
                setup=long_setup,
                zone_snapshot=zone_snapshot,
                current_ema=current_ema,
                last_open=last_open,
                last_high=last_high,
                last_close=last_close,
                prior_decline_lookback=prior_decline_lookback,
                prior_decline_pct=prior_decline_pct,
                min_confirm_close_pos=min_confirm_close_pos,
                min_effective_risk_pct=min_effective_risk_pct,
                target_r_multiple=target_r_multiple,
                long_min_room_to_resistance=long_min_room_to_resistance,
                priority=priority,
                max_days=max_days,
                as_of_date=as_of_date,
                volume=volume,
            )
            if long_signal is not None:
                candidates.append(long_signal)

        if direction_mode in {"both", "short"}:
            short_setup = find_bearish_divergence_setup(
                df,
                rsi_series,
                macd_frame=macd_frame,
                left_bars=pivot_left_bars,
                right_bars=pivot_right_bars,
                min_separation_bars=min_separation_bars,
                max_pivot_lookback=pivot_lookback_bars,
            )
            short_signal = self._build_short_signal(
                ticker=ticker,
                df=df,
                setup=short_setup,
                zone_snapshot=zone_snapshot,
                current_ema=current_ema,
                last_open=last_open,
                last_low=last_low,
                last_close=last_close,
                prior_rally_lookback=prior_rally_lookback,
                prior_rally_pct=prior_rally_pct,
                min_confirm_close_pos=min_confirm_close_pos,
                min_effective_risk_pct=min_effective_risk_pct,
                target_r_multiple=target_r_multiple,
                short_min_room_to_support=short_min_room_to_support,
                priority=priority,
                max_days=max_days,
                as_of_date=as_of_date,
                volume=volume,
            )
            if short_signal is not None:
                candidates.append(short_signal)

        if not candidates:
            return None
        return max(candidates, key=lambda signal: float(signal["Score"]))

    def get_exit_conditions(
        self,
        position: dict[str, Any],
        df: pd.DataFrame,
        current_date: pd.Timestamp = None,
    ) -> Optional[dict[str, Any]]:
        settings = self._load_external_settings()
        trail_ma = int(settings["DIVERGENCE_REVERSAL_TRAIL_MA"])
        zone_exit_tolerance_pct = float(settings["DIVERGENCE_REVERSAL_ZONE_EXIT_TOLERANCE_PCT"])

        if df is None or df.empty or "Close" not in df.columns:
            return None

        close = pd.to_numeric(df["Close"], errors="coerce")
        high = pd.to_numeric(df["High"], errors="coerce") if "High" in df.columns else close
        low = pd.to_numeric(df["Low"], errors="coerce") if "Low" in df.columns else close
        last_close = float(close.iloc[-1])
        last_high = float(high.iloc[-1])
        last_low = float(low.iloc[-1])
        direction = str(position.get("Direction", "LONG")).upper()
        metadata = position.get("metadata", {})

        stop_loss = position.get("stop_loss") or position.get("StopLoss") or metadata.get("StopLoss")
        if stop_loss is not None:
            stop_price = float(stop_loss)
            if direction == "LONG" and last_low <= stop_price:
                return {"reason": "stop_loss", "exit_price": stop_price}
            if direction == "SHORT" and last_high >= stop_price:
                return {"reason": "stop_loss", "exit_price": stop_price}

        zone_support = position.get("ZoneSupport") or position.get("zone_support") or metadata.get("ZoneSupport")
        zone_resistance = position.get("ZoneResistance") or position.get("zone_resistance") or metadata.get("ZoneResistance")
        if direction == "LONG" and zone_support is not None:
            if long_zone_broken(last_close, float(zone_support), zone_exit_tolerance_pct):
                return {"reason": "zone_support_fail", "exit_price": last_close}
        if direction == "SHORT" and zone_resistance is not None:
            if short_zone_broken(last_close, float(zone_resistance), zone_exit_tolerance_pct):
                return {"reason": "zone_resistance_fail", "exit_price": last_close}

        trail_ema = ema(close, trail_ma)
        last_ema = float(trail_ema.iloc[-1])
        if pd.isna(last_ema):
            return None
        if direction == "LONG" and last_close < last_ema:
            return {"reason": f"trailing_ema{trail_ma}", "exit_price": last_close}
        if direction == "SHORT" and last_close > last_ema:
            return {"reason": f"trailing_ema{trail_ma}", "exit_price": last_close}
        return None

    def _build_long_signal(
        self,
        *,
        ticker: str,
        df: pd.DataFrame,
        setup: DivergenceSetup | None,
        zone_snapshot,
        current_ema: float,
        last_open: float,
        last_high: float,
        last_close: float,
        prior_decline_lookback: int,
        prior_decline_pct: float,
        min_confirm_close_pos: float,
        min_effective_risk_pct: float,
        target_r_multiple: float,
        long_min_room_to_resistance: float,
        priority: int,
        max_days: int,
        as_of_date: pd.Timestamp | None,
        volume: pd.Series,
    ) -> Optional[dict[str, Any]]:
        if setup is None or last_close <= current_ema:
            return None
        if last_close <= setup.trigger_level or last_high <= setup.trigger_level:
            return None

        close_pos = self._close_position_for_bar(df.iloc[-1])
        if last_close <= last_open or close_pos < min_confirm_close_pos:
            return None
        if not self._has_meaningful_prior_decline(
            df,
            pivot_idx=setup.second_pivot_idx,
            lookback=prior_decline_lookback,
            min_decline_pct=prior_decline_pct,
        ):
            return None

        effective_risk = max(last_close - float(setup.invalidation_level), last_close * min_effective_risk_pct)
        if effective_risk <= 0:
            return None
        stop_loss = last_close - effective_risk
        if stop_loss <= 0:
            return None

        min_room = max(long_min_room_to_resistance, target_r_multiple * (effective_risk / last_close))
        if zone_snapshot is not None and not long_zone_entry_ok(
            zone_snapshot,
            min_room_to_resistance=min_room,
            require_near_term_check=True,
        ):
            return None

        zone_support = float(setup.invalidation_level)
        if zone_snapshot is not None and 0 < float(zone_snapshot.prior_short_low) < last_close:
            zone_support = max(zone_support, float(zone_snapshot.prior_short_low))

        target = round(last_close + (target_r_multiple * effective_risk), 2)
        room_to_target = (
            float(zone_snapshot.room_to_long_ceiling_pct) * 100
            if zone_snapshot is not None
            else None
        )
        score = self._score_signal(
            entry_price=last_close,
            first_price=setup.first_price,
            second_price=setup.second_price,
            first_oscillator=setup.first_oscillator,
            second_oscillator=setup.second_oscillator,
            macd_bonus=setup.macd_bonus,
            close_pos=close_pos,
        )
        context = self.build_price_action_context(df)
        if context.liquidity_sweep == "bearish_sweep":
            return None
        if context.order_flow_score < self.MIN_DIRECTIONAL_ORDER_FLOW_SCORE:
            return None

        signal = {
            "Ticker": ticker,
            "Strategy": self.name,
            "Direction": "LONG",
            "Priority": priority,
            "Close": round(last_close, 2),
            "Price": round(last_close, 2),
            "Entry": round(last_close, 2),
            "StopLoss": round(stop_loss, 2),
            "StopPrice": round(stop_loss, 2),
            "Target": target,
            "RiskPerShare": round(effective_risk, 2),
            "Score": score,
            "EntryScore": score,
            "SignalType": "confirmed_bullish_divergence",
            "TriggerLevel": round(float(setup.trigger_level), 2),
            "ZoneSupport": round(zone_support, 2),
            "RoomToResistancePct": round(room_to_target, 2) if room_to_target is not None else None,
            "DivergencePrice1": round(float(setup.first_price), 2),
            "DivergencePrice2": round(float(setup.second_price), 2),
            "DivergenceRSI1": round(float(setup.first_oscillator), 2),
            "DivergenceRSI2": round(float(setup.second_oscillator), 2),
            "MACDBonus": round(float(setup.macd_bonus), 2),
            "Volume": int(volume.iloc[-1]),
            "Date": as_of_date if as_of_date is not None else df.index[-1],
            "AsOfDate": as_of_date if as_of_date is not None else df.index[-1],
            "MaxDays": max_days,
        }
        return self.enrich_signal_with_price_action_context(signal, df, context=context)

    def _build_short_signal(
        self,
        *,
        ticker: str,
        df: pd.DataFrame,
        setup: DivergenceSetup | None,
        zone_snapshot,
        current_ema: float,
        last_open: float,
        last_low: float,
        last_close: float,
        prior_rally_lookback: int,
        prior_rally_pct: float,
        min_confirm_close_pos: float,
        min_effective_risk_pct: float,
        target_r_multiple: float,
        short_min_room_to_support: float,
        priority: int,
        max_days: int,
        as_of_date: pd.Timestamp | None,
        volume: pd.Series,
    ) -> Optional[dict[str, Any]]:
        if setup is None or last_close >= current_ema:
            return None
        if last_close >= setup.trigger_level or last_low >= setup.trigger_level:
            return None

        close_pos = self._close_position_for_bar(df.iloc[-1])
        if last_close >= last_open or close_pos > (1.0 - min_confirm_close_pos):
            return None
        if not self._has_meaningful_prior_rally(
            df,
            pivot_idx=setup.second_pivot_idx,
            lookback=prior_rally_lookback,
            min_rally_pct=prior_rally_pct,
        ):
            return None

        effective_risk = max(float(setup.invalidation_level) - last_close, last_close * min_effective_risk_pct)
        if effective_risk <= 0:
            return None
        stop_loss = last_close + effective_risk

        min_room = max(short_min_room_to_support, target_r_multiple * (effective_risk / last_close))
        if zone_snapshot is not None and not short_zone_entry_ok(
            zone_snapshot,
            min_room_to_support=min_room,
            require_near_term_check=True,
        ):
            return None

        zone_resistance = float(setup.invalidation_level)
        if zone_snapshot is not None and float(zone_snapshot.prior_short_high) > last_close:
            zone_resistance = min(zone_resistance, float(zone_snapshot.prior_short_high))

        target = round(last_close - (target_r_multiple * effective_risk), 2)
        room_to_target = (
            float(zone_snapshot.room_to_long_floor_pct) * 100
            if zone_snapshot is not None
            else None
        )
        score = self._score_signal(
            entry_price=last_close,
            first_price=setup.first_price,
            second_price=setup.second_price,
            first_oscillator=setup.first_oscillator,
            second_oscillator=setup.second_oscillator,
            macd_bonus=setup.macd_bonus,
            close_pos=(1.0 - close_pos),
        )
        context = self.build_price_action_context(df)
        if context.liquidity_sweep == "bullish_sweep":
            return None
        if context.order_flow_score > (-1.0 * self.MIN_DIRECTIONAL_ORDER_FLOW_SCORE):
            return None

        signal = {
            "Ticker": ticker,
            "Strategy": self.name,
            "Direction": "SHORT",
            "Priority": priority,
            "Close": round(last_close, 2),
            "Price": round(last_close, 2),
            "Entry": round(last_close, 2),
            "StopLoss": round(stop_loss, 2),
            "StopPrice": round(stop_loss, 2),
            "Target": target,
            "RiskPerShare": round(effective_risk, 2),
            "Score": score,
            "EntryScore": score,
            "SignalType": "confirmed_bearish_divergence",
            "TriggerLevel": round(float(setup.trigger_level), 2),
            "ZoneResistance": round(zone_resistance, 2),
            "RoomToSupportPct": round(room_to_target, 2) if room_to_target is not None else None,
            "DivergencePrice1": round(float(setup.first_price), 2),
            "DivergencePrice2": round(float(setup.second_price), 2),
            "DivergenceRSI1": round(float(setup.first_oscillator), 2),
            "DivergenceRSI2": round(float(setup.second_oscillator), 2),
            "MACDBonus": round(float(setup.macd_bonus), 2),
            "Volume": int(volume.iloc[-1]),
            "Date": as_of_date if as_of_date is not None else df.index[-1],
            "AsOfDate": as_of_date if as_of_date is not None else df.index[-1],
            "MaxDays": max_days,
        }
        return self.enrich_signal_with_price_action_context(signal, df, context=context)

    @staticmethod
    def _has_meaningful_prior_decline(
        df: pd.DataFrame,
        *,
        pivot_idx: int,
        lookback: int,
        min_decline_pct: float,
    ) -> bool:
        start_idx = max(0, pivot_idx - lookback)
        history = pd.to_numeric(df["High"].iloc[start_idx:pivot_idx], errors="coerce")
        if history.empty:
            return False
        recent_high = float(history.max())
        pivot_low = float(pd.to_numeric(df["Low"].iloc[pivot_idx], errors="coerce"))
        if recent_high <= 0:
            return False
        return (pivot_low / recent_high) <= (1.0 - min_decline_pct)

    @staticmethod
    def _has_meaningful_prior_rally(
        df: pd.DataFrame,
        *,
        pivot_idx: int,
        lookback: int,
        min_rally_pct: float,
    ) -> bool:
        start_idx = max(0, pivot_idx - lookback)
        history = pd.to_numeric(df["Low"].iloc[start_idx:pivot_idx], errors="coerce")
        if history.empty:
            return False
        recent_low = float(history.min())
        pivot_high = float(pd.to_numeric(df["High"].iloc[pivot_idx], errors="coerce"))
        if recent_low <= 0:
            return False
        return (pivot_high / recent_low) >= (1.0 + min_rally_pct)

    @staticmethod
    def _close_position_for_bar(bar: pd.Series) -> float:
        high = float(bar["High"])
        low = float(bar["Low"])
        close = float(bar["Close"])
        if high <= low:
            return 0.0
        return (close - low) / (high - low)

    @staticmethod
    def _score_signal(
        *,
        entry_price: float,
        first_price: float,
        second_price: float,
        first_oscillator: float,
        second_oscillator: float,
        macd_bonus: float,
        close_pos: float,
    ) -> float:
        oscillator_improvement = max(0.0, second_oscillator - first_oscillator)
        price_divergence_pct = abs(second_price - first_price) / max(abs(first_price), 1e-9)
        raw_score = (
            45.0
            + min(20.0, oscillator_improvement * 1.5)
            + min(15.0, price_divergence_pct * 200.0)
            + min(20.0, macd_bonus)
            + (max(0.0, min(1.0, close_pos)) * 10.0)
        )
        if entry_price <= 0:
            return 0.0
        return round(min(100.0, raw_score), 1)

    @classmethod
    def _load_external_settings(cls) -> dict[str, Any]:
        if cls.EXTERNAL_SETTINGS_PATH.exists():
            with cls.EXTERNAL_SETTINGS_PATH.open("r", encoding="utf-8") as handle:
                settings = json.load(handle)
        else:
            with tempfile.TemporaryDirectory(prefix="divergence-reversal-settings-") as tmp_dir:
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
            raise ValueError(f"Divergence reversal config missing required settings keys: {missing}")
        return settings
