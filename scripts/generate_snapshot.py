"""
generate_snapshot.py
---------------------
Computes daily technical indicators for all S&P 500 tickers and saves a
clean JSON snapshot. This snapshot is the input to the Copilot CLI stock
analyst skill.

Usage:
    python scripts/generate_snapshot.py                  # uses today's date
    python scripts/generate_snapshot.py --date 2026-04-04

Output:
    data/predictor/snapshots/snapshot_YYYY-MM-DD.json
    data/predictor/snapshots/latest.json  (symlink / copy)
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analysis.predictor.data_loader import load_daily, DATA_DIR
from src.analysis.predictor.daily_indicators import compute_daily_indicators, get_snapshot

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "snapshots")


def list_tickers():
    return sorted(
        f.replace(".csv", "")
        for f in os.listdir(DATA_DIR)
        if f.endswith(".csv") and not f.startswith("_")
    )


def snap_to_dict(snap: pd.Series, ticker: str) -> dict:
    """Convert a snapshot row to a clean JSON-serializable dict."""

    def _f(k, decimals=3):
        v = snap.get(k)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return round(float(v), decimals)

    close = _f("close", 2)
    atr14 = _f("atr14", 4)
    atr_pct = round(atr14 / close * 100, 2) if (close and atr14) else None

    rsi14 = _f("rsi14", 1)
    rsi7  = _f("rsi7", 1)
    rsi_signal = None
    if rsi7 is not None and rsi14 is not None:
        rsi_signal = "RECOVERING" if rsi7 > rsi14 else "FALLING"

    h52  = _f("pct_from_52w_high", 3)
    h52p = round(h52 * 100, 1) if h52 is not None else None

    return {
        "ticker": ticker,
        # Price
        "close":          close,
        "roc5_pct":       round(_f("roc5", 4) * 100, 2) if _f("roc5") is not None else None,
        "roc21_pct":      round(_f("roc21", 4) * 100, 2) if _f("roc21") is not None else None,
        # Trend
        "ema9":           _f("ema9", 2),
        "ema21":          _f("ema21", 2),
        "ema50":          _f("ema50", 2),
        "ema200":         _f("ema200", 2),
        "ema_align":      int(snap.get("ema_align", 0) or 0),
        "pct_vs_ema50":   round(_f("pct_vs_ema50", 4) * 100, 2) if _f("pct_vs_ema50") is not None else None,
        "pct_vs_ema200":  round(_f("pct_vs_ema200", 4) * 100, 2) if _f("pct_vs_ema200") is not None else None,
        # Momentum
        "rsi14":          rsi14,
        "rsi7":           rsi7,
        "rsi_signal":     rsi_signal,
        "macd_hist":      _f("macd_hist", 4),
        "macd_hist_rising": bool(snap.get("macd_hist_rising", 0)),
        "macd_cross_days": int(snap.get("macd_cross_days", 0) or 0),
        "stoch_k":        _f("stoch_k", 1),
        "stoch_d":        _f("stoch_d", 1),
        # Strength
        "adx":            _f("adx", 1),
        "di_spread":      _f("di_spread", 1),
        # Volatility
        "atr14":          atr14,
        "atr_pct":        atr_pct,
        "bb_pct":         _f("bb_pct", 3),
        "bb_width":       _f("bb_width", 4),
        "in_squeeze":     bool(snap.get("in_squeeze", False)),
        # Volume / Money Flow
        "cmf":            _f("cmf", 3),
        "mfi":            _f("mfi", 1),
        "obv_slope":      _f("obv_slope", 4),
        "vol_ratio_20":   _f("vol_ratio_20", 2),
        # Position
        "pct_from_52w_high": h52p,
        "pct_from_52w_low":  round(_f("pct_from_52w_low", 4) * 100, 1) if _f("pct_from_52w_low") is not None else None,
        # RS vs SPY
        "rs_21d":         _f("rs_21d", 4),
    }


def generate(as_of_date: str):
    print(f"[snapshot] Generating as-of {as_of_date}")
    date_ts = pd.Timestamp(as_of_date)

    # Load SPY for relative strength
    spy = load_daily("SPY", end=as_of_date)

    tickers = list_tickers()
    print(f"[snapshot] Found {len(tickers)} tickers")

    results = []
    errors  = []

    for i, ticker in enumerate(tickers):
        try:
            df = load_daily(ticker, end=as_of_date)
            if df is None or len(df) < 200:
                continue
            ind_df = compute_daily_indicators(df, spy=spy)
            snap   = get_snapshot(ind_df, date_ts)
            if snap is None:
                continue
            row = snap_to_dict(snap, ticker)
            results.append(row)
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})

        if (i + 1) % 50 == 0:
            print(f"  ... processed {i+1}/{len(tickers)}")

    # Compute SPY regime summary
    regime = {}
    try:
        spy_ind = compute_daily_indicators(spy)
        spy_snap = get_snapshot(spy_ind, date_ts)
        if spy_snap is not None:
            regime = {
                "spy_close":      round(float(spy_snap.get("close", 0)), 2),
                "spy_ema50":      round(float(spy_snap.get("ema50", 0)), 2),
                "spy_ema200":     round(float(spy_snap.get("ema200", 0)), 2),
                "spy_above_ema50": bool(spy_snap.get("close", 0) > spy_snap.get("ema50", 0)),
                "spy_rsi14":      round(float(spy_snap.get("rsi14", 50)), 1),
                "spy_roc21_pct":  round(float(spy_snap.get("roc21", 0)) * 100, 1),
                "spy_cmf":        round(float(spy_snap.get("cmf", 0)), 3),
                "regime_label":   "bull" if spy_snap.get("close", 0) > spy_snap.get("ema50", 0) else "bear",
            }
    except Exception:
        pass

    output = {
        "as_of_date":   as_of_date,
        "generated_at": datetime.utcnow().isoformat(),
        "ticker_count": len(results),
        "regime":       regime,
        "tickers":      results,
        "errors":       errors,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path    = os.path.join(OUTPUT_DIR, f"snapshot_{as_of_date}.json")
    latest_path = os.path.join(OUTPUT_DIR, "latest.json")

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    with open(latest_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[snapshot] Done — {len(results)} tickers, {len(errors)} errors")
    print(f"[snapshot] Saved -> {out_path}")
    print(f"[snapshot] Latest -> {latest_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate indicator snapshot for Copilot analyst skill")
    parser.add_argument("--date", default=None, help="As-of date YYYY-MM-DD (default: last Friday)")
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        # Default: most recent weekday
        today = datetime.utcnow().date()
        offset = max(1, today.weekday() - 4) if today.weekday() >= 5 else 0
        date_str = str(today - timedelta(days=offset))

    generate(date_str)
