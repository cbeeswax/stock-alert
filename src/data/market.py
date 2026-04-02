from pathlib import Path
import pandas as pd
import yfinance as yf
import time
import random

DATA_DIR = Path("data/historical")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_market_cap(ticker):
    """Retrieves market capitalization from yfinance safely."""
    try:
        info = yf.Ticker(ticker).info
        if not info:
            print(f"⚠️ [market.py] No info returned for {ticker}")
            return 0
        market_cap = info.get("marketCap", 0)
        if isinstance(market_cap, pd.Series):
            market_cap = market_cap.iloc[-1]
        return float(market_cap or 0)
    except Exception as e:
        print(f"⚠️ [market.py] Error getting market cap for {ticker}: {e}")
        return 0


def get_historical_data(ticker: str) -> pd.DataFrame:
    """Load cached daily OHLCV from data/historical/{ticker}.csv.
    Falls back to GCS if not cached locally."""
    file = DATA_DIR / f"{ticker}.csv"

    # Pull from GCS if not cached locally
    if not file.exists():
        from src.storage.gcs import download_file
        gcs_path = f"historical-data/{ticker}.csv"
        download_file(gcs_path, file)

    if not file.exists():
        return pd.DataFrame()
    # parse_dates=True no longer reliably converts the index in pandas 2.x,
    # so we explicitly convert after loading.
    df = pd.read_csv(file, index_col=0)
    df.index = pd.to_datetime(df.index, errors='coerce')

    # Drop rows with unparseable / corrupt index (e.g. PLTR's 81469727 row)
    df = df[df.index.notna()]
    df = df.sort_index()

    # Drop rows with obviously corrupt prices (> 100x the median close).
    # This catches data errors without rejecting legitimate high-priced stocks.
    if "Close" in df.columns and not df.empty:
        median_close = df["Close"].median()
        if median_close > 0:
            df = df[df["Close"] <= median_close * 100]

    return df


def download_historical(
    ticker: str,
    period: str = "2y",
    interval: str = "1d",
    max_retries: int = 5,
) -> pd.DataFrame:
    """
    Download and cache daily OHLCV data via yfinance.
    Handles all known yfinance column naming variants.
    Incrementally updates the cache on subsequent calls.

    Returns cached DataFrame (may be empty on persistent failure).
    """
    for attempt in range(1, max_retries + 1):
        try:
            data = yf.download(
                ticker, period=period, interval=interval,
                progress=False, auto_adjust=False, group_by="ticker",
            )

            if isinstance(data, pd.Series):
                data = data.to_frame().T

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = ["_".join(col).strip() for col in data.columns.values]

            tkr_upper = ticker.upper()
            renamed = {}
            for col in list(data.columns):
                if col.startswith(tkr_upper + "_"):
                    renamed[col] = col.replace(tkr_upper + "_", "")
                elif col.endswith("_" + tkr_upper):
                    renamed[col] = col.replace("_" + tkr_upper, "")
            if renamed:
                data = data.rename(columns=renamed)

            if "Close" not in data.columns:
                raise ValueError(f"Missing 'Close' column. Got: {list(data.columns)}")

            numeric_cols = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in data.columns]
            data = data[numeric_cols].apply(pd.to_numeric, errors="coerce").dropna(subset=["Close"])

            if data.empty:
                raise ValueError("No valid price data after cleaning")

            file_path = DATA_DIR / f"{ticker}.csv"
            if file_path.exists():
                try:
                    cached = pd.read_csv(file_path, index_col=0, parse_dates=True)
                    new_rows = data[~data.index.isin(cached.index)]
                    if not new_rows.empty:
                        updated = pd.concat([cached, new_rows]).sort_index()
                        updated.to_csv(file_path)
                        from src.storage.gcs import upload_file
                        upload_file(file_path, f"historical-data/{ticker}.csv")
                        return updated
                    return cached
                except Exception:
                    pass

            data.to_csv(file_path)

            # Upload to GCS
            from src.storage.gcs import upload_file
            upload_file(file_path, f"historical-data/{ticker}.csv")

            return data

        except Exception as e:
            wait = 2 ** attempt + random.random()
            print(f"⚠️ [market.py] Attempt {attempt} failed for {ticker}: {e}. Retry in {wait:.1f}s")
            time.sleep(wait)

    print(f"❌ [market.py] Failed to download {ticker} after {max_retries} attempts")
    return pd.DataFrame()