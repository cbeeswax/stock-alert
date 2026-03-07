#!/usr/bin/env python
"""
Backtester Entry Point

Runs historical backtests of position trading strategies on S&P 500 data.

Supports:
- Full backtests over historical periods
- Walk-forward testing
- Strategy performance comparison
- Detailed trade logging and analysis

Usage:
    python scripts/backtest.py                          # Run default backtest
    python scripts/backtest.py --strategy RS_Ranker     # Test single strategy
    python scripts/backtest.py --start-date 2022-01-01  # Custom date range
    python scripts/backtest.py --walk-forward 252       # Walk-forward with 1-year window
    python scripts/backtest.py --output results.csv     # Save results to file
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.backtest import run_backtest
from src.config.settings import (
    STRATEGIES_CONFIG,
    POSITION_INITIAL_EQUITY,
    POSITION_RISK_PER_TRADE_PCT,
    POSITION_MAX_TOTAL,
)


def validate_date(date_string: str) -> datetime:
    """Validate and parse date string."""
    try:
        return pd.Timestamp(date_string)
    except:
        raise ValueError(f"Invalid date format: {date_string}. Use YYYY-MM-DD")


def get_available_strategies() -> list:
    """Get list of available strategies."""
    strategies = []
    if hasattr(STRATEGIES_CONFIG, 'keys'):
        strategies = list(STRATEGIES_CONFIG.keys())
    return strategies or [
        "RelativeStrength_Ranker_Position",
        "High52_Position",
        "BigBase_Breakout_Position",
    ]


def display_header(args):
    """Display backtest header."""
    print("\n" + "=" * 80)
    print("📊 POSITION TRADING BACKTEST")
    print("=" * 80)
    print(f"📅 Start Date: {args.start_date}")
    print(f"📅 End Date: {args.end_date}")
    print(f"💰 Initial Equity: ${POSITION_INITIAL_EQUITY:,}")
    print(f"⚠️  Risk per Trade: {POSITION_RISK_PER_TRADE_PCT}%")
    print(f"📊 Max Positions: {POSITION_MAX_TOTAL}")
    if args.walk_forward:
        print(f"🔄 Walk-Forward Window: {args.walk_forward} days")
    print("=" * 80 + "\n")


def run_single_backtest(
    start_date: datetime,
    end_date: datetime,
    strategy: str = None
):
    """
    Run a single backtest.
    
    Args:
        start_date: Start date
        end_date: End date
        strategy: Optional specific strategy to test
        
    Returns:
        dict: Backtest results
    """
    print(f"Running backtest: {start_date.date()} to {end_date.date()}")
    
    try:
        results = run_backtest(
            start_date=start_date,
            end_date=end_date,
            strategies=strategy,
            verbose=True
        )
        return results
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        return None


def run_walk_forward_backtest(
    start_date: datetime,
    end_date: datetime,
    window_days: int,
    strategy: str = None
):
    """
    Run walk-forward backtest.
    
    Args:
        start_date: Start date
        end_date: End date
        window_days: Window size in days
        strategy: Optional specific strategy to test
        
    Returns:
        list: List of backtest results
    """
    print(f"Running walk-forward backtest (window: {window_days} days)")
    print(f"Period: {start_date.date()} to {end_date.date()}\n")
    
    results = []
    current_start = start_date
    step = 1  # Move window forward by 1 day
    
    while current_start < end_date - timedelta(days=window_days):
        current_end = current_start + timedelta(days=window_days)
        
        print(f"Testing window: {current_start.date()} to {current_end.date()}", end=" ... ")
        
        try:
            result = run_backtest(
                start_date=current_start,
                end_date=current_end,
                strategies=strategy,
                verbose=False
            )
            results.append(result)
            print("✅")
        except Exception as e:
            print(f"❌ ({e})")
        
        current_start += timedelta(days=step)
    
    return results


def save_results(results, output_file: str):
    """Save backtest results to CSV."""
    if not results:
        print("⚠️  No results to save")
        return
    
    try:
        if isinstance(results, list) and results:
            # Walk-forward results - combine into single dataframe
            combined = pd.concat(
                [r if isinstance(r, pd.DataFrame) else pd.DataFrame([r]) for r in results],
                ignore_index=True
            )
            combined.to_csv(output_file, index=False)
        elif isinstance(results, pd.DataFrame):
            results.to_csv(output_file, index=False)
        else:
            # Single result dict
            pd.DataFrame([results]).to_csv(output_file, index=False)
        
        print(f"\n✅ Results saved to {output_file}")
    except Exception as e:
        print(f"\n❌ Error saving results: {e}")


def display_results(results):
    """Display backtest results."""
    if not results:
        print("❌ No results to display")
        return
    
    print("\n" + "=" * 80)
    print("📈 BACKTEST RESULTS")
    print("=" * 80 + "\n")
    
    if isinstance(results, list):
        # Walk-forward results
        print(f"Completed {len(results)} walk-forward windows\n")
        
        # Aggregate stats
        if results:
            returns = [r.get('total_return_pct', 0) if isinstance(r, dict) else 0 for r in results]
            avg_return = sum(returns) / len(returns) if returns else 0
            max_return = max(returns) if returns else 0
            min_return = min(returns) if returns else 0
            
            print(f"Average Return: {avg_return:.2f}%")
            print(f"Max Return: {max_return:.2f}%")
            print(f"Min Return: {min_return:.2f}%")
            print(f"Positive Windows: {sum(1 for r in returns if r > 0)}/{len(returns)}")
    else:
        # Single backtest result
        if isinstance(results, dict):
            print("Backtest Statistics:")
            for key, value in results.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")
        elif isinstance(results, pd.DataFrame):
            print(results.describe())


def main():
    """Main entry point for backtester."""
    parser = argparse.ArgumentParser(
        description="Position Trading Strategy Backtester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/backtest.py                          # Run default backtest
  python scripts/backtest.py --strategy RS_Ranker     # Test single strategy
  python scripts/backtest.py --start-date 2022-01-01  # Custom date range
  python scripts/backtest.py --walk-forward 252       # Walk-forward test
  python scripts/backtest.py --output results.csv     # Save to file
        """
    )
    
    # Determine default end date and calculate default start date (2 years back)
    default_end = datetime.now()
    default_start = default_end - timedelta(days=365*2)
    
    parser.add_argument(
        "--strategy",
        help="Specific strategy to test (if not specified, tests all)",
        choices=get_available_strategies() + ["all"],
        default=None
    )
    parser.add_argument(
        "--start-date",
        default=default_start.strftime("%Y-%m-%d"),
        help=f"Start date (default: {default_start.strftime('%Y-%m-%d')})"
    )
    parser.add_argument(
        "--end-date",
        default=default_end.strftime("%Y-%m-%d"),
        help=f"End date (default: {default_end.strftime('%Y-%m-%d')})"
    )
    parser.add_argument(
        "--walk-forward",
        type=int,
        default=None,
        help="Run walk-forward test with window size (days)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for results (CSV)"
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress detailed output"
    )
    
    args = parser.parse_args()
    
    # Parse and validate dates
    try:
        start_date = validate_date(args.start_date)
        end_date = validate_date(args.end_date)
    except ValueError as e:
        print(f"❌ {e}")
        return 1
    
    if start_date >= end_date:
        print("❌ Start date must be before end date")
        return 1
    
    # Display header
    display_header(args)
    
    # Run backtest
    if args.walk_forward:
        results = run_walk_forward_backtest(
            start_date, end_date, args.walk_forward, args.strategy
        )
    else:
        results = run_single_backtest(start_date, end_date, args.strategy)
    
    # Display results
    if not args.quiet:
        display_results(results)
    
    # Save results if requested
    if args.output:
        save_results(results, args.output)
    
    print("\n" + "=" * 80)
    print("✨ Backtest Complete")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
