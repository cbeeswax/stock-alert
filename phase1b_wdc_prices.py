"""
Phase 1B: Diagnose why WDC generates no signals after 2024-08-02
"""
import pandas as pd
from src.data.market import get_historical_data
from src.config.settings import MIN_PRICE, MAX_PRICE

ticker = "WDC"
wdc = get_historical_data(ticker)
spy = get_historical_data("SPY")

if wdc is None or wdc.empty:
    print(f"ERROR: Cannot load {ticker} data")
    exit(1)

print(f"WDC data loaded: {len(wdc)} rows")
print(f"Date range: {wdc.index[0].date()} to {wdc.index[-1].date()}")

# Check specific dates
test_dates = ['2024-04-23', '2024-08-02', '2024-08-09', '2024-09-01', '2024-12-31']

print("\n" + "="*80)
print("WDC Price & Volume Analysis:")
print("="*80)

for date_str in test_dates:
    try:
        date = pd.Timestamp(date_str)
        if date in wdc.index:
            row = wdc.loc[date]
            close = row['Close']
            volume = row['Volume']
            price_check = MIN_PRICE <= close <= MAX_PRICE
            vol_check = volume > 0
            
            print(f"\n{date_str}:")
            print(f"  Close: ${close:.2f} (MIN: ${MIN_PRICE}, MAX: ${MAX_PRICE}) {'✅' if price_check else '❌'}")
            print(f"  Volume: {volume:,.0f} {'✅' if vol_check else '❌'}")
        else:
            print(f"\n{date_str}: NOT IN DATA")
    except Exception as e:
        print(f"\n{date_str}: ERROR - {e}")

print("\n" + "="*80)
print("Check if WDC went bankrupt or delisted:")
print("="*80)

# Check last 10 dates
print("\nLast 10 trading days:")
for i in range(10):
    idx = -(i+1)
    date = wdc.index[idx]
    close = wdc['Close'].iloc[idx]
    volume = wdc['Volume'].iloc[idx]
    print(f"{date.date()}: ${close:.2f} | Vol: {volume:,.0f}")
