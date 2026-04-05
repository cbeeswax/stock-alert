"""Score each ticker using weighted composite of indicator signals."""

import json
import os
import numpy as np
import pandas as pd

DEFAULT_WEIGHTS = {
    "trend": 0.25,      # ema_align + ema9_slope
    "momentum": 0.20,   # rsi_score + roc4 + roc13
    "strength": 0.20,   # adx_score + rs_score
    "volatility": 0.15, # bb_score
    "fibonacci": 0.10,  # fib_score
    "volume": 0.10,     # vol_score + obv_score
}

WEIGHTS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "predictor", "weights.json"
)


def load_weights() -> dict:
    """Load weights from file, falling back to defaults."""
    path = os.path.abspath(WEIGHTS_FILE)
    if os.path.exists(path):
        with open(path) as f:
            loaded = json.load(f)
        # Merge with defaults to handle missing keys
        weights = {**DEFAULT_WEIGHTS, **loaded}
    else:
        weights = dict(DEFAULT_WEIGHTS)
    return _normalize(weights)


def save_weights(weights: dict) -> None:
    path = os.path.abspath(WEIGHTS_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(weights, f, indent=2)


def _normalize(weights: dict) -> dict:
    total = sum(weights.values())
    if total == 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: v / total for k, v in weights.items()}


def _category_scores(row: pd.Series) -> dict:
    """Map indicator columns to category scores (each 0.0–1.0)."""
    def _safe(val):
        if pd.isna(val) or np.isinf(val):
            return 0.0
        return float(np.clip(val, 0.0, 1.0))

    trend = 0.5 * _safe(row.get("ema_align", 0)) + 0.5 * _safe(
        np.clip(row.get("ema9_slope", 0) * 10, 0, 1)  # scale slope %
    )

    rsi_score = _safe(row.get("rsi_score", 0))
    roc4 = _safe(np.clip(row.get("roc4", 0) * 5, 0, 1))
    roc13 = _safe(np.clip(row.get("roc13", 0) * 3, 0, 1))
    momentum = (rsi_score + roc4 + roc13) / 3.0

    adx_s = _safe(row.get("adx_score", 0))
    rs_s = _safe(row.get("rs_score", 0.5))
    strength = 0.5 * adx_s + 0.5 * rs_s

    volatility = _safe(row.get("bb_score", 0))
    fibonacci = _safe(row.get("fib_score", 0))

    vol_s = _safe(row.get("vol_score", 0))
    obv_s = _safe(row.get("obv_score", 0))
    volume = 0.5 * vol_s + 0.5 * obv_s

    return {
        "trend": trend,
        "momentum": momentum,
        "strength": strength,
        "volatility": volatility,
        "fibonacci": fibonacci,
        "volume": volume,
    }


def score_ticker(row: pd.Series, weights: dict = None) -> tuple[float, dict]:
    """
    Return (composite_score, category_breakdown) for a single bar.
    composite_score is 0.0–100.0.
    """
    if weights is None:
        weights = load_weights()
    cats = _category_scores(row)
    composite = sum(weights[k] * cats[k] for k in cats) * 100
    return composite, cats


def score_all(indicators_df: dict[str, pd.DataFrame], as_of: str, weights: dict = None) -> pd.DataFrame:
    """
    Score all tickers as of a specific date.

    Parameters
    ----------
    indicators_df : dict ticker -> DataFrame with indicator columns
    as_of : ISO date string (e.g. '2026-01-03') — use last available row <= this date
    weights : optional weight dict

    Returns
    -------
    DataFrame with columns: ticker, score, trend, momentum, strength, volatility, fibonacci, volume
    """
    if weights is None:
        weights = load_weights()

    rows = []
    ts = pd.Timestamp(as_of)
    for ticker, df in indicators_df.items():
        if df.empty:
            continue
        available = df[df.index <= ts]
        if len(available) < 30:
            continue
        last = available.iloc[-1]
        composite, cats = score_ticker(last, weights)
        rows.append({"ticker": ticker, "score": composite, **cats})

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("score", ascending=False).reset_index(drop=True)
    return result
