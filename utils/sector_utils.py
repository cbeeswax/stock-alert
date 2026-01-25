"""
Sector filtering utilities for strategy-specific universe selection
"""
import pandas as pd
from pathlib import Path


def get_sp500_data():
    """Load S&P 500 constituents data with sector information"""
    data_path = Path(__file__).parent.parent / "data" / "sp500_constituents.csv"
    try:
        df = pd.read_csv(data_path)
        return df
    except FileNotFoundError:
        print(f"Warning: S&P500 data file not found at {data_path}")
        return pd.DataFrame()


def get_tickers_by_sector(sectors):
    """
    Filter S&P 500 tickers by GICS sector

    Args:
        sectors: List of sector names (e.g., ["Information Technology", "Communication Services"])

    Returns:
        List of ticker symbols in the specified sectors
    """
    df = get_sp500_data()
    if df.empty:
        return []

    # Filter by sector
    filtered = df[df["GICS Sector"].isin(sectors)]

    # Return list of symbols
    return filtered["Symbol"].tolist()


def get_ticker_sector(ticker):
    """
    Get the GICS sector for a specific ticker

    Args:
        ticker: Stock ticker symbol

    Returns:
        Sector name string, or None if not found
    """
    df = get_sp500_data()
    if df.empty:
        return None

    match = df[df["Symbol"] == ticker]
    if match.empty:
        return None

    return match["GICS Sector"].iloc[0]


def filter_tickers_by_sectors(tickers, sectors):
    """
    Filter a list of tickers to only include those in specified sectors

    Args:
        tickers: List of ticker symbols to filter
        sectors: List of sector names to include

    Returns:
        Filtered list of tickers
    """
    sector_tickers = get_tickers_by_sector(sectors)
    return [t for t in tickers if t in sector_tickers]
