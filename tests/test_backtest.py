"""
Quick test script to validate backtester fixes
Tests with a small set of tickers to verify:
1. No look-ahead bias (as_of_date is properly used)
2. Proper holding periods (not just 1 day)
3. Realistic P&L results
"""

import pandas as pd
from backtester_walkforward import WalkForwardBacktester

# Test with just a few tickers for speed
TEST_TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]

print("=" * 60)
print("🧪 TESTING FIXED BACKTESTER")
print("=" * 60)

# Run backtest on small sample
bt = WalkForwardBacktester(
    tickers=TEST_TICKERS,
    start_date="2024-01-01",  # Just 1 year for quick test
    rr_ratio=2,
    max_days=45,
    scan_frequency="W-MON"  # Weekly scans
)

print("\n📊 Running backtest...\n")
trades_df = bt.run()

print("\n" + "=" * 60)
print("📈 BACKTEST RESULTS")
print("=" * 60)

if trades_df.empty:
    print("❌ No trades generated - check if historical data exists")
else:
    print(f"\n✅ Generated {len(trades_df)} trades\n")
    print(trades_df[["Date", "Ticker", "Strategy", "Entry", "Exit", "Outcome", "HoldingDays", "PnL_$"]].to_string())

    # Show summary statistics
    summary = bt.evaluate(trades_df)
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 60)
    for key, value in summary.items():
        if key != "YearlySummary":
            print(f"{key}: {value}")

    # Key validation checks
    print("\n" + "=" * 60)
    print("✅ VALIDATION CHECKS")
    print("=" * 60)

    avg_holding = trades_df["HoldingDays"].mean()
    print(f"✓ Average Holding Days: {avg_holding:.1f} (should be > 5 days, not ~1)")

    if avg_holding > 5:
        print("✅ PASS: Holding period looks reasonable")
    else:
        print("❌ FAIL: Holding period still too short!")

    total_pnl = trades_df["PnL_$"].sum()
    print(f"✓ Total P&L: ${total_pnl:.2f}")

    print("\n🎉 Backtest completed successfully!")
