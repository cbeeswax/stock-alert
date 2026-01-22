"""
Relative Strength Utilities
============================
Calculates relative strength ratings for stocks vs benchmark (e.g., SPY).
Used to filter stocks with strong relative performance (HIGH IMPACT #1).
"""

import pandas as pd
from utils.market_data import get_historical_data


def calculate_rs_rating(ticker, benchmark_df, period=55):
    """
    Calculates relative strength rating vs benchmark over 55-day period.

    Args:
        ticker: Stock ticker symbol
        benchmark_df: Historical DataFrame for benchmark (e.g., SPY)
        period: Lookback period for RS calculation (default 55 days)

    Returns:
        float: RS percentile score (0-100), or None if insufficient data
    """
    try:
        stock_df = get_historical_data(ticker)
        if stock_df.empty or len(stock_df) < period:
            return None

        # Calculate returns over period
        stock_return = (stock_df["Close"].iloc[-1] / stock_df["Close"].iloc[-period] - 1) * 100
        bench_return = (benchmark_df["Close"].iloc[-1] / benchmark_df["Close"].iloc[-period] - 1) * 100

        # RS rating: outperformance vs benchmark
        rs_rating = stock_return - bench_return

        # Convert to percentile-like score (normalize to 0-100 scale)
        # Assume RS ratings range from -50 to +50 for most stocks
        rs_percentile = min(100, max(0, (rs_rating + 50) * 2))

        return round(rs_percentile, 2)

    except Exception as e:
        print(f"Error calculating RS for {ticker}: {e}")
        return None
