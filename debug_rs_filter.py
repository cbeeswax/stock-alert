import pandas as pd
from src.data.market import get_historical_data
from src.scanning.scanner import run_scan_as_of
from src.scanning.rs_bought_tracker import RSBoughtTracker

# Test RS filter on 2026-03-10
date = pd.Timestamp('2026-03-10')
print(f"Checking WDC on {date.date()}:")

tracker = RSBoughtTracker()
signals_list = run_scan_as_of(date, tickers=['WDC'], rs_bought_tracker=tracker)

print(f"All signals: {len(signals_list)}")
for sig in signals_list:
    print(f"  {sig['Ticker']} {sig['Strategy']}")

# Now manually check why it doesn't generate RS signal
df = get_historical_data('WDC')
if not isinstance(df.index, pd.DatetimeIndex):
    df.index = pd.to_datetime(df.index, errors='coerce')

mask = df.index <= date
if mask.any():
    row_idx = mask.sum() - 1
    row = df[mask].iloc[-1]
    print(f"\nWDC Data ({date.date()}):")
    print(f"  Close: ${row['Close']:.2f}")
    if 'ADX' in df.columns:
        print(f"  ADX: {row['ADX']:.1f}")
    if 'SMA50' in df.columns and 'SMA100' in df.columns and 'SMA200' in df.columns:
        print(f"  SMA50: ${row['SMA50']:.2f}, SMA100: ${row['SMA100']:.2f}, SMA200: ${row['SMA200']:.2f}")
        stacked = row['Close'] > row['SMA50'] > row['SMA100'] > row['SMA200']
        print(f"  Stacked MAs: {stacked}")
