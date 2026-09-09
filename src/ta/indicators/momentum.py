"""
Momentum indicators — pure functions, no I/O.
"""
import pandas as pd
from src.ta.indicators.moving_averages import ema


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI using Wilder's EMA smoothing method.
    Identical to the existing compute_rsi() — drop-in replacement.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def smoothed_rsi(series: pd.Series, ema_period: int = 21, rsi_period: int = 10) -> pd.Series:
    """
    RSI computed on the EMA series instead of raw price.

    Smoothing price before calculating RSI reduces noise in momentum readings.

    Args:
        series:     Raw price series (typically Close)
        ema_period: Smoothing period for the EMA (default 21)
        rsi_period: RSI lookback on the smoothed series (default 10)

    Returns:
        pd.Series of smoothed RSI values
    """
    ema_series = ema(series, ema_period)
    return rsi(ema_series, rsi_period)
