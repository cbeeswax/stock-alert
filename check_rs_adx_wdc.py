"""
Check RS and ADX for WDC on specific date.
"""
import pandas as pd
from src.data.market import get_historical_data
from src.scanning.scanner import calculate_relative_strength, calculate_adx
from src.config.settings import UNIVERSAL_RS_MIN, UNIVERSAL_ADX_MIN

test_date = pd.Timestamp('2024-04-23')

print("="*80)
print(f"WDC DETAILED FILTER CHECK: {test_date.date()}")
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
qqq_mask = qqq_df.index <= test_date

if not mask.any() or not qqq_mask.any():
    print(f"No data for {test_date.date()}")
    exit(1)

df = df[mask]
qqq_df = qqq_df[qqq_mask]

print(f"\n1️⃣ RELATIVE STRENGTH (6 months / 126 days)")
print("-" * 80)
rs_6mo = calculate_relative_strength(df, qqq_df, 126)
print(f"  WDC RS vs QQQ: {rs_6mo:.2%}")
print(f"  Threshold:     {UNIVERSAL_RS_MIN:.0%}")
print(f"  Status:        {'✓ PASS' if rs_6mo >= UNIVERSAL_RS_MIN else '✗ BLOCKED'}")

print(f"\n2️⃣ ADX (Average Directional Index)")
print("-" * 80)
adx = calculate_adx(df, 14)
adx_val = adx.iloc[-1] if len(adx) > 0 else None
print(f"  ADX(14):       {adx_val:.1f}" if adx_val else "  ADX(14):       N/A")
print(f"  Threshold:     {UNIVERSAL_ADX_MIN}")
print(f"  Status:        {'✓ PASS' if adx_val and adx_val >= UNIVERSAL_ADX_MIN else '✗ BLOCKED'}")

print(f"\n" + "="*80)
print("SUMMARY:")
print("="*80)

if rs_6mo < UNIVERSAL_RS_MIN:
    print(f"❌ RS is TOO LOW ({rs_6mo:.1%} < {UNIVERSAL_RS_MIN:.0%})")
    print(f"   WDC is underperforming vs QQQ - likely a growth stock in tech selloff")
elif adx_val and adx_val < UNIVERSAL_ADX_MIN:
    print(f"❌ ADX is TOO LOW ({adx_val:.1f} < {UNIVERSAL_ADX_MIN})")
    print(f"   WDC lacks trend strength - too choppy for entry")
else:
    print(f"✓ Both RS and ADX PASS!")
    print(f"  WDC should generate RS_Ranker signal unless blocked by:")
    print(f"    - Already in bought list")
    print(f"    - In cooldown period")
    print(f"    - Failed 3-month high & EMA21 trigger")

print("="*80)
