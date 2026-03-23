"""
Trend indicators — pure functions, no I/O.
"""
import pandas as pd


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average Directional Index (ADX).
    Measures trend strength regardless of direction.
    ADX >= 25 = trending, >= 30 = strong trend.
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    plus_dm = high.diff()
    minus_dm = low.diff() * -1
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    smoothed_tr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / smoothed_tr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / smoothed_tr)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    return dx.rolling(period).mean()


def adx_latest(df: pd.DataFrame, period: int = 14) -> float:
    """Most recent ADX value as a scalar."""
    result = adx(df, period)
    return float(result.iloc[-1]) if not result.empty else 0.0
