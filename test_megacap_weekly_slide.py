"""
Test MegaCap Weekly Slide SHORT strategy
Run backtest from 2015-01-01 to latest on hard-coded mega-cap list
"""

import pandas as pd
from datetime import datetime
from backtester_walkforward import WalkForwardBacktester
from config.trading_config import MEGACAP_WEEKLY_SLIDE_CFG

def main():
    print("=" * 80)
    print("MegaCap Weekly Slide SHORT Strategy - Backtest")
    print("=" * 80)

    # Get hard-coded symbol list from config
    symbols = MEGACAP_WEEKLY_SLIDE_CFG.get('SYMBOLS', [])

    print(f"\n📊 Universe: {len(symbols)} mega-cap stocks")
    print(f"   {', '.join(symbols)}")

    print(f"\n🔍 MegaCap Weekly Slide Config:")
    print(f"   Weekly context: close < MA10 & MA20, RSI < 50, ≤10% off 52w high")
    print(f"   Daily entry: close < MA20, close < 10d low, volume ≥ {MEGACAP_WEEKLY_SLIDE_CFG.get('DAILY_VOLUME_MULT', 1.1)}×")
    print(f"   Stop: above max(swing_high_10d, MA20) + {MEGACAP_WEEKLY_SLIDE_CFG.get('STOP_BUFFER_PCT', 0.01)*100}%")
    print(f"   Partial: {int(MEGACAP_WEEKLY_SLIDE_CFG.get('PARTIAL_SIZE', 0.5)*100)}% at +{MEGACAP_WEEKLY_SLIDE_CFG.get('PARTIAL_R', 2.0)}R")
    print(f"   Breakeven stop after partial: {MEGACAP_WEEKLY_SLIDE_CFG.get('BREAKEVEN_AFTER_PARTIAL', True)}")
    print(f"   Hard time stop: {MEGACAP_WEEKLY_SLIDE_CFG.get('MAX_DAYS', 50)} days")
    print(f"   Max positions: {MEGACAP_WEEKLY_SLIDE_CFG.get('MAX_POSITIONS', 2)}")
    print(f"   Cooldown: {MEGACAP_WEEKLY_SLIDE_CFG.get('COOLDOWN_DAYS', 10)} days per symbol")
    print(f"   Risk per trade: {MEGACAP_WEEKLY_SLIDE_CFG.get('RISK_PER_TRADE_PCT', 0.5)}%")

    # Run backtest from 2015-01-01
    start_date = "2015-01-01"
    backtester = WalkForwardBacktester(
        tickers=symbols,
        start_date=start_date,
        scan_frequency="W-MON",  # Weekly scans on Monday
        initial_capital=100000
    )

    print(f"\n🚀 Running backtest from {start_date}...")
    results_df = backtester.run()

    if results_df.empty:
        print("\n⚠️  No trades executed in backtest")
        return

    # Filter for MegaCap_WeeklySlide_Short strategy only
    strategy_results = results_df[results_df['Strategy'] == 'MegaCap_WeeklySlide_Short'].copy()

    if strategy_results.empty:
        print("\n⚠️  No MegaCap_WeeklySlide_Short trades found")
        return

    # Save results
    output_file = "backtest_results_megacap_weekly_slide.csv"
    strategy_results.to_csv(output_file, index=False)
    print(f"\n💾 Results saved to: {output_file}")

    # Analysis
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)

    total_trades = len(strategy_results)

    # Count Full and Partial entries separately
    full_positions = strategy_results[strategy_results['PositionType'] == 'Full']
    partial_exits = strategy_results[strategy_results['PositionType'] == 'Partial']
    runner_exits = strategy_results[strategy_results['PositionType'] == 'Runner']

    # Calculate unique positions (Full + first Partial)
    unique_positions = len(full_positions) + len(partial_exits)

    print(f"\n📊 Total Entries: {total_trades}")
    print(f"   Full positions: {len(full_positions)}")
    print(f"   Partial exits: {len(partial_exits)}")
    print(f"   Runner exits: {len(runner_exits)}")
    print(f"   Unique positions: {unique_positions}")

    # Win/Loss analysis (count Full and Runner exits only, not Partials)
    trade_outcomes = strategy_results[strategy_results['PositionType'].isin(['Full', 'Runner'])].copy()

    if len(trade_outcomes) > 0:
        wins = trade_outcomes[trade_outcomes['RMultiple'] > 0]
        losses = trade_outcomes[trade_outcomes['RMultiple'] <= 0]

        win_rate = len(wins) / len(trade_outcomes) * 100
        avg_r = trade_outcomes['RMultiple'].mean()
        total_pnl = strategy_results['PnL_$'].sum()

        print(f"\n📈 Win/Loss:")
        print(f"   Wins: {len(wins)} ({win_rate:.1f}%)")
        print(f"   Losses: {len(losses)} ({100-win_rate:.1f}%)")
        print(f"   Average R: {avg_r:+.2f}R")
        print(f"   Total P&L: ${total_pnl:+,.2f}")

    # Year-by-year breakdown
    print(f"\n📅 Year-by-Year Breakdown:")
    for year in sorted(strategy_results['Year'].unique()):
        year_trades = strategy_results[strategy_results['Year'] == year]
        year_outcomes = year_trades[year_trades['PositionType'].isin(['Full', 'Runner'])]

        if len(year_outcomes) > 0:
            year_wins = year_outcomes[year_outcomes['RMultiple'] > 0]
            year_win_rate = len(year_wins) / len(year_outcomes) * 100
            year_avg_r = year_outcomes['RMultiple'].mean()
            year_pnl = year_trades['PnL_$'].sum()

            print(f"   {year}: {len(year_outcomes)} trades, {year_win_rate:.1f}% WR, {year_avg_r:+.2f}R avg, ${year_pnl:+,.2f}")

    # R-multiple distribution
    print(f"\n📊 R-Multiple Distribution:")
    r_multiples = trade_outcomes['RMultiple']

    big_wins = r_multiples[r_multiples >= 2.0]
    small_wins = r_multiples[(r_multiples > 0) & (r_multiples < 2.0)]
    small_losses = r_multiples[(r_multiples < 0) & (r_multiples >= -0.5)]
    big_losses = r_multiples[r_multiples < -0.5]

    print(f"   Big wins (≥2.0R): {len(big_wins)} trades")
    print(f"   Small wins (0 to 2.0R): {len(small_wins)} trades")
    print(f"   Small losses (0 to -0.5R): {len(small_losses)} trades")
    print(f"   Big losses (<-0.5R): {len(big_losses)} trades")

    # Exit reason analysis
    print(f"\n🚪 Exit Reason Analysis:")
    for exit_reason in trade_outcomes['ExitReason'].value_counts().index:
        count = len(trade_outcomes[trade_outcomes['ExitReason'] == exit_reason])
        avg_r = trade_outcomes[trade_outcomes['ExitReason'] == exit_reason]['RMultiple'].mean()
        pct = count / len(trade_outcomes) * 100
        print(f"   {exit_reason}: {count} ({pct:.1f}%), avg {avg_r:+.2f}R")

    # Best/worst trades
    print(f"\n🏆 Best Trades:")
    best_trades = trade_outcomes.nlargest(5, 'RMultiple')
    for _, trade in best_trades.iterrows():
        print(f"   {trade['Ticker']} ({trade['Date'].date()}): {trade['RMultiple']:+.2f}R (${trade['PnL_$']:+,.2f}) in {trade['HoldingDays']}d")

    print(f"\n📉 Worst Trades:")
    worst_trades = trade_outcomes.nsmallest(5, 'RMultiple')
    for _, trade in worst_trades.iterrows():
        print(f"   {trade['Ticker']} ({trade['Date'].date()}): {trade['RMultiple']:+.2f}R (${trade['PnL_$']:+,.2f}) in {trade['HoldingDays']}d")

    print("\n" + "=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
