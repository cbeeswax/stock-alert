import pandas as pd
from src.data.market import get_historical_data
from src.scanning.scanner import run_scan_as_of
from src.scanning.rs_bought_tracker import RSBoughtTracker

# Check what strategies are enabled on CURRENT branch
from src.config.settings import POSITION_MAX_PER_STRATEGY

print("Current enabled strategies:")
for strat, limit in POSITION_MAX_PER_STRATEGY.items():
    if limit > 0:
        print(f"  ✓ {strat}: {limit}")
    else:
        print(f"  ✗ {strat}: DISABLED")

# Check signals on 2024-04-23
date = pd.Timestamp('2024-04-23')
print(f"\nScanning on {date.date()}...")

rs_tracker = RSBoughtTracker()
signals_list = run_scan_as_of(date, tickers=['WDC'], rs_bought_tracker=rs_tracker)

print(f"Signals: {len(signals_list)}")
for signal in signals_list:
    print(f"  • {signal.get('Ticker')} {signal.get('Strategy')}")
