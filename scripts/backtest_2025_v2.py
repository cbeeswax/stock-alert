"""
backtest_2025_v2.py
-------------------
Improved 2025 backtest addressing three structural limitations of v1:

1. MULTI-WEEK HOLDING: Hold winners up to MAX_HOLD_WEEKS with trailing stop.
   Positions exit when:
     - Trailing stop triggered (TRAIL_PCT below highest weekly close)
     - Hard initial stop hit (from scoring)
     - MAX_HOLD_WEEKS reached

2. QUALITY FILTER: Only take picks scoring >= MIN_SCORE.
   Skip weeks with no qualifying setups rather than forcing mediocre picks.

3. CONVICTION SIZING: Scale risk per trade by score strength.
   Score >= 90  -> 1.5x risk ($3k)
   Score >= 85  -> 1.25x risk ($2.5k)
   Score < 85   -> 1.0x risk ($2k)

Usage:
    python scripts/backtest_2025_v2.py
    python scripts/backtest_2025_v2.py --macro-only
    python scripts/backtest_2025_v2.py --no-macro
    python scripts/backtest_2025_v2.py --min-score 80
"""

import os, sys, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict

from src.analysis.predictor.data_loader import load_daily, DATA_DIR
from src.analysis.predictor.daily_indicators import (
    compute_daily_indicators, compute_weekly_indicators,
    compute_sector_rs,
    get_snapshot, get_weekly_snapshot,
)
from src.analysis.macro.news_risk import get_macro_risk, get_max_picks
from scripts.backtest_comprehensive import score_ticker_comprehensive

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

# ── Parameters ────────────────────────────────────────────────────────────────
PORTFOLIO      = 100_000
BASE_RISK      = 2_000    # base $ risk per trade (no position size cap — pure risk sizing)
MAX_POSITIONS  = 5        # max concurrent open positions
MAX_HOLD_WEEKS = 4        # max weeks to hold a position
TRAIL_PCT      = 0.08     # trailing stop: 8% below highest weekly close
MIN_SCORE      = 75       # minimum score to take a pick

# ── Weekly schedule ───────────────────────────────────────────────────────────
def generate_weeks_2025():
    holidays = {
        datetime(2025, 1, 1),
        datetime(2025, 1, 20),
        datetime(2025, 2, 17),
        datetime(2025, 5, 26),
        datetime(2025, 6, 19),
        datetime(2025, 7, 4),
        datetime(2025, 9, 1),
        datetime(2025, 11, 27),
        datetime(2025, 12, 25),
    }
    weeks = []
    dt = datetime(2025, 1, 6)
    while dt.year == 2025:
        if dt.weekday() == 0 and dt not in holidays:
            as_of   = dt - timedelta(days=3)
            entry   = dt
            exit_dt = dt + timedelta(days=4)
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

# ── Daily close lookup (cached) ───────────────────────────────────────────────
_daily_cache: dict = {}

def get_close_on_date(ticker: str, date_str: str) -> float | None:
    if ticker not in _daily_cache:
        _daily_cache[ticker] = load_daily(ticker)
    df = _daily_cache[ticker]
    if df is None or df.empty:
        return None
    ts = pd.Timestamp(date_str)
    rows = df[df.index <= ts]
    if rows.empty:
        return None
    return float(rows.iloc[-1]["close"])

def get_trading_days(ticker: str, start_date: str, end_date: str) -> list[tuple[str, float, float]]:
    """Return list of (date_str, low, close) for each trading day in range."""
    if ticker not in _daily_cache:
        _daily_cache[ticker] = load_daily(ticker)
    df = _daily_cache[ticker]
    if df is None or df.empty:
        return []
    start_ts = pd.Timestamp(start_date)
    end_ts   = pd.Timestamp(end_date)
    rows = df[(df.index >= start_ts) & (df.index <= end_ts)]
    result = []
    for dt, row in rows.iterrows():
        low   = float(row.get("low",   row["close"]))
        close = float(row["close"])
        result.append((dt.strftime("%Y-%m-%d"), low, close))
    return result

def get_open_price(ticker: str, date_str: str) -> float | None:
    if ticker not in _daily_cache:
        _daily_cache[ticker] = load_daily(ticker)
    df = _daily_cache[ticker]
    if df is None or df.empty:
        return None
    ts = pd.Timestamp(date_str)
    rows = df[df.index >= ts]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return float(row.get("open", row["close"]))

# ── Conviction-based risk sizing ──────────────────────────────────────────────
def get_risk_amount(score: float) -> float:
    if score >= 90:
        return BASE_RISK * 1.50
    elif score >= 85:
        return BASE_RISK * 1.25
    return BASE_RISK

def get_shares(score: float, entry: float, stop: float) -> int:
    stop_dist = entry - stop
    if stop_dist <= 0:
        stop_dist = entry * 0.05
    risk_amt = get_risk_amount(score)
    shares = int(risk_amt / stop_dist)
    return max(shares, 1)

# ── Update open positions — checked DAILY for stops, weekly for max hold ──────
def update_positions_daily(open_pos: list, week_idx: int,
                            entry_date: str, exit_date: str) -> tuple[list, list]:
    """
    Check each trading day for stop/trail hits.
    Stop triggered at that day's CLOSE (conservative vs intraday low).
    Trailing stop updates daily on new highs.
    Max hold still measured in weeks.
    """
    still_open = []
    closed = []
    hold_weeks = week_idx - 0  # computed per-position below

    for pos in open_pos:
        days = get_trading_days(pos["ticker"], entry_date, exit_date)
        hold_weeks_pos = week_idx - pos["start_week_idx"] + 1

        exit_day   = None
        exit_price = None
        exit_reason = None

        for day_str, day_low, day_close in days:
            # Update trailing stop on new high
            if day_close > pos["highest_close"]:
                pos["highest_close"] = day_close
                pos["trailing_stop"] = day_close * (1 - TRAIL_PCT)

            # Check stop hit using intraday LOW (realistic — stop triggered intraday)
            if day_low <= pos["stop_price"]:
                exit_day    = day_str
                exit_price  = pos["stop_price"]  # exit at stop price (not close)
                exit_reason = "STOP"
                break

            # Check trailing stop using intraday LOW
            if day_low <= pos["trailing_stop"]:
                exit_day    = day_str
                exit_price  = pos["trailing_stop"]
                exit_reason = "TRAIL"
                break

        # Max hold — exit at week's last close if no stop hit
        if exit_day is None and hold_weeks_pos >= MAX_HOLD_WEEKS:
            last_close = get_close_on_date(pos["ticker"], exit_date)
            if last_close is not None:
                exit_day    = exit_date
                exit_price  = last_close
                exit_reason = "MAX_HOLD"

        if exit_day is not None and exit_price is not None:
            pnl_pct    = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
            dollar_pnl = round(pos["shares"] * (exit_price - pos["entry_price"]), 2)
            pos.update({
                "exit_date":   exit_day,
                "exit_price":  round(exit_price, 2),
                "pnl_pct":     round(pnl_pct, 2),
                "dollar_pnl":  dollar_pnl,
                "hold_weeks":  hold_weeks_pos,
                "win":         pnl_pct > 1.0,
                "loss":        pnl_pct < -1.0,
                "exit_reason": exit_reason,
            })
            closed.append(pos)
        else:
            still_open.append(pos)

    return still_open, closed

# ── SPY weekly return ─────────────────────────────────────────────────────────
def get_spy_ret(entry_date: str, exit_date: str, spy_df: pd.DataFrame) -> float:
    try:
        row_e = spy_df[spy_df.index >= pd.Timestamp(entry_date)].iloc[0]
        row_x = spy_df[spy_df.index <= pd.Timestamp(exit_date)].iloc[-1]
        ep = float(row_e.get("open", row_e.iloc[0]))
        xp = float(row_x["close"])
        return (xp - ep) / ep * 100
    except Exception:
        return 0.0

# ── Main backtest ─────────────────────────────────────────────────────────────
SECTOR_ETFS = ["XLK","XLF","XLV","XLE","XLI","XLU","XLP","XLY","XLB","XLRE","XLC"]
SECTOR_MAP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "sector_map.json")

def run_backtest(macro_filter=True, macro_only=False, min_score=MIN_SCORE):
    weeks = generate_weeks_2025()
    print(f"\n{'='*80}")
    print(f"2025 BACKTEST v2 -- Multi-week Holds | Min Score {min_score} | "
          f"Trail {TRAIL_PCT*100:.0f}% | Max {MAX_HOLD_WEEKS}wk")
    print(f"{'='*80}")

    spy_df = load_daily("SPY")
    sector_map = {}
    if os.path.exists(SECTOR_MAP_PATH):
        with open(SECTOR_MAP_PATH) as f:
            sector_map = json.load(f)

    tickers = [f.replace(".csv","") for f in os.listdir(DATA_DIR)
               if f.endswith(".csv") and not f.startswith("_")]
    exclude = {"SPY"} | set(SECTOR_ETFS)
    tickers = sorted(t for t in tickers if t not in exclude)

    open_positions: list = []
    all_closed:     list = []
    portfolio_value = float(PORTFOLIO)
    weeks_skipped = 0

    for week_idx, wk in enumerate(weeks):
        label      = wk["week_label"]
        as_of      = wk["as_of"]
        entry_date = wk["entry_date"]
        exit_date  = wk["exit_date"]

        spy_ret = get_spy_ret(entry_date, exit_date, spy_df)

        # ── Macro check ───────────────────────────────────────────────────────
        macro = get_macro_risk(as_of, use_cache=True)
        max_picks = get_max_picks(macro) if macro_filter else 5

        if macro_filter and max_picks == 0:
            weeks_skipped += 1
            print(f"\n  WEEK {label:7}  EXTREME -- SKIPPED  SPY={spy_ret:+.1f}%")
            # Still check stops daily even during skipped weeks
            open_positions, closed = update_positions_daily(open_positions, week_idx, entry_date, exit_date)
            all_closed.extend(closed)
            continue

        if macro_only:
            print(f"  WEEK {label:7}  {macro.level:<8}  max={max_picks}  SPY={spy_ret:+5.1f}%")
            continue

        # ── Score new candidates for this week ────────────────────────────────
        spy_slice = load_daily("SPY", end=as_of)
        spy_above_ema50 = True
        regime_label = "BULL"
        sector_dfs_week = {}

        if spy_slice is not None and len(spy_slice) >= 50:
            spy_ind  = compute_daily_indicators(spy_slice)
            spy_snap = get_snapshot(spy_ind, pd.Timestamp(as_of))
            if spy_snap is not None:
                spy_above_ema50 = float(spy_snap.get("close") or 0) > float(spy_snap.get("ema50") or 0)
                regime_label = "BULL" if spy_above_ema50 else "BEAR"
            for etf in SECTOR_ETFS:
                sdf = load_daily(etf, end=as_of)
                if sdf is not None and not sdf.empty:
                    sector_dfs_week[etf] = sdf
        else:
            spy_slice = None

        scored = []
        open_tickers = {p["ticker"] for p in open_positions}
        for ticker in tickers:
            if ticker in open_tickers:
                continue  # already holding this ticker
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
                if result is None or result["score"] < min_score:
                    continue
                result["ticker"] = ticker
                scored.append(result)
            except Exception:
                continue

        # Apply macro sector preference
        defensive = set(macro.safe_sectors) if macro_filter and macro.level in ("MEDIUM","HIGH") else set()
        if defensive:
            scored.sort(key=lambda p: (0 if sector_map.get(p["ticker"],"") in defensive else 1, -p["score"]))
        else:
            scored.sort(key=lambda p: -p["score"])

        if macro_filter and macro.level == "HIGH":
            acc = [p for p in scored if p.get("institutional","") in ("ACCUMULATING","MARKUP")]
            if acc:
                scored = acc

        # Available slots
        available = MAX_POSITIONS - len(open_positions)
        new_picks = scored[:min(available, max_picks)]

        # ── Open new positions ─────────────────────────────────────────────────
        opened = []
        for pick in new_picks:
            ticker = pick["ticker"]
            entry_price = get_open_price(ticker, entry_date)
            if entry_price is None or entry_price <= 0:
                continue
            stop_raw = pick.get("stop", 0)
            stop_price = float(stop_raw) if stop_raw and float(stop_raw) > 0 else entry_price * 0.95
            shares = get_shares(pick["score"], entry_price, stop_price)
            risk_taken = shares * (entry_price - stop_price)
            pos_size = shares * entry_price
            open_positions.append({
                "ticker":         ticker,
                "score":          pick["score"],
                "setup":          pick.get("setup",""),
                "stage":          pick.get("stage",""),
                "macro_risk":     macro.level,
                "entry_date":     entry_date,
                "entry_price":    round(entry_price, 2),
                "stop_price":     round(stop_price, 2),
                "shares":         shares,
                "pos_size":       round(pos_size, 2),
                "highest_close":  entry_price,
                "trailing_stop":  round(entry_price * (1 - TRAIL_PCT), 2),
                "start_week_idx": week_idx,
                "week_label":     label,
                "risk_taken":     round(risk_taken, 2),
            })
            opened.append(f"{ticker}({pick['score']:.0f} ${pos_size:,.0f})")

        # ── Update ALL open positions at end of week ───────────────────────────
        open_positions, closed_this_week = update_positions_daily(open_positions, week_idx, entry_date, exit_date)
        all_closed.extend(closed_this_week)

        # Portfolio value: sum closed P&L
        week_closed_pnl = sum(t["dollar_pnl"] for t in closed_this_week)
        portfolio_value += week_closed_pnl

        n_closed = len(closed_this_week)
        n_wins   = sum(1 for t in closed_this_week if t["win"])
        print(f"\n  WEEK {label:7}  {macro.level:<7}  regime={regime_label:<5}  "
              f"SPY={spy_ret:+5.1f}%  [{len(open_positions)} open | {available} slots]")
        if new_picks:
            print(f"    NEW: {', '.join(opened)}")
        if closed_this_week:
            for t in closed_this_week:
                sym = "WIN " if t["win"] else ("LOSS" if t["loss"] else "flat")
                print(f"    CLOSED {t['ticker']:<5} {sym}  "
                      f"{t['pnl_pct']:+6.2f}%  ${t['dollar_pnl']:>+7,.0f}  "
                      f"held {t['hold_weeks']}wk  [{t['exit_reason']}]")
            print(f"    --- closed {n_closed} trades | {n_wins}/{n_closed} wins | "
                  f"week PnL ${week_closed_pnl:>+7,.0f} | portfolio ${portfolio_value:,.0f}")
        elif not new_picks:
            print(f"    (no qualifying setups above score {min_score})")

    # Close any still-open positions at year end
    last_exit = weeks[-1]["exit_date"]
    for pos in open_positions:
        close = get_close_on_date(pos["ticker"], last_exit)
        if close is None:
            continue
        pnl_pct = (close - pos["entry_price"]) / pos["entry_price"] * 100
        dollar_pnl = round(pos["shares"] * (close - pos["entry_price"]), 2)
        pos.update({
            "exit_date":   last_exit,
            "exit_price":  round(close, 2),
            "pnl_pct":     round(pnl_pct, 2),
            "dollar_pnl":  dollar_pnl,
            "hold_weeks":  len(weeks) - pos["start_week_idx"],
            "win":         pnl_pct > 1.0,
            "loss":        pnl_pct < -1.0,
            "exit_reason": "YEAR_END",
        })
        all_closed.append(pos)
        portfolio_value += dollar_pnl

    # ── Summary ───────────────────────────────────────────────────────────────
    total_picks   = len(all_closed)
    total_wins    = sum(1 for t in all_closed if t["win"])
    total_dollar  = sum(t["dollar_pnl"] for t in all_closed)
    avg_hold      = sum(t["hold_weeks"] for t in all_closed) / total_picks if total_picks else 0
    win_pnl       = [t["dollar_pnl"] for t in all_closed if t["win"]]
    loss_pnl      = [t["dollar_pnl"] for t in all_closed if t["loss"]]

    print(f"\n{'='*80}")
    print(f"2025 BACKTEST v2 -- FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"  Total trades:     {total_picks}")
    print(f"  Win rate:         {total_wins}/{total_picks} ({100*total_wins/total_picks:.1f}%)" if total_picks else "")
    print(f"  Avg hold:         {avg_hold:.1f} weeks")
    print(f"  Total $ PnL:      ${total_dollar:>+,.0f}  ({100*total_dollar/PORTFOLIO:.1f}%)")
    print(f"  Final portfolio:  ${portfolio_value:>,.0f}  ({100*(portfolio_value-PORTFOLIO)/PORTFOLIO:.1f}%)")
    print(f"  Avg WIN:          ${sum(win_pnl)/len(win_pnl):>+,.0f}" if win_pnl else "")
    print(f"  Avg LOSS:         ${sum(loss_pnl)/len(loss_pnl):>+,.0f}" if loss_pnl else "")
    print(f"  Weeks skipped:    {weeks_skipped} (EXTREME macro risk)")

    # Exit reason breakdown
    reasons = defaultdict(int)
    for t in all_closed:
        reasons[t.get("exit_reason","?")] += 1
    print(f"\n  Exit reasons:")
    for r, n in sorted(reasons.items()):
        print(f"    {r:<12} {n:>3} trades")

    # Best/worst trades
    if all_closed:
        best  = max(all_closed, key=lambda t: t["dollar_pnl"])
        worst = min(all_closed, key=lambda t: t["dollar_pnl"])
        print(f"\n  Best trade:   {best['ticker']} {best['week_label']}  ${best['dollar_pnl']:>+,.0f}  ({best['pnl_pct']:+.1f}% x {best['shares']}sh, held {best['hold_weeks']}wk)")
        print(f"  Worst trade:  {worst['ticker']} {worst['week_label']}  ${worst['dollar_pnl']:>+,.0f}  ({worst['pnl_pct']:+.1f}% x {worst['shares']}sh, held {worst['hold_weeks']}wk)")

    # Save
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "backtest_2025_v2_trades.json")
    with open(out_path, "w") as f:
        json.dump(all_closed, f, indent=2)
    print(f"\n  Saved {total_picks} trades -> {out_path}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-macro",    action="store_true")
    p.add_argument("--macro-only",  action="store_true")
    p.add_argument("--min-score",   type=float, default=MIN_SCORE)
    args = p.parse_args()
    run_backtest(
        macro_filter=not args.no_macro,
        macro_only=args.macro_only,
        min_score=args.min_score,
    )
