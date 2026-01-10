import pandas as pd
from utils.ema_utils import compute_ema_incremental, compute_rsi

def get_ema_signals(ticker):
    """
    Detects bullish EMA20/EMA50 crossover in an established uptrend.
    Designed for large-cap (>$10B) S&P / Nasdaq stocks.
    """

    df = compute_ema_incremental(ticker)
    if df.empty or len(df) < 220:
        return None

    df = df.copy()

    # --- Trend / Momentum metrics ---
    df["EMA200_slope"] = (df["EMA200"] - df["EMA200"].shift(20)) / df["EMA200"]
    df["AvgVolume20"] = df["Volume"].rolling(20).mean()
    df["VolumeRatio"] = df["Volume"] / df["AvgVolume20"]
    df["RSI14"] = compute_rsi(df["Close"], period=14)
    df["PriceMomentum5"] = (df["Close"] - df["Close"].shift(5)) / df["Close"].shift(5)

    # --- EMA crossover detection ---
    df["BullishCross"] = (
        (df["EMA20"] > df["EMA50"]) &
        (df["EMA20"].shift(1) <= df["EMA50"].shift(1))
    )

    # --- Allow EMA50 > EMA200 within recent window ---
    ema50_above_ema200_recent = (
        (df["EMA50"] > df["EMA200"])
        .rolling(10)
        .max()
        .astype(bool)
    )

    # --- Volume confirmation (recent, not exact day) ---
    volume_confirmed = df["VolumeRatio"].rolling(3).max() >= 1.1

    # --- Combined screening mask ---
    mask = (
        df["BullishCross"] &
        ema50_above_ema200_recent &
        (df["EMA200_slope"] > -0.002) &
        volume_confirmed &
        df["RSI14"].between(45, 72)
    )

    # --- Only recent signals ---
    df_filtered = df[mask].tail(40)
    if df_filtered.empty:
        return None

    signal = df_filtered.iloc[-1]
    current_price = df.iloc[-1]["Close"]

    # --- Price location filters ---
    pct_above_cross = (current_price - signal["Close"]) / signal["Close"] * 100
    pct_above_ema200 = (current_price - signal["EMA200"]) / signal["EMA200"] * 100

    if not (2 <= pct_above_cross <= 15 and 1 <= pct_above_ema200 <= 18):
        return None

    score = compute_momentum_adjusted_score(
        signal, pct_above_cross, pct_above_ema200
    )

    return {
        "Ticker": ticker,
        "CrossoverDate": str(signal.name.date()),
        "CrossoverPrice": round(signal["Close"], 2),
        "CurrentPrice": round(current_price, 2),
        "PctAboveCrossover": round(pct_above_cross, 2),
        "PctAboveEMA200": round(pct_above_ema200, 2),
        "EMA20": round(signal["EMA20"], 2),
        "EMA50": round(signal["EMA50"], 2),
        "EMA200": round(signal["EMA200"], 2),
        "RSI14": round(signal["RSI14"], 1),
        "VolumeRatio": round(signal["VolumeRatio"], 2),
        "Score": score,
    }


# --- Momentum-adjusted scoring ---
def compute_momentum_adjusted_score(today, pct_cross, pct_ema200):
    base_score = (
        (pct_cross * 0.4) +
        (pct_ema200 * 0.4) +
        (min(today["VolumeRatio"], 3) * 10 * 0.2)
    )

    momentum_factor = min(
        (today["EMA200_slope"] + today["PriceMomentum5"]),
        0.1
    )

    return round(base_score * (1 + momentum_factor), 2)
