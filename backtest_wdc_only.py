"""
Temporary WDC-only backtest to debug signal generation.
"""
import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
from src.scanning.scanner import run_scan_as_of
from src.scanning.rs_bought_tracker import RSBoughtTracker
from src.data.market import get_historical_data
from src.config.settings import BACKTEST_START_DATE

# Run for 2024 when WDC historically appeared
start = pd.Timestamp('2024-01-01')
end = pd.Timestamp('2024-12-31')

print("="*80)
print(f"WDC-ONLY BACKTEST: {start.date()} to {end.date()}")
print("="*80)

tracker = RSBoughtTracker()
scan_dates = pd.date_range(start, end, freq='D')

wdc_entries = []
wdc_signals = []

for idx, date in enumerate(scan_dates):
    if idx % 50 == 0:
        print(f"Progress: {idx}/{len(scan_dates)}")
    
    signals_list = run_scan_as_of(date, tickers=['WDC'], rs_bought_tracker=tracker)
    
    for sig in signals_list:
        wdc_signals.append({
            'Date': date,
            'Strategy': sig['Strategy'],
            'Price': sig.get('Price', 'N/A')
        })
        
        # Track entries
        if sig['Strategy'] == 'RelativeStrength_Ranker_Position':
            wdc_entries.append({
                'Date': date,
                'Price': sig.get('Price'),
                'Strategy': 'RS_Ranker'
            })

print("\n" + "="*80)
print("RESULTS:")
print("="*80)

if wdc_signals:
    print(f"\n✓ Total signals: {len(wdc_signals)}")
    
    # Group by strategy
    by_strategy = {}
    for sig in wdc_signals:
        strat = sig['Strategy']
        if strat not in by_strategy:
            by_strategy[strat] = []
        by_strategy[strat].append(sig['Date'])
    
    for strat, dates in sorted(by_strategy.items()):
        print(f"\n  {strat}: {len(dates)} signals")
        for date in sorted(dates)[:5]:  # Show first 5
            print(f"    • {date.date()}")
        if len(dates) > 5:
            print(f"    ... and {len(dates) - 5} more")
else:
    print("\n✗ No signals generated for WDC in 2024")

if wdc_entries:
    print(f"\n💰 RS_Ranker ENTRIES: {len(wdc_entries)}")
    for entry in wdc_entries:
        print(f"  • {entry['Date'].date()} @ ${entry['Price']:.2f}")
else:
    print("\n✗ No RS_Ranker entries for WDC in 2024")

print("\n" + "="*80)
