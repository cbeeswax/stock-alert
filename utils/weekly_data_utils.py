"""
Weekly Data Utilities
======================
Fetches and caches weekly timeframe data for multi-timeframe confirmation (MEDIUM IMPACT #7).
Checks weekly trend alignment (price above EMA10) for stronger signals.
"""

import pandas as pd
import yfinance as yf
from pathlib import Path

WEEKLY_DATA_DIR = Path("data/weekly")
WEEKLY_DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_weekly_data(ticker):
    """
    Fetches weekly OHLCV data for ticker (cached).

    Args:
        ticker: Stock ticker symbol

    Returns:
        DataFrame: Weekly data with OHLCV columns
    """
    cache_file = WEEKLY_DATA_DIR / f"{ticker}_weekly.csv"

    try:
        # Check cache (update if older than 7 days)
        if cache_file.exists():
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            last_date = df.index[-1]
            if (pd.Timestamp.now() - last_date).days < 7:
                return df

        # Download weekly data
        df = yf.download(ticker, period="2y", interval="1wk", progress=False, auto_adjust=True)

        if df.empty:
            return pd.DataFrame()

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        # Standardize columns
        if "Adj Close" in df.columns:
            df = df.rename(columns={"Adj Close": "Close"})

        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df.to_csv(cache_file)

        return df

    except Exception as e:
        print(f"Error fetching weekly data for {ticker}: {e}")
        return pd.DataFrame()


def check_weekly_trend_alignment(ticker, as_of_date=None):
    """
    Checks if stock is above weekly EMA10 (MEDIUM IMPACT #7).

    Args:
        ticker: Stock ticker symbol
        as_of_date: Optional date for backtesting

    Returns:
        bool: True if weekly trend aligned, False otherwise
    """
    df = get_weekly_data(ticker)
    if df.empty or len(df) < 10:
        return True  # Insufficient data, allow trade

    if as_of_date:
        df = df[df.index <= pd.to_datetime(as_of_date)]

    if df.empty or len(df) < 10:
        return True  # Insufficient data after filtering, allow trade

    weekly_ema10 = df["Close"].ewm(span=10).mean().iloc[-1]
    current_price = df["Close"].iloc[-1]

    return current_price > weekly_ema10
