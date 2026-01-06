import pandas as pd
from utils.ema_utils import compute_ema_incremental

def get_ema_signals(ticker):
    """
    Detects bullish EMA crossover (20>50 while 50>200) within last 20 days.
    Returns a dictionary with ticker info if 5–10% above crossover, else None.
    """
    df = compute_ema_incremental(ticker)
    if df.empty or len(df) < 200:
        return None

    for i in range(-20, 0):
        today = df.iloc[i]
        yesterday = df.iloc[i - 1]
        if any(pd.isna([today["EMA20"], today["EMA50"], today["EMA200"]])):
            continue

        crossed = yesterday["EMA20"] <= yesterday["EMA50"] and today["EMA20"] > today["EMA50"]
        if crossed and today["EMA50"] > today["EMA200"]:
            crossover_price = today["Close"]

            pct_above_cross = round(
                (current_price - crossover_price) / crossover_price * 100, 2
            )

            pct_above_ema200 = round(
                (current_price - today["EMA200"]) / today["EMA200"] * 100, 2
            )

            if (
                5 <= pct_above_cross <= 10
                and 5 <= pct_above_ema200 <= 10
            ):
                return {
                    "ticker": ticker,
                    "CrossoverDate": str(today.name.date()),
                    "CrossoverPrice": round(crossover_price, 2),
                    "CurrentPrice": round(current_price, 2),
                    "PctAboveCrossover": pct_above_cross,
                    "PctAboveEMA200": pct_above_ema200,
                    "EMA20": round(today["EMA20"], 2),
                    "EMA50": round(today["EMA50"], 2),
                    "EMA200": round(today["EMA200"], 2),
                }
    return None
