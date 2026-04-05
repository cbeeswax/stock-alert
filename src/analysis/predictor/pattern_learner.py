"""
Pattern Learner — train on 2022-2025 daily OHLCV data.

For every stock, every week in the training period:
  1. Compute daily indicators up to that Friday
  2. Build a fingerprint (discretized indicator state)
  3. Measure: did next week's price close higher than entry? By how much?
  4. Accumulate pattern → outcome statistics

Produces data/predictor/pattern_library.json:
  {
    "patterns": { fingerprint_key: {count, wins, win_rate, avg_pnl, p25_pnl, p75_pnl, conditions} },
    "feature_win_rates": { "feature:value": {count, win_rate, avg_pnl} },
    "feature_importance": { feature_name: importance_score },
    "trained_on": "2022-01-03 to 2025-12-31",
    "total_setups": N
  }
"""

import json
import os
from collections import defaultdict
from itertools import combinations

import numpy as np
import pandas as pd

from .data_loader import available_tickers, load_daily
from .daily_indicators import compute_daily_indicators, get_snapshot, make_fingerprint

PATTERN_LIBRARY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "predictor", "pattern_library.json")
)


def _all_fridays(start: str, end: str) -> list[pd.Timestamp]:
    idx = pd.date_range(start, end, freq="W-FRI")
    return list(idx)


def _next_week_return(daily: pd.DataFrame, this_friday: pd.Timestamp) -> float | None:
    """
    Return next week's % move: (next_friday_close - next_monday_open) / next_monday_open.
    Uses the first available open >= next_monday and close on next_friday (or last available).
    """
    next_monday = this_friday + pd.Timedelta(days=3)
    next_friday = this_friday + pd.Timedelta(days=7)

    entry_bars = daily[daily.index >= next_monday]
    exit_bars = daily[(daily.index >= next_monday) & (daily.index <= next_friday)]

    if entry_bars.empty or exit_bars.empty:
        return None

    entry = float(entry_bars.iloc[0]["open"])
    exit_p = float(exit_bars.iloc[-1]["close"])

    if entry <= 0:
        return None
    return (exit_p - entry) / entry


def build_pattern_library(
    data_dir: str,
    train_start: str = "2022-01-01",
    train_end: str = "2025-12-31",
    min_pattern_count: int = 5,
    win_threshold: float = 0.01,  # 1% weekly gain = win
    verbose: bool = True,
) -> dict:
    """
    Build pattern library by training on all available tickers over train period.

    Returns the library dict (also saved to PATTERN_LIBRARY_PATH).
    """
    tickers = available_tickers()
    if verbose:
        print(f"Training on {len(tickers)} tickers  [{train_start} → {train_end}]")

    # Load SPY once for relative strength
    spy_daily = load_daily("SPY")
    if spy_daily.empty:
        # Try from data_dir directly
        spy_path = os.path.join(data_dir, "SPY.csv")
        if os.path.exists(spy_path):
            spy_daily = pd.read_csv(spy_path, skiprows=[1], index_col=0)
            spy_daily.index = pd.to_datetime(spy_daily.index, format="%Y-%m-%d", errors="coerce")
            spy_daily = spy_daily[spy_daily.index.notna()].sort_index()
            spy_daily.columns = [c.lower() for c in spy_daily.columns]

    fridays = _all_fridays(train_start, train_end)

    # Accumulators
    pattern_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl_sum": 0.0, "pnls": []})
    feature_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl_sum": 0.0})
    pair_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl_sum": 0.0})
    total_setups = 0

    for i, ticker in enumerate(tickers):
        if verbose and i % 25 == 0:
            print(f"  [{i}/{len(tickers)}] processing {ticker}...")

        daily = load_daily(ticker)
        if daily.empty or len(daily) < 250:
            continue

        # Only compute indicators once per ticker
        try:
            ind = compute_daily_indicators(daily, spy=spy_daily)
        except Exception:
            continue

        for friday in fridays:
            # Must have sufficient history before this friday
            hist = ind[ind.index <= friday]
            if len(hist) < 200:
                continue

            snap = hist.iloc[-1]
            if pd.isna(snap.get("ema_align", np.nan)):
                continue

            ret = _next_week_return(daily, friday)
            if ret is None:
                continue

            is_win = int(ret >= win_threshold)
            fp = make_fingerprint(snap)
            fp_key = "|".join(f"{k}={v}" for k, v in sorted(fp.items()))

            # Full fingerprint
            ps = pattern_stats[fp_key]
            ps["count"] += 1
            ps["wins"] += is_win
            ps["pnl_sum"] += ret * 100
            ps["pnls"].append(ret * 100)

            # Individual features
            for feat, val in fp.items():
                fk = f"{feat}:{val}"
                fs = feature_stats[fk]
                fs["count"] += 1
                fs["wins"] += is_win
                fs["pnl_sum"] += ret * 100

            # Feature pairs (2-way interactions)
            feat_items = sorted(fp.items())
            for (f1, v1), (f2, v2) in combinations(feat_items, 2):
                pk = f"{f1}={v1}|{f2}={v2}"
                pa = pair_stats[pk]
                pa["count"] += 1
                pa["wins"] += is_win
                pa["pnl_sum"] += ret * 100

            total_setups += 1

    if verbose:
        print(f"  Done. Total setups: {total_setups:,}  Patterns: {len(pattern_stats):,}")

    # Filter patterns by minimum count
    patterns = {}
    for fp_key, ps in pattern_stats.items():
        if ps["count"] < min_pattern_count:
            continue
        pnls = ps["pnls"]
        patterns[fp_key] = {
            "count": ps["count"],
            "wins": ps["wins"],
            "win_rate": round(ps["wins"] / ps["count"], 4),
            "avg_pnl": round(ps["pnl_sum"] / ps["count"], 3),
            "p25_pnl": round(float(np.percentile(pnls, 25)), 3),
            "p75_pnl": round(float(np.percentile(pnls, 75)), 3),
        }

    # Feature-level win rates
    feature_win_rates = {}
    for fk, fs in feature_stats.items():
        if fs["count"] < 10:
            continue
        feature_win_rates[fk] = {
            "count": fs["count"],
            "win_rate": round(fs["wins"] / fs["count"], 4),
            "avg_pnl": round(fs["pnl_sum"] / fs["count"], 3),
        }

    # Pair win rates (top 500 by count)
    pair_win_rates = {}
    top_pairs = sorted(pair_stats.items(), key=lambda x: -x[1]["count"])[:1000]
    for pk, pa in top_pairs:
        if pa["count"] < 20:
            continue
        pair_win_rates[pk] = {
            "count": pa["count"],
            "win_rate": round(pa["wins"] / pa["count"], 4),
            "avg_pnl": round(pa["pnl_sum"] / pa["count"], 3),
        }

    # Feature importance: std deviation of win rate across that feature's buckets
    feature_importance = {}
    feature_names = set(fk.split(":")[0] for fk in feature_win_rates.keys())
    for feat in feature_names:
        buckets = {fk: v for fk, v in feature_win_rates.items() if fk.startswith(f"{feat}:")}
        if len(buckets) < 2:
            continue
        win_rates = [v["win_rate"] for v in buckets.values()]
        importance = round(float(np.std(win_rates)), 4)  # higher std = more discriminating
        feature_importance[feat] = importance

    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: -x[1]))

    library = {
        "trained_on": f"{train_start} to {train_end}",
        "total_setups": total_setups,
        "total_patterns": len(patterns),
        "win_threshold_pct": win_threshold * 100,
        "feature_importance": feature_importance,
        "feature_win_rates": feature_win_rates,
        "pair_win_rates": pair_win_rates,
        "patterns": patterns,
    }

    os.makedirs(os.path.dirname(PATTERN_LIBRARY_PATH), exist_ok=True)
    with open(PATTERN_LIBRARY_PATH, "w") as f:
        json.dump(library, f, indent=2)

    if verbose:
        print(f"\nPattern library saved → {PATTERN_LIBRARY_PATH}")
        print(f"  Patterns (min {min_pattern_count} samples): {len(patterns):,}")
        print(f"  Feature win rates: {len(feature_win_rates):,}")
        print(f"\nTop feature importance (most discriminating):")
        for feat, imp in list(feature_importance.items())[:10]:
            print(f"  {feat:20s}  importance={imp:.4f}")

    return library


def load_pattern_library() -> dict:
    if not os.path.exists(PATTERN_LIBRARY_PATH):
        return {}
    with open(PATTERN_LIBRARY_PATH) as f:
        return json.load(f)


def lookup_pattern(fp: dict, library: dict, top_k: int = 5) -> dict:
    """
    Find the best matching patterns in the library for a given fingerprint.

    Uses exact match first, then progressively relaxes by removing less-important features.

    Returns dict with:
      matched_pattern: closest pattern stats (or None)
      similar_patterns: list of partially matching patterns
      historical_win_rate: estimated win rate based on best match
      confidence: how many samples backed the match
    """
    if not library or "patterns" not in library:
        return {"historical_win_rate": None, "confidence": 0}

    fp_key = "|".join(f"{k}={v}" for k, v in sorted(fp.items()))
    patterns = library.get("patterns", {})
    feature_importance = library.get("feature_importance", {})

    # Exact match
    if fp_key in patterns:
        p = patterns[fp_key]
        return {
            "match_type": "exact",
            "historical_win_rate": p["win_rate"],
            "avg_pnl": p["avg_pnl"],
            "p25_pnl": p["p25_pnl"],
            "p75_pnl": p["p75_pnl"],
            "sample_count": p["count"],
            "confidence": min(p["count"] / 20, 1.0),
        }

    # Partial match: find patterns sharing most features
    fp_set = set(fp_key.split("|"))
    best_overlap = 0
    best_match = None

    for pat_key, pat in patterns.items():
        pat_set = set(pat_key.split("|"))
        overlap = len(fp_set & pat_set) / len(fp_set)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = pat

    if best_match and best_overlap >= 0.6:
        return {
            "match_type": f"partial_{best_overlap:.0%}",
            "historical_win_rate": best_match["win_rate"],
            "avg_pnl": best_match["avg_pnl"],
            "p25_pnl": best_match["p25_pnl"],
            "p75_pnl": best_match["p75_pnl"],
            "sample_count": best_match["count"],
            "confidence": round(best_overlap * min(best_match["count"] / 20, 1.0), 2),
        }

    # Fallback: use feature-level win rates (weighted by importance)
    fwr = library.get("feature_win_rates", {})
    total_weight = 0.0
    weighted_wr = 0.0
    for feat, val in fp.items():
        fk = f"{feat}:{val}"
        if fk in fwr:
            imp = feature_importance.get(feat, 0.01)
            weighted_wr += fwr[fk]["win_rate"] * imp
            total_weight += imp

    if total_weight > 0:
        return {
            "match_type": "feature_weighted",
            "historical_win_rate": round(weighted_wr / total_weight, 4),
            "avg_pnl": None,
            "sample_count": 0,
            "confidence": 0.3,
        }

    return {"historical_win_rate": None, "confidence": 0}


def get_top_feature_insights(fp: dict, library: dict) -> list[dict]:
    """
    For a fingerprint, return the most insightful feature observations:
    - Which features are at their historically best/worst win-rate buckets?
    - Which features deviate from the typical winning setup?
    """
    fwr = library.get("feature_win_rates", {})
    feature_importance = library.get("feature_importance", {})

    insights = []
    for feat, val in fp.items():
        # All buckets for this feature
        feat_buckets = {
            k.split(":")[1]: v
            for k, v in fwr.items()
            if k.startswith(f"{feat}:") and v["count"] >= 20
        }
        if len(feat_buckets) < 2:
            continue

        current = feat_buckets.get(val)
        if not current:
            continue

        all_win_rates = [v["win_rate"] for v in feat_buckets.values()]
        best_bucket = max(feat_buckets, key=lambda b: feat_buckets[b]["win_rate"])
        worst_bucket = min(feat_buckets, key=lambda b: feat_buckets[b]["win_rate"])
        avg_wr = np.mean(all_win_rates)

        current_wr = current["win_rate"]
        best_wr = feat_buckets[best_bucket]["win_rate"]
        imp = feature_importance.get(feat, 0.0)

        deviation = current_wr - avg_wr
        insights.append({
            "feature": feat,
            "current_bucket": val,
            "current_win_rate": current_wr,
            "best_bucket": best_bucket,
            "best_win_rate": best_wr,
            "worst_bucket": worst_bucket,
            "avg_win_rate": round(avg_wr, 4),
            "deviation_from_avg": round(deviation, 4),
            "importance": imp,
            "is_warning": (deviation < -0.05 and imp > 0.01),  # significantly below average
            "is_strength": (deviation > 0.05 and imp > 0.01),
        })

    # Sort by importance × deviation magnitude
    insights.sort(key=lambda x: -x["importance"] * abs(x["deviation_from_avg"]))
    return insights
