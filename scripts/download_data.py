#!/usr/bin/env python
"""
Data Download Utility

Download historical market data for backtesting and analysis.

Supports:
- Individual stocks
- S&P 500 constituents
- Market indices
- Bulk downloads with progress tracking

Usage:
    python scripts/download_data.py --tickers AAPL,MSFT    # Download specific stocks
    python scripts/download_data.py --sp500                # Download all S&P 500 stocks
    python scripts/download_data.py --indices QQQ,SPY      # Download indices
    python scripts/download_data.py --start-date 2020-01-01  # Custom date range
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.market import get_historical_data


def parse_tickers(tickers_str: str) -> list:
    """Parse comma-separated ticker list."""
    return [t.strip().upper() for t in tickers_str.split(',')]


def download_single_ticker(
    ticker: str,
    start_date: datetime = None,
    end_date: datetime = None,
    output_dir: Path = None
) -> bool:
    """
    Download data for single ticker.
    
    Args:
        ticker: Stock ticker
        start_date: Start date (default: 2 years ago)
        end_date: End date (default: today)
        output_dir: Output directory for CSV
        
    Returns:
        bool: Success
    """
    print(f"Downloading {ticker}...", end=" ", flush=True)
    
    try:
        data = get_historical_data(
            ticker,
            start_date=start_date,
            end_date=end_date
        )
        
        if data.empty:
            print("⚠️  No data found")
            return False
        
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = output_dir / f"{ticker}_data.csv"
            data.to_csv(output_file, index=False)
            print(f"✅ ({len(data)} rows → {output_file.name})")
        else:
            print(f"✅ ({len(data)} rows)")
        
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def download_multiple_tickers(
    tickers: list,
    start_date: datetime = None,
    end_date: datetime = None,
    output_dir: Path = None
) -> dict:
    """
    Download data for multiple tickers.
    
    Args:
        tickers: List of tickers
        start_date: Start date
        end_date: End date
        output_dir: Output directory
        
    Returns:
        dict: Results {ticker: success}
    """
    results = {}
    
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] ", end="", flush=True)
        success = download_single_ticker(ticker, start_date, end_date, output_dir)
        results[ticker] = success
    
    return results


def load_sp500_constituents() -> list:
    """Load S&P 500 ticker list."""
    sp500_file = project_root / "data" / "sp500_constituents.csv"
    
    if not sp500_file.exists():
        print(f"⚠️  S&P 500 file not found: {sp500_file}")
        print("   Using default list of major stocks")
        return [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
            "META", "TSLA", "BRK.B", "JNJ", "V",
            "MA", "PG", "UNH", "HD", "MCD",
            "NFLX", "PYPL", "AMD", "CRM", "ADBE",
        ]
    
    try:
        df = pd.read_csv(sp500_file)
        return df["Symbol"].tolist()
    except Exception as e:
        print(f"Error loading S&P 500 list: {e}")
        return []


def display_header(args):
    """Display download header."""
    print("\n" + "=" * 80)
    print("📥 DATA DOWNLOAD UTILITY")
    print("=" * 80)
    print(f"📅 Start Date: {args.start_date}")
    print(f"📅 End Date: {args.end_date}")
    if args.output_dir:
        print(f"💾 Output Directory: {args.output_dir}")
    print("=" * 80 + "\n")


def display_summary(results: dict):
    """Display download summary."""
    total = len(results)
    successful = sum(1 for v in results.values() if v)
    failed = total - successful
    
    print("\n" + "=" * 80)
    print("📊 DOWNLOAD SUMMARY")
    print("=" * 80)
    print(f"✅ Successful: {successful}/{total}")
    print(f"❌ Failed: {failed}/{total}")
    
    if failed > 0:
        print("\nFailed tickers:")
        for ticker, success in results.items():
            if not success:
                print(f"  - {ticker}")
    
    print("=" * 80)


def main():
    """Main entry point for data downloader."""
    parser = argparse.ArgumentParser(
        description="Market Data Download Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/download_data.py --tickers AAPL,MSFT    # Download specific stocks
  python scripts/download_data.py --sp500                # Download all S&P 500
  python scripts/download_data.py --indices QQQ,SPY      # Download indices
  python scripts/download_data.py --start-date 2020-01-01  # Custom date range
  python scripts/download_data.py --tickers AAPL --output data/raw  # Save to directory
        """
    )
    
    # Default dates
    default_end = datetime.now()
    default_start = default_end - timedelta(days=365*2)
    
    parser.add_argument(
        "--tickers",
        help="Comma-separated ticker list (e.g., AAPL,MSFT,GOOGL)"
    )
    parser.add_argument(
        "--sp500",
        action="store_true",
        help="Download all S&P 500 constituents"
    )
    parser.add_argument(
        "--indices",
        help="Comma-separated index list (e.g., QQQ,SPY,DIA)"
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
        "--output-dir",
        "-o",
        help="Output directory for CSV files"
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress detailed output"
    )
    
    args = parser.parse_args()
    
    # Parse dates
    try:
        start_date = pd.Timestamp(args.start_date)
        end_date = pd.Timestamp(args.end_date)
    except:
        print("❌ Invalid date format. Use YYYY-MM-DD")
        return 1
    
    if start_date >= end_date:
        print("❌ Start date must be before end date")
        return 1
    
    # Determine which tickers to download
    tickers_to_download = []
    
    if args.tickers:
        tickers_to_download = parse_tickers(args.tickers)
    elif args.sp500:
        print("Loading S&P 500 constituents...")
        tickers_to_download = load_sp500_constituents()
        if not tickers_to_download:
            print("❌ Failed to load S&P 500 constituents")
            return 1
    elif args.indices:
        tickers_to_download = parse_tickers(args.indices)
    else:
        print("❌ Please specify --tickers, --sp500, or --indices")
        return 1
    
    print(f"Will download {len(tickers_to_download)} ticker(s)")
    
    if not args.quiet:
        display_header(args)
    
    # Download data
    results = download_multiple_tickers(
        tickers_to_download,
        start_date=start_date,
        end_date=end_date,
        output_dir=args.output_dir
    )
    
    # Display summary
    if not args.quiet:
        display_summary(results)
    else:
        successful = sum(1 for v in results.values() if v)
        print(f"Downloaded {successful}/{len(results)} tickers")
    
    # Return success if all downloads succeeded
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
