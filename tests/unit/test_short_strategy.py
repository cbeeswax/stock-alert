"""
Short Strategy Backtester
==========================
Day-by-day backtest of ShortWeakRS_Retrace_Position strategy.
Tests short strategy in isolation to validate performance before enabling in main system.

Usage:
    python test_short_strategy.py
"""

import pandas as pd
from datetime import datetime
from backtester_walkforward import WalkForwardBacktester
from src.config.settings import (
    BACKTEST_START_DATE,
    BACKTEST_SCAN_FREQUENCY,
    POSITION_INITIAL_EQUITY,
    SHORT_ENABLED,
    POSITION_MAX_PER_STRATEGY,
)

def run_short_only_backtest():
    """
    Run backtest with ONLY the short strategy enabled.
    Disables all long strategies to isolate short performance.
    """
    print("\n" + "="*80)
    print("SHORT STRATEGY BACKTEST (ISOLATED)")
    print("="*80)
    print("Strategy: ShortWeakRS_Retrace_Position")
    print("Testing period: 2022-01-01 to present")
    print("Scan frequency: Daily")
    print("="*80 + "\n")

    # Check if short strategy is enabled
    if not SHORT_ENABLED:
        print("⚠️  SHORT_ENABLED = False in config")
        print("   To run this backtest, set SHORT_ENABLED = True in config/trading_config.py")
        print("   Then set POSITION_MAX_PER_STRATEGY['ShortWeakRS_Retrace_Position'] = 5")
        return None

    # Check if short strategy has position slots
    short_max = POSITION_MAX_PER_STRATEGY.get("ShortWeakRS_Retrace_Position", 0)
    if short_max == 0:
        print("⚠️  ShortWeakRS_Retrace_Position max positions = 0")
        print("   To run this backtest, set POSITION_MAX_PER_STRATEGY['ShortWeakRS_Retrace_Position'] = 5")
        return None

    print(f"✅ SHORT_ENABLED = True")
    print(f"✅ Max short positions: {short_max}")
    print(f"\n🚀 Starting backtest...\n")

    # Load S&P 500 tickers
    tickers = pd.read_csv("data/sp500_constituents.csv")["Symbol"].tolist()
    print(f"📋 Loaded {len(tickers)} tickers from S&P 500")

    # IMPORTANT: Temporarily disable ALL long strategies to test SHORT in isolation
    # Save original config
    original_max_per_strategy = POSITION_MAX_PER_STRATEGY.copy()

    # Disable all long strategies
    POSITION_MAX_PER_STRATEGY["RelativeStrength_Ranker_Position"] = 0
    POSITION_MAX_PER_STRATEGY["High52_Position"] = 0
    POSITION_MAX_PER_STRATEGY["BigBase_Breakout_Position"] = 0
    POSITION_MAX_PER_STRATEGY["EMA_Crossover_Position"] = 0
    POSITION_MAX_PER_STRATEGY["TrendContinuation_Position"] = 0
    POSITION_MAX_PER_STRATEGY["MeanReversion_Position"] = 0
    POSITION_MAX_PER_STRATEGY["%B_MeanReversion_Position"] = 0

    print(f"🚫 Disabled all LONG strategies for isolated SHORT testing")

    # Run backtester with DAILY scans (override config)
    backtester = WalkForwardBacktester(
        tickers=tickers,
        start_date=BACKTEST_START_DATE,
        initial_capital=POSITION_INITIAL_EQUITY,
        scan_frequency="D"  # Daily scans instead of weekly
    )

    try:
        results = backtester.run()
    finally:
        # Restore original config (even if backtest fails)
        POSITION_MAX_PER_STRATEGY.update(original_max_per_strategy)

    return results


def analyze_short_results(results):
    """
    Analyze backtest results and display short strategy performance.
    """
    if results is None or results.empty:
        print("\n❌ No results to analyze")
        return

    print("\n" + "="*80)
    print("SHORT STRATEGY PERFORMANCE ANALYSIS")
    print("="*80)

    # Filter for short trades only
    short_trades = results[results['Direction'] == 'SHORT'].copy()
    long_trades = results[results['Direction'] == 'LONG'].copy()

    print(f"\n📊 TRADE BREAKDOWN:")
    print(f"   Total trades: {len(results)}")
    print(f"   Long trades: {len(long_trades)}")
    print(f"   Short trades: {len(short_trades)}")

    if len(short_trades) == 0:
        print("\n⚠️  No short trades found!")
        print("   Possible reasons:")
        print("   1. Market conditions don't meet short entry criteria")
        print("   2. No weak stocks (RS ≤ -15%) rallying to 50-MA")
        print("   3. Check if scanner is evaluating short strategy correctly")
        return

    # Analyze short trades
    print(f"\n" + "="*80)
    print(f"SHORT TRADES ANALYSIS ({len(short_trades)} trades)")
    print("="*80)

    # Win rate
    wins = short_trades[short_trades['Outcome'] == 'Win']
    losses = short_trades[short_trades['Outcome'] == 'Loss']
    win_rate = len(wins) / len(short_trades) * 100 if len(short_trades) > 0 else 0

    print(f"\n📈 WIN RATE:")
    print(f"   Wins: {len(wins)} ({len(wins)/len(short_trades)*100:.1f}%)")
    print(f"   Losses: {len(losses)} ({len(losses)/len(short_trades)*100:.1f}%)")
    print(f"   Win Rate: {win_rate:.1f}%")

    # R-multiples
    avg_r = short_trades['RMultiple'].mean()
    avg_win_r = wins['RMultiple'].mean() if len(wins) > 0 else 0
    avg_loss_r = losses['RMultiple'].mean() if len(losses) > 0 else 0

    print(f"\n📊 R-MULTIPLES:")
    print(f"   Average R: {avg_r:.2f}R")
    print(f"   Average Win: {avg_win_r:.2f}R")
    print(f"   Average Loss: {avg_loss_r:.2f}R")
    print(f"   Max Win: {short_trades['RMultiple'].max():.2f}R")
    print(f"   Max Loss: {short_trades['RMultiple'].min():.2f}R")

    # P&L
    total_pnl = short_trades['PnL_$'].sum()
    avg_pnl = short_trades['PnL_$'].mean()
    avg_win_pnl = wins['PnL_$'].mean() if len(wins) > 0 else 0
    avg_loss_pnl = losses['PnL_$'].mean() if len(losses) > 0 else 0

    print(f"\n💰 PROFIT & LOSS:")
    print(f"   Total P&L: ${total_pnl:+,.2f}")
    print(f"   Average P&L: ${avg_pnl:+,.2f}")
    print(f"   Average Win: ${avg_win_pnl:+,.2f}")
    print(f"   Average Loss: ${avg_loss_pnl:+,.2f}")
    print(f"   Largest Win: ${wins['PnL_$'].max():+,.2f}" if len(wins) > 0 else "   Largest Win: N/A")
    print(f"   Largest Loss: ${losses['PnL_$'].min():+,.2f}" if len(losses) > 0 else "   Largest Loss: N/A")

    # Holding period
    avg_days = short_trades['HoldingDays'].mean()
    median_days = short_trades['HoldingDays'].median()
    max_days = short_trades['HoldingDays'].max()

    print(f"\n⏱️  HOLDING PERIOD:")
    print(f"   Average: {avg_days:.1f} days")
    print(f"   Median: {median_days:.0f} days")
    print(f"   Max: {max_days:.0f} days")

    # Exit reasons
    print(f"\n🚪 EXIT REASONS:")
    exit_breakdown = short_trades.groupby('ExitReason').agg({
        'RMultiple': ['count', 'mean'],
        'PnL_$': 'sum'
    }).round(2)
    exit_breakdown.columns = ['Count', 'Avg R', 'Total P&L']
    print(exit_breakdown.to_string())

    # Expectancy calculation (Van Tharp)
    expectancy = (win_rate/100 * avg_win_r) - ((100-win_rate)/100 * abs(avg_loss_r))

    print(f"\n🎯 EXPECTANCY (Van Tharp):")
    print(f"   Formula: (WinRate × AvgWin) - ((1-WinRate) × |AvgLoss|)")
    print(f"   Expectancy: {expectancy:.2f}R per trade")

    if expectancy > 0.5:
        status = "✅ GOOD - Positive expectancy"
    elif expectancy > 0:
        status = "⚠️  MARGINAL - Barely profitable"
    else:
        status = "❌ POOR - Negative expectancy"
    print(f"   Status: {status}")

    # Year-by-year breakdown
    print(f"\n📅 YEAR-BY-YEAR BREAKDOWN:")
    yearly = short_trades.groupby('Year').agg({
        'RMultiple': ['count', 'mean'],
        'PnL_$': 'sum',
        'Outcome': lambda x: (x == 'Win').sum() / len(x) * 100
    }).round(2)
    yearly.columns = ['Trades', 'Avg R', 'Total P&L', 'Win Rate %']
    print(yearly.to_string())

    # Sample trades
    print(f"\n📋 TOP 5 WINNING SHORT TRADES:")
    top_wins = short_trades.nlargest(5, 'PnL_$')[['Date', 'Ticker', 'Entry', 'Exit', 'RMultiple', 'PnL_$', 'HoldingDays', 'ExitReason']]
    print(top_wins.to_string(index=False))

    print(f"\n📋 TOP 5 LOSING SHORT TRADES:")
    top_losses = short_trades.nsmallest(5, 'PnL_$')[['Date', 'Ticker', 'Entry', 'Exit', 'RMultiple', 'PnL_$', 'HoldingDays', 'ExitReason']]
    print(top_losses.to_string(index=False))

    # Final recommendation
    print(f"\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)

    if expectancy > 0.5 and win_rate >= 40:
        print("✅ PASS - Short strategy shows positive expectancy")
        print(f"   Win Rate: {win_rate:.1f}% (target: ≥40%)")
        print(f"   Expectancy: {expectancy:.2f}R (target: ≥0.5R)")
        print(f"   Total P&L: ${total_pnl:+,.2f}")
        print("\n   Safe to enable for live trading after paper trading validation.")
    elif expectancy > 0:
        print("⚠️  MARGINAL - Short strategy barely profitable")
        print(f"   Win Rate: {win_rate:.1f}% (target: ≥40%)")
        print(f"   Expectancy: {expectancy:.2f}R (target: ≥0.5R)")
        print(f"   Total P&L: ${total_pnl:+,.2f}")
        print("\n   Consider additional filtering or skip this strategy.")
    else:
        print("❌ FAIL - Short strategy shows negative expectancy")
        print(f"   Win Rate: {win_rate:.1f}% (target: ≥40%)")
        print(f"   Expectancy: {expectancy:.2f}R (negative!)")
        print(f"   Total P&L: ${total_pnl:+,.2f}")
        print("\n   DO NOT enable for live trading. Strategy needs significant revision.")

    print("="*80 + "\n")

    return short_trades


def compare_long_vs_short(results):
    """
    Compare long and short performance side-by-side.
    """
    if results is None or results.empty:
        return

    print("\n" + "="*80)
    print("LONG vs SHORT COMPARISON")
    print("="*80)

    long_trades = results[results['Direction'] == 'LONG']
    short_trades = results[results['Direction'] == 'SHORT']

    if len(long_trades) == 0 and len(short_trades) == 0:
        print("No trades to compare")
        return

    comparison = pd.DataFrame({
        'Metric': ['Total Trades', 'Win Rate %', 'Avg R-Multiple', 'Total P&L', 'Avg P&L/Trade', 'Expectancy'],
        'LONG': [
            len(long_trades),
            f"{(long_trades['Outcome']=='Win').sum()/len(long_trades)*100:.1f}%" if len(long_trades) > 0 else "N/A",
            f"{long_trades['RMultiple'].mean():.2f}R" if len(long_trades) > 0 else "N/A",
            f"${long_trades['PnL_$'].sum():+,.0f}" if len(long_trades) > 0 else "$0",
            f"${long_trades['PnL_$'].mean():+,.0f}" if len(long_trades) > 0 else "$0",
            f"{((long_trades['Outcome']=='Win').sum()/len(long_trades) * long_trades[long_trades['Outcome']=='Win']['RMultiple'].mean() - (1-(long_trades['Outcome']=='Win').sum()/len(long_trades)) * abs(long_trades[long_trades['Outcome']=='Loss']['RMultiple'].mean())):.2f}R" if len(long_trades) > 0 and len(long_trades[long_trades['Outcome']=='Loss']) > 0 else "N/A"
        ],
        'SHORT': [
            len(short_trades),
            f"{(short_trades['Outcome']=='Win').sum()/len(short_trades)*100:.1f}%" if len(short_trades) > 0 else "N/A",
            f"{short_trades['RMultiple'].mean():.2f}R" if len(short_trades) > 0 else "N/A",
            f"${short_trades['PnL_$'].sum():+,.0f}" if len(short_trades) > 0 else "$0",
            f"${short_trades['PnL_$'].mean():+,.0f}" if len(short_trades) > 0 else "$0",
            f"{((short_trades['Outcome']=='Win').sum()/len(short_trades) * short_trades[short_trades['Outcome']=='Win']['RMultiple'].mean() - (1-(short_trades['Outcome']=='Win').sum()/len(short_trades)) * abs(short_trades[short_trades['Outcome']=='Loss']['RMultiple'].mean())):.2f}R" if len(short_trades) > 0 and len(short_trades[short_trades['Outcome']=='Loss']) > 0 else "N/A"
        ]
    })

    print(comparison.to_string(index=False))
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SHORT STRATEGY BACKTESTER")
    print("="*80)
    print("Day-by-day backtest of ShortWeakRS_Retrace_Position strategy")
    print(f"Test date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*80)

    # Run backtest
    results = run_short_only_backtest()

    if results is not None and not results.empty:
        # Analyze results
        short_trades = analyze_short_results(results)

        # Save results
        output_file = "backtest_results_short.csv"
        results.to_csv(output_file, index=False)
        print(f"✅ Results saved to: {output_file}")

        # Save short trades only
        if short_trades is not None and len(short_trades) > 0:
            short_file = "backtest_results_short_only.csv"
            short_trades.to_csv(short_file, index=False)
            print(f"✅ Short trades saved to: {short_file}")

    print("\n✅ Backtest complete\n")
