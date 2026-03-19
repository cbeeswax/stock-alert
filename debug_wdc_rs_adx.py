#!/usr/bin/env python3
"""Debug WDC RS and ADX values during backtest."""

import pandas as pd
from datetime import datetime, timedelta
from src.data.market import get_historical_data
from src.analysis.relative_strength import calculate_rs
from src.analysis.technical_analysis import calculate_adx, calculate_ema, calculate_ma
from src.config.settings import RS_RANKER_RS_THRESHOLD

# Load WDC and SPY data
wdc_data = get_historical_data('WDC', start_date='2024-01-01', end_date='2024-12-31')
spy_data = get_historical_data('SPY', start_date='2024-01-01', end_date='2024-12-31')

if wdc_data is None or wdc_data.empty or spy_data is None or spy_data.empty:
    print("ERROR: Could not load data")
    exit(1)

# Align indices
spy_data = spy_data.loc[spy_data.index.isin(wdc_data.index)]
wdc_data = wdc_data.loc[wdc_data.index.isin(spy_data.index)]

# Calculate RS and ADX
wdc_data['RS'] = calculate_rs(wdc_data, spy_data)

wdc_data['ADX'] = calculate_adx(wdc_data)
wdc_data['EMA21'] = calculate_ema(wdc_data['Close'], 21)
wdc_data['MA100'] = calculate_ma(wdc_data['Close'], 100)
wdc_data['MA200'] = calculate_ma(wdc_data['Close'], 200)

# Check dates of interest
test_dates = [
    "2024-01-25",  # Original entry attempt
    "2024-04-23",  # Previous run entry
    "2024-04-24", "2024-04-25", "2024-04-26", "2024-04-27",
    "2024-04-28", "2024-04-29", "2024-04-30",
    "2024-05-01", "2024-05-02", "2024-05-03",
]

print(f"\nRS Threshold for RS_Ranker: {RS_RANKER_RS_THRESHOLD:.2%}")
print(f"ADX Threshold for RS_Ranker (Neutral): 20\n")
print("="*100)

for date_str in test_dates:
    try:
        date = pd.Timestamp(date_str)
        if date in wdc_data.index:
            row = wdc_data.loc[date]
            print(f"{date_str}: Close=${row['Close']:.2f} | RS={row['RS']:.2%} | ADX={row['ADX']:.2f} | MA100=${row['MA100']:.2f} | MA200=${row['MA200']:.2f}")
            
            rs_pass = row['RS'] >= RS_RANKER_RS_THRESHOLD
            adx_pass = row['ADX'] >= 20
            ma_pass = row['EMA21'] > row['MA100']
            
            print(f"           RS PASS: {rs_pass} | ADX PASS: {adx_pass} | EMA21>MA100: {ma_pass}")
        else:
            print(f"{date_str}: NOT IN DATA")
    except Exception as e:
        print(f"{date_str}: ERROR - {e}")
    print("-"*100)
