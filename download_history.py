import time
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
from config import SP500_SOURCE

# ----------------------------
# Folders and settings
# ----------------------------
DATA_DIR = Path("data/historical")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SLEEP_SECONDS = 0.5  # Reduced delay for faster incremental updates

# ----------------------------
# Download single ticker (with incremental update support)
# ----------------------------
def download_ticker(ticker: str):
    file = DATA_DIR / f"{ticker}.csv"

    try:
        # Check if file exists for incremental update
        if file.exists():
            # Read existing data
            existing_df = pd.read_csv(file, index_col=0, parse_dates=True)
            last_date = existing_df.index.max()
            today = pd.Timestamp.now().normalize()

            # If data is up to date (within 1 day), skip
            if (today - last_date).days <= 1:
                print(f"⚡ {ticker}: Already up to date (last: {last_date.date()})")
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
        else:
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
        if file.exists():
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
