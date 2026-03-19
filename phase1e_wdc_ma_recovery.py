"""
Find when WDC started passing stacked MA filter again
"""
import pandas as pd
from src.data.market import get_historical_data

wdc = get_historical_data('WDC')

# Check from Aug 2024 onwards
start_check = pd.Timestamp('2024-08-01')
end_check = pd.Timestamp('2026-03-13')

wdc_subset = wdc[start_check:end_check]

close = wdc_subset['Close']
ma50 = close.rolling(50).mean()
ma100 = close.rolling(100).mean()
ma200 = close.rolling(200).mean()

stacked_ma = (close > ma50) & (ma50 > ma100) & (ma100 > ma200)

# Find first date when stacked MA passes
first_pass_idx = stacked_ma[stacked_ma == True].index
if len(first_pass_idx) > 0:
    first_pass_date = first_pass_idx[0]
    print(f"First date stacked MA passes: {first_pass_date.date()}")
    
    # Show context
    for i in range(5):
        if i < len(first_pass_idx):
            date = first_pass_idx[i]
            row_idx = list(wdc_subset.index).index(date)
            print(f"\n{date.date()}:")
            print(f"  Close: ${close.iloc[row_idx]:.2f}")
            print(f"  MA50: ${ma50.iloc[row_idx]:.2f}")
            print(f"  MA100: ${ma100.iloc[row_idx]:.2f}")
            print(f"  MA200: ${ma200.iloc[row_idx]:.2f}")
else:
    print("Stacked MA never passes!")
    
# Show last few dates
print(f"\n\nLast 5 dates of data:")
for i in range(5):
    idx = -(i+1)
    date = wdc_subset.index[idx]
    row_idx = list(wdc_subset.index).index(date)
    c = close.iloc[row_idx]
    m50 = ma50.iloc[row_idx]
    m100 = ma100.iloc[row_idx]
    m200 = ma200.iloc[row_idx]
    passes = (c > m50) and (m50 > m100) and (m100 > m200)
    print(f"\n{date.date()}: {'PASS' if passes else 'FAIL'}")
    print(f"  Close: ${c:.2f} {'>' if c > m50 else '<'} MA50: ${m50:.2f}")
    print(f"  MA50: ${m50:.2f} {'>' if m50 > m100 else '<'} MA100: ${m100:.2f}")
    print(f"  MA100: ${m100:.2f} {'>' if m100 > m200 else '<'} MA200: ${m200:.2f}")
