#!/usr/bin/env python
"""
Refresh Historical Data
=======================
Downloads fresh daily OHLCV data for all S&P 500 constituents and
key market indices. Runs incrementally — only adds new rows to
existing cache files, so it is fast on subsequent runs.

Called by the GitHub Actions workflow before main.py to ensure the
scanner always has up-to-date data.

Usage:
    python scripts/refresh_data.py
    python scripts/refresh_data.py --period 1mo   # limit download window
"""

import sys
import argparse
import time
from pathlib import Path

import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.market import download_historical
from src.storage.gcs import sync_from_gcs, sync_to_gcs

# Market indices always included regardless of S&P 500 list
ALWAYS_REFRESH = ["QQQ", "SPY", "IWM", "XLI", "XLV", "XLE", "XLB", "XLY"]


def load_tickers() -> list:
    sp500_file = project_root / "data" / "sp500_current_constituents.csv"
    fallback_file = project_root / "data" / "sp500_constituents.csv"
    if not sp500_file.exists():
        try:
            from src.storage.gcs import download_file
            download_file("config/sp500_current_constituents.csv", sp500_file)
        except Exception as exc:
            print(f"⚠️  Could not pull sp500_current_constituents.csv from GCS: {exc}")
    if not sp500_file.exists() and fallback_file.exists():
        sp500_file = fallback_file
    if not sp500_file.exists():
        print(f"⚠️  {sp500_file} not found — refreshing indices only")
        return ALWAYS_REFRESH
    df = pd.read_csv(sp500_file)
    tickers = df["Symbol"].tolist()
    extras = [t for t in ALWAYS_REFRESH if t not in tickers]
    return tickers + extras


def main():
    parser = argparse.ArgumentParser(description="Refresh historical market data")
    parser.add_argument(
        "--period", default="2y",
        help="yfinance period string (default: 2y). Use '1mo' for quick refresh."
    )
    args = parser.parse_args()

    tickers = load_tickers()
    total = len(tickers)

    # Pull existing CSVs from GCS so incremental updates work correctly
    historical_dir = project_root / "data" / "historical"
    print("☁️  Syncing historical data from GCS…")
    pulled = sync_from_gcs("historical-data", historical_dir)
    print(f"   ↓ {pulled} new files downloaded from GCS")

    print(f"📥 Refreshing {total} tickers (period={args.period})…")

    failed = []
    for i, ticker in enumerate(tickers, 1):
        try:
            df = download_historical(ticker, period=args.period)
            status = f"✅ {len(df)} rows" if not df.empty else "⚠️  empty"
        except Exception as e:
            status = f"❌ {e}"
            failed.append(ticker)
        if i % 50 == 0 or i == total:
            print(f"  [{i}/{total}] {ticker}: {status}")

        # Brief pause every 100 tickers to avoid rate-limiting
        if i % 100 == 0:
            time.sleep(2)

    print(f"\n✅ Done. {total - len(failed)}/{total} refreshed.")
    if failed:
        print(f"❌ Failed ({len(failed)}): {', '.join(failed)}")

    # Note: individual download_historical() calls already upload each file
    # to GCS as they complete. This final sync catches any that were skipped.
    print("\n☁️  Final sync of all local CSVs → GCS…")
    uploaded = sync_to_gcs(historical_dir, "historical-data")
    print(f"   ↑ {uploaded} files pushed to GCS")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
