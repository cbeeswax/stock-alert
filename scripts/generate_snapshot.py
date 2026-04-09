"""
generate_snapshot.py
---------------------
Computes daily technical indicators for all S&P 500 tickers and saves a
clean JSON snapshot. This snapshot is the input to the Copilot CLI stock
analyst skill.

Usage:
    python scripts/generate_snapshot.py                  # uses today's date
    python scripts/generate_snapshot.py --date 2026-04-04
    python scripts/generate_snapshot.py --macro-check    # include macro risk in output

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
from src.analysis.predictor.daily_indicators import (
    compute_daily_indicators,
    compute_weekly_indicators,
    compute_sector_rs,
    compute_sector_regime,
    get_snapshot,
    get_weekly_snapshot,
)
from src.analysis.macro.news_risk import get_macro_risk, get_max_picks, should_prefer_defensive

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "snapshots")
SECTOR_MAP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "sector_map.json")

SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLU", "XLP", "XLY", "XLB", "XLRE", "XLC"]


def list_tickers():
    all_files = [f.replace(".csv", "") for f in os.listdir(DATA_DIR)
                 if f.endswith(".csv") and not f.startswith("_")]
    # Exclude SPY and sector ETFs from the stock picker universe
    exclude = {"SPY"} | set(SECTOR_ETFS)
    return sorted(t for t in all_files if t not in exclude)


def load_sector_map() -> dict:
    if os.path.exists(SECTOR_MAP_PATH):
        with open(SECTOR_MAP_PATH) as f:
            return json.load(f)
    return {}


def load_sector_etfs(end: str) -> dict:
    """Pre-load all 11 sector ETF DataFrames. Returns {etf: df}."""
    sectors = {}
    for etf in SECTOR_ETFS:
        df = load_daily(etf, end=end)
        if not df.empty:
            sectors[etf] = df
    return sectors


def snap_to_dict(snap: pd.Series, wsnap: pd.Series, ticker: str) -> dict:
    """Convert a snapshot row to a clean JSON-serializable dict."""

    def _f(k, decimals=3, source=snap):
        v = source.get(k)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return round(float(v), decimals)

    def _b(k, source=snap):
        v = source.get(k)
        if v is None:
            return None
        return bool(v)

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

    d = {
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
        "pct_vs_ema21":   round(_f("pct_vs_ema21", 4) * 100, 2) if _f("pct_vs_ema21") is not None else None,
        "pct_vs_ema50":   round(_f("pct_vs_ema50", 4) * 100, 2) if _f("pct_vs_ema50") is not None else None,
        "pct_vs_ema200":  round(_f("pct_vs_ema200", 4) * 100, 2) if _f("pct_vs_ema200") is not None else None,
        # Momentum
        "rsi14":          rsi14,
        "rsi7":           rsi7,
        "rsi_signal":     rsi_signal,
        "macd_hist":      _f("macd_hist", 4),
        "macd_hist_rising": _b("macd_hist_rising"),
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
        "in_squeeze":     _b("in_squeeze"),
        # Volume / Money Flow
        "cmf":            _f("cmf", 3),
        "mfi":            _f("mfi", 1),
        "obv_slope":      _f("obv_slope", 4),
        "vol_ratio_20":   _f("vol_ratio_20", 2),
        # Position
        "pct_from_52w_high": h52p,
        "pct_from_52w_low":  round(_f("pct_from_52w_low", 4) * 100, 1) if _f("pct_from_52w_low") is not None else None,
        # RS vs SPY (daily)
        "rs_21d":         _f("rs_21d", 4),
        "rs_63d":         _f("rs_63d", 4),
        # RS line trend (institutional positioning signals)
        "rs_line_new_high":    _b("rs_line_new_high"),
        "rs_line_63d_high":    _b("rs_line_63d_high"),
        "rs_line_above_ema21": _b("rs_line_above_ema21"),
        "rs_line_slope_10d":   _f("rs_line_slope_10d", 4),
        # Sector RS
        "rs_vs_sector_21d":    _f("rs_vs_sector_21d", 4),
        "rs_vs_sector_63d":    _f("rs_vs_sector_63d", 4),
        "sector_leader":       _b("sector_leader"),
        # SPY regime
        "spy_above_ema200":    _b("spy_above_ema200"),
    }

    # Weekly context (structural)
    if wsnap is not None and not wsnap.empty:
        d.update({
            "weekly_above_ema10":       _b("weekly_above_ema10", source=wsnap),
            "weekly_above_ema40":       _b("weekly_above_ema40", source=wsnap),
            "weekly_ema10_slope":       round(_f("weekly_ema10_slope", 4, source=wsnap) * 100, 2) if _f("weekly_ema10_slope", source=wsnap) is not None else None,
            "weekly_rsi14":             _f("weekly_rsi14", 1, source=wsnap),
            "weekly_macd_bullish":      _b("weekly_macd_bullish", source=wsnap),
            "weekly_macd_hist_rising":  _b("weekly_macd_hist_rising", source=wsnap),
            "weekly_bb_pct":            _f("weekly_bb_pct", 3, source=wsnap),
            "weekly_vol_ratio":         _f("weekly_vol_ratio", 2, source=wsnap),
            "weekly_vol_expansion":     _b("weekly_vol_expansion", source=wsnap),
            "weekly_pct_vs_ema40":      round(_f("weekly_pct_vs_ema40", 4, source=wsnap) * 100, 2) if _f("weekly_pct_vs_ema40", source=wsnap) is not None else None,
            "weekly_pct_from_52w_high": round(_f("weekly_pct_from_52w_high", 4, source=wsnap) * 100, 1) if _f("weekly_pct_from_52w_high", source=wsnap) is not None else None,
            "weekly_rs_13w":            _f("weekly_rs_13w", 4, source=wsnap),
            "weekly_rs_line_new_high":  _b("weekly_rs_line_new_high", source=wsnap),
            "weekly_rs_line_rising":    _b("weekly_rs_line_rising", source=wsnap),
        })

    return d


def generate(as_of_date: str, macro_check: bool = False):
    print(f"[snapshot] Generating as-of {as_of_date}")
    date_ts = pd.Timestamp(as_of_date)

    # --- Optional macro risk check (Step 0 for the analyst) ---
    macro_risk_summary = None
    if macro_check:
        print("[snapshot] Checking macro risk...")
        risk = get_macro_risk(as_of_date, use_cache=True)
        max_picks = get_max_picks(risk)
        prefer_defensive = should_prefer_defensive(risk)
        macro_risk_summary = {
            "level":            risk.level,
            "max_picks":        max_picks,
            "prefer_defensive": prefer_defensive,
            "reasoning":        risk.reasoning,
            "sectors_at_risk":  risk.sectors_at_risk,
            "safe_sectors":     risk.safe_sectors,
            "signal_counts":    risk.signal_counts,
        }
        banner = {
            "LOW":     f"[macro] LOW risk — full 5 picks allowed. {risk.reasoning}",
            "MEDIUM":  f"[macro] MEDIUM risk — max 3 picks, favor defensives. {risk.reasoning}",
            "HIGH":    f"[macro] HIGH risk — max 2 picks, ACCUMULATING only. {risk.reasoning}",
            "EXTREME": f"[macro] EXTREME risk — SKIP THIS WEEK. {risk.reasoning}",
        }
        print(banner.get(risk.level, ""))
        if risk.level == "EXTREME":
            print("[snapshot] Snapshot still generated — skill will suppress picks.")


    # Load SPY for relative strength
    spy = load_daily("SPY", end=as_of_date)

    # Load sector data once (expensive, shared across all tickers)
    print("[snapshot] Loading sector ETFs...")
    sector_map = load_sector_map()
    sector_dfs = load_sector_etfs(end=as_of_date)
    print(f"[snapshot] Loaded {len(sector_dfs)} sector ETFs, {len(sector_map)} ticker mappings")

    # Pre-compute sector regime snapshots
    sector_regime_snaps = {}
    for etf, sdf in sector_dfs.items():
        regime_df = compute_sector_regime(sdf, spy)
        if not regime_df.empty:
            past = regime_df[regime_df.index <= date_ts]
            if not past.empty:
                sector_regime_snaps[etf] = past.iloc[-1]

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

            # Add sector RS if we have a mapping and sector data
            sector_etf = sector_map.get(ticker)
            if sector_etf and sector_etf in sector_dfs:
                ind_df = compute_sector_rs(ind_df, sector_dfs[sector_etf])

            # Add weekly indicators
            weekly_df = compute_weekly_indicators(df, spy=spy)

            snap  = get_snapshot(ind_df, date_ts)
            wsnap = get_weekly_snapshot(weekly_df, as_of_date) if not weekly_df.empty else pd.Series(dtype=float)

            if snap is None or snap.empty:
                continue

            row = snap_to_dict(snap, wsnap, ticker)

            # Attach sector metadata
            if sector_etf:
                row["sector_etf"] = sector_etf
                sreg = sector_regime_snaps.get(sector_etf)
                if sreg is not None:
                    row["sector_rs_21d"] = round(float(sreg.get("sector_rs_21d", 0) or 0), 4)
                    row["sector_rs_63d"] = round(float(sreg.get("sector_rs_63d", 0) or 0), 4)
                    row["sector_leadership"] = int(sreg.get("sector_leadership", 0) or 0)

            results.append(row)
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})

        if (i + 1) % 50 == 0:
            print(f"  ... processed {i+1}/{len(tickers)}")

    # Compute SPY regime summary (enhanced with weekly)
    regime = {}
    try:
        spy_ind = compute_daily_indicators(spy)
        spy_weekly = compute_weekly_indicators(spy)
        spy_snap = get_snapshot(spy_ind, date_ts)
        spy_wsnap = get_weekly_snapshot(spy_weekly, as_of_date)
        if spy_snap is not None:
            regime = {
                "spy_close":         round(float(spy_snap.get("close", 0)), 2),
                "spy_ema50":         round(float(spy_snap.get("ema50", 0)), 2),
                "spy_ema200":        round(float(spy_snap.get("ema200", 0)), 2),
                "spy_above_ema50":   bool(spy_snap.get("close", 0) > spy_snap.get("ema50", 0)),
                "spy_above_ema200":  bool(spy_snap.get("close", 0) > spy_snap.get("ema200", 0)),
                "spy_rsi14":         round(float(spy_snap.get("rsi14", 50)), 1),
                "spy_roc21_pct":     round(float(spy_snap.get("roc21", 0)) * 100, 1),
                "spy_cmf":           round(float(spy_snap.get("cmf", 0)), 3),
                "regime_label":      "bull" if spy_snap.get("close", 0) > spy_snap.get("ema50", 0) else "bear",
            }
            if not spy_wsnap.empty:
                regime["spy_weekly_above_ema40"] = bool(spy_wsnap.get("weekly_above_ema40", False))
                regime["spy_weekly_rsi14"] = round(float(spy_wsnap.get("weekly_rsi14", 50)), 1)
                regime["spy_weekly_macd_bullish"] = bool(spy_wsnap.get("weekly_macd_bullish", False))
    except Exception:
        pass

    # Sector leadership summary
    sector_summary = {}
    for etf, sreg_snap in sector_regime_snaps.items():
        try:
            sector_summary[etf] = {
                "rs_21d": round(float(sreg_snap.get("sector_rs_21d", 0) or 0), 4),
                "rs_63d": round(float(sreg_snap.get("sector_rs_63d", 0) or 0), 4),
                "leadership": int(sreg_snap.get("sector_leadership", 0) or 0),
            }
        except Exception:
            pass

    output = {
        "as_of_date":      as_of_date,
        "generated_at":    datetime.utcnow().isoformat(),
        "ticker_count":    len(results),
        "macro_risk":      macro_risk_summary,
        "regime":          regime,
        "sector_summary":  sector_summary,
        "tickers":         results,
        "errors":          errors,
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
    parser.add_argument("--macro-check", action="store_true", help="Include macro risk classification in output")
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        # Default: most recent weekday
        today = datetime.utcnow().date()
        offset = max(1, today.weekday() - 4) if today.weekday() >= 5 else 0
        date_str = str(today - timedelta(days=offset))

    generate(date_str, macro_check=args.macro_check)
