import pandas as pd
from utils.ema_utils import compute_ema_incremental, compute_rsi

def get_ema_signals(ticker):
    """
    Detects bullish EMA crossover (20>50 while 50>200) within last 20 days.
    Returns a dictionary with ticker info if 5–10% above crossover, else None.
    """
    df = compute_ema_incremental(ticker)
    if df.empty or len(df) < 210:
        return None

    df = df.copy()
    df["EMA200_slope"] = df["EMA200"] - df["EMA200"].shift(5)
    df["AvgVolume20"] = df["Volume"].rolling(20).mean()
    df["VolumeRatio"] = df["Volume"] / df["AvgVolume20"]
    df["RSI14"] = compute_rsi(df["Close"], period=14)
    df["PriceMomentum5"] = (df["Close"] - df["Close"].shift(5)) / df["Close"].shift(5)

    # --- Vectorized crossover detection ---
    df["BullishCross"] = (df["EMA20"] > df["EMA50"]) & (df["EMA20"].shift(1) <= df["EMA50"].shift(1))

    # --- Vectorized filters ---
    mask = (
        df["BullishCross"] &
        (df["EMA50"] > df["EMA200"]) &
        (df["EMA200_slope"] > 0) &
        (df["VolumeRatio"] >= 1.2) &
        (df["RSI14"] < 70)
    )

    # Only consider last 50 days
    df_filtered = df[mask].tail(40)

    if df_filtered.empty:
        return None

    # Pick the last crossover signal
    today = df_filtered.iloc[-1]
    current_price = df.iloc[-1]["Close"]

    crossover_price = today["Close"]
    pct_above_cross = (current_price - crossover_price) / crossover_price * 100
    pct_above_ema200 = (current_price - today["EMA200"]) / today["EMA200"] * 100

    if not (3 <= pct_above_cross <= 12 and 3 <= pct_above_ema200 <= 12):
        return None

    # --- Momentum-adjusted score ---
    score = compute_momentum_adjusted_score(today, pct_above_cross, pct_above_ema200)

    return {
        "Ticker": ticker,
        "CrossoverDate": str(today.name.date()),
        "CrossoverPrice": round(crossover_price, 2),
        "CurrentPrice": round(current_price, 2),
        "PctAboveCrossover": round(pct_above_cross, 2),
        "PctAboveEMA200": round(pct_above_ema200, 2),
        "EMA20": round(today["EMA20"], 2),
        "EMA50": round(today["EMA50"], 2),
        "EMA200": round(today["EMA200"], 2),
        "VolumeRatio": round(today["VolumeRatio"], 2),
        "Score": score,
    }

# --- RSI filter is now implicit in the vectorized mask ---

# --- Momentum-adjusted scoring ---
def compute_momentum_adjusted_score(today, pct_cross, pct_ema200):
    base_score = (pct_cross * 0.4) + (pct_above_ema200 * 0.4) + (min(today["VolumeRatio"], 3) * 10 * 0.2)
    momentum_factor = min(today["EMA200_slope"] / today["EMA200"] + today["PriceMomentum5"], 0.1)  # capped 10%
    final_score = round(base_score * (1 + momentum_factor), 2)
    return final_score
