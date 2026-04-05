"""Load and prepare daily OHLCV data, resampling to weekly bars."""

import os
import pandas as pd


DATA_DIR = os.environ.get(
    "HISTORICAL_DATA_DIR",
    r"C:\Users\pelac\Git\HistoricalData\historical",
)


def _read_ticker(ticker: str) -> pd.DataFrame:
    """Read a single ticker CSV (yfinance multi-ticker export format)."""
    path = os.path.join(DATA_DIR, f"{ticker}.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, skiprows=[1], index_col=0)
    df.index = pd.to_datetime(df.index, format="%Y-%m-%d", errors="coerce")
    df = df[df.index.notna()].sort_index()
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    return df


def load_daily(ticker: str, start: str = None, end: str = None) -> pd.DataFrame:
    """Return daily OHLCV DataFrame for a ticker, optionally filtered by date."""
    df = _read_ticker(ticker)
    if df.empty:
        return df
    if start:
        df = df[df.index >= start]
    if end:
        df = df[df.index <= end]
    return df


def to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly (Monday-open, Friday-close) bars."""
    if daily.empty:
        return daily
    weekly = daily.resample("W-FRI").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    weekly = weekly.dropna(how="all")
    return weekly


def load_weekly(ticker: str, start: str = None, end: str = None) -> pd.DataFrame:
    """Return weekly OHLCV DataFrame for a ticker."""
    daily = load_daily(ticker, start=start, end=end)
    return to_weekly(daily)


def available_tickers() -> list[str]:
    """Return sorted list of all tickers with data files."""
    return sorted(
        f[:-4] for f in os.listdir(DATA_DIR) if f.endswith(".csv")
    )
