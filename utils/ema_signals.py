import pandas as pd
from utils.ema_utils import compute_ema_incremental

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

    current_price = df.iloc[-1]["Close"]
    current_volume = df.iloc[-1]["Volume"]
    avg_volume = df.iloc[-1]["AvgVolume20"]

    if current_volume < 1.2 * avg_volume:
        return None

    for i in range(-20, 0):
        today = df.iloc[i]
        yesterday = df.iloc[i - 1]

        if any(pd.isna([today["EMA20"], today["EMA50"], today["EMA200"], today["EMA200_slope"]])):
            continue

        crossed = yesterday["EMA20"] <= yesterday["EMA50"] and today["EMA20"] > today["EMA50"]
        if not crossed:
            continue

        if today["EMA50"] <= today["EMA200"]:
            continue

        if today["EMA200_slope"] <= 0:
            continue

        # --- Improvement1: Additional filter example (RSI < 70) ---
        if not improvement1(today, df):
            continue

         # --- RSI Filter ---
        if not rsi_filter(df, i):
            continue

        crossover_price = today["Close"]
        pct_above_cross = (current_price - crossover_price) / crossover_price * 100
        pct_above_ema200 = (current_price - today["EMA200"]) / today["EMA200"] * 100

        if not (5 <= pct_above_cross <= 10 and 5 <= pct_above_ema200 <= 10):
            continue

        # --- Momentum-adjusted scoring ---
        score = compute_momentum_adjusted_score(today, pct_above_cross, pct_above_ema200, current_volume, avg_volume, df)

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
            "VolumeRatio": round(current_volume / avg_volume, 2),
            "Score": score,
        }

    return None

# --- RSI Filter ---
def rsi_filter(df, index, period=14, rsi_threshold=70):
    """
    Returns True if RSI < rsi_threshold
    """
    if index < period:
        return True  # Not enough data to calculate RSI, allow it by default

    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Check current RSI
    current_rsi = rsi.iloc[index]
    if pd.isna(current_rsi):
        return True  # Treat NaN as pass
    return current_rsi < rsi_threshold

def compute_momentum_adjusted_score(today, pct_cross, pct_ema200, current_vol, avg_vol, df):
    """
    Momentum-adjusted scoring:
    - Base score: weighted pct_above_cross, pct_above_ema200, volume ratio
    - Momentum boost: EMA200 slope + 5-day price change
    """
    # Base score (existing logic)
    base_score = (pct_cross * 0.4) + (pct_ema200 * 0.4) + (min(current_vol/avg_vol, 3)*10*0.2)

    # Momentum components
    ema_slope_factor = today["EMA200_slope"] / today["EMA200"]  # long-term trend strength
    price_momentum_factor = (today["Close"] - df["Close"].shift(5).iloc[today.name]) / df["Close"].shift(5).iloc[today.name]

    # Normalize & cap momentum to avoid extreme boosts
    momentum_factor = min(ema_slope_factor + price_momentum_factor, 0.1)  # cap at 10%
    
    # Final score
    final_score = round(base_score * (1 + momentum_factor), 2)
    return final_score
