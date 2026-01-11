import numpy as np
import pandas as pd


def calculate_ema_slope(series, lookback=10):
    """
    Calculates percentage slope over lookback period
    """
    if len(series) < lookback:
        return 0.0
    return (series.iloc[-1] - series.iloc[-lookback]) / series.iloc[-lookback]


def score_52week_high_stock(row):
    """
    Calculates pre-buy score for 52-week high breakout stocks
    """

    # ----------------------------
    # 1️⃣ HARD FILTERS
    # ----------------------------
    if not (0 >= row["PctFrom52High"] >= -8):
        return None

    if not (row["EMA20"] > row["EMA50"] > row["EMA200"]):
        return None

    if row["VolumeRatio"] < 1.2:
        return None

    if row["RSI14"] > 75:
        return None

    # ----------------------------
    # 2️⃣ BASE SCORE
    # ----------------------------

    # Price proximity (closer to high = better)
    price_score = abs(row["PctFrom52High"]) * 0.4

    # EMA structure score (binary, institutional trend)
    ema_structure_score = 10 * 0.4

    # Volume confirmation (capped)
    volume_score = min(row["VolumeRatio"], 3) * 10 * 0.2

    base_score = price_score + ema_structure_score + volume_score

    # ----------------------------
    # 3️⃣ MOMENTUM BOOST
    # ----------------------------

    ema200_slope = row.get("EMA200Slope", 0)
    price_momentum_5d = row.get("PriceMomentum5D", 0)

    momentum_boost = min(ema200_slope + price_momentum_5d, 0.10)

    # ----------------------------
    # 4️⃣ FINAL SCORE
    # ----------------------------
    final_score = round(base_score * (1 + momentum_boost), 2)

    return final_score
