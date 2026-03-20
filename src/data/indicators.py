"""
src/data/indicators.py
======================
Data-layer indicator functions (with I/O / caching).
Pure math is delegated to src/ta/indicators/ — this module
adds the data-loading and caching layer on top.

Backward-compatible: all existing callers continue to work unchanged.
"""
import pandas as pd
from pathlib import Path
from src.data.market import get_historical_data

# Re-export pure indicator functions so callers can import from here
from src.ta.indicators.momentum import rsi as _rsi_pure, smoothed_rsi
from src.ta.indicators.volatility import bollinger_bands as _bb_pure, percent_b as _pct_b_pure
from src.ta.indicators.trend import adx, adx_latest
from src.ta.indicators.gaps import gap_pct, is_gap_up, is_gap_down, gap_fill_level


EMA_FOLDER = Path("ema_data")
EMA_FOLDER.mkdir(exist_ok=True)

EMA_PERIODS = [20, 50, 200]


def compute_ema_incremental(ticker):
    """
    Loads cached EMA data (if any), updates with new price data, and saves.
    Returns a DataFrame with Close + EMA20, EMA50, EMA200.
    """
    hist_df = get_historical_data(ticker)
    if hist_df.empty or 'Close' not in hist_df.columns:
        return pd.DataFrame()

    ema_file = EMA_FOLDER / f"{ticker}_ema.csv"

    if ema_file.exists():
        ema_df = pd.read_csv(ema_file, index_col=0, parse_dates=True)
        last_cached_date = ema_df.index[-1]
        new_data = hist_df[hist_df.index > last_cached_date]
        if new_data.empty:
            return ema_df
        df = pd.concat([ema_df, new_data])
    else:
        df = hist_df.copy()

    for period in EMA_PERIODS:
        col = f"EMA{period}"
        alpha = 2 / (period + 1)
        if col in df.columns and ema_file.exists():
            last_ema = df[col].iloc[-len(new_data) - 1] if len(new_data) > 0 else df[col].iloc[-1]
            for date, row in new_data.iterrows():
                last_ema = (row["Close"] * alpha) + (last_ema * (1 - alpha))
                df.loc[date, col] = last_ema
        else:
            df[col] = df["Close"].ewm(span=period, adjust=False).mean()

    df.to_csv(ema_file)
    return df


def compute_rsi(series, period=14):
    """RSI — delegates to src/ta/indicators/momentum.py."""
    return _rsi_pure(series, period)


def compute_bollinger_bands(series, period=20, std_dev=2):
    """
    Bollinger Bands — delegates to src/ta/indicators/volatility.py.

    Returns:
        tuple: (middle_band, upper_band, lower_band, bandwidth)
    """
    return _bb_pure(series, period, std_dev)


def compute_percent_b(price, upper_band, lower_band):
    """
    %B (Percent B) — delegates to src/ta/indicators/volatility.py.

    %B = 0: lower band, 0.5: middle, 1: upper band.
    """
    return _pct_b_pure(price, upper_band, lower_band)
