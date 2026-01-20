import pandas as pd
import yfinance as yf
from utils.market_data import get_historical_data
from utils.ledger_utils import update_highs_ledger
from utils.ema_utils import compute_ema_incremental, compute_rsi


def check_new_high(ticker):
    """
    Checks if current closing price is a new 52-week high and applies strategy filters:
    - Volume spike (relative to 50-day average)
    - Trend confirmation via EMA20 > EMA50
    - RSI for overbought/oversold
    Returns a dict with ticker info and score if signal detected, else None.
    """
    try:
        df = get_historical_data(ticker)
        if df.empty or "Close" not in df.columns:
            return None

        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
        df = df.dropna(subset=["Close"])  # Drop rows where Close is NaN

        # --- Check 52-week high ---
        # Exclude today to check if today breaks above previous highs
        max_close_previous = df["Close"].iloc[:-1].max()
        close_today = df["Close"].iloc[-1]
        if close_today <= max_close_previous:
            return None  # no new high

        # --- Trend indicators (reuse EMA logic if available) ---
        ema_df = compute_ema_incremental(ticker)
        if ema_df.empty:
            return None

        ema20 = ema_df["EMA20"].iloc[-1]
        ema50 = ema_df["EMA50"].iloc[-1]

        # --- Volume ratio ---
        df["AvgVolume50"] = df["Volume"].rolling(50).mean()
        volume_ratio = df["Volume"].iloc[-1] / max(df["AvgVolume50"].iloc[-1], 1)

        # --- RSI ---
        rsi14 = compute_rsi(df["Close"], period=14).iloc[-1]

        # --- Scoring ---
        score = 0
        score += 2 if volume_ratio >= 1.5 else 1
        score += 2 if ema20 > ema50 else 0
        score += 1 if 50 < rsi14 < 70 else 0  # RSI moderate = healthy breakout

        # --- Signal summary ---
        info = yf.Ticker(ticker).info
        name = info.get("shortName", ticker)
        date = df.index[-1]

        update_highs_ledger(ticker, name, close_today, date)

        return {
            "Ticker": ticker,
            "Company": name,
            "Close": round(close_today, 2),
            "HighDate": str(date.date()),
            "VolumeRatio": round(volume_ratio, 2),
            "EMA20": round(ema20, 2),
            "EMA50": round(ema50, 2),
            "RSI14": round(rsi14, 2),
            "Trend": "Uptrend" if ema20 > ema50 else "No Uptrend",
            "Score": score
        }

    except Exception as e:
        print(f"⚠️ [highs.py] Unexpected error for {ticker}: {e}")
        return None
