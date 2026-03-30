"""
VCP_Momentum_Position Strategy
================================
Daily VCP (Volatility Contraction Pattern) Momentum Swing Strategy.

Finds stocks in strong uptrends that form a VCP — shrinking pullbacks, drying volume —
then enter when the stock breaks above the consolidation high with a volume surge.

Entry logic:
  1. Trend filter:     close > EMA200 AND EMA200 is rising (today > 20 bars ago)
  2. Momentum filter:  monthly gain ≥ 20% OR within 25% of 52-week high
  3. Consolidation:    ATR contracting + last 3 bars tight range (< 3%) + volume drying up
  4. Breakout:         today's close > 10-bar consolidation high + volume surge (> 1.5x avg)

Entry:  today's close (breakout confirmation bar)
Stop:   lowest low of the 10-bar consolidation window
Exit:   2 consecutive closes below EMA10 (momentum failure, fast exit)
Partial: 30% at 2.5R, stop moves to breakeven
MaxDays: 60 (swing trade, not a long-term hold)
"""
import pandas as pd
from typing import Optional, Dict, Any

from src.strategies.base import BaseStrategy


class VCPMomentumPosition(BaseStrategy):
    """
    Daily VCP Momentum Swing Strategy.

    Scans for:
        - Strong uptrend (above rising EMA200)
        - Momentum context (recent 20% gain or near 52W high)
        - Volatility contraction (shrinking ATR + tight 3-day range + drying volume)
        - Breakout above 10-bar consolidation high with volume surge

    Exit conditions (checked by backtester and live monitor):
        - Hard stop: low <= consolidation low (stop_price)
        - EMA10 trail: 2 consecutive closes below EMA10 → exit
        - MaxDays: 60-day hard cap
    """

    name = "VCP_Momentum_Position"
    description = "VCP breakout pattern: uptrend + contraction + volume surge breakout, EMA10 trail exit"

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        as_of_date=None,
    ) -> Optional[Dict[str, Any]]:
        from src.config.settings import (
            VCP_EMA_SLOW, VCP_EMA_FAST, VCP_EMA_SLOW_RISING_BARS,
            VCP_MONTHLY_GAIN_PCT, VCP_HIGH52W_THRESHOLD,
            VCP_CONSOLIDATION_BARS, VCP_ATR_CONTRACTION_RATIO,
            VCP_TIGHT_CLOSE_BARS, VCP_TIGHT_CLOSE_RANGE_PCT,
            VCP_VOLUME_DRY_RATIO, VCP_VOLUME_SURGE_RATIO,
            VCP_MAX_DAYS, VCP_PRIORITY,
            MIN_LIQUIDITY_USD, MIN_PRICE,
        )

        try:
            # Need 252 bars for EMA200 + 52W high
            if len(df) < 252:
                return None

            if "Open" not in df.columns or "High" not in df.columns or "Low" not in df.columns:
                return None

            close = df["Close"].astype(float)
            high = df["High"].astype(float)
            low = df["Low"].astype(float)
            volume = df["Volume"].astype(float)

            last_close = float(close.iloc[-1])
            last_volume = float(volume.iloc[-1])

            # Price and liquidity filters
            if last_close < MIN_PRICE:
                return None
            avg_vol_20 = float(volume.rolling(20).mean().iloc[-1])
            if avg_vol_20 <= 0 or avg_vol_20 * last_close < MIN_LIQUIDITY_USD:
                return None

            # ─── Step 1: Trend filter ───────────────────────────────────────────
            ema200 = close.ewm(span=VCP_EMA_SLOW, adjust=False).mean()
            ema200_now = float(ema200.iloc[-1])
            ema200_prev = float(ema200.iloc[-VCP_EMA_SLOW_RISING_BARS - 1])

            if last_close <= ema200_now:
                return None  # Price not above 200 EMA

            if ema200_now <= ema200_prev:
                return None  # 200 EMA not rising

            # ─── Step 2: Momentum filter ────────────────────────────────────────
            # Monthly gain OR near 52-week high (either passes)
            close_21_bars_ago = float(close.iloc[-22]) if len(close) > 22 else float(close.iloc[0])
            monthly_gain = (last_close - close_21_bars_ago) / close_21_bars_ago

            high_52w = float(high.iloc[-253:-1].max())  # 252 bars BEFORE today (no look-ahead)
            near_52w_high = last_close >= high_52w * (1 - VCP_HIGH52W_THRESHOLD)

            if monthly_gain < VCP_MONTHLY_GAIN_PCT and not near_52w_high:
                return None  # Neither momentum filter passes

            # ─── Step 3: Consolidation detection ───────────────────────────────
            n = VCP_CONSOLIDATION_BARS
            tight = VCP_TIGHT_CLOSE_BARS

            if len(df) < n + tight + 21:
                return None

            # ATR contraction: compare current ATR14 vs ATR14 from 20 bars ago
            def atr14(df_slice):
                h = df_slice["High"].astype(float)
                l = df_slice["Low"].astype(float)
                c = df_slice["Close"].astype(float)
                tr = pd.concat([
                    h - l,
                    (h - c.shift(1)).abs(),
                    (l - c.shift(1)).abs(),
                ], axis=1).max(axis=1)
                return tr.rolling(14).mean().iloc[-1]

            atr_current = atr14(df)
            atr_past = atr14(df.iloc[:-20])
            if pd.isna(atr_current) or pd.isna(atr_past) or atr_past <= 0:
                return None
            if atr_current >= atr_past * VCP_ATR_CONTRACTION_RATIO:
                return None  # ATR not contracting enough

            # 3-day tight close range (exclude today — today is breakout bar)
            tight_window = close.iloc[-(tight + 1):-1]  # tight bars before today
            tight_max = float(tight_window.max())
            tight_min = float(tight_window.min())
            if tight_min <= 0:
                return None
            if (tight_max - tight_min) / tight_min > VCP_TIGHT_CLOSE_RANGE_PCT:
                return None  # Last 3 bars too wide — not a tight base

            # Volume drying up: last N bars avg volume < VCP_VOLUME_DRY_RATIO × 20d avg
            dry_vol_window = volume.iloc[-(n + 1):-1]  # n bars before today
            dry_vol_avg = float(dry_vol_window.mean())
            if dry_vol_avg >= avg_vol_20 * VCP_VOLUME_DRY_RATIO:
                return None  # Volume not drying up

            # ─── Step 4: Breakout ───────────────────────────────────────────────
            # Consolidation window: n bars before today
            consolidation = df.iloc[-(n + 1):-1]
            consol_high = float(consolidation["Close"].max())
            consol_low = float(consolidation["Low"].min())

            if last_close <= consol_high:
                return None  # No breakout yet

            # Volume surge on breakout bar
            if last_volume < avg_vol_20 * VCP_VOLUME_SURGE_RATIO:
                return None  # Breakout lacks volume confirmation

            # ─── Build signal ───────────────────────────────────────────────────
            entry_price = last_close
            stop_price = consol_low  # Invalidation: consolidation low breaks → exit

            if stop_price >= entry_price or stop_price <= 0:
                return None  # Invalid risk geometry

            # Score: based on monthly gain, volume ratio, ATR contraction
            vol_ratio = last_volume / max(avg_vol_20, 1)
            atr_contraction = 1 - (atr_current / atr_past)
            score = round(
                min(100, (monthly_gain * 100) * 0.4 + min(vol_ratio, 5) * 5 + atr_contraction * 20),
                1,
            )

            return {
                "Ticker": ticker,
                "Strategy": self.name,
                "Direction": "LONG",
                "Priority": VCP_PRIORITY,
                "Close": round(last_close, 2),
                "Price": round(last_close, 2),
                "Entry": round(entry_price, 2),
                "StopLoss": round(stop_price, 2),
                "StopPrice": round(stop_price, 2),
                "Target": None,                    # Trailing exit — no fixed target
                "ConsolHigh": round(consol_high, 2),
                "ConsolLow": round(consol_low, 2),
                "MonthlyGain": round(monthly_gain * 100, 1),
                "VolumeRatio": round(vol_ratio, 2),
                "ATRContraction": round(atr_contraction * 100, 1),
                "Score": score,
                "Volume": int(last_volume),
                "Date": as_of_date if as_of_date is not None else df.index[-1],
                "AsOfDate": as_of_date if as_of_date is not None else df.index[-1],
                "MaxDays": VCP_MAX_DAYS,
            }

        except Exception:
            return None

    def get_exit_conditions(
        self,
        position: Dict[str, Any],
        df: pd.DataFrame,
        current_date=None,
    ) -> Optional[Dict[str, Any]]:
        """
        Exit when:
        1. Hard stop: Low <= consolidation low (stop_price)
        2. EMA10 trail: 2 consecutive closes below EMA10
        3. MaxDays exceeded (handled by backtester)
        """
        from src.config.settings import VCP_EMA_FAST, VCP_TRAIL_CONSECUTIVE

        try:
            close = df["Close"].astype(float)
            low = df["Low"].astype(float)
            last_close = float(close.iloc[-1])
            last_low = float(low.iloc[-1])

            stop_price = position.get("stop_price") or position.get("StopLoss")
            if stop_price is None:
                stop_price = position.get("metadata", {}).get("StopLoss")

            # 1. Hard stop: Low hits consolidation low
            if stop_price is not None and last_low <= float(stop_price):
                return {"reason": "consolidation_low_stop", "exit_price": float(stop_price)}

            # 2. EMA10 trailing exit (2 consecutive closes below EMA10)
            if len(close) >= VCP_EMA_FAST:
                ema10 = close.ewm(span=VCP_EMA_FAST, adjust=False).mean()
                last_ema = float(ema10.iloc[-1])
                prev_ema = float(ema10.iloc[-2]) if len(ema10) >= 2 else last_ema
                prev_close = float(close.iloc[-2]) if len(close) >= 2 else last_close

                # Both today AND yesterday closed below EMA10 → momentum failed
                if last_close < last_ema and prev_close < prev_ema:
                    return {"reason": f"ema{VCP_EMA_FAST}_trail_2bar", "exit_price": last_close}

        except Exception:
            pass

        return None
