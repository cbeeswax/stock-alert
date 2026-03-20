"""
GapReversal_Position Strategy
==============================
Breakaway Gap / Reversal Gap strategy on daily charts.

Long  setup:  stock gaps UP  after a strong decline  + smoothed RSI < 10  + weekly trend UP
Short setup:  stock gaps DOWN after a strong rally   + smoothed RSI > 90  + weekly trend DOWN

The key novelty: RSI(10) is computed on the 21-day EMA of price, not raw close.
This produces far fewer but higher-conviction extreme readings (< 10 or > 90).

Stop loss:  Gap fill level (prior day's close) — gap filled = setup invalidated.
Exit:       Trailing EMA21 — hold while close stays on the right side of EMA21.
"""
import pandas as pd
from typing import Optional, Dict, Any

from src.strategies.base import BaseStrategy
from src.ta.indicators.momentum import smoothed_rsi
from src.ta.indicators.moving_averages import ema
from src.ta.indicators.gaps import (
    gap_pct, is_gap_up, is_gap_down, gap_fill_level,
)
from src.ta.indicators.volatility import atr_latest


class GapReversalPosition(BaseStrategy):
    """
    Breakaway Gap Reversal strategy.

    Scans for:
        Long:  gap_up AND smoothed_rsi(21, 10) < rsi_oversold AND weekly trend UP
        Short: gap_down AND smoothed_rsi(21, 10) > rsi_overbought AND weekly trend DOWN

    Exit conditions (checked by backtester and live monitor):
        - Gap fill: Low of any bar falls to/below gap_fill_level → stop out
        - EMA21 cross: Close crosses EMA21 against the trade direction → exit
        - MaxDays: 120-day hard cap
    """

    name = "GapReversal_Position"
    description = "Breakaway gap reversal on daily chart, smoothed RSI extreme, weekly trend filter"

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        as_of_date=None,
    ) -> Optional[Dict[str, Any]]:
        from src.config.settings import (
            GAP_REVERSAL_MIN_GAP_PCT,
            GAP_REVERSAL_RSI_OVERSOLD,
            GAP_REVERSAL_RSI_OVERBOUGHT,
            GAP_REVERSAL_EMA_PERIOD,
            GAP_REVERSAL_RSI_PERIOD,
            GAP_REVERSAL_DIRECTION,
            GAP_REVERSAL_WEEKLY_TF_FILTER,
            GAP_REVERSAL_MAX_DAYS,
            GAP_REVERSAL_PRIORITY,
            MIN_LIQUIDITY_USD,
            MIN_PRICE,
        )

        try:
            # Need enough history for smoothed RSI (EMA21 needs warmup, then RSI10 on top)
            min_bars = GAP_REVERSAL_EMA_PERIOD + GAP_REVERSAL_RSI_PERIOD + 30
            if len(df) < min_bars:
                return None

            if "Open" not in df.columns:
                return None

            close = df["Close"]
            last_close = float(close.iloc[-1])
            last_open = float(df["Open"].iloc[-1])
            volume = df["Volume"]

            # Price and liquidity filters
            if last_close < MIN_PRICE:
                return None
            avg_vol = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else 0
            if avg_vol * last_close < MIN_LIQUIDITY_USD:
                return None

            # Smoothed RSI on EMA21 series
            srsi = smoothed_rsi(close, GAP_REVERSAL_EMA_PERIOD, GAP_REVERSAL_RSI_PERIOD)
            current_srsi = float(srsi.iloc[-1])
            if pd.isna(current_srsi):
                return None

            # Gap detection (using current bar — no look-ahead)
            gap_up = bool(is_gap_up(df, GAP_REVERSAL_MIN_GAP_PCT).iloc[-1])
            gap_dn = bool(is_gap_down(df, GAP_REVERSAL_MIN_GAP_PCT).iloc[-1])
            fill_level = float(gap_fill_level(df).iloc[-1])  # = prior close

            direction = GAP_REVERSAL_DIRECTION  # "long", "short", or "both"

            is_long = gap_up and current_srsi < GAP_REVERSAL_RSI_OVERSOLD
            is_short = gap_dn and current_srsi > GAP_REVERSAL_RSI_OVERBOUGHT

            if direction == "long":
                is_short = False
            elif direction == "short":
                is_long = False

            if not (is_long or is_short):
                return None

            # Higher-timeframe weekly trend filter
            if GAP_REVERSAL_WEEKLY_TF_FILTER:
                try:
                    from src.ta.timeframes import get_weekly_trend
                    weekly_trend = get_weekly_trend(ticker, as_of_date)
                    if is_long and weekly_trend == "DOWN":
                        return None
                    if is_short and weekly_trend == "UP":
                        return None
                except Exception:
                    pass  # If weekly data unavailable, allow trade

            # Entry at today's open (gap open price)
            entry_price = last_open
            trade_direction = "LONG" if is_long else "SHORT"

            # Stop loss = gap fill level (prior close)
            stop_loss = fill_level

            # Score: how extreme is the RSI? More extreme = higher conviction
            if is_long:
                # Lower RSI = stronger oversold = higher score
                score = round(max(0, (GAP_REVERSAL_RSI_OVERSOLD - current_srsi) * 5), 1)
            else:
                # Higher RSI = stronger overbought = higher score
                score = round(max(0, (current_srsi - GAP_REVERSAL_RSI_OVERBOUGHT) * 5), 1)

            # Gap size for info
            gap = float(gap_pct(df).iloc[-1])

            return {
                "Ticker": ticker,
                "Strategy": self.name,
                "Direction": trade_direction,
                "Priority": GAP_REVERSAL_PRIORITY,
                "Close": round(last_close, 2),
                "Price": round(last_close, 2),
                "Entry": round(entry_price, 2),
                "StopLoss": round(stop_loss, 2),
                "StopPrice": round(stop_loss, 2),
                "GapFillLevel": round(fill_level, 2),
                "Target": None,         # Trailing exit — no fixed target
                "SmoothedRSI": round(current_srsi, 2),
                "GapPct": round(gap * 100, 2),
                "Score": score,
                "Volume": int(volume.iloc[-1]),
                "Date": as_of_date if as_of_date is not None else df.index[-1],
                "AsOfDate": as_of_date if as_of_date is not None else df.index[-1],
                "MaxDays": GAP_REVERSAL_MAX_DAYS,
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
        1. Gap fill: any bar's Low <= gap_fill_level (stop, gap invalidated)
        2. EMA21 cross: close crosses EMA21 against trade direction
        3. MaxDays exceeded (handled by backtester)
        """
        from src.config.settings import GAP_REVERSAL_TRAIL_MA

        try:
            close = df["Close"]
            low = df["Low"]
            last_close = float(close.iloc[-1])
            last_low = float(low.iloc[-1])

            direction = position.get("Direction", "LONG")
            gap_fill = position.get("GapFillLevel") or position.get("stop_loss")
            if gap_fill is None:
                gap_fill = position.get("metadata", {}).get("GapFillLevel")

            # 1. Gap fill stop
            if gap_fill is not None:
                if direction == "LONG" and last_low <= float(gap_fill):
                    return {"reason": "gap_fill_stop", "exit_price": float(gap_fill)}
                if direction == "SHORT" and last_close >= float(gap_fill):
                    return {"reason": "gap_fill_stop", "exit_price": float(gap_fill)}

            # 2. EMA21 trailing exit
            trail_ema = ema(close, GAP_REVERSAL_TRAIL_MA)
            last_ema = float(trail_ema.iloc[-1])

            if direction == "LONG" and last_close < last_ema:
                return {"reason": f"trailing_ema{GAP_REVERSAL_TRAIL_MA}", "exit_price": last_close}
            if direction == "SHORT" and last_close > last_ema:
                return {"reason": f"trailing_ema{GAP_REVERSAL_TRAIL_MA}", "exit_price": last_close}

        except Exception:
            pass

        return None
