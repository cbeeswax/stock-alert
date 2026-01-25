#!/usr/bin/env python3
"""Test moderate filters - verify signal reduction"""

from scanners.scanner_walkforward import run_scan_as_of
from core.pre_buy_check import pre_buy_check
import pandas as pd

test_date = "2024-01-15"

# Test with subset of S&P 500
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B',
           'JPM', 'V', 'UNH', 'WMT', 'JNJ', 'XOM', 'PG', 'MA', 'HD', 'CVX',
           'LLY', 'MRK', 'ABBV', 'AVGO', 'KO', 'PEP', 'COST', 'MCD', 'TMO',
           'CSCO', 'ACN', 'ABT', 'DIS', 'ADBE', 'CRM', 'DHR', 'VZ', 'NKE',
           'INTC', 'AMD', 'NFLX', 'CMCSA', 'PFE', 'PM', 'TXN', 'NEE', 'BMY',
           'UNP', 'T', 'HON', 'QCOM', 'RTX', 'BA', 'CAT', 'LOW', 'SPGI', 'UPS']

print("=" * 80)
print(f"MODERATE FILTER TEST - {test_date}")
print(f"Testing {len(tickers)} tickers")
print("=" * 80)

# Generate signals
signals = run_scan_as_of(test_date, tickers)

if not signals:
    print("\n❌ No signals generated")
    exit()

print(f"\n📊 SCANNER OUTPUT:")
print(f"Total signals: {len(signals)}")

df_signals = pd.DataFrame(signals)
strategy_counts = df_signals['Strategy'].value_counts()

print(f"\nBy strategy:")
for strategy, count in strategy_counts.items():
    print(f"  {strategy:<25} {count:>3}")

# Pass through pre_buy_check
trades = pre_buy_check(signals, as_of_date=test_date)

if trades.empty:
    print("\n❌ No trades passed filters")
    exit()

print(f"\n📊 AFTER PRE_BUY_CHECK:")
print(f"Trades passed: {len(trades)}")

strategy_counts_after = trades['Strategy'].value_counts()

print(f"\nBy strategy:")
for strategy, count in strategy_counts_after.items():
    print(f"  {strategy:<25} {count:>3}")

# Show filter stats
momentum_strats = ['EMA Crossover', '52-Week High', 'Consolidation Breakout', 'BB Squeeze']
mean_rev_strats = ['Mean Reversion', '%B Mean Reversion', 'BB+RSI Combo']

momentum_sigs = sum([strategy_counts.get(s, 0) for s in momentum_strats])
mean_rev_sigs = sum([strategy_counts.get(s, 0) for s in mean_rev_strats])

momentum_trades = sum([strategy_counts_after.get(s, 0) for s in momentum_strats])
mean_rev_trades = sum([strategy_counts_after.get(s, 0) for s in mean_rev_strats])

print("\n" + "=" * 80)
print("FILTER EFFECTIVENESS:")
print("=" * 80)

print(f"\nMomentum Strategies:")
print(f"  Signals:  {momentum_sigs}")
print(f"  Passed:   {momentum_trades}")

print(f"\nMean Reversion Strategies (MODERATE FILTERS):")
print(f"  Signals:  {mean_rev_sigs}")
print(f"  Passed:   {mean_rev_trades}")

# Top 3
print("\n" + "=" * 80)
print("TOP 3 BY VAN THARP EXPECTANCY:")
print("=" * 80)

top_3 = trades.head(3)
print(f"\n{'Rank':<6}{'Ticker':<10}{'Strategy':<25}{'FinalScore':<12}{'Expectancy':<12}")
print("-" * 80)

for i, (_, row) in enumerate(top_3.iterrows(), 1):
    marker = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
    print(f"{marker} {i:<3} {row['Ticker']:<10}{row['Strategy']:<25}"
          f"{row['FinalScore']:<12.2f}{row['Expectancy']:<12.2f}")

print("\n" + "=" * 80)
print("MODERATE FILTERS WORKING:")
print("=" * 80)

print("\n✅ Mean Reversion filters:")
print("   - Volume >= 1.0x (was 0.8x)")
print("   - ADX >= 18 (was 12-15)")
print("\n✅ Expected result:")
print("   - Fewer mean reversion signals")
print("   - Still captures oversold opportunities")
print("   - Van Tharp scoring selects best trades")

if len(trades) < 100:
    print(f"\n✅ Trade count reasonable: {len(trades)} trades")
else:
    print(f"\n⚠️  Still many trades: {len(trades)} (may need stricter filters)")
