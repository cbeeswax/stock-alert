"""
Debug WDC re-entry after recent stop fix.
Check if has_recent_stop() is blocking it.
"""
import pandas as pd
from src.scanning.rs_bought_tracker import RSBoughtTracker

# Test date: 2024-08-09 (5+ days after WDC exited on 2024-08-02)
test_date = pd.Timestamp('2024-08-09')

tracker = RSBoughtTracker()

print("="*80)
print(f"WDC RE-ENTRY DEBUG: {test_date.date()}")
print("="*80)

# Check WDC status
is_bought = tracker.is_bought('WDC')
has_recent_stop = tracker.has_recent_stop('WDC', trading_days_lookback=5, as_of_date=test_date)

print(f"\n1️⃣ ACTIVE POSITION CHECK:")
print(f"   is_bought('WDC'): {is_bought}")
print(f"   → Should block: {is_bought}")

print(f"\n2️⃣ RECENT STOP CHECK:")
print(f"   has_recent_stop('WDC', 5 days): {has_recent_stop}")
print(f"   → Should block: {has_recent_stop}")

print(f"\n3️⃣ WDC TRACKER DATA:")
if 'WDC' in tracker.bought_tickers:
    wdc_data = tracker.bought_tickers['WDC']
    print(f"   entry_date: {wdc_data.get('entry_date')}")
    print(f"   exit_date: {wdc_data.get('exit_date')}")
    print(f"   exit_reason: {wdc_data.get('exit_reason')}")
    print(f"   status: {wdc_data.get('status')}")
else:
    print(f"   WDC not in tracker")

print(f"\n" + "="*80)
if is_bought:
    print("❌ BLOCKED: WDC is still in active position")
elif has_recent_stop:
    print("❌ BLOCKED: WDC was recently stopped out (within 5 days)")
else:
    print("✅ PASS: WDC can re-enter if all filters pass")
print("="*80)
