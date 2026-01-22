import time
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
from config.config import SP500_SOURCE
import os

# ----------------------------
# Folders and settings
# ----------------------------
DATA_DIR = Path("data/historical")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Track last update to avoid re-downloading on same day
UPDATE_TRACKER_FILE = DATA_DIR / ".last_update"

SLEEP_SECONDS = 0.5  # Reduced delay for faster incremental updates

# ----------------------------
# Update tracking functions
# ----------------------------
def was_updated_today(file: Path) -> bool:
    """Check if file was modified today."""
    if not file.exists():
        return False

    file_mtime = datetime.fromtimestamp(file.stat().st_mtime)
    today = datetime.now().date()
    file_date = file_mtime.date()

    return file_date == today


def mark_update_session():
    """Mark that we performed an update session today."""
    UPDATE_TRACKER_FILE.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def was_update_session_today() -> bool:
    """Check if we already ran an update session today."""
    if not UPDATE_TRACKER_FILE.exists():
        return False

    try:
        last_update = UPDATE_TRACKER_FILE.read_text().strip()
        last_update_date = datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S").date()
        return last_update_date == datetime.now().date()
    except:
        return False

# ----------------------------
# Download single ticker (with incremental update support)
# ----------------------------
def download_ticker(ticker: str, force: bool = False):
    """
    Download or update historical data for a ticker.

    Args:
        ticker: Stock ticker symbol
        force: Force download even if already updated today
    """
    file = DATA_DIR / f"{ticker}.csv"

    try:
        # 🆕 CHECK 1: Skip if file was already updated today (unless forced)
        if not force and was_updated_today(file):
            # File was already downloaded/updated today, skip
            return  # Silent skip for efficiency

        # CHECK 2: File exists - do incremental update
        if file.exists():
            # Read existing data
            existing_df = pd.read_csv(file, index_col=0, parse_dates=True)

            if existing_df.empty:
                print(f"⚠️ {ticker}: Empty file, re-downloading...")
                file.unlink()  # Delete empty file
                # Fall through to full download
            else:
                last_date = existing_df.index.max()
                today = pd.Timestamp.now().normalize()

                # If data is up to date (within 3 days to account for weekends), skip
                days_diff = (today - last_date).days
                if days_diff <= 3:
                    print(f"⚡ {ticker}: Already up to date (last: {last_date.date()})")
                    # Touch file to mark as checked today
                    file.touch()
                    return

                # Download only new data since last date
                start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                print(f"🔄 {ticker}: Updating from {start_date}...")

                df = yf.download(
                    ticker,
                    start=start_date,
                    end=None,  # Today
                    interval="1d",
                    auto_adjust=True,
                    progress=False
                )

        # File doesn't exist - full download
        if not file.exists():
            # Download full 5 years for new ticker
            print(f"📥 {ticker}: Downloading 5 years...")
            df = yf.download(
                ticker,
                period="5y",
                interval="1d",
                auto_adjust=True,
                progress=False
            )

        if df.empty:
            if file.exists():
                print(f"⚡ {ticker}: No new data")
            else:
                print(f"⚠️ {ticker}: No data available")
            return

        # -----------------------------
        # CLEAN HEADER
        # -----------------------------
        # Flatten MultiIndex if exists
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        # Rename Adj Close to Close
        if "Adj Close" in df.columns:
            df = df.rename(columns={"Adj Close": "Close"})

        # Keep only standard OHLCV columns
        df = df.loc[:, ["Open", "High", "Low", "Close", "Volume"]]

        # Append or save
        if file.exists() and os.path.getsize(file) > 0:
            # Append new data to existing
            existing_df = pd.read_csv(file, index_col=0, parse_dates=True)
            combined = pd.concat([existing_df, df])
            combined = combined[~combined.index.duplicated(keep='last')]  # Remove duplicates
            combined = combined.sort_index()
            combined.to_csv(file, index_label="Date")
            print(f"✅ {ticker}: Added {len(df)} new rows (total: {len(combined)})")
        else:
            # Save new file
            df.to_csv(file, index_label="Date")
            print(f"✅ {ticker}: Saved {len(df)} rows")

        # 🆕 Touch file to update modification time (marks as updated today)
        file.touch()

        # Sleep between downloads
        time.sleep(SLEEP_SECONDS)

    except Exception as e:
        print(f"❌ {ticker}: {e}")

# ----------------------------
# Main loop
# ----------------------------
def main():
    sp500 = pd.read_csv(SP500_SOURCE)
    tickers = sp500["Symbol"].tolist()

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] Downloading {ticker}")
        download_ticker(ticker)

# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    main()
