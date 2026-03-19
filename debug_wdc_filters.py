"""
Debug WDC signal generation with detailed filter logging.
"""
import pandas as pd
import numpy as np
from src.data.market import get_historical_data
from src.data.indicators import compute_rsi, compute_bollinger_bands
from src.scanning.scanner import get_ticker_sector, calculate_relative_strength, calculate_adx, calculate_atr
from src.config.settings import (
    RS_RANKER_SECTORS, UNIVERSAL_RS_MIN, UNIVERSAL_ADX_MIN,
    RS_RANKER_STOP_ATR_MULT, RS_RANKER_MAX_DAYS
)

# Test date when WDC had TrendContinuation signal
test_date = pd.Timestamp('2024-04-23')

print("="*80)
print(f"WDC FILTER ANALYSIS: {test_date.date()}")
print("="*80)

# Get data
df = get_historical_data('WDC')
qqq_df = get_historical_data('QQQ')

if not isinstance(df.index, pd.DatetimeIndex):
    df.index = pd.to_datetime(df.index, errors='coerce')
    df = df[df.index.notna()]

if not isinstance(qqq_df.index, pd.DatetimeIndex):
    qqq_df.index = pd.to_datetime(qqq_df.index, errors='coerce')
    qqq_df = qqq_df[qqq_df.index.notna()]

# Filter to date
mask = df.index <= test_date
if not mask.any():
    print(f"No data for {test_date.date()}")
    exit(1)

df = df[mask]
qqq_df = qqq_df[qqq_df.index <= test_date]

close = df['Close']
high = df['High']
last_close = close.iloc[-1]

# Compute indicators
ma50 = close.rolling(50).mean()
ma100 = close.rolling(100).mean()
ma200 = close.rolling(200).mean()
ema21 = close.ewm(span=21).mean()
atr20 = compute_atr(df, 20)
rs_6mo = calculate_relative_strength(df, qqq_df, 126)
adx = calculate_adx(df, 14)

print(f"\n📊 Price Data:")
print(f"  Close: ${last_close:.2f}")
print(f"  High 3mo: ${high.rolling(63).max().iloc[-1]:.2f}")

print(f"\n📈 Moving Averages:")
print(f"  Price: ${last_close:.2f}")
print(f"  MA50: ${ma50.iloc[-1]:.2f}")
print(f"  MA100: ${ma100.iloc[-1]:.2f}")
print(f"  MA200: ${ma200.iloc[-1]:.2f}")
stacked = last_close > ma50.iloc[-1] > ma100.iloc[-1] > ma200.iloc[-1]
print(f"  Stacked (P > 50 > 100 > 200): {stacked} {'✓' if stacked else '✗'}")

print(f"\n💪 Strength Metrics:")
print(f"  RS 6mo: {rs_6mo:.1%} (need: ≥{UNIVERSAL_RS_MIN:.0%}) {'✓' if rs_6mo >= UNIVERSAL_RS_MIN else '✗'}")
print(f"  ADX: {adx.iloc[-1] if len(adx) > 0 else 'N/A':.1f} (need: ≥{UNIVERSAL_ADX_MIN}) {'✓' if len(adx) > 0 and adx.iloc[-1] >= UNIVERSAL_ADX_MIN else '✗'}")

print(f"\n📉 Volatility:")
daily_returns = close.pct_change()
volatility_20d = daily_returns.rolling(20).std().iloc[-1]
print(f"  20d volatility: {volatility_20d:.2%} (max: 4%) {'✓' if volatility_20d <= 0.04 else '✗ TOO HIGH'}")

print(f"\n🎯 Entry Triggers:")
high_3mo = high.rolling(63).max().iloc[-1]
is_3mo_high = last_close >= high_3mo * 0.995
print(f"  3-month high: {is_3mo_high} ({'✓' if is_3mo_high else '✗'})")

near_ema21 = abs(last_close - ema21.iloc[-1]) / ema21.iloc[-1] < 0.02
close_above_prior = last_close > high.iloc[-2] if len(high) >= 2 else False
pullback = near_ema21 and close_above_prior
print(f"  EMA21 pullback: {pullback} ({near_ema21=}, {close_above_prior=})")

print(f"\n✅ Sector Check:")
sector = get_ticker_sector('WDC')
is_tech = sector in RS_RANKER_SECTORS
print(f"  Sector: {sector}")
print(f"  In RS_RANKER_SECTORS: {is_tech} {'✓' if is_tech else '✗'}")

print(f"\n" + "="*80)
all_pass = stacked and (rs_6mo >= UNIVERSAL_RS_MIN) and (volatility_20d <= 0.04) and (is_3mo_high or pullback)
print(f"OVERALL: {'✓ WOULD GENERATE RS_RANKER SIGNAL' if all_pass else '✗ BLOCKED'}")
print("="*80)
