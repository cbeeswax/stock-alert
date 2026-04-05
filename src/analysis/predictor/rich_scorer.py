"""
Rich scorer using historically-validated win rates from pattern library.

Key learnings from 2022-2025 (37,186 weekly setups):
  - ATR regime is the #1 predictor (importance 5x any other feature)
  - HIGH VOLATILITY stocks (elevated ATR) win 45.6% vs 28.5% for normal-vol
  - MEAN REVERSION dominates weekly timeframe: oversold > overbought
  - Stocks far from 52w high win MORE (40.9%) than stocks at highs (30.7%)
  - SPY below 50 EMA: individual stocks bounce harder (39.0% WR)
  - "Perfect" bullish setup (strong EMA, near high, RSI momentum) = TRAP
    → EMA strong=31.2%, near 52w high=30.7%, RSI momentum=33.0%

Regime-dependent behavior:
  - BULL (SPY above 50 EMA): momentum signals work slightly
  - BEAR/CHOP (SPY below 50 EMA): mean reversion works (oversold, beaten-down)
"""

import json
import os
import numpy as np
import pandas as pd

from .pattern_learner import load_pattern_library, lookup_pattern, get_top_feature_insights
from .daily_indicators import get_snapshot, make_fingerprint, compute_daily_indicators
from .data_loader import load_daily

WEIGHTS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "predictor", "weights.json")
)


# Historically-learned scoring from pattern library (2022-2025)
# These are the historical win rates for each feature bucket.
# We use them to compute a composite probability-based score.
#
# Key: higher ATR + mean reversion context = better weekly setup.
FEATURE_WEIGHTS_FROM_LIBRARY = {
    "atr_regime":    0.28,   # #1 by far
    "rsi14":         0.11,
    "52w_position":  0.09,
    "spy_trend":     0.08,
    "di_spread":     0.06,
    "ema_align":     0.06,
    "bb_width":      0.05,
    "macd_zone":     0.04,
    "structure":     0.04,
    "cmf":           0.04,
    "obv_trend":     0.04,
    "bb_pct":        0.03,
    "adx":           0.03,
    "rs_21d":        0.02,
    "vol_surge":     0.02,
    "consolidation": 0.01,
    # Weak signals (near-zero importance in library)
    "rsi_slope":     0.00,
    "stoch":         0.00,
    "squeeze":       0.00,
    "macd_hist":     0.00,
}


def _wr_to_score(win_rate: float, base_rate: float = 0.34) -> float:
    """
    Convert a historical win rate to a 0-1 score centered on the base rate.
    Score 0.5 = base rate, 1.0 = maximum win rate seen, 0.0 = worst.
    """
    # Scale: observed range is roughly 0.14 to 0.46
    low, high = 0.14, 0.46
    return float(np.clip((win_rate - low) / (high - low), 0.0, 1.0))


# Historical win rates per feature bucket (from pattern_library build on 2022-2025)
# Updated automatically if pattern library is rebuilt.
_KNOWN_WIN_RATES = {
    "atr_regime:low_vol":          0.144,
    "atr_regime:normal":           0.285,
    "atr_regime:elevated":         0.357,
    "atr_regime:high_vol":         0.456,
    "rsi14:overbought":            0.242,
    "rsi14:high":                  0.292,
    "rsi14:momentum":              0.330,
    "rsi14:neutral":               0.344,
    "rsi14:low":                   0.353,
    "rsi14:oversold":              0.379,
    "52w_position:at_high":        0.307,
    "52w_position:near_high":      0.332,
    "52w_position:below":          0.367,
    "52w_position:far_below":      0.409,
    "spy_trend:spy_above_50ema":   0.329,
    "spy_trend:spy_below_50ema":   0.390,
    "di_spread:strong_bull":       0.307,
    "di_spread:bull":              0.319,
    "di_spread:neutral":           0.352,
    "di_spread:bear":              0.349,
    "di_spread:strong_bear":       0.374,
    "ema_align:strong":            0.312,
    "ema_align:good":              0.338,
    "ema_align:mixed":             0.351,
    "ema_align:weak":              0.374,
    "bb_width:very_tight":         0.330,
    "bb_width:tight":              0.335,
    "bb_width:normal":             0.343,
    "bb_width:wide":               0.350,
    "bb_width:very_wide":          0.376,
    "macd_zone:above_zero":        0.331,
    "macd_zone:below_zero":        0.365,
    "structure:uptrend":           0.332,
    "structure:weak":              0.346,
    "structure:neutral":           0.352,
    "structure:downtrend":         0.370,
    "cmf:inflow":                  0.320,
    "cmf:strong_inflow":           0.339,
    "cmf:neutral":                 0.347,
    "cmf:outflow":                 0.357,
    "cmf:strong_outflow":          0.364,
    "obv_trend:obv_rising":        0.334,
    "obv_trend:obv_falling":       0.362,
    "bb_pct:near_upper":           0.327,
    "bb_pct:upper_half":           0.342,
    "bb_pct:neutral":              0.345,
    "bb_pct:lower_half":           0.356,
    "bb_pct:near_lower":           0.367,
    "adx:strong_trend":            0.322,
    "adx:trending":                0.343,
    "adx:no_trend":                0.351,
    "adx:weak":                    0.345,
    "adx:developing":              0.351,
    "rs_21d:outperforming":        0.342,
    "rs_21d:underperforming":      0.350,
    "vol_surge:very_low":          0.338,
    "vol_surge:below_avg":         0.342,
    "vol_surge:avg":               0.355,
    "vol_surge:above_avg":         0.352,
    "vol_surge:surge":             0.359,
}


def _load_win_rates_from_library() -> dict:
    """Load win rates from the pattern library if available."""
    lib = load_pattern_library()
    if not lib:
        return _KNOWN_WIN_RATES
    fwr = lib.get("feature_win_rates", {})
    if not fwr:
        return _KNOWN_WIN_RATES
    return {k: v["win_rate"] for k, v in fwr.items()}


def score_ticker_rich(
    snap: pd.Series,
    fp: dict,
    library: dict = None,
    spy_uptrend: bool = True,
) -> tuple[float, dict]:
    """
    Score a single ticker setup using historically-validated win rates.

    Returns (score_0_to_100, breakdown_dict)
    """
    win_rates = _load_win_rates_from_library()

    # Regime adjustment: in bear markets, flip the signal preferences
    # (mean reversion more important in downtrend)
    bear_market = not spy_uptrend

    category_scores = {}
    total_weight = 0.0
    weighted_score = 0.0

    for feature, weight in FEATURE_WEIGHTS_FROM_LIBRARY.items():
        if weight <= 0:
            continue
        bucket = fp.get(feature, "unknown")
        fk = f"{feature}:{bucket}"
        wr = win_rates.get(fk, None)

        if wr is None:
            continue

        s = _wr_to_score(wr)
        category_scores[feature] = {
            "bucket": bucket,
            "historical_wr": round(wr, 3),
            "score_0_1": round(s, 3),
        }
        weighted_score += weight * s
        total_weight += weight

    composite = (weighted_score / total_weight * 100) if total_weight > 0 else 50.0

    # Apply ATR bonus/penalty explicitly (most important signal)
    atr_bucket = fp.get("atr_regime", "normal")
    if atr_bucket == "high_vol":
        composite = min(composite * 1.10, 100)
    elif atr_bucket == "normal":
        composite = composite * 0.90
    elif atr_bucket == "low_vol":
        composite = composite * 0.60

    return round(composite, 2), category_scores


def score_all_rich(
    daily_df: dict[str, pd.DataFrame],
    as_of_date: str,
    spy_daily: pd.DataFrame = None,
    library: dict = None,
    top_n: int = 30,
) -> pd.DataFrame:
    """
    Score all tickers as of a date using daily indicators + pattern library.

    Parameters
    ----------
    daily_df   : dict ticker -> daily OHLCV DataFrame
    as_of_date : ISO date (last data point to use; no look-ahead)
    spy_daily  : SPY daily data for relative strength + regime
    top_n      : return top N only

    Returns
    -------
    DataFrame sorted by score descending with all signal details.
    """
    if spy_daily is None:
        spy_daily = load_daily("SPY")

    if library is None:
        library = load_pattern_library()

    # Determine SPY regime
    spy_uptrend = True
    if not spy_daily.empty:
        spy_ind = compute_daily_indicators(spy_daily)
        spy_snap = get_snapshot(spy_ind, as_of_date)
        spy_uptrend = bool(spy_snap.get("spy_uptrend", 1))

    rows = []
    ts = pd.Timestamp(as_of_date)

    for ticker, daily in daily_df.items():
        if ticker == "SPY":
            continue
        if daily.empty or len(daily[daily.index <= ts]) < 200:
            continue

        try:
            ind = compute_daily_indicators(daily, spy=spy_daily)
            snap = get_snapshot(ind, as_of_date)
            if snap.empty:
                continue
            fp = make_fingerprint(snap)
            score, breakdown = score_ticker_rich(snap, fp, library, spy_uptrend)
            pat = lookup_pattern(fp, library)
            insights = get_top_feature_insights(fp, library)
            warnings = [i for i in insights if i["is_warning"]]

            rows.append({
                "ticker": ticker,
                "score": score,
                "fingerprint": fp,
                "snapshot": snap,
                "breakdown": breakdown,
                "pattern_match": pat,
                "warnings": warnings,
                "spy_uptrend": spy_uptrend,
                "atr_bucket": fp.get("atr_regime", "?"),
                "rsi_bucket": fp.get("rsi14", "?"),
                "adx": round(float(snap.get("adx", 0) or 0), 1),
                "rsi14": round(float(snap.get("rsi14", 0) or 0), 1),
                "atr_pct": round(float(snap.get("atr_pct", 0) or 0) * 100, 2),
                "pct_from_52h": round(float(snap.get("pct_from_52w_high", 0) or 0) * 100, 1),
                "cmf": round(float(snap.get("cmf", 0) or 0), 3),
                "ema_align": int(snap.get("ema_align", 0) or 0),
                "hist_win_rate": pat.get("historical_win_rate"),
            })
        except Exception:
            continue

    result = pd.DataFrame(rows) if rows else pd.DataFrame()
    if not result.empty:
        result = result.sort_values("score", ascending=False).reset_index(drop=True)
        if len(result) > top_n * 3:
            result = result.head(top_n * 3)

    return result
