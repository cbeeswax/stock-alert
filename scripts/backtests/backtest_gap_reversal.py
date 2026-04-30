"""
Gap Reversal Strategy Backtest
================================
Standalone backtest for the GapReversal_Position strategy on S&P 500.

Usage:
    python scripts/backtest_gap_reversal.py
    python scripts/backtest_gap_reversal.py --start 2020-01-01 --freq B
    python scripts/backtest_gap_reversal.py --direction long   # longs only
    python scripts/backtest_gap_reversal.py --direction short  # shorts only

Output:
    - Console summary: win rate, avg R-multiple, profit factor, max drawdown
    - backtest_results_gap_reversal.csv: full trade log
    - logs/backtest_gap_reversal.log: full debug log
"""
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import argparse
import logging
import time
import pandas as pd
import numpy as np

# ─── ensure project root on path ───────────────────────────────────────────
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtesting.engine import WalkForwardBacktester
from src.config.settings import (
    BACKTEST_START_DATE,
    BACKTEST_SCAN_FREQUENCY,
    GAP_REVERSAL_DIRECTION,
    POSITION_RISK_PER_TRADE_PCT,
)
from scripts.download_history import download_ticker, was_update_session_today, mark_update_session
import src.config.settings as cfg


# ─── logging setup ──────────────────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "backtest_gap_reversal.log"

    logger = logging.getLogger("backtest_gap_reversal")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

        # File: DEBUG and above — full detail for troubleshooting
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console: WARNING and above — keep terminal clean
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger

# ─── CLI args ───────────────────────────────────────────────────────────────
def _parse_args():
    p = argparse.ArgumentParser(description="Gap Reversal Strategy Backtest")
    p.add_argument("--start", default=str(BACKTEST_START_DATE), help="Backtest start date (YYYY-MM-DD)")
    p.add_argument(
        "--freq",
        default=BACKTEST_SCAN_FREQUENCY,
        choices=["B", "W-MON", "W-TUE", "W-WED", "W-THU", "W-FRI"],
        help="Scan frequency (B=daily, W-MON=weekly)",
    )
    p.add_argument(
        "--direction",
        default=GAP_REVERSAL_DIRECTION,
        choices=["long", "short", "both"],
        help="Trade direction filter",
    )
    p.add_argument("--capital", type=float, default=100_000, help="Starting capital")
    p.add_argument(
        "--max-positions", type=int, default=5,
        help="Max concurrent GapReversal positions (overrides config)",
    )
    p.add_argument("--no-weekly-filter", action="store_true", help="Disable weekly TF filter")
    p.add_argument("--output", default="backtest_results_gap_reversal.csv", help="Output CSV path")
    return p.parse_args()


# ─── performance metrics ────────────────────────────────────────────────────
def compute_metrics(df: pd.DataFrame) -> dict:
    """Compute comprehensive performance metrics from trade log."""
    if df.empty:
        return {}

    wins = df["Outcome"] == "Win"
    losses = ~wins

    # Basic
    total = len(df)
    win_count = wins.sum()
    loss_count = losses.sum()
    win_rate = win_count / total * 100

    # R-multiples
    avg_r = df["RMultiple"].mean()
    avg_win_r = df.loc[wins, "RMultiple"].mean() if win_count else 0
    avg_loss_r = df.loc[losses, "RMultiple"].mean() if loss_count else 0
    max_r = df["RMultiple"].max()
    min_r = df["RMultiple"].min()

    # Profit factor
    gross_profit = df.loc[wins, "PnL_$"].sum()
    gross_loss = abs(df.loc[losses, "PnL_$"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Equity curve & drawdown
    cumulative = df["PnL_$"].cumsum()
    rolling_max = cumulative.cummax()
    drawdown = cumulative - rolling_max
    max_drawdown = drawdown.min()

    return {
        "TotalTrades": total,
        "Wins": int(win_count),
        "Losses": int(loss_count),
        "WinRate%": round(win_rate, 1),
        "AvgR": round(avg_r, 2),
        "AvgWinR": round(avg_win_r, 2),
        "AvgLossR": round(avg_loss_r, 2),
        "MaxR": round(max_r, 2),
        "MinR": round(min_r, 2),
        "GrossProfit$": round(gross_profit, 2),
        "GrossLoss$": round(gross_loss, 2),
        "ProfitFactor": round(profit_factor, 2),
        "TotalPnL$": round(df["PnL_$"].sum(), 2),
        "MaxDrawdown$": round(max_drawdown, 2),
        "AvgHoldDays": round(df["HoldingDays"].mean(), 1),
    }


def print_summary(trades: pd.DataFrame, args):
    """Print formatted backtest results."""
    sep = "=" * 72

    print(f"\n{sep}")
    print("  GAP REVERSAL STRATEGY — BACKTEST RESULTS")
    print(sep)
    print(f"  Direction:   {args.direction.upper()}")
    print(f"  Start date:  {args.start}")
    print(f"  Frequency:   {args.freq}")
    print(f"  Capital:     ${args.capital:,.0f}")
    print(f"  Weekly TF:   {'DISABLED' if args.no_weekly_filter else 'ENABLED'}")
    print(sep)

    if trades.empty:
        print("  ⚠️  No trades executed.")
        return

    # Filter to GapReversal trades only
    gap_trades = trades[trades["Strategy"] == "GapReversal_Position"].copy()
    if gap_trades.empty:
        print("  ⚠️  No GapReversal_Position trades found in results.")
        return

    m = compute_metrics(gap_trades)

    print(f"\n  📊 OVERALL PERFORMANCE ({m['TotalTrades']} trades)")
    print(f"  {'Win Rate':<25} {m['WinRate%']}%  ({m['Wins']}W / {m['Losses']}L)")
    print(f"  {'Avg R-Multiple':<25} {m['AvgR']:+.2f}")
    print(f"  {'Avg Win R':<25} {m['AvgWinR']:+.2f}")
    print(f"  {'Avg Loss R':<25} {m['AvgLossR']:+.2f}")
    print(f"  {'Max R (best trade)':<25} {m['MaxR']:+.2f}")
    print(f"  {'Min R (worst trade)':<25} {m['MinR']:+.2f}")
    print(f"  {'Profit Factor':<25} {m['ProfitFactor']:.2f}")
    print(f"  {'Total PnL':<25} ${m['TotalPnL$']:+,.2f}")
    print(f"  {'Max Drawdown':<25} ${m['MaxDrawdown$']:,.2f}")
    print(f"  {'Avg Hold Days':<25} {m['AvgHoldDays']:.1f}")

    # By direction
    if args.direction == "both":
        print(f"\n  📈 LONG vs SHORT BREAKDOWN")
        for d in ["LONG", "SHORT"]:
            sub = gap_trades[gap_trades["Direction"] == d]
            if sub.empty:
                continue
            dm = compute_metrics(sub)
            print(f"\n  {d} ({dm['TotalTrades']} trades):")
            print(f"    Win Rate: {dm['WinRate%']}%  |  Avg R: {dm['AvgR']:+.2f}  |  PnL: ${dm['TotalPnL$']:+,.2f}")

    # By year
    if "Year" in gap_trades.columns:
        print(f"\n  📅 YEARLY BREAKDOWN")
        by_year = (
            gap_trades.groupby("Year")
            .agg(
                Trades=("RMultiple", "count"),
                Wins=("Outcome", lambda x: (x == "Win").sum()),
                AvgR=("RMultiple", "mean"),
                TotalPnL=("PnL_$", "sum"),
            )
            .round(2)
        )
        header = f"  {'Year':<6} {'Trades':<8} {'WinRate':<10} {'AvgR':<8} {'PnL':<12}"
        print("  " + "-" * 56)
        print(header)
        print("  " + "-" * 56)
        for year, row in by_year.iterrows():
            wr = row["Wins"] / row["Trades"] * 100
            print(f"  {year:<6} {int(row['Trades']):<8} {wr:<9.1f}%  {row['AvgR']:<8.2f} ${row['TotalPnL']:>+,.2f}")

    # Exit reason breakdown
    if "ExitReason" in gap_trades.columns:
        print(f"\n  🚪 EXIT REASON BREAKDOWN")
        by_exit = (
            gap_trades.groupby("ExitReason")
            .agg(Count=("RMultiple", "count"), AvgR=("RMultiple", "mean"), PnL=("PnL_$", "sum"))
            .sort_values("Count", ascending=False)
            .round(2)
        )
        print("  " + "-" * 56)
        for reason, row in by_exit.iterrows():
            print(f"  {reason:<28} {int(row['Count']):<6} AvgR: {row['AvgR']:+.2f}  PnL: ${row['PnL']:>+,.2f}")

    print(f"\n{sep}\n")


# ─── main ───────────────────────────────────────────────────────────────────
def main():
    args = _parse_args()
    log = _setup_logging()

    log.info("=" * 60)
    log.info("Gap Reversal Backtest started")
    log.info(f"  start={args.start}  freq={args.freq}  direction={args.direction}")
    log.info(f"  capital=${args.capital:,.0f}  max_positions={args.max_positions}  weekly_filter={'OFF' if args.no_weekly_filter else 'ON'}")
    log.info("=" * 60)

    # Apply runtime config overrides
    cfg.GAP_REVERSAL_DIRECTION = args.direction
    cfg.POSITION_MAX_PER_STRATEGY["GapReversal_Position"] = args.max_positions
    if args.no_weekly_filter:
        cfg.GAP_REVERSAL_WEEKLY_TF_FILTER = False

    # Load S&P 500 universe
    sp500 = pd.read_csv("data/sp500_constituents.csv")
    tickers = sp500["Symbol"].tolist()
    log.info(f"Universe: {len(tickers)} S&P 500 tickers loaded")
    print(f"Universe: {len(tickers)} S&P 500 tickers")

    # Update data if needed
    print("\n" + "=" * 60)
    print("📥 CHECKING HISTORICAL DATA")
    print("=" * 60)
    if was_update_session_today():
        log.info("Data already updated today — skipping download")
        print("⚡ Data already updated today — skipping download")
    else:
        import gc
        log.info("Downloading/updating historical data for all tickers...")
        print("🔄 Updating historical data...")
        batch_size = 10
        for i, ticker in enumerate(tickers, 1):
            if i % 50 == 0:
                log.debug(f"  Data download progress: [{i}/{len(tickers)}]")
                print(f"  [{i}/{len(tickers)}]")
            download_ticker(ticker)
            if i % batch_size == 0:
                gc.collect()
                time.sleep(0.1)
        gc.collect()
        download_ticker("SPY")
        download_ticker("QQQ")
        gc.collect()
        mark_update_session()
        log.info("Data update complete")
        print("✅ Data update complete!\n")

    # Run backtest
    print("=" * 60)
    print("🚀 Starting GapReversal backtest...")
    print("=" * 60)
    log.info(f"Running backtest from {args.start} ...")
    t0 = time.time()

    bt = WalkForwardBacktester(
        tickers=tickers,
        start_date=args.start,
        scan_frequency=args.freq,
        initial_capital=args.capital,
    )

    try:
        trades = bt.run()
    except Exception as e:
        log.exception(f"Backtest engine crashed: {e}")
        raise

    elapsed = time.time() - t0
    log.info(f"Backtest completed in {elapsed:.1f}s — {len(trades)} total trades")
    print(f"\n⏱️  Backtest completed in {elapsed:.1f}s")

    # Save
    if not trades.empty:
        trades.to_csv(args.output, index=False)
        log.info(f"Trade log saved to {args.output}")
        print(f"💾 Full trade log saved to: {args.output}")

        # Log summary stats to file
        gap_trades = trades[trades["Strategy"] == "GapReversal_Position"]
        if not gap_trades.empty:
            m = compute_metrics(gap_trades)
            log.info(
                f"GapReversal results: trades={m['TotalTrades']} "
                f"wr={m['WinRate%']}% avgR={m['AvgR']:+.2f} "
                f"pf={m['ProfitFactor']:.2f} pnl=${m['TotalPnL$']:+,.2f} "
                f"maxDD=${m['MaxDrawdown$']:,.2f}"
            )
    else:
        log.warning("No trades generated — check filters, RSI thresholds, or data quality")

    # Print summary
    print_summary(trades, args)


    # Detailed stats from evaluator
    if not trades.empty:
        stats = bt.evaluate(trades)
        if "StrategyAnalysis" in stats and "GapReversal_Position" in stats["StrategyAnalysis"]:
            gap_stats = stats["StrategyAnalysis"]["GapReversal_Position"]
            print(f"  Strategy evaluator confirms:")
            print(f"    Trades: {int(gap_stats['Trades'])}  WinRate: {gap_stats['WinRate%']:.1f}%  AvgR: {gap_stats['AvgRMultiple']:.2f}")


if __name__ == "__main__":
    main()
