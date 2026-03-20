"""
src/ta/timeframes.py
=====================
Multi-timeframe data utilities.
Fetches and caches weekly (and monthly) OHLCV data for higher-timeframe
trend confirmation in strategies like the Breakaway Gap Reversal.

Migrated and enhanced from utils/weekly_data_utils.py.
"""
import pandas as pd
import yfinance as yf
from pathlib import Path
from src.ta.indicators.moving_averages import ema

WEEKLY_DATA_DIR = Path("data") / "weekly"
WEEKLY_DATA_DIR.mkdir(parents=True, exist_ok=True)

MONTHLY_DATA_DIR = Path("data") / "monthly"
MONTHLY_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Weekly data
# ---------------------------------------------------------------------------

def get_weekly_data(ticker: str, as_of_date=None) -> pd.DataFrame:
    """
    Fetch and cache weekly OHLCV data for ticker.

    Args:
        ticker:      Stock symbol
        as_of_date:  If provided, returns only rows up to this date (backtest safe)

    Returns:
        DataFrame with columns Open, High, Low, Close, Volume; DatetimeIndex weekly
    """
    cache_file = WEEKLY_DATA_DIR / f"{ticker}_weekly.csv"

    df = pd.DataFrame()

    if cache_file.exists():
        try:
            cached = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            # Refresh if more than 5 days stale (relative to latest cached row)
            if not cached.empty and (pd.Timestamp.now() - cached.index[-1]).days < 8:
                df = cached
            else:
                df = _download_weekly(ticker)
                if not df.empty:
                    df.to_csv(cache_file)
        except Exception:
            df = _download_weekly(ticker)
            if not df.empty:
                df.to_csv(cache_file)
    else:
        df = _download_weekly(ticker)
        if not df.empty:
            df.to_csv(cache_file)

    if df.empty:
        return df

    if as_of_date is not None:
        df = df[df.index <= pd.Timestamp(as_of_date)]

    return df.sort_index()


def _download_weekly(ticker: str) -> pd.DataFrame:
    """Download 3 years of weekly data from yfinance."""
    try:
        data = yf.download(
            ticker, period="3y", interval="1wk",
            progress=False, auto_adjust=True,
        )
        if data.empty:
            return pd.DataFrame()

        # Flatten MultiIndex columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        if "Adj Close" in data.columns and "Close" not in data.columns:
            data = data.rename(columns={"Adj Close": "Close"})

        cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]
        return data[cols].dropna(subset=["Close"])
    except Exception as e:
        print(f"⚠️ [timeframes.py] Failed to download weekly data for {ticker}: {e}")
        return pd.DataFrame()


def get_weekly_trend(ticker: str, as_of_date=None, ema_period: int = 21) -> str:
    """
    Determine weekly trend direction using EMA of weekly closes.

    Used as the higher-timeframe filter in the Breakaway Gap Reversal strategy:
      - "UP":      weekly close > weekly EMA(ema_period)  → bias long
      - "DOWN":    weekly close < weekly EMA(ema_period)  → bias short
      - "NEUTRAL": insufficient data

    Args:
        ticker:      Stock symbol
        as_of_date:  Date to evaluate as of (backtest safe)
        ema_period:  EMA period on weekly closes (default 21 weeks)

    Returns:
        "UP", "DOWN", or "NEUTRAL"
    """
    df = get_weekly_data(ticker, as_of_date)

    if df.empty or len(df) < ema_period:
        return "NEUTRAL"

    weekly_ema = ema(df["Close"], ema_period)
    last_close = df["Close"].iloc[-1]
    last_ema = weekly_ema.iloc[-1]

    if last_close > last_ema:
        return "UP"
    elif last_close < last_ema:
        return "DOWN"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Weekly trend alignment (backward-compat helper matching old API)
# ---------------------------------------------------------------------------

def check_weekly_trend_alignment(ticker: str, as_of_date=None) -> bool:
    """
    Legacy compatibility shim — True if weekly trend is UP.
    Equivalent to old check_weekly_trend_alignment() in utils/weekly_data_utils.py
    but uses EMA21 (was EMA10).
    """
    return get_weekly_trend(ticker, as_of_date) == "UP"
