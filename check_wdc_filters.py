import pandas as pd
import sys
from src.data.market import get_historical_data
from src.config.settings import RS_RANKER_RS_THRESHOLD, RS_RANKER_STOP_ATR_MULT

# Check 2024-04-23 specifically
target_date = pd.Timestamp('2024-04-23')

wdc = get_historical_data('WDC')
spy = get_historical_data('SPY')

if wdc is None or spy is None:
    print("ERROR: Could not load data")
    sys.exit(1)

# Align indices
spy_indexed = spy.loc[spy.index.isin(wdc.index)]
wdc_indexed = wdc.loc[wdc.index.isin(spy_indexed.index)]

# Get data up to target_date
wdc_hist = wdc_indexed[:target_date]
spy_hist = spy_indexed[:target_date]

if target_date not in wdc_hist.index:
    print(f"Target date {target_date} not in WDC data")
    sys.exit(1)

# Calculate RS (6-month momentum)
wdc_hist['Mom6M'] = (wdc_hist['Close'] / wdc_hist['Close'].shift(126) - 1)
spy_hist['Mom6M'] = (spy_hist['Close'] / spy_hist['Close'].shift(126) - 1)
rs_6mo = wdc_hist['Mom6M'] / spy_hist['Mom6M']
rs_6mo_val = rs_6mo.iloc[-1]

# Calculate technical indicators
close = wdc_hist['Close']
high = wdc_hist['High']
low = wdc_hist['Low']

# Simple MA calc
ma50 = close.rolling(50).mean()
ma100 = close.rolling(100).mean()
ma200 = close.rolling(200).mean()

# ATR
tr = pd.concat([
    high - low,
    (high - close.shift(1)).abs(),
    (low - close.shift(1)).abs()
], axis=1).max(axis=1)
atr20 = tr.rolling(20).mean()

# EMA21
ema21 = close.ewm(span=21, adjust=False).mean()

# ADX (simple)
plus_dm = high.diff().clip(lower=0)
minus_dm = (-low.diff()).clip(lower=0)
tr_smooth = tr.rolling(14).mean()
plus_di = 100 * (plus_dm.rolling(14).mean() / tr_smooth)
minus_di = 100 * (minus_dm.rolling(14).mean() / tr_smooth)
dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
adx = dx.rolling(14).mean()

# Get last values
last_close = close.iloc[-1]
last_adx = adx.iloc[-1]
last_atr = atr20.iloc[-1]
last_ema21 = ema21.iloc[-1]
last_ma50 = ma50.iloc[-1]
last_ma100 = ma100.iloc[-1]
last_ma200 = ma200.iloc[-1]
high_3mo = high.rolling(63).max().iloc[-1]

# Daily volatility
daily_returns = close.pct_change()
vol_20d = daily_returns.rolling(20).std().iloc[-1]

# Checks
stacked_mas = (last_close > last_ma50 and last_ma50 > last_ma100 and last_ma100 > last_ma200)
strong_rs = rs_6mo_val >= RS_RANKER_RS_THRESHOLD
is_3mo_high = last_close >= high_3mo * 0.995
near_ema21 = abs(last_close - last_ema21) / last_ema21 < 0.02
close_above_prior = last_close > high.iloc[-2] if len(high) >= 2 else False
pullback_breakout = near_ema21 and close_above_prior
strong_adx = last_adx >= 20

print(f"WDC as of {target_date.date()}")
print(f"Price: ${last_close:.2f}")
print(f"RS 6M: {rs_6mo_val:.2%} (threshold: {RS_RANKER_RS_THRESHOLD:.2%})")
print(f"ADX 14: {last_adx:.2f} (threshold: 20)")
print(f"Volatility 20d: {vol_20d:.2%} (threshold: 4%)")
print()
print(f"Stacked MAs (P>MA50>MA100>MA200): {stacked_mas}")
print(f"  Price: ${last_close:.2f}")
print(f"  MA50: ${last_ma50:.2f}")
print(f"  MA100: ${last_ma100:.2f}")
print(f"  MA200: ${last_ma200:.2f}")
print()
print(f"Strong RS ({rs_6mo_val:.2%} >= {RS_RANKER_RS_THRESHOLD:.2%}): {strong_rs}")
print(f"Is 3-month high: {is_3mo_high} (High 3M: ${high_3mo:.2f})")
print(f"Near EMA21: {near_ema21} (Price: ${last_close:.2f}, EMA21: ${last_ema21:.2f})")
print(f"Close above prior close: {close_above_prior} (Prior: ${high.iloc[-2]:.2f})")
print(f"Pullback breakout: {pullback_breakout}")
print(f"Strong ADX ({last_adx:.2f} >= 20): {strong_adx}")
print(f"Volatility OK (<4%): {vol_20d <= 0.04}")
print()
print(f"All filters pass: {all([stacked_mas, strong_rs, (is_3mo_high or pullback_breakout), strong_adx, vol_20d <= 0.04])}")
