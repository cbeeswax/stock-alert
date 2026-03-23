"""
Volatility indicators — pure functions, no I/O.
"""
import pandas as pd
from typing import Tuple


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (series)."""
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"] - df["Close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def atr_latest(df: pd.DataFrame, period: int = 14) -> float:
    """Most recent ATR value as a scalar."""
    result = atr(df, period)
    return float(result.iloc[-1]) if not result.empty else 0.0


def bollinger_bands(
    series: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands.

    Returns:
        (middle_band, upper_band, lower_band, bandwidth)
        bandwidth = (upper - lower) / middle * 100
    """
    middle = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    bandwidth = (upper - lower) / middle * 100
    return middle, upper, lower, bandwidth


def percent_b(price: pd.Series, upper: pd.Series, lower: pd.Series) -> pd.Series:
    """
    %B — where price sits relative to Bollinger Bands.
    0 = lower band, 0.5 = middle, 1 = upper band.
    """
    return (price - lower) / (upper - lower)
