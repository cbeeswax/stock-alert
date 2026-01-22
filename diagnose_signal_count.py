#!/usr/bin/env python3
"""Diagnose which strategies are generating the most signals"""

from scanners.scanner_walkforward import run_scan_as_of
from core.pre_buy_check import pre_buy_check
import pandas as pd

# Test a recent date
test_date = "2024-01-15"

# Use full S&P 500 (or subset)
# For quick test, use a sample
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B',
           'JPM', 'V', 'UNH', 'WMT', 'JNJ', 'XOM', 'PG', 'MA', 'HD', 'CVX',
           'LLY', 'MRK', 'ABBV', 'AVGO', 'KO', 'PEP', 'COST', 'MCD', 'TMO',
           'CSCO', 'ACN', 'ABT', 'DIS', 'ADBE', 'CRM', 'DHR', 'VZ', 'NKE',
           'INTC', 'AMD', 'NFLX', 'CMCSA', 'PFE', 'PM', 'TXN', 'NEE', 'BMY',
           'UNP', 'T', 'HON', 'QCOM', 'RTX', 'BA', 'CAT', 'LOW', 'SPGI', 'UPS']

print("=" * 80)
print(f"SIGNAL ANALYSIS for {test_date}")
print(f"Testing {len(tickers)} tickers")
print("=" * 80)

# Step 1: Generate signals from scanner
signals = run_scan_as_of(test_date, tickers)

if not signals:
    print("\n❌ No signals generated")
    exit()

print(f"\n📊 STEP 1: Signals from Scanner")
print(f"Total signals: {len(signals)}")

df_signals = pd.DataFrame(signals)
strategy_counts = df_signals['Strategy'].value_counts().sort_values(ascending=False)

print(f"\nSignals by strategy (BEFORE pre_buy_check):")
for strategy, count in strategy_counts.items():
    pct = count / len(signals) * 100
    print(f"  {strategy:<25} {count:>4} ({pct:>5.1f}%)")

# Step 2: Pass through pre_buy_check
trades = pre_buy_check(signals, as_of_date=test_date)

if trades.empty:
    print("\n❌ No trades passed pre_buy_check")
    exit()

print(f"\n📊 STEP 2: After pre_buy_check")
print(f"Total trades passed: {len(trades)}")

strategy_counts_after = trades['Strategy'].value_counts().sort_values(ascending=False)

print(f"\nTrades by strategy (AFTER pre_buy_check):")
for strategy, count in strategy_counts_after.items():
    pct = count / len(trades) * 100
    print(f"  {strategy:<25} {count:>4} ({pct:>5.1f}%)")

# Step 3: Show top trades by FinalScore
print(f"\n📊 STEP 3: Top 10 by FinalScore (Van Tharp)")
print("-" * 80)

top_10 = trades.head(10)
print(f"{'Rank':<6}{'Ticker':<10}{'Strategy':<25}{'FinalScore':<12}{'Expectancy':<12}")
print("-" * 80)

for i, (_, row) in enumerate(top_10.iterrows(), 1):
    rank_marker = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
    print(f"{rank_marker} {i:<3} {row['Ticker']:<10}{row['Strategy']:<25}"
          f"{row['FinalScore']:<12.2f}{row['Expectancy']:<12.2f}")

# Analysis
print("\n" + "=" * 80)
print("ANALYSIS:")
print("=" * 80)

momentum_strats = ['EMA Crossover', '52-Week High', 'Consolidation Breakout', 'BB Squeeze']
mean_rev_strats = ['Mean Reversion', '%B Mean Reversion', 'BB+RSI Combo']

momentum_count = sum([strategy_counts.get(s, 0) for s in momentum_strats])
mean_rev_count = sum([strategy_counts.get(s, 0) for s in mean_rev_strats])

print(f"\nSignal Generation:")
print(f"  Momentum strategies:     {momentum_count:>4} signals ({momentum_count/len(signals)*100:.1f}%)")
print(f"  Mean Reversion strategies: {mean_rev_count:>4} signals ({mean_rev_count/len(signals)*100:.1f}%)")

momentum_count_after = sum([strategy_counts_after.get(s, 0) for s in momentum_strats])
mean_rev_count_after = sum([strategy_counts_after.get(s, 0) for s in mean_rev_strats])

print(f"\nAfter Filters:")
print(f"  Momentum strategies:     {momentum_count_after:>4} trades ({momentum_count_after/len(trades)*100:.1f}%)")
print(f"  Mean Reversion strategies: {mean_rev_count_after:>4} trades ({mean_rev_count_after/len(trades)*100:.1f}%)")

# Top 3 selected
top_3 = trades.head(3)
top_3_momentum = len([s for s in top_3['Strategy'] if s in momentum_strats])
top_3_mean_rev = len([s for s in top_3['Strategy'] if s in mean_rev_strats])

print(f"\nTop 3 Selected (MAX_TRADES_PER_SCAN = 3):")
print(f"  Momentum:      {top_3_momentum}")
print(f"  Mean Reversion: {top_3_mean_rev}")

print("\n" + "=" * 80)
print("INSIGHTS:")
print("=" * 80)

if mean_rev_count > momentum_count * 2:
    print("⚠️  Mean Reversion generates 2x+ more signals than Momentum!")
    print("   Reason: Lighter filters (ADX 12-15, Volume 0.8x)")
    print("   This is by design - buying weakness needs looser criteria")
else:
    print("✅ Signal distribution looks balanced")

if top_3_momentum >= 2:
    print("✅ Van Tharp scoring working! Momentum strategies (higher expectancy) selected")
elif top_3_mean_rev >= 2:
    print("⚠️  Mean Reversion dominating top 3")
    print("   Check if momentum strategies had no signals this day")
else:
    print("✅ Balanced selection between strategy types")

print("\n" + "=" * 80)
print("RECOMMENDATION:")
print("=" * 80)

if len(trades) > 50:
    print("Many trades passing filters ({}). Options:".format(len(trades)))
    print("  1. This is OK - Van Tharp scoring ranks them appropriately")
    print("  2. Only top 3 are selected anyway (MAX_TRADES_PER_SCAN)")
    print("  3. If concerned, tighten mean reversion filters:")
    print("     - Increase ADX threshold: 15 → 18")
    print("     - Increase Volume threshold: 0.8x → 1.0x")
else:
    print("Trade count looks reasonable ({} trades)".format(len(trades)))
    print("Van Tharp scoring will select the best 3")
