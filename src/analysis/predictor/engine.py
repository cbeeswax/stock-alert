"""
Select top-N stocks for a given week and compute entry/stop/target.
"""

import pandas as pd
import numpy as np

from .scorer import score_all, load_weights


def _monday_open(ticker_df: pd.DataFrame, week_start: str) -> float:
    """Return the first available open price on or after week_start."""
    ts = pd.Timestamp(week_start)
    fwd = ticker_df[ticker_df.index >= ts]
    if fwd.empty:
        return float("nan")
    return float(fwd.iloc[0]["open"])


def generate_predictions(
    indicators_df: dict[str, pd.DataFrame],
    daily_df: dict[str, pd.DataFrame],
    week_start: str,
    top_n: int = 10,
    risk_reward: float = 2.5,
    atr_stop_mult: float = 1.5,
    weights: dict = None,
) -> list[dict]:
    """
    Generate top-N predictions for the week starting on week_start (Monday).

    Parameters
    ----------
    indicators_df : dict ticker -> weekly DataFrame with indicator columns (built up to week_start - 1 day)
    daily_df      : dict ticker -> daily OHLCV DataFrame (to get Monday open price)
    week_start    : ISO date string for the Monday (e.g. '2026-01-06')
    top_n         : number of stocks to pick
    risk_reward   : R:R ratio for target (target = entry + risk_reward × risk)
    atr_stop_mult : ATR multiplier for stop loss
    weights       : optional weight dict (loads from file if None)

    Returns
    -------
    list of dicts with keys:
        ticker, score, entry, stop, target, risk_pct, atr,
        trend, momentum, strength, volatility, fibonacci, volume
    """
    if weights is None:
        weights = load_weights()

    # Score as of last Friday before week_start
    as_of = (pd.Timestamp(week_start) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    scores = score_all(indicators_df, as_of=as_of, weights=weights)

    if scores.empty:
        return []

    top = scores.head(top_n * 3)  # take extra in case of missing price data

    picks = []
    for _, row in top.iterrows():
        ticker = row["ticker"]
        daily = daily_df.get(ticker, pd.DataFrame())
        if daily.empty:
            continue

        entry = _monday_open(daily, week_start)
        if np.isnan(entry) or entry <= 0:
            continue

        # ATR from weekly indicators
        wdf = indicators_df.get(ticker, pd.DataFrame())
        atr_val = float("nan")
        if not wdf.empty:
            past = wdf[wdf.index < week_start]
            if not past.empty:
                atr_val = float(past.iloc[-1].get("atr14", float("nan")))

        if np.isnan(atr_val) or atr_val <= 0:
            atr_val = entry * 0.02  # fallback: 2% of price

        stop = round(entry - atr_stop_mult * atr_val, 4)
        risk = entry - stop
        if risk <= 0:
            continue
        target = round(entry + risk_reward * risk, 4)
        risk_pct = round(risk / entry * 100, 2)

        picks.append(
            {
                "ticker": ticker,
                "score": round(float(row["score"]), 2),
                "entry": round(entry, 4),
                "stop": stop,
                "target": target,
                "risk_pct": risk_pct,
                "atr": round(atr_val, 4),
                "category_scores": {
                    "trend": round(float(row["trend"]), 3),
                    "momentum": round(float(row["momentum"]), 3),
                    "strength": round(float(row["strength"]), 3),
                    "volatility": round(float(row["volatility"]), 3),
                    "fibonacci": round(float(row["fibonacci"]), 3),
                    "volume": round(float(row["volume"]), 3),
                },
            }
        )

        if len(picks) == top_n:
            break

    return picks
