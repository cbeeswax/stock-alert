#!/usr/bin/env python3
"""Analyze actual backtest results to get REAL strategy performance"""

import pandas as pd
import numpy as np

# Load backtest results
print("=" * 80)
print("ANALYZING ACTUAL BACKTEST RESULTS")
print("=" * 80)

try:
    df = pd.read_csv("backtest_results.csv")
except FileNotFoundError:
    print("\n❌ Error: backtest_results.csv not found")
    print("Please run: python backtester_walkforward.py --scan-frequency B")
    exit(1)

print(f"\nLoaded {len(df)} trades\n")

# Overall stats
total_trades = len(df)
wins = (df['Outcome'] == 'Win').sum()
losses = total_trades - wins
win_rate = wins / total_trades

print("📊 OVERALL PERFORMANCE:")
print(f"  Total Trades: {total_trades}")
print(f"  Wins: {wins} | Losses: {losses}")
print(f"  Win Rate: {win_rate*100:.2f}%")
print(f"  Avg R-Multiple: {df['RMultiple'].mean():.2f}")

# Calculate avg win and avg loss
winners = df[df['Outcome'] == 'Win']
losers = df[df['Outcome'] != 'Win']

avg_win_r = winners['RMultiple'].mean() if len(winners) > 0 else 0
avg_loss_r = losers['RMultiple'].mean() if len(losers) > 0 else 0

print(f"  Avg Win R: {avg_win_r:.2f}R")
print(f"  Avg Loss R: {avg_loss_r:.2f}R")

# Van Tharp Expectancy
expectancy = (win_rate * avg_win_r) - ((1 - win_rate) * abs(avg_loss_r))
print(f"  Van Tharp Expectancy: {expectancy:.2f}R")

# Break down by strategy
print("\n" + "=" * 80)
print("PERFORMANCE BY STRATEGY:")
print("=" * 80)

strategies = df['Strategy'].unique()

strategy_stats = []
for strategy in strategies:
    strat_df = df[df['Strategy'] == strategy]

    if len(strat_df) == 0:
        continue

    strat_wins = (strat_df['Outcome'] == 'Win').sum()
    strat_total = len(strat_df)
    strat_wr = strat_wins / strat_total

    strat_winners = strat_df[strat_df['Outcome'] == 'Win']
    strat_losers = strat_df[strat_df['Outcome'] != 'Win']

    strat_avg_win = strat_winners['RMultiple'].mean() if len(strat_winners) > 0 else 0
    strat_avg_loss = strat_losers['RMultiple'].mean() if len(strat_losers) > 0 else 0

    strat_expectancy = (strat_wr * strat_avg_win) - ((1 - strat_wr) * abs(strat_avg_loss))

    strategy_stats.append({
        'Strategy': strategy,
        'Trades': strat_total,
        'Wins': strat_wins,
        'WinRate': strat_wr,
        'AvgWinR': strat_avg_win,
        'AvgLossR': strat_avg_loss,
        'Expectancy': strat_expectancy,
        'TotalPnL': strat_df['PnL_$'].sum()
    })

# Sort by expectancy
strategy_stats.sort(key=lambda x: x['Expectancy'], reverse=True)

print(f"\n{'Strategy':<25}{'Trades':<8}{'WR':<8}{'AvgWin':<10}{'AvgLoss':<10}{'Expectancy':<12}{'PnL':<12}")
print("-" * 100)

for s in strategy_stats:
    print(f"{s['Strategy']:<25}{s['Trades']:<8}{s['WinRate']*100:<7.1f}%"
          f"{s['AvgWinR']:<10.2f}{s['AvgLossR']:<10.2f}"
          f"{s['Expectancy']:<12.2f}${s['TotalPnL']:<12,.2f}")

# Check Cascading specifically
print("\n" + "=" * 80)
print("CASCADING CROSSOVER ANALYSIS:")
print("=" * 80)

cascading = df[df['CrossoverType'] == 'Cascading']
if len(cascading) > 0:
    casc_wins = (cascading['Outcome'] == 'Win').sum()
    casc_wr = casc_wins / len(cascading)

    print(f"\nCascading Trades: {len(cascading)}")
    print(f"Win Rate: {casc_wr*100:.1f}% (Expected: 65%)")
    print(f"Avg R: {cascading['RMultiple'].mean():.2f}R")
    print(f"Avg Holding: {cascading['HoldingDays'].mean():.1f} days")

    # Exit reasons
    print(f"\nExit Reasons:")
    exit_counts = cascading['ExitReason'].value_counts()
    for reason, count in exit_counts.items():
        pct = count / len(cascading) * 100
        print(f"  {reason:<20} {count:>3} ({pct:>5.1f}%)")

    print("\n⚠️  PROBLEM: Cascading performing WAY below expected (14.6% vs 65%)")
    print("   Possible causes:")
    print("   1. Detection logic might be wrong")
    print("   2. Exit logic might be too aggressive")
    print("   3. Filters might be filtering out best setups")
else:
    print("\n❌ No Cascading trades found!")

# Exit reason analysis
print("\n" + "=" * 80)
print("EXIT REASON ANALYSIS:")
print("=" * 80)

exit_stats = df.groupby('ExitReason').agg({
    'PnL_$': 'sum',
    'RMultiple': 'mean',
    'Outcome': lambda x: (x == 'Win').sum()
}).reset_index()

exit_stats['Count'] = df.groupby('ExitReason').size().values
exit_stats['WinRate'] = exit_stats['Outcome'] / exit_stats['Count']

exit_stats = exit_stats.sort_values('Count', ascending=False)

print(f"\n{'Reason':<20}{'Count':<8}{'WinRate':<10}{'AvgR':<10}{'TotalPnL':<12}")
print("-" * 70)

for _, row in exit_stats.iterrows():
    print(f"{row['ExitReason']:<20}{row['Count']:<8}{row['WinRate']*100:<9.1f}%"
          f"{row['RMultiple']:<10.2f}${row['PnL_$']:<12,.2f}")

# Generate corrected metrics
print("\n" + "=" * 80)
print("CORRECTED VAN THARP METRICS (Based on ACTUAL backtest):")
print("=" * 80)

print("\n# Use these metrics in core/pre_buy_check.py:")
print("STRATEGY_METRICS = {")

for s in strategy_stats:
    if s['Trades'] >= 10:  # Only include strategies with enough trades
        strategy = s['Strategy']
        wr = s['WinRate']
        avg_win = s['AvgWinR']
        avg_loss = s['AvgLossR']

        print(f'    "{strategy}": ({wr:.2f}, {avg_win:.2f}, {avg_loss:.2f}),  # {s["Trades"]} trades, {wr*100:.1f}% WR')

print("}")

print("\n" + "=" * 80)
print("KEY FINDINGS:")
print("=" * 80)

# Find biggest issues
worst_strategy = min(strategy_stats, key=lambda x: x['WinRate'])
best_strategy = max(strategy_stats, key=lambda x: x['Expectancy'])

print(f"\n❌ Worst Strategy: {worst_strategy['Strategy']}")
print(f"   Win Rate: {worst_strategy['WinRate']*100:.1f}%")
print(f"   Expectancy: {worst_strategy['Expectancy']:.2f}R")
print(f"   → Consider disabling or fixing")

print(f"\n✅ Best Strategy: {best_strategy['Strategy']}")
print(f"   Win Rate: {best_strategy['WinRate']*100:.1f}%")
print(f"   Expectancy: {best_strategy['Expectancy']:.2f}R")
print(f"   → This is working!")

# Check if stop loss is the main issue
stop_loss_count = (df['ExitReason'] == 'StopLoss').sum()
stop_loss_pct = stop_loss_count / total_trades * 100

if stop_loss_pct > 50:
    print(f"\n⚠️  MAJOR ISSUE: {stop_loss_pct:.1f}% of trades hit stop loss!")
    print("   This suggests:")
    print("   1. Entries are poor quality (getting stopped out immediately)")
    print("   2. Stops might be too tight")
    print("   3. Strategies need better filters")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)

if cascading['WinRate'].iloc[0] < 0.3 if len(cascading) > 0 else False:
    print("\n1. FIX CASCADING CROSSOVER (14.6% WR is broken)")
    print("   - Check detection logic")
    print("   - Review exit conditions")
    print("   - May need to disable if unfixable")

if stop_loss_pct > 50:
    print(f"\n2. REDUCE STOP LOSS RATE ({stop_loss_pct:.1f}% is too high)")
    print("   - Tighten entry filters further")
    print("   - Improve signal quality")
    print("   - Consider wider stops for some strategies")

print("\n3. UPDATE VAN THARP METRICS with real data above")
print("   - Current metrics are based on assumptions")
print("   - Use actual backtest performance instead")

if worst_strategy['Expectancy'] < 0:
    print(f"\n4. DISABLE {worst_strategy['Strategy']} (negative expectancy)")
