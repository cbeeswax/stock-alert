"""
Quick test script for TechMomentum_Swing_30_60 strategy
"""
import pandas as pd
from src.scanning.scanner import run_scan_as_of
from src.analysis.sectors import get_tickers_by_sector
from src.config.settings import TECHMOMENTUM_SECTORS


# Get tech/comm tickers
tech_tickers = get_tickers_by_sector(TECHMOMENTUM_SECTORS)
print(f"Testing TechMomentum on {len(tech_tickers)} tech/communication stocks")
print(f"Sample tickers: {tech_tickers[:10]}\n")

# Test scanning on a recent date
test_date = pd.Timestamp.today() - pd.Timedelta(days=5)
print(f"Scanning as of: {test_date.date()}")

# Run scan (this will check all strategies including TechMomentum)
signals = run_scan_as_of(test_date, tech_tickers)

# Filter for TechMomentum signals
techmomentum_signals = [s for s in signals if s.get("Strategy") == "TechMomentum_Swing_30_60"]

print(f"\nTotal signals found: {len(signals)}")
print(f"TechMomentum signals: {len(techmomentum_signals)}")

if techmomentum_signals:
    print("\nTechMomentum Signals:")
    for sig in techmomentum_signals[:5]:  # Show first 5
        print(f"  {sig['Ticker']}: ${sig['Price']:.2f} | Score: {sig['Score']:.1f} | RS: {sig['RelativeStrength']:.1f}%")
else:
    print("\nNo TechMomentum signals found on this date (this is normal - strategy is selective)")
    print("Try running a full backtest to see results over time.")

print("\n✅ Test complete!")
