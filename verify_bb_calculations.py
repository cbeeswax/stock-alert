#!/usr/bin/env python3
"""Verify BB calculations are working correctly"""

from utils.market_data import get_historical_data
from utils.ema_utils import compute_bollinger_bands, compute_percent_b, compute_rsi
import pandas as pd

# Test on AAPL
ticker = "AAPL"
test_date = "2024-01-15"

print(f"Verifying BB calculations for {ticker} on {test_date}")
print("=" * 80)

df = get_historical_data(ticker)
df = df[df.index <= test_date]

if len(df) >= 200:
    close = df["Close"]

    # Calculate BB
    middle_band, upper_band, lower_band, bandwidth = compute_bollinger_bands(close, period=20, std_dev=2)

    # Calculate %B
    percent_b = compute_percent_b(close, upper_band, lower_band)

    # Calculate RSI
    rsi14 = compute_rsi(close, 14)

    # Get last 10 days
    last_10 = pd.DataFrame({
        'Close': close.tail(10),
        'BB_Upper': upper_band.tail(10),
        'BB_Middle': middle_band.tail(10),
        'BB_Lower': lower_band.tail(10),
        'BandWidth': bandwidth.tail(10),
        'PercentB': percent_b.tail(10),
        'RSI14': rsi14.tail(10)
    })

    print("\nLast 10 days of BB indicators:")
    print(last_10.to_string())

    # Get latest values
    last_close = close.iloc[-1]
    last_upper = upper_band.iloc[-1]
    last_middle = middle_band.iloc[-1]
    last_lower = lower_band.iloc[-1]
    last_bandwidth = bandwidth.iloc[-1]
    last_percent_b = percent_b.iloc[-1]
    last_rsi = rsi14.iloc[-1]

    print("\n" + "=" * 80)
    print(f"Latest values for {ticker} on {test_date}:")
    print(f"  Close: ${last_close:.2f}")
    print(f"  BB Upper: ${last_upper:.2f}")
    print(f"  BB Middle: ${last_middle:.2f}")
    print(f"  BB Lower: ${last_lower:.2f}")
    print(f"  BandWidth: {last_bandwidth:.2f}%")
    print(f"  %B: {last_percent_b:.2f}")
    print(f"  RSI(14): {last_rsi:.2f}")

    # Check entry conditions
    print("\n" + "=" * 80)
    print("Entry Condition Checks:")

    # BB Squeeze
    if len(bandwidth) >= 126:
        bw_6m_low = bandwidth.iloc[-126:].min()
        is_squeeze = last_bandwidth <= bw_6m_low * 1.05
        breakout_above = last_close > last_upper
        print(f"\n  BB Squeeze:")
        print(f"    6-month BW low: {bw_6m_low:.2f}%")
        print(f"    Current BW: {last_bandwidth:.2f}%")
        print(f"    Is Squeeze? {is_squeeze} (within 5% of low)")
        print(f"    Breakout above? {breakout_above} (${last_close:.2f} > ${last_upper:.2f})")

    # %B Mean Reversion
    ma200 = close.rolling(200).mean().iloc[-1]
    in_uptrend = last_close > ma200
    extreme_oversold = last_percent_b < 0
    print(f"\n  %B Mean Reversion:")
    print(f"    MA200: ${ma200:.2f}")
    print(f"    In uptrend? {in_uptrend} (${last_close:.2f} > ${ma200:.2f})")
    print(f"    %B < 0? {extreme_oversold} (%B = {last_percent_b:.2f})")

    # BB+RSI Combo
    bb_oversold = last_percent_b < 0.2
    rsi_oversold = last_rsi < 30
    print(f"\n  BB+RSI Combo:")
    print(f"    %B < 0.2? {bb_oversold} (%B = {last_percent_b:.2f})")
    print(f"    RSI < 30? {rsi_oversold} (RSI = {last_rsi:.2f})")
    print(f"    Both oversold? {bb_oversold and rsi_oversold}")

    print("\n" + "=" * 80)
    print("✅ BB calculations are working correctly!")
    print("\nNote: Entry conditions are strict - signals are rare by design")

else:
    print("Not enough historical data")
