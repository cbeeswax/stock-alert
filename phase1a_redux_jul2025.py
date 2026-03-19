"""
Phase 1A Redux: Check if WDC generates signals from July 2025 onwards
"""
import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
from src.scanning.scanner import run_scan_as_of
from src.scanning.rs_bought_tracker import RSBoughtTracker

# Run from July 2025 onwards (when stacked MA recovered)
start = pd.Timestamp('2025-07-20')
end = pd.Timestamp('2026-03-13')

print("="*80)
print(f"PHASE 1A REDUX: WDC Signals from July 2025 Onwards (When MA Recovered)")
print("="*80)

tracker = RSBoughtTracker(load_from_file=False)  # Fresh tracker for diagnostics
scan_dates = pd.date_range(start, end, freq='B')  # Business days only

wdc_by_strategy = {}

for idx, date in enumerate(scan_dates):
    if idx % 50 == 0:
        print(f"Progress: {idx}/{len(scan_dates)}")
    
    signals_list = run_scan_as_of(date, tickers=['WDC'], rs_bought_tracker=tracker)
    
    for sig in signals_list:
        strategy = sig['Strategy']
        if strategy not in wdc_by_strategy:
            wdc_by_strategy[strategy] = []
        wdc_by_strategy[strategy].append({
            'Date': date,
            'Price': sig.get('Price'),
            'RS_6mo': sig.get('RS_6mo'),
        })

print("\n" + "="*80)
print("RESULTS:")
print("="*80)

if wdc_by_strategy:
    print(f"\nTotal WDC signals: {sum(len(v) for v in wdc_by_strategy.values())}\n")
    for strategy in sorted(wdc_by_strategy.keys()):
        dates = wdc_by_strategy[strategy]
        print(f"{strategy}: {len(dates)} signals")
        for item in sorted(dates, key=lambda x: x['Date'])[:10]:
            print(f"  - {item['Date'].date()} @ ${item['Price']:.2f} (RS: {item.get('RS_6mo', 'N/A')}%)")
        if len(dates) > 10:
            print(f"  ... and {len(dates)-10} more")
else:
    print("\nNO WDC signals generated from July 2025 onwards!")
    print("Even though stacked MAs recovered on 2025-07-25")
    print("This suggests a DEEPER ISSUE in signal generation or tracker state")
