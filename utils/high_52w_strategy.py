def score_52week_high_stock(row):
    if not (0 >= row["PctFrom52High"] >= -8):
        return None

    if not (row["EMA20"] > row["EMA50"] > row["EMA200"]):
        return None

    if row["VolumeRatio"] < 1.2:
        return None

    if row["RSI14"] > 75:
        return None

    price_score = abs(row["PctFrom52High"]) * 0.4
    ema_score = 10 * 0.4
    volume_score = min(row["VolumeRatio"], 3) * 10 * 0.2

    base = price_score + ema_score + volume_score

    momentum_boost = min(
        row.get("EMA200Slope", 0) + row.get("PriceMomentum5D", 0),
        0.10
    )

    final_score = round(base * (1 + momentum_boost), 2)

    return final_score


def is_52w_watchlist_candidate(row):
    if not (-15 <= row["PctFrom52High"] < -8):
        return False

    if not (row["EMA20"] > row["EMA50"] > row["EMA200"]):
        return False

    if row["RSI14"] >= 80:
        return False

    return True
