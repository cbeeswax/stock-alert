import pandas as pd
from src.data.market import get_historical_data
from src.data.indicators import compute_ema_incremental, compute_rsi


def check_consolidation_breakout(ticker, lookback=20):
    """
    Detects consolidation breakout:
    - Stock has been trading in a tight range for `lookback` days (<5% price range)
    - Breaks above the recent high with volume confirmation
    - EMA trend confirmation and RSI filter
    Returns a dict with breakout info and score if valid, else None
    """
    try:
        df = get_historical_data(ticker)
        if df.empty or "Close" not in df.columns:
            return None

        df = df.copy()
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
        df = df.dropna(subset=["Close"])  # Drop rows where Close is NaN

        # Need at least lookback+1 rows for consolidation and additional rows for momentum
        if len(df) < max(lookback + 1, 6):
            return None

        # EMA trend
        ema_df = compute_ema_incremental(ticker)
        if ema_df.empty:
            return None
        ema20 = ema_df["EMA20"].iloc[-1]
        ema50 = ema_df["EMA50"].iloc[-1]
        ema200 = ema_df["EMA200"].iloc[-1]

        # Consolidation: price range < 5% over lookback (excluding today)
        recent = df["Close"].iloc[-lookback-1:-1]  # Exclude today from consolidation range
        max_close = recent.max()
        min_close = recent.min()
        if (max_close - min_close) / min_close * 100 > 5:
            return None  # Not a tight range

        # Breakout today
        close_today = df["Close"].iloc[-1]
        if close_today <= max_close:
            return None  # No breakout yet

        # Volume confirmation
        avg_vol = df["Volume"].rolling(lookback).mean().iloc[-1]
        vol_ratio = df["Volume"].iloc[-1] / max(avg_vol, 1)
        if vol_ratio < 1.2:
            return None

        # RSI
        rsi14 = compute_rsi(df["Close"], period=14).iloc[-1]
        if rsi14 > 75:
            return None

        # ----------------------------
        # Score calculation
        # ----------------------------
        price_score = ((close_today - max_close) / max_close * 100) * 0.4
        ema_score = 10 * 0.4 if ema20 > ema50 > ema200 else 0
        vol_score = min(vol_ratio, 3) * 10 * 0.2
        base_score = price_score + ema_score + vol_score

        # EMA200 slope and short-term price momentum for momentum boost
        ema200_slope = 0
        price_momentum_5d = 0
        if len(ema_df) >= 6 and len(df) >= 6:
            ema200_slope = (ema200 - ema_df["EMA200"].iloc[-6]) / ema200 if ema200 != 0 else 0
            price_momentum_5d = (close_today - df["Close"].iloc[-6]) / df["Close"].iloc[-6]
        momentum_boost = min(ema200_slope + price_momentum_5d, 0.1)  # capped at 10%

        final_score = round(base_score * (1 + momentum_boost), 2)

        return {
            "Ticker": ticker,
            "Close": round(close_today, 2),
            "RangeLow": round(min_close, 2),
            "RangeHigh": round(max_close, 2),
            "VolumeRatio": round(vol_ratio, 2),
            "EMA20": round(ema20, 2),
            "EMA50": round(ema50, 2),
            "EMA200": round(ema200, 2),
            "RSI14": round(rsi14, 2),
            "Score": final_score
        }

    except Exception as e:
        print(f"⚠️ [consolidation_breakout] Error for {ticker}: {e}")
        return None
