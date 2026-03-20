"""
Backward-compatibility shim. 
The backtester has moved to src/backtesting/engine.py.
This file is kept so existing scripts continue to work.
"""
import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.backtesting.engine import WalkForwardBacktester  # noqa: F401
import time
import pandas as pd
from src.config.settings import (
    BACKTEST_START_DATE, BACKTEST_SCAN_FREQUENCY,
    POSITION_RISK_PER_TRADE_PCT, POSITION_MAX_PER_STRATEGY,
    POSITION_MAX_TOTAL, POSITION_PYRAMID_ENABLED
)
from scripts.download_history import download_ticker, was_update_session_today, mark_update_session

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Position trading backtest")
    parser.add_argument(
        "--scan-frequency",
        type=str,
        default=BACKTEST_SCAN_FREQUENCY,
        choices=["B", "W-MON", "W-TUE", "W-WED", "W-THU", "W-FRI"],
        help="Scan frequency (default: B for daily)"
    )
    args = parser.parse_args()

    tickers = pd.read_csv("data/sp500_constituents.csv")["Symbol"].tolist()

    print("="*60)
    print("📥 CHECKING HISTORICAL DATA")
    print("="*60)

    if was_update_session_today():
        print("⚡ Data already updated today - skipping download")
    else:
        import gc
        print("🔄 Updating historical data for all tickers...")
        batch_size = 10
        for i, ticker in enumerate(tickers, 1):
            if i % 50 == 0:
                print(f"\n[Progress: {i}/{len(tickers)} tickers processed]")
            download_ticker(ticker)
            if i % batch_size == 0:
                gc.collect()
                time.sleep(0.2)
        gc.collect()
        print("\n📊 Updating benchmark data...")
        download_ticker("SPY")
        download_ticker("QQQ")
        gc.collect()
        mark_update_session()
        print("\n✅ Data update complete!")

    print("\n" + "="*60)
    print("🚀 Starting position trading backtest...")
    print("="*60 + "\n")

    bt = WalkForwardBacktester(
        tickers=tickers,
        start_date=BACKTEST_START_DATE,
        scan_frequency=args.scan_frequency
    )

    print(f"⚙️  CONFIG:")
    print(f"   Risk per trade: {POSITION_RISK_PER_TRADE_PCT}%")
    if isinstance(POSITION_MAX_PER_STRATEGY, dict):
        print(f"   Max positions: {POSITION_MAX_TOTAL} total")
        print(f"   Per-strategy limits: RS_Ranker/High52=8, BigBase=6, EMA_Cross=4, Others=3")
    else:
        print(f"   Max positions: {POSITION_MAX_TOTAL} total, {POSITION_MAX_PER_STRATEGY} per strategy")
    print(f"   Scan frequency: {args.scan_frequency}")
    print(f"   Pyramiding: {'Enabled' if POSITION_PYRAMID_ENABLED else 'Disabled'}\n")

    trades = bt.run()
    if not trades.empty:
        trades.to_csv("backtest_results.csv", index=False)
        print(f"\n💾 Results saved to: backtest_results.csv")

    stats = bt.evaluate(trades)

    print("\n" + "="*80)
    print("📊 POSITION TRADING BACKTEST SUMMARY")
    print("="*80)
    print(f"\n📈 Overall Performance:")
    print(f"   Total Trades: {stats['TotalTrades']}")
    print(f"   Wins: {stats['Wins']} | Losses: {stats['Losses']}")
    print(f"   Win Rate: {stats['WinRate%']}%")
    print(f"   Total PnL: ${stats['TotalPnL_$']:,.2f}")
    print(f"   Avg R-Multiple: {stats['AvgRMultiple']}")
    print(f"   Avg Holding Days: {stats['AvgHoldingDays']}")
    print("\n" + "="*80)
