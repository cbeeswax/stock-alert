"""
backtest_2025.py
----------------
Full-year 2025 backtest with macro risk filter.

For each week:
  1. Fetch macro risk from Finnhub (cached after first run)
  2. If EXTREME → skip week (0 picks)
  3. If HIGH    → top 2 ACCUMULATING picks only
  4. If MEDIUM  → top 3 picks, defensive sectors preferred
  5. If LOW     → top 5 picks (normal)
  6. Score and compare vs actual weekly returns

Usage:
    python scripts/backtest_2025.py              # full year 2025
    python scripts/backtest_2025.py --macro-only # just show macro risk per week, no scoring
"""

import os, sys, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter, defaultdict

from src.analysis.predictor.data_loader import load_daily, DATA_DIR
from src.analysis.predictor.daily_indicators import (
    compute_daily_indicators, compute_weekly_indicators,
    compute_sector_rs,
    get_snapshot, get_weekly_snapshot,
)
from src.analysis.macro.news_risk import get_macro_risk, get_max_picks

# ── Load dotenv ───────────────────────────────────────────────────────────────
def _load_dotenv():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
_load_dotenv()

# ── Import scorer from backtest_comprehensive ─────────────────────────────────
from scripts.backtest_comprehensive import (
    score_ticker_comprehensive, get_weekly_return,
)

# ── Generate 2025 weekly schedule ─────────────────────────────────────────────
def generate_weeks_2025():
    """All trading Mondays in 2025 with as-of (prev Friday) and exit (next Friday)."""
    # US market holidays 2025 (Mondays affected)
    holidays = {
        datetime(2025, 1, 1),   # New Year's
        datetime(2025, 1, 20),  # MLK Day
        datetime(2025, 2, 17),  # Presidents Day
        datetime(2025, 5, 26),  # Memorial Day
        datetime(2025, 6, 19),  # Juneteenth
        datetime(2025, 7, 4),   # Independence Day (Friday)
        datetime(2025, 9, 1),   # Labor Day
        datetime(2025, 11, 27), # Thanksgiving (Thursday, but affects week)
        datetime(2025, 12, 25), # Christmas
    }

    weeks = []
    # Start from first Monday of 2025 (Jan 6, since Jan 1 is holiday)
    dt = datetime(2025, 1, 6)
    while dt.year == 2025:
        if dt.weekday() == 0 and dt not in holidays:  # Monday
            as_of   = dt - timedelta(days=3)   # prior Friday
            entry   = dt
            exit_dt = dt + timedelta(days=4)   # next Friday
            # Adjust exit if it's a holiday
            while exit_dt in holidays or exit_dt.weekday() > 4:
                exit_dt -= timedelta(days=1)
            weeks.append({
                "week_label": entry.strftime("%b %d").replace(" 0", " "),
                "as_of":      as_of.strftime("%Y-%m-%d"),
                "entry_date": entry.strftime("%Y-%m-%d"),
                "exit_date":  exit_dt.strftime("%Y-%m-%d"),
            })
        dt += timedelta(days=1)
    return weeks

# ── SPY weekly return (for macro validation) ──────────────────────────────────
def get_spy_weekly_return(entry_date: str, exit_date: str, spy_df: pd.DataFrame) -> float:
    try:
        entry_dt = pd.Timestamp(entry_date)
        exit_dt  = pd.Timestamp(exit_date)
        row_entry = spy_df[spy_df.index >= entry_dt].iloc[0]
        row_exit  = spy_df[spy_df.index <= exit_dt].iloc[-1]
        entry_p   = float(row_entry["open"] if "open" in row_entry else row_entry.iloc[0])
        exit_p    = float(row_exit["close"] if "close" in row_exit else row_exit.iloc[-1])
        return (exit_p - entry_p) / entry_p * 100
    except Exception:
        return 0.0

# ── Sector ETF loader ─────────────────────────────────────────────────────────
SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLU", "XLP", "XLY", "XLB", "XLRE", "XLC"]
SECTOR_MAP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "sector_map.json")

# ── Main backtest ─────────────────────────────────────────────────────────────
def run_2025_backtest(macro_filter: bool = True, macro_only: bool = False):
    weeks = generate_weeks_2025()
    print(f"\n{'='*75}")
    print(f"2025 BACKTEST — {'WITH' if macro_filter else 'WITHOUT'} MACRO FILTER")
    print(f"{'='*75}")
    print(f"Testing {len(weeks)} weeks | Jan 6 2025 → Dec 29 2025\n")

    # Load SPY for weekly return validation only (regime loaded per week with end= slicing)
    spy_df = load_daily("SPY")

    # Load sector map
    sector_map = {}
    if os.path.exists(SECTOR_MAP_PATH):
        with open(SECTOR_MAP_PATH) as f:
            sector_map = json.load(f)

    # Load all tickers once
    tickers = [f.replace(".csv","") for f in os.listdir(DATA_DIR)
               if f.endswith(".csv") and not f.startswith("_")]
    exclude = {"SPY"} | set(SECTOR_ETFS)
    tickers = sorted(t for t in tickers if t not in exclude)

    # Tracking
    all_trades       = []
    grand_wins       = 0
    grand_picks      = 0
    grand_pnl        = 0.0
    weeks_skipped    = 0
    weeks_reduced    = 0
    macro_summary    = []

    for wk in weeks:
        label      = wk["week_label"]
        as_of      = wk["as_of"]
        entry_date = wk["entry_date"]
        exit_date  = wk["exit_date"]

        # ── Step 0: Macro risk check ──────────────────────────────────────────
        macro = get_macro_risk(as_of, use_cache=True)
        max_picks = get_max_picks(macro) if macro_filter else 5
        spy_ret   = get_spy_weekly_return(entry_date, exit_date, spy_df)

        macro_summary.append({
            "week":      label,
            "as_of":     as_of,
            "risk":      macro.level,
            "max_picks": max_picks,
            "spy_ret":   spy_ret,
            "reasoning": macro.reasoning[:80],
        })

        status_tag = ""
        if macro_filter and max_picks == 0:
            status_tag = f"  [SKIPPED — EXTREME | SPY {spy_ret:+.1f}%]"
            weeks_skipped += 1
            print(f"  WEEK {label:7}  {macro.level:<7}  SPY={spy_ret:+5.1f}%  {status_tag}")
            continue
        elif macro_filter and max_picks < 5:
            status_tag = f"[{macro.level}: {max_picks} picks max]"
            weeks_reduced += 1

        if macro_only:
            print(f"  WEEK {label:7}  {macro.level:<7}  max={max_picks}  SPY={spy_ret:+5.1f}%  {macro.reasoning[:60]}")
            continue

        # -- Step 1: Market regime ---------------------------------------------------
        spy_slice = load_daily("SPY", end=as_of)
        spy_above_ema50 = True
        regime_label    = "BULL"
        sector_dfs_week = {}

        if spy_slice is not None and len(spy_slice) >= 50:
            spy_ind  = compute_daily_indicators(spy_slice)
            spy_snap = get_snapshot(spy_ind, pd.Timestamp(as_of))
            if spy_snap is not None:
                spy_above_ema50 = float(spy_snap.get("close") or 0) > float(spy_snap.get("ema50") or 0)
                regime_label    = "BULL" if spy_above_ema50 else "BEAR"
            for etf in SECTOR_ETFS:
                sdf = load_daily(etf, end=as_of)
                if sdf is not None and not sdf.empty:
                    sector_dfs_week[etf] = sdf
        else:
            spy_slice = None

        # -- Step 2: Score all tickers ----------------------------------------------
        scored = []
        for ticker in tickers:
            try:
                df = load_daily(ticker, end=as_of)
                if df is None or len(df) < 200:
                    continue
                ind = compute_daily_indicators(df, spy=spy_slice)

                sector_etf = sector_map.get(ticker)
                if sector_etf and sector_etf in sector_dfs_week:
                    ind = compute_sector_rs(ind, sector_dfs_week[sector_etf])

                weekly_df = compute_weekly_indicators(df, spy=spy_slice)
                wsnap = get_weekly_snapshot(weekly_df, as_of) if not weekly_df.empty else pd.Series(dtype=float)

                snap = get_snapshot(ind, pd.Timestamp(as_of))
                if snap is None or snap.empty:
                    continue

                result = score_ticker_comprehensive(snap, ind, spy_above_ema50, wsnap=wsnap)
                if result is None:
                    continue
                result["ticker"] = ticker
                scored.append(result)
            except Exception:
                continue

        if not scored:
            print(f"  WEEK {label}: no scored tickers")
            continue

        # ── Step 3: Apply macro filter to top N picks ─────────────────────────
        scored.sort(key=lambda x: x["score"], reverse=True)

        # In MEDIUM/HIGH, prefer defensive sectors
        defensive = set(macro.safe_sectors) if macro_filter and macro.level in ("MEDIUM", "HIGH") else set()
        if defensive:
            def _pref(p):
                ticker_sector = sector_map.get(p["ticker"], "")
                return (0 if ticker_sector in defensive else 1, -p["score"])
            scored.sort(key=_pref)

        # In HIGH, require ACCUMULATING institutional pattern
        if macro_filter and macro.level == "HIGH":
            scored = [p for p in scored if p.get("institutional", "") in ("ACCUMULATING", "MARKUP")] or scored

        top5 = scored[:max_picks]
        week_wins = 0
        week_pnl  = 0.0

        print(f"\n  WEEK {label:7}  {macro.level:<7}  {max_picks} picks  regime={regime_label:<6}  SPY={spy_ret:+5.1f}%  {status_tag}")

        for rank, pick in enumerate(top5, 1):
            ticker = pick["ticker"]
            actual = get_weekly_return(ticker, entry_date, exit_date)
            if actual:
                pnl  = actual["pnl_pct"]
                sym  = "WIN " if actual["win"] else ("LOSS" if actual["loss"] else "flat")
                print(f"    {rank}. {ticker:<5}  score={pick['score']:>3.0f}  "
                      f"{pick['stage']:<14} {pick['setup']:<22}  "
                      f"PnL={pnl:+6.2f}%  {sym}")
                week_pnl  += pnl
                grand_pnl += pnl
                grand_picks += 1
                if actual["win"]:
                    week_wins  += 1
                    grand_wins += 1
                all_trades.append({
                    "week": label, "ticker": ticker, "score": pick["score"],
                    "setup": pick["setup"], "stage": pick["stage"],
                    "macro": macro.level, "max_picks": max_picks,
                    "pnl_pct": pnl, "win": actual["win"], "loss": actual["loss"],
                    "spy_ret": spy_ret, "entry": actual["entry_price"],
                    "exit": actual["exit_price"], "stop": pick["stop"],
                })

        avg = week_pnl / len(top5) if top5 else 0
        print(f"    --- {week_wins}/{len(top5)} wins | week avg = {avg:+.2f}% ---")

    # ── Macro filter summary ──────────────────────────────────────────────────
    print(f"\n{'='*75}")
    print("MACRO RISK SCAN — 2025")
    print(f"{'='*75}")
    print(f"{'Week':<8} {'Risk':<8} {'MaxPick':<8} {'SPY%':>6}  Reasoning")
    print("-"*75)
    for m in macro_summary:
        flag = "<< SAVED" if m["risk"] == "EXTREME" and m["spy_ret"] < -1 else \
               "!! FP"    if m["risk"] in ("HIGH","EXTREME") and m["spy_ret"] > 1 else ""
        print(f"  {m['week']:<8} {m['risk']:<8} {m['max_picks']:<8} {m['spy_ret']:>+5.1f}%  "
              f"{m['reasoning'][:55]}  {flag}")

    # Validate macro signal vs SPY
    extreme_weeks = [m for m in macro_summary if m["risk"] == "EXTREME"]
    high_weeks    = [m for m in macro_summary if m["risk"] == "HIGH"]
    extreme_down  = sum(1 for m in extreme_weeks if m["spy_ret"] < -1)
    high_down     = sum(1 for m in high_weeks    if m["spy_ret"] < 0)

    print(f"\nMacro classifier accuracy:")
    print(f"  EXTREME weeks: {len(extreme_weeks)} — SPY actually down >1%: {extreme_down}/{len(extreme_weeks)} ({extreme_down/max(len(extreme_weeks),1)*100:.0f}%)")
    print(f"  HIGH weeks:    {len(high_weeks)} — SPY actually down: {high_down}/{max(len(high_weeks),1)} ({high_down/max(len(high_weeks),1)*100:.0f}%)")
    print(f"  Weeks skipped (EXTREME): {weeks_skipped}")
    print(f"  Weeks reduced (HIGH/MEDIUM): {weeks_reduced}")

    if not macro_only and all_trades:
        print(f"\n{'='*75}")
        print("BACKTEST SUMMARY — 2025")
        print(f"{'='*75}")
        print(f"Total picks: {grand_picks} | Wins: {grand_wins} ({grand_wins/grand_picks*100:.0f}%)")
        print(f"Total PnL (sum picks): {grand_pnl:+.2f}%  |  Avg per pick: {grand_pnl/grand_picks:+.2f}%")

        wins   = [t for t in all_trades if t["win"]]
        losses = [t for t in all_trades if t["loss"]]
        if wins:   print(f"Avg WIN:  {sum(t['pnl_pct'] for t in wins)/len(wins):+.2f}%")
        if losses: print(f"Avg LOSS: {sum(t['pnl_pct'] for t in losses)/len(losses):+.2f}%")

        print(f"\nBy macro risk level:")
        for level in ["LOW", "MEDIUM", "HIGH"]:
            lt = [t for t in all_trades if t["macro"] == level]
            if lt:
                lw = sum(1 for t in lt if t["win"])
                print(f"  {level:<7}: {lw}/{len(lt)} wins ({lw/len(lt)*100:.0f}%)  "
                      f"avg {sum(t['pnl_pct'] for t in lt)/len(lt):+.2f}%")

        print(f"\nSetup breakdown:")
        for setup, cnt in Counter(t["setup"] for t in all_trades).most_common(8):
            st = [t for t in all_trades if t["setup"] == setup]
            sw = sum(1 for t in st if t["win"])
            print(f"  {setup:<30} {sw}/{cnt} wins")

        print(f"\nBest weeks:")
        week_agg = defaultdict(list)
        for t in all_trades:
            week_agg[t["week"]].append(t["pnl_pct"])
        for wk, vals in sorted(week_agg.items(), key=lambda x: sum(x[1]), reverse=True)[:5]:
            print(f"  {wk:8}  total={sum(vals):+.1f}%  picks={len(vals)}")

        # Save trades
        out_path = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "backtest_2025_trades.json")
        with open(out_path, "w") as f:
            json.dump(all_trades, f, indent=2)
        print(f"\nTrades saved: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-macro",    action="store_true", help="Run without macro filter")
    parser.add_argument("--macro-only",  action="store_true", help="Only show macro risk, skip scoring")
    args = parser.parse_args()

    run_2025_backtest(
        macro_filter=not args.no_macro,
        macro_only=args.macro_only,
    )
