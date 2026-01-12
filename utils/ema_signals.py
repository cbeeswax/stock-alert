import pandas as pd
from utils.ema_utils import compute_ema_incremental, compute_rsi

def get_ema_signals(ticker):
    df = compute_ema_incremental(ticker)
    if df.empty or len(df) < 220:
        return None

    df = df.copy()

    df["EMA200_slope"] = (df["EMA200"] - df["EMA200"].shift(20)) / df["EMA200"]
    df["AvgVolume20"] = df["Volume"].rolling(20).mean()
    df["VolumeRatio"] = df["Volume"] / df["AvgVolume20"]
    df["RSI14"] = compute_rsi(df["Close"], 14)
    df["PriceMomentum5"] = (df["Close"] - df["Close"].shift(5)) / df["Close"].shift(5)

    df["BullishCross"] = (
        (df["EMA20"] > df["EMA50"]) &
        (df["EMA20"].shift(1) <= df["EMA50"].shift(1))
    )

    recent_cross = df["BullishCross"] & (df.index >= df.index[-15])

    ema50_above_ema200_recent = (
        (df["EMA50"] > df["EMA200"]).rolling(10).max().astype(bool)
    )

    volume_confirmed = df["VolumeRatio"].rolling(3).max() >= 1.1

    mask = (
        recent_cross &
        ema50_above_ema200_recent &
        (df["EMA200_slope"] > -0.002) &
        volume_confirmed &
        df["RSI14"].between(45, 72)
    )

    df_filtered = df[mask]
    if df_filtered.empty:
        return None

    signal = df_filtered.iloc[-1]
    current_price = df.iloc[-1]["Close"]

    pct_above_cross = (current_price - signal["Close"]) / signal["Close"] * 100
    pct_above_ema200 = (current_price - signal["EMA200"]) / signal["EMA200"] * 100
    pct_above_ema20 = (current_price - signal["EMA20"]) / signal["EMA20"] * 100

    # 🔒 Pullback safety filter
    if not (2 <= pct_above_cross <= 15 and 1 <= pct_above_ema200 <= 18):
        return None

    if pct_above_ema20 > 8:
        return None

    score = compute_momentum_adjusted_score(signal, pct_above_cross, pct_above_ema200)

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


def compute_momentum_adjusted_score(today, pct_cross, pct_ema200):
    base = (
        (pct_cross * 0.4) +
        (pct_ema200 * 0.4) +
        (min(today["VolumeRatio"], 3) * 10 * 0.2)
    )

    momentum = min(today["EMA200_slope"] + today["PriceMomentum5"], 0.1)
    return round(base * (1 + momentum), 2)
