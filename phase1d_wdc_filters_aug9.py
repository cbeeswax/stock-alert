"""
Check all WDC filters on 2024-08-09 (when RS recovered to 70.40%)
"""
import pandas as pd
from src.data.market import get_historical_data
from src.config.settings import RS_RANKER_RS_THRESHOLD, RS_RANKER_STOP_ATR_MULT, UNIVERSAL_ADX_MIN

target_date = pd.Timestamp('2024-08-09')

wdc = get_historical_data('WDC')
spy = get_historical_data('SPY')

# Cut to target date
wdc = wdc[:target_date]
spy = spy[:target_date]

# Align
spy = spy.loc[spy.index.isin(wdc.index)]
wdc = wdc.loc[wdc.index.isin(spy.index)]

if target_date not in wdc.index:
    print(f"ERROR: {target_date} not in data")
    exit(1)

# Calculate RS
wdc['Mom6M'] = (wdc['Close'] / wdc['Close'].shift(126) - 1)
spy['Mom6M'] = (spy['Close'] / spy['Close'].shift(126) - 1)
rs_6mo = (wdc['Mom6M'] / spy['Mom6M']).iloc[-1]

close = wdc['Close']
high = wdc['High']
low = wdc['Low']

last_close = close.iloc[-1]

# MAs
ma50 = close.rolling(50).mean().iloc[-1]
ma100 = close.rolling(100).mean().iloc[-1]
ma200 = close.rolling(200).mean().iloc[-1]

# EMA21
ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]

# ATR
tr = pd.concat([
    high - low,
    (high - close.shift(1)).abs(),
    (low - close.shift(1)).abs()
], axis=1).max(axis=1)
atr20 = tr.rolling(20).mean().iloc[-1]

# ADX (simple)
plus_dm = high.diff().clip(lower=0)
minus_dm = (-low.diff()).clip(lower=0)
tr_smooth = tr.rolling(14).mean()
plus_di = 100 * (plus_dm.rolling(14).mean() / tr_smooth)
minus_di = 100 * (minus_dm.rolling(14).mean() / tr_smooth)
dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
adx = dx.rolling(14).mean().iloc[-1]

# 3-month high
high_3mo = high.rolling(63).max().iloc[-1]

# Daily volatility
daily_returns = close.pct_change()
vol_20d = daily_returns.rolling(20).std().iloc[-1]

print("="*80)
print(f"WDC Filter Analysis on {target_date.date()}")
print("="*80)

print(f"\n1. RS_6mo: {rs_6mo:.2%} >= 30%? {rs_6mo >= 0.30}")
print(f"2. Stacked MAs (P>50>100>200)? {last_close > ma50 and ma50 > ma100 and ma100 > ma200}")
print(f"   - Price: ${last_close:.2f}")
print(f"   - MA50: ${ma50:.2f}")
print(f"   - MA100: ${ma100:.2f}")
print(f"   - MA200: ${ma200:.2f}")
print(f"\n3. ADX: {adx:.2f} >= 20? {adx >= 20}")
print(f"\n4. Volatility: {vol_20d:.2%} < 4%? {vol_20d < 0.04}")
print(f"\n5. 3-month High/Breakout:")
print(f"   - Price: ${last_close:.2f}")
print(f"   - 3mo High: ${high_3mo:.2f}")
print(f"   - Within 0.5% of high? {last_close >= high_3mo * 0.995}")
print(f"   - EMA21: ${ema21:.2f}")
print(f"   - Near EMA21 (<2%)? {abs(last_close - ema21) / ema21 < 0.02}")
if len(high) >= 2:
    print(f"   - Close > prior high? {last_close > high.iloc[-2]}")

print(f"\n" + "="*80)
all_pass = (rs_6mo >= 0.30 and 
            last_close > ma50 and ma50 > ma100 and ma100 > ma200 and
            adx >= 20 and 
            vol_20d < 0.04)
print(f"ALL FILTERS PASS: {all_pass}")
