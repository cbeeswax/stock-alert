"""
Debug WDC signal generation - simple version.
"""
import pandas as pd
from src.data.market import get_historical_data
from src.scanning.scanner import get_ticker_sector
from src.config.settings import RS_RANKER_SECTORS, UNIVERSAL_RS_MIN

# Test date when WDC had TrendContinuation signal
test_date = pd.Timestamp('2024-04-23')

print("="*80)
print(f"WDC FILTER ANALYSIS: {test_date.date()}")
print("="*80)

# Get data
df = get_historical_data('WDC')

if not isinstance(df.index, pd.DatetimeIndex):
    df.index = pd.to_datetime(df.index, errors='coerce')
    df = df[df.index.notna()]

# Filter to date
mask = df.index <= test_date
if not mask.any():
    print(f"No data for {test_date.date()}")
    exit(1)

df = df[mask]

close = df['Close']
high = df['High']
last_close = close.iloc[-1]

# Compute indicators
ma50 = close.rolling(50).mean()
ma100 = close.rolling(100).mean()
ma200 = close.rolling(200).mean()
ema21 = close.ewm(span=21).mean()

print(f"\n📊 Price Data:")
print(f"  Close: ${last_close:.2f}")
if len(high) >= 63:
    high_3mo = high.rolling(63).max().iloc[-1]
    print(f"  High 3mo: ${high_3mo:.2f}")

print(f"\n📈 Moving Averages:")
print(f"  Price: ${last_close:.2f}")
print(f"  MA50: ${ma50.iloc[-1]:.2f}")
print(f"  MA100: ${ma100.iloc[-1]:.2f}")
print(f"  MA200: ${ma200.iloc[-1]:.2f}")
stacked = last_close > ma50.iloc[-1] > ma100.iloc[-1] > ma200.iloc[-1]
print(f"  Stacked (P > 50 > 100 > 200): {stacked} {'✓' if stacked else '✗ BLOCKED'}")

print(f"\n💪 Strength Metrics:")
# RS would need QQQ data, skip for now
print(f"  (RS check skipped in this debug)")

print(f"\n📉 Volatility:")
daily_returns = close.pct_change()
volatility_20d = daily_returns.rolling(20).std().iloc[-1]
print(f"  20d volatility: {volatility_20d:.2%} (max: 4%) {'✓' if volatility_20d <= 0.04 else '✗ BLOCKED'}")

print(f"\n🎯 Entry Triggers:")
if len(high) >= 63:
    high_3mo = high.rolling(63).max().iloc[-1]
    is_3mo_high = last_close >= high_3mo * 0.995
    print(f"  3-month high: {is_3mo_high} ({'✓' if is_3mo_high else '✗'})")
else:
    print(f"  3-month high: Can't compute (need 63+ bars)")

near_ema21 = abs(last_close - ema21.iloc[-1]) / ema21.iloc[-1] < 0.02
close_above_prior = last_close > high.iloc[-2] if len(high) >= 2 else False
pullback = near_ema21 and close_above_prior
print(f"  EMA21 pullback: {pullback} (near={near_ema21}, above_prior={close_above_prior})")

print(f"\n✅ Sector Check:")
sector = get_ticker_sector('WDC')
is_tech = sector in RS_RANKER_SECTORS
print(f"  Sector: {sector}")
print(f"  In RS_RANKER_SECTORS: {is_tech} {'✓' if is_tech else '✗'}")

print(f"\n" + "="*80)
if not stacked:
    print("❌ BLOCKED: MAs NOT STACKED")
elif volatility_20d > 0.04:
    print("❌ BLOCKED: VOLATILITY TOO HIGH")
else:
    print("✓ PASSES BASIC FILTERS (other filters not checked)")
print("="*80)
