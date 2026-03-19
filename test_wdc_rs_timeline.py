import pandas as pd
from src.scanning.scanner import run_scan_as_of
from src.scanning.rs_bought_tracker import RSBoughtTracker

# Test multiple dates to find when WDC qualifies for RS
test_dates = [
    pd.Timestamp('2024-01-15'),
    pd.Timestamp('2024-04-23'),
    pd.Timestamp('2025-01-10'),
    pd.Timestamp('2026-01-20'),
    pd.Timestamp('2026-03-10'),
]

tracker = RSBoughtTracker()

print("WDC Signal History:")
print("-" * 80)

for date in test_dates:
    signals_list = run_scan_as_of(date, tickers=['WDC'], rs_bought_tracker=tracker)
    rs_signals = [s for s in signals_list if s['Strategy'] == 'RelativeStrength_Ranker_Position']
    other_signals = [s for s in signals_list if s['Strategy'] != 'RelativeStrength_Ranker_Position']
    
    print(f"{date.date()}:")
    if rs_signals:
        print(f"  ✓ RelativeStrength_Ranker: {len(rs_signals)} signal(s)")
    else:
        print(f"  ✗ RelativeStrength_Ranker: No signals")
    
    if other_signals:
        for sig in other_signals:
            print(f"  • {sig['Strategy']}")
    print()
