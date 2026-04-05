"""Compute technical indicators on weekly OHLCV DataFrames."""

import numpy as np
import pandas as pd


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _true_range(df: pd.DataFrame) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = _true_range(df)
    return tr.ewm(com=period - 1, adjust=False).mean()


def _adx(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (ADX, +DI, -DI)."""
    tr = _true_range(df)
    plus_dm = df["high"].diff().clip(lower=0)
    minus_dm = (-df["low"].diff()).clip(lower=0)
    # Zero out when other DM is larger
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)

    atr = tr.ewm(com=period - 1, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(com=period - 1, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(com=period - 1, adjust=False).mean() / atr.replace(0, np.nan))

    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(com=period - 1, adjust=False).mean()
    return adx, plus_di, minus_di


def _bollinger(close: pd.Series, period: int = 20, n_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (upper, middle, lower)."""
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return mid + n_std * std, mid, mid - n_std * std


def _fibonacci_score(df: pd.DataFrame, lookback: int = 26) -> pd.Series:
    """
    Score proximity to key Fibonacci retracement levels.
    Uses a rolling lookback window high/low to define the range.
    Returns +1 if price is near 38.2 / 50 / 61.8% support and trending up,
    0 otherwise.
    """
    roll_high = df["high"].rolling(lookback).max()
    roll_low = df["low"].rolling(lookback).min()
    rng = roll_high - roll_low

    fib_382 = roll_low + 0.382 * rng
    fib_500 = roll_low + 0.500 * rng
    fib_618 = roll_low + 0.618 * rng

    close = df["close"]
    tolerance = 0.03 * rng  # within 3% of fib level

    near = (
        ((close - fib_382).abs() < tolerance)
        | ((close - fib_500).abs() < tolerance)
        | ((close - fib_618).abs() < tolerance)
    )
    return near.astype(float)


def compute_all(df: pd.DataFrame, spy: pd.DataFrame = None) -> pd.DataFrame:
    """
    Compute all indicators on a weekly OHLCV DataFrame.
    Returns the same DataFrame with added indicator columns.
    """
    if len(df) < 30:
        return df

    close = df["close"]
    volume = df["volume"]

    # Trend: EMA alignment
    df["ema9"] = _ema(close, 9)
    df["ema21"] = _ema(close, 21)
    df["ema50"] = _ema(close, 50)
    df["ema200"] = _ema(close, 200)

    # EMA alignment score: count how many EMAs are stacked correctly
    df["ema_align"] = (
        (close > df["ema9"]).astype(int)
        + (df["ema9"] > df["ema21"]).astype(int)
        + (df["ema21"] > df["ema50"]).astype(int)
        + (df["ema50"] > df["ema200"]).astype(int)
    ) / 4.0  # 0.0 to 1.0

    # EMA9 slope (weekly % change of EMA9)
    df["ema9_slope"] = df["ema9"].pct_change(4)  # 4-week momentum

    # Momentum: RSI
    df["rsi"] = _rsi(close, 14)
    # RSI score: best between 50-70 (momentum zone without overbought)
    df["rsi_score"] = (
        (df["rsi"] > 50).astype(float)
        * (df["rsi"] < 75).astype(float)
    )

    # Rate of change (4-week, 13-week)
    df["roc4"] = close.pct_change(4)
    df["roc13"] = close.pct_change(13)

    # Strength: ADX
    adx, plus_di, minus_di = _adx(df, 14)
    df["adx"] = adx
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di
    df["adx_score"] = (df["adx"] > 20).astype(float) * (df["plus_di"] > df["minus_di"]).astype(float)

    # Volatility: Bollinger Bands
    bb_upper, bb_mid, bb_lower = _bollinger(close, 20, 2.0)
    df["bb_upper"] = bb_upper
    df["bb_mid"] = bb_mid
    df["bb_lower"] = bb_lower
    bb_width = (bb_upper - bb_lower) / bb_mid.replace(0, np.nan)
    # Normalize BB position: 0 = at lower band, 1 = at upper band
    df["bb_pct"] = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
    df["bb_width"] = bb_width
    # Score: consolidating (narrow band) and price above midline
    df["bb_score"] = (
        (df["bb_pct"] > 0.5).astype(float)
        * (bb_width < bb_width.rolling(52).median()).astype(float)
    )

    # ATR for stop calculation
    df["atr14"] = _atr(df, 14)

    # Fibonacci proximity score
    df["fib_score"] = _fibonacci_score(df, 26)

    # Volume surge score
    vol_avg = volume.rolling(20).mean()
    df["vol_ratio"] = volume / vol_avg.replace(0, np.nan)
    df["vol_score"] = (df["vol_ratio"] > 1.2).astype(float)

    # OBV
    obv = (
        (close.diff() > 0).astype(float) * volume
        - (close.diff() < 0).astype(float) * volume
    ).cumsum()
    df["obv"] = obv
    df["obv_score"] = (obv.diff(4) > 0).astype(float)  # OBV rising over 4 weeks

    # Relative strength vs SPY
    if spy is not None and not spy.empty:
        spy_ret = spy["close"].pct_change(13)
        stock_ret = close.pct_change(13)
        # Align index
        spy_ret = spy_ret.reindex(df.index, method="ffill")
        df["rs_score"] = (stock_ret > spy_ret).astype(float)
    else:
        df["rs_score"] = 0.5

    return df
