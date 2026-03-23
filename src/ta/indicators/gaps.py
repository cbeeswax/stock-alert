"""
Gap indicators — pure functions, no I/O.

A gap is measured from previous close to current open.
These functions operate on daily OHLCV DataFrames with columns:
    Open, High, Low, Close, Volume
and a DatetimeIndex sorted ascending.

No look-ahead bias: all calculations use only Open of the current bar
and Close of the previous bar — both of which are known at market open.
"""
import pandas as pd


def gap_pct(df: pd.DataFrame) -> pd.Series:
    """
    Gap percentage: (Open_today - Close_yesterday) / Close_yesterday.

    Positive = gap up, negative = gap down.
    """
    prev_close = df["Close"].shift(1)
    return (df["Open"] - prev_close) / prev_close


def is_gap_up(df: pd.DataFrame, min_pct: float = 0.005) -> pd.Series:
    """
    True when today's open is at least min_pct above yesterday's close.
    Default minimum gap: 0.5% (filters noise).
    """
    return gap_pct(df) >= min_pct


def is_gap_down(df: pd.DataFrame, min_pct: float = 0.005) -> pd.Series:
    """
    True when today's open is at least min_pct below yesterday's close.
    Default minimum gap: 0.5%.
    """
    return gap_pct(df) <= -min_pct


def gap_fill_level(df: pd.DataFrame) -> pd.Series:
    """
    The gap fill level is the prior day's close.

    For a gap-up long trade: if price falls back to this level,
    the gap is filled and the setup is invalidated — use as stop loss.
    For a gap-down short trade: same logic in reverse.
    """
    return df["Close"].shift(1)
