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

    This is the core novelty of the Breakaway Gap Reversal strategy:
    RSI(10) of EMA(21) produces far fewer, higher-conviction extreme readings
    (<10 or >90) than RSI on raw price, triggering only at genuine extremes.

    Args:
        series:     Raw price series (typically Close)
        ema_period: Smoothing period for the EMA (default 21)
        rsi_period: RSI lookback on the smoothed series (default 10)

    Returns:
        pd.Series of smoothed RSI values
    """
    ema_series = ema(series, ema_period)
    return rsi(ema_series, rsi_period)
