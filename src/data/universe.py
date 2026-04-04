"""
src/data/universe.py
=====================
S&P 500 universe and sector utilities.
Migrated from utils/sector_utils.py — drop-in replacement.
"""
import pandas as pd
from pathlib import Path
from functools import lru_cache

_SP500_PATH = Path("data") / "sp500_constituents.csv"


@lru_cache(maxsize=1)
def _load_sp500() -> pd.DataFrame:
    """Load S&P 500 constituents (cached in memory after first call).
    Falls back to GCS if not found locally."""
    if not _SP500_PATH.exists():
        try:
            from src.storage.gcs import download_file
            download_file("config/sp500_constituents.csv", _SP500_PATH)
        except Exception as exc:
            print(f"⚠️  [universe] Could not pull sp500_constituents.csv from GCS: {exc}")
    try:
        return pd.read_csv(_SP500_PATH)
    except FileNotFoundError:
        print(f"Warning: S&P 500 data file not found at {_SP500_PATH}")
        return pd.DataFrame()


def get_sp500_tickers() -> list:
    """Return full list of S&P 500 ticker symbols."""
    df = _load_sp500()
    if df.empty:
        return []
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    return df[col].tolist()


def get_sp500_data() -> pd.DataFrame:
    """Return full S&P 500 DataFrame (Symbol, Security, GICS Sector, …)."""
    return _load_sp500()


def get_tickers_by_sector(sectors: list) -> list:
    """
    Filter S&P 500 tickers to the given GICS sectors.

    Args:
        sectors: e.g. ["Information Technology", "Communication Services"]
    """
    df = _load_sp500()
    if df.empty:
        return []
    filtered = df[df["GICS Sector"].isin(sectors)]
    return filtered["Symbol"].tolist()


def get_ticker_sector(ticker: str) -> str | None:
    """Return the GICS sector for a ticker, or None if not found."""
    df = _load_sp500()
    if df.empty:
        return None
    match = df[df["Symbol"] == ticker]
    return match["GICS Sector"].iloc[0] if not match.empty else None


def filter_tickers_by_sectors(tickers: list, sectors: list) -> list:
    """Filter a list of tickers to only those belonging to the given sectors."""
    sector_set = set(get_tickers_by_sector(sectors))
    return [t for t in tickers if t in sector_set]
