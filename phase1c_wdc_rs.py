"""Check WDC RS value in Aug 2024"""
import pandas as pd
from src.data.market import get_historical_data
from src.config.settings import RS_RANKER_RS_THRESHOLD

wdc = get_historical_data('WDC')
spy = get_historical_data('SPY')

# Align to common dates
spy = spy.loc[spy.index.isin(wdc.index)]
wdc = wdc.loc[wdc.index.isin(spy.index)]

# Calculate RS
wdc['Mom6M'] = (wdc['Close'] / wdc['Close'].shift(126) - 1)
spy['Mom6M'] = (spy['Close'] / spy['Close'].shift(126) - 1)
rs = wdc['Mom6M'] / spy['Mom6M']

print("="*80)
print(f"WDC RS_6M Analysis (Threshold: {RS_RANKER_RS_THRESHOLD:.0%})")
print("="*80)

# Test dates
test_dates = pd.date_range('2024-04-20', '2024-12-31', freq='D')

rs_values = []
for date in test_dates:
    if date in rs.index:
        val = rs.loc[date]
        rs_values.append({'date': date, 'rs': val})

print(f"\nTotal days scanned: {len(rs_values)}")
print(f"Days with RS >= {RS_RANKER_RS_THRESHOLD:.0%}: {sum(1 for x in rs_values if x['rs'] >= RS_RANKER_RS_THRESHOLD)}")
print(f"Days with RS < {RS_RANKER_RS_THRESHOLD:.0%}: {sum(1 for x in rs_values if x['rs'] < RS_RANKER_RS_THRESHOLD)}")

# Show first 10 days in Aug
print("\nFirst 10 trading days of Aug 2024:")
aug_start = pd.Timestamp('2024-08-01')
aug_end = pd.Timestamp('2024-08-10')
for item in rs_values:
    if aug_start <= item['date'] <= aug_end:
        passes = "PASS" if item['rs'] >= RS_RANKER_RS_THRESHOLD else "FAIL"
        print(f"{item['date'].date()}: RS={item['rs']:.2%} {passes}")

# Show stats
print("\nRS Statistics in Aug 2024:")
aug_rs = [x['rs'] for x in rs_values if pd.Timestamp('2024-08-01') <= x['date'] <= pd.Timestamp('2024-08-31')]
print(f"  Min: {min(aug_rs):.2%}")
print(f"  Max: {max(aug_rs):.2%}")
print(f"  Mean: {sum(aug_rs)/len(aug_rs):.2%}")
print(f"  % passing threshold: {sum(1 for x in aug_rs if x >= RS_RANKER_RS_THRESHOLD) / len(aug_rs) * 100:.1f}%")
