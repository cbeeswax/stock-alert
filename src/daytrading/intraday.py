from __future__ import annotations

from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

MARKET_TZ = ZoneInfo("America/New_York")
INTRADAY_DATA_DIR = Path("data") / "intraday"
INTRADAY_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_intraday_df(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(data, pd.Series):
        data = data.to_frame().T

    if isinstance(data.columns, pd.MultiIndex):
        flattened = []
        ticker_upper = ticker.replace(".", "-").upper()
        for left, right in data.columns.to_list():
            if left == ticker_upper:
                flattened.append(right)
            elif right == ticker_upper:
                flattened.append(left)
            else:
                flattened.append(left or right)
        data.columns = flattened

    rename_map = {}
    for column in list(data.columns):
        normalized = str(column)
        if normalized.endswith(f"_{ticker}") or normalized.endswith(f"_{ticker.replace('.', '-')}"):
            rename_map[column] = normalized.split("_")[0]
        elif normalized.startswith(f"{ticker}_") or normalized.startswith(f"{ticker.replace('.', '-')}_"):
            rename_map[column] = normalized.split("_", 1)[1]
    if rename_map:
        data = data.rename(columns=rename_map)

    keep_columns = [column for column in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if column in data.columns]
    if not keep_columns:
        raise ValueError(f"Intraday data for {ticker} is missing OHLCV columns: {list(data.columns)}")

    normalized_df = data[keep_columns].copy()
    normalized_df.index = pd.to_datetime(normalized_df.index, errors="coerce", utc=True)
    normalized_df = normalized_df[normalized_df.index.notna()].sort_index()
    normalized_df = normalized_df.apply(pd.to_numeric, errors="coerce")
    normalized_df = normalized_df.dropna(subset=["Close"])
    if normalized_df.index.tz is None:
        normalized_df.index = normalized_df.index.tz_localize(MARKET_TZ)
    else:
        normalized_df.index = normalized_df.index.tz_convert(MARKET_TZ)
    return normalized_df


def get_latest_regular_session(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    local_df = df.copy().sort_index()
    if local_df.index.tz is None:
        local_df.index = local_df.index.tz_localize(MARKET_TZ)
    else:
        local_df.index = local_df.index.tz_convert(MARKET_TZ)

    regular = local_df.between_time("09:30", "16:00")
    if regular.empty:
        return regular

    latest_session_date = regular.index[-1].date()
    session_mask = regular.index.date == latest_session_date
    return regular.loc[session_mask].copy()


def add_session_vwap(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    result = df.copy().sort_index()
    typical_price = (result["High"] + result["Low"] + result["Close"]) / 3.0
    volume = result["Volume"].fillna(0)
    cumulative_volume = volume.cumsum()
    cumulative_turnover = (typical_price * volume).cumsum()
    result["VWAP"] = cumulative_turnover.div(cumulative_volume.where(cumulative_volume > 0))
    return result


def load_intraday_cache(ticker: str, interval: str = "5m") -> pd.DataFrame:
    cache_file = INTRADAY_DATA_DIR / f"{ticker}_{interval}.csv"
    if not cache_file.exists():
        return pd.DataFrame()

    cached = pd.read_csv(cache_file, index_col=0)
    return _normalize_intraday_df(cached, ticker)


def download_intraday_data(
    ticker: str,
    period: str = "5d",
    interval: str = "5m",
    include_prepost: bool = False,
) -> pd.DataFrame:
    data = yf.download(
        ticker.replace(".", "-"),
        period=period,
        interval=interval,
        prepost=include_prepost,
        progress=False,
        auto_adjust=False,
        group_by="ticker",
    )
    if data.empty:
        raise ValueError(f"No intraday data returned for {ticker}")

    normalized_df = _normalize_intraday_df(data, ticker)
    cache_file = INTRADAY_DATA_DIR / f"{ticker}_{interval}.csv"
    normalized_df.to_csv(cache_file)
    return normalized_df


def download_intraday_batch(
    tickers: Iterable[str],
    period: str = "5d",
    interval: str = "5m",
    include_prepost: bool = False,
) -> dict[str, pd.DataFrame]:
    return {
        ticker: download_intraday_data(
            ticker=ticker,
            period=period,
            interval=interval,
            include_prepost=include_prepost,
        )
        for ticker in tickers
    }
