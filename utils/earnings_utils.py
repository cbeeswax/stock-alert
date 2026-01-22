"""
Earnings Date Utilities
========================
Fetches and caches earnings announcement dates to avoid trading near earnings (HIGH IMPACT #3).
Uses yfinance calendar with 24-hour caching to minimize API calls.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path
import json

EARNINGS_CACHE_DIR = Path("data/earnings_cache")
EARNINGS_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_next_earnings_date(ticker, as_of_date=None):
    """
    Gets next earnings date for ticker using yfinance calendar.

    Args:
        ticker: Stock ticker symbol
        as_of_date: Optional date for backtesting (not used for cache, only for comparison)

    Returns:
        datetime: Next earnings date, or None if unavailable
    """
    cache_file = EARNINGS_CACHE_DIR / f"{ticker}_earnings.json"

    # Try cache first (valid for 24 hours)
    if cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text())
            cache_date = datetime.fromisoformat(cache_data["fetched_at"])
            if (datetime.now() - cache_date).days < 1:
                earnings_date = cache_data.get("next_earnings")
                if earnings_date:
                    return pd.to_datetime(earnings_date)
        except Exception:
            pass  # Cache read error, fetch fresh data

    try:
        stock = yf.Ticker(ticker)
        calendar = stock.calendar

        if calendar is None or calendar.empty:
            return None

        next_earnings = calendar.get("Earnings Date")
        if next_earnings is None or (isinstance(next_earnings, pd.Series) and next_earnings.empty):
            return None

        # Extract date (may be range, take first date)
        if isinstance(next_earnings, pd.Series):
            next_earnings = next_earnings.iloc[0]

        earnings_date = pd.to_datetime(next_earnings)

        # Cache result
        cache_file.write_text(json.dumps({
            "ticker": ticker,
            "next_earnings": earnings_date.isoformat(),
            "fetched_at": datetime.now().isoformat()
        }))

        return earnings_date

    except Exception as e:
        print(f"Warning: Could not fetch earnings for {ticker}: {e}")
        return None


def is_near_earnings(ticker, as_of_date=None, days_buffer=5):
    """
    Checks if stock is within days_buffer of earnings announcement.

    Args:
        ticker: Stock ticker symbol
        as_of_date: Optional date for backtesting
        days_buffer: Number of days before earnings to avoid trading (default 5)

    Returns:
        bool: True if near earnings (skip trade), False otherwise
    """
    next_earnings = get_next_earnings_date(ticker, as_of_date)
    if next_earnings is None:
        return False  # No earnings data, allow trade

    check_date = pd.to_datetime(as_of_date) if as_of_date else pd.Timestamp.now()
    days_until_earnings = (next_earnings - check_date).days

    return 0 <= days_until_earnings <= days_buffer
