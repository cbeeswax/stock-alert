"""
Weekly Stock Prediction CLI

Usage
-----
Generate predictions for a specific week:
    python scripts/run_predictor.py predict --week 2026-01-06

Evaluate a closed week and learn:
    python scripts/run_predictor.py evaluate --week 2026-01-06

Full walk-forward backtest (train + auto-evaluate each week):
    python scripts/run_predictor.py backtest --start 2023-01-02 --end 2025-12-31

Show learning log summary:
    python scripts/run_predictor.py log

Environment variables
---------------------
HISTORICAL_DATA_DIR : path to directory of per-ticker daily CSVs
                      (default: C:\\Users\\pelac\\Git\\HistoricalData\\historical)
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta

import pandas as pd

# Allow running from repo root without pip-installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analysis.predictor.data_loader import available_tickers, load_daily, load_weekly
from src.analysis.predictor.rich_scorer import score_all_rich
from src.analysis.predictor.daily_indicators import compute_daily_indicators, get_snapshot
from src.analysis.predictor.pattern_learner import load_pattern_library
from src.analysis.predictor.deep_introspector import (
    deep_evaluate_week,
    write_deep_learning_log,
    print_week_report,
)

PREDICTIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "predictions")
OUTCOMES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "outcomes")


def _week_filename(week_start: str, suffix: str = "") -> str:
    return f"week_{week_start}{suffix}.json"


def _save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _load_json(path: str):
    with open(path) as f:
        return json.load(f)


def _next_friday(monday: date) -> date:
    return monday + timedelta(days=4)


def _all_mondays(start: str, end: str) -> list:
    """Return all Mondays between start and end (inclusive)."""
    d = pd.Timestamp(start)
    while d.dayofweek != 0:
        d += pd.Timedelta(days=1)
    mondays = []
    end_ts = pd.Timestamp(end)
    while d <= end_ts:
        mondays.append(d.date())
        d += pd.Timedelta(weeks=1)
    return mondays


def _build_daily_data(tickers: list, end_date: str = None) -> dict:
    """Load daily OHLCV for all tickers. Returns {ticker: DataFrame}."""
    print(f"Loading daily data for {len(tickers)} tickers...")
    daily_df = {}
    for i, ticker in enumerate(tickers):
        if i % 50 == 0:
            print(f"  {i}/{len(tickers)} ...", flush=True)
        daily = load_daily(ticker, end=end_date)
        if not daily.empty:
            daily_df[ticker] = daily
    print(f"  Done -- {len(daily_df)} tickers loaded.")
    return daily_df


def cmd_predict(args):
    week_start = args.week
    tickers = available_tickers()
    if "SPY" not in tickers:
        tickers = ["SPY"] + tickers

    # Strict look-ahead cutoff: only data available before week starts
    cutoff = (pd.Timestamp(week_start) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    daily_df = _build_daily_data(tickers, end_date=cutoff)
    spy_daily = daily_df.get("SPY", pd.DataFrame())
    library = load_pattern_library()

    scored = score_all_rich(daily_df, cutoff, spy_daily=spy_daily, library=library)
    if scored.empty:
        print("ERROR: No scoreable tickers found.")
        sys.exit(1)

    # Top 10 picks -- apply ATR hard gate: skip low_vol
    top = scored[scored["atr_bucket"] != "low_vol"].head(10)
    if len(top) < 5:
        top = scored.head(10)  # fall back if too few

    # Build entry/stop/target from ATR
    picks = []
    for _, row in top.iterrows():
        ticker = row["ticker"]
        snap = row["snapshot"]

        entry = float(snap.get("close", 0) or 0)
        atr = float(snap.get("atr14", 0) or 0)
        if entry <= 0 or atr <= 0:
            continue

        stop = round(entry - 1.5 * atr, 2)
        target = round(entry + 2.5 * (entry - stop), 2)
        risk_pct = round((entry - stop) / entry * 100, 2)

        picks.append({
            "ticker": ticker,
            "score": row["score"],
            "entry": round(entry, 2),
            "stop": stop,
            "target": target,
            "risk_pct": risk_pct,
            "atr_bucket": row["atr_bucket"],
            "rsi_bucket": row["rsi_bucket"],
            "adx": row["adx"],
            "rsi14": row["rsi14"],
            "atr_pct": row["atr_pct"],
            "pct_from_52h": row["pct_from_52h"],
            "hist_win_rate": row.get("hist_win_rate"),
            "fingerprint": row["fingerprint"],
        })

    out_path = os.path.join(PREDICTIONS_DIR, _week_filename(week_start))
    _save_json(out_path, {"week_start": week_start, "scorer": "rich_v2", "picks": picks})

    spy_uptrend = scored.iloc[0]["spy_uptrend"] if not scored.empty else True
    spy_regime = "bull" if spy_uptrend else "bear/chop"

    print(f"\n{'='*70}")
    print(f"  TOP 10 PREDICTIONS -- Week of {week_start}  (SPY: {spy_regime})")
    print(f"{'='*70}")
    print(f"  {'#':<3} {'Ticker':<7} {'Score':>6}  {'ATR regime':>10}  {'RSI':>9}  {'Entry':>8}  {'Target':>8}  {'Hist WR':>8}")
    print(f"  {'-'*70}")
    for i, p in enumerate(picks, 1):
        hwr = f"{p['hist_win_rate']:.0%}" if p.get("hist_win_rate") else "N/A"
        print(
            f"  {i:<3} {p['ticker']:<7} {p['score']:>6.1f}  "
            f"{p['atr_bucket']:>10}  {p['rsi_bucket']:>9}  "
            f"{p['entry']:>8.2f}  {p['target']:>8.2f}  {hwr:>8}"
        )
    print(f"\n  Saved -> {out_path}")


def cmd_evaluate(args):
    week_start = args.week
    pred_path = os.path.join(PREDICTIONS_DIR, _week_filename(week_start))
    if not os.path.exists(pred_path):
        print(f"ERROR: No predictions found for {week_start}. Run predict first.")
        sys.exit(1)

    data = _load_json(pred_path)
    picks = data["picks"]
    tickers = [p["ticker"] for p in picks]
    if "SPY" not in tickers:
        tickers = ["SPY"] + tickers

    daily_df = _build_daily_data(tickers)
    week_end = _next_friday(pd.Timestamp(week_start).date()).strftime("%Y-%m-%d")
    library = load_pattern_library()

    outcomes, week_summary = deep_evaluate_week(
        picks, daily_df, week_start, week_end, library=library
    )

    out_path = os.path.join(OUTCOMES_DIR, _week_filename(week_start, "_outcome"))
    _save_json(out_path, {
        "week_start": week_start,
        "week_end": week_end,
        "outcomes": outcomes,
        "summary": week_summary,
    })

    write_deep_learning_log(week_summary)
    print_week_report(outcomes, week_summary)
    print(f"\n  Outcome saved -> {out_path}")


def cmd_log(args):
    from src.analysis.predictor.deep_introspector import _load_log
    log = _load_log()
    if not log:
        print("No learning log entries yet.")
        return
    print(f"\n{'='*65}")
    print(f"  LEARNING LOG  ({len(log)} weeks recorded)")
    print(f"{'='*65}")
    for entry in log:
        wr = entry.get("win_rate_pct", 0)
        pnl = entry.get("avg_pnl_pct", 0)
        wins = entry.get("wins", "?")
        losses = entry.get("losses", "?")
        print(
            f"  {entry['week_start']}  W{wins}/L{losses}  "
            f"WinRate={wr:.0f}%  AvgPnL={pnl:+.2f}%"
        )
        if entry.get("failure_analysis"):
            for fa in entry["failure_analysis"][:3]:
                reason = fa.get("root_cause", fa.get("note", ""))
                print(f"    FAIL {fa['ticker']}: {reason[:80]}")


def main():
    parser = argparse.ArgumentParser(description="Weekly Stock Predictor")
    sub = parser.add_subparsers(dest="command")

    p_pred = sub.add_parser("predict", help="Generate top-10 picks for a week")
    p_pred.add_argument("--week", required=True, help="Monday date of the week (YYYY-MM-DD)")

    p_eval = sub.add_parser("evaluate", help="Evaluate a closed week with deep analysis")
    p_eval.add_argument("--week", required=True, help="Monday date of the week (YYYY-MM-DD)")

    p_bt = sub.add_parser("backtest", help="Walk-forward backtest over date range")
    p_bt.add_argument("--start", required=True, help="Start Monday (YYYY-MM-DD)")
    p_bt.add_argument("--end", required=True, help="End Friday (YYYY-MM-DD)")

    sub.add_parser("log", help="Show learning log summary")

    args = parser.parse_args()
    if args.command == "predict":
        cmd_predict(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "log":
        cmd_log(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
