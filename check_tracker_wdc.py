"""
Check RS bought tracker status for WDC.
"""
import pandas as pd
from src.scanning.rs_bought_tracker import RSBoughtTracker

test_date = pd.Timestamp('2024-04-23')

tracker = RSBoughtTracker()

print("="*80)
print(f"WDC RS TRACKER STATUS: {test_date.date()}")
print("="*80)

# Check if WDC is in bought list
is_bought = tracker.is_bought('WDC')
print(f"\nis_bought('WDC'): {is_bought}")

# Check if can buy again
can_buy = tracker.can_buy_again('WDC', cooldown_days=30, as_of_date=test_date)
print(f"can_buy_again('WDC', cooldown=30): {can_buy}")

# Show tracker contents
print(f"\nTracker contents:")
if tracker.bought:
    for ticker, info in tracker.bought.items():
        print(f"  {ticker}: {info}")
else:
    print(f"  (empty)")

print("\n" + "="*80)
print("ℹ️  Empty tracker means no prior position or cooldown")
print("    WDC should be allowed to enter if all other filters pass!")
print("="*80)
