import time
import pandas as pd
import yfinance as yf
from pathlib import Path
from config import SP500_SOURCE

# ----------------------------
# Folders and settings
# ----------------------------
DATA_DIR = Path("data/historical")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SLEEP_SECONDS = 3  # Delay between downloads to avoid blocking

# ----------------------------
# Download single ticker
# ----------------------------
def download_ticker(ticker: str):
    file = DATA_DIR / f"{ticker}.csv"
    if file.exists():
        print(f"⚡ Skipping {ticker}, already downloaded")
        return

    try:
        df = yf.download(
            ticker,
            period="5y",
            interval="1d",
            auto_adjust=True,
            progress=False
        )

        if df.empty:
            print(f"⚠️ {ticker}: No data")
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

        # Save CSV with proper Date index
        df.to_csv(file, index_label="Date")
        print(f"✅ Saved {ticker}")

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
