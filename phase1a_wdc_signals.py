"""
Phase 1A Diagnostic: Check if WDC generates signals after 2024-08-02
"""
import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
from src.scanning.scanner import run_scan_as_of
from src.scanning.rs_bought_tracker import RSBoughtTracker

# Run for Aug 2024 onwards (after WDC exit on 2024-08-02)
start = pd.Timestamp('2024-08-01')
end = pd.Timestamp('2024-12-31')

print("="*80)
print(f"PHASE 1A: WDC Signal Generation After Exit (2024-08-01 to 2024-12-31)")
print("="*80)

tracker = RSBoughtTracker()
scan_dates = pd.date_range(start, end, freq='B')  # Business days only

wdc_by_strategy = {}

for idx, date in enumerate(scan_dates):
    if idx % 10 == 0:
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
        for item in sorted(dates, key=lambda x: x['Date'])[:5]:
            print(f"  • {item['Date'].date()} @ ${item['Price']:.2f} (RS: {item.get('RS_6mo', 'N/A')}%)")
        if len(dates) > 5:
            print(f"  ... and {len(dates)-5} more")
else:
    print("\n❌ NO WDC signals generated from Aug 2024 onwards!")
    print("   This means WDC is NOT passing any strategy filters in this period")

print("\n" + "="*80)
print("TRACKER STATE at end of scan:")
print("="*80)
status = tracker.get_status()
print(status)
