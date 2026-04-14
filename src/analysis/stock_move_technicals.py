"""
Event-driven stock move technical analysis.

Reads user-supplied move windows, computes a broad technical snapshot for each
window, and returns both event-level summaries and daily technical detail.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import numpy as np
import pandas as pd

from src.data.market import download_historical, get_historical_data
from src.patterns.features.builder import build_features
from src.ta.indicators.gaps import gap_pct
from src.ta.indicators.momentum import rsi, smoothed_rsi
from src.ta.indicators.moving_averages import ema, sma
from src.ta.indicators.trend import adx
from src.ta.indicators.volatility import atr, bollinger_bands, percent_b


EVENT_COLUMN_ALIASES = {
    "ticker": ("ticker", "symbol", "stock", "stock_name", "name"),
    "start_date": ("start_date", "start", "from", "window_start", "date_start"),
    "end_date": ("end_date", "end", "to", "window_end", "date_end"),
    "time_range": ("time_range", "date_range", "range", "window", "period"),
    "move_type": ("move_type", "move", "direction", "label", "rally_or_down"),
    "event_id": ("event_id", "id", "event", "event_name"),
}

MOVE_TYPE_MAP = {
    "rally": "rally",
    "run": "rally",
    "run_up": "rally",
    "runup": "rally",
    "up": "rally",
    "bullish": "rally",
    "uptrend": "rally",
    "rise": "rally",
    "down": "down",
    "downfall": "down",
    "drop": "down",
    "selloff": "down",
    "decline": "down",
    "bearish": "down",
    "downtrend": "down",
}

SMA_PERIODS = (10, 20, 50, 100, 200)
EMA_PERIODS = (10, 20, 50, 100, 200)
BENCHMARKS = ("SPY", "QQQ")


def load_event_file(path: str | Path) -> pd.DataFrame:
    """Load an event file in CSV, JSON, or Excel format."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(file_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_path)

    raise ValueError(
        f"Unsupported event file format: {file_path.suffix}. "
        "Use CSV, JSON, or Excel."
    )


def normalize_event_file(events_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize user event input into the canonical event schema."""
    if events_df.empty:
        raise ValueError("Event file is empty.")

    df = events_df.copy()
    df.columns = [_normalize_column_name(col) for col in df.columns]

    ticker_col = _find_first_column(df.columns, EVENT_COLUMN_ALIASES["ticker"])
    move_col = _find_first_column(df.columns, EVENT_COLUMN_ALIASES["move_type"])
    event_id_col = _find_first_column(df.columns, EVENT_COLUMN_ALIASES["event_id"])
    start_col = _find_first_column(df.columns, EVENT_COLUMN_ALIASES["start_date"])
    end_col = _find_first_column(df.columns, EVENT_COLUMN_ALIASES["end_date"])
    range_col = _find_first_column(df.columns, EVENT_COLUMN_ALIASES["time_range"])

    if not ticker_col:
        raise ValueError("Missing ticker column. Expected ticker, symbol, or stock_name.")
    if not move_col:
        raise ValueError(
            "Missing move type column. Expected move_type, direction, or rally_or_down."
        )

    normalized_rows: list[dict[str, object]] = []
    for source_row, row in df.iterrows():
        start_date, end_date = _resolve_event_dates(row, start_col, end_col, range_col)
        ticker = str(row[ticker_col]).strip().upper()
        move_type = _normalize_move_type(row[move_col])

        if not ticker:
            raise ValueError(f"Row {source_row + 1}: ticker is blank.")
        if pd.isna(start_date) or pd.isna(end_date):
            raise ValueError(
                f"Row {source_row + 1}: missing start/end date or parseable time range."
            )
        if start_date > end_date:
            raise ValueError(
                f"Row {source_row + 1}: start_date {start_date.date()} is after "
                f"end_date {end_date.date()}."
            )

        event_id = (
            str(row[event_id_col]).strip()
            if event_id_col and pd.notna(row[event_id_col]) and str(row[event_id_col]).strip()
            else _default_event_id(ticker, start_date, end_date, move_type, source_row)
        )
        normalized_rows.append(
            {
                "event_id": event_id,
                "ticker": ticker,
                "start_date": start_date.normalize(),
                "end_date": end_date.normalize(),
                "move_type": move_type,
                "source_row": source_row + 1,
            }
        )

    normalized = pd.DataFrame(normalized_rows)
    return normalized.sort_values(["ticker", "start_date", "end_date"]).reset_index(drop=True)


def analyze_event_file(path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load, normalize, and analyze an event file."""
    events = normalize_event_file(load_event_file(path))
    return analyze_events(events)


def analyze_events(events_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Analyze each event and return (summary_df, daily_df)."""
    if events_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    benchmark_cache = _load_benchmark_cache()
    technical_cache: dict[str, pd.DataFrame] = {}
    summary_rows: list[dict[str, object]] = []
    daily_frames: list[pd.DataFrame] = []

    for event in events_df.itertuples(index=False):
        event_dict = event._asdict()
        ticker = str(event_dict["ticker"]).upper()

        try:
            if ticker not in technical_cache:
                history = _load_price_history(ticker, event_dict["start_date"])
                technical_cache[ticker] = build_technical_frame(history, benchmark_cache)

            summary_row, daily_frame = analyze_single_event(
                technical_cache[ticker],
                event_dict,
            )
            summary_rows.append(summary_row)
            daily_frames.append(daily_frame)
        except Exception as exc:
            summary_rows.append(
                {
                    "event_id": event_dict["event_id"],
                    "ticker": ticker,
                    "move_type": event_dict["move_type"],
                    "requested_start_date": event_dict["start_date"],
                    "requested_end_date": event_dict["end_date"],
                    "status": "error",
                    "error": str(exc),
                    "source_row": event_dict.get("source_row"),
                }
            )

    summary_df = pd.DataFrame(summary_rows)
    daily_df = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    return summary_df, daily_df


def analyze_single_event(
    technical_df: pd.DataFrame,
    event: dict[str, object],
) -> tuple[dict[str, object], pd.DataFrame]:
    """Analyze a single event window against an already enriched technical frame."""
    start_date = pd.Timestamp(event["start_date"])
    end_date = pd.Timestamp(event["end_date"])

    window = technical_df.loc[
        (technical_df.index >= start_date) & (technical_df.index <= end_date)
    ].copy()
    if window.empty:
        raise ValueError("No trading data found inside the requested date range.")

    actual_start = window.index[0]
    actual_end = window.index[-1]
    start_close = float(window["close"].iloc[0])
    end_close = float(window["close"].iloc[-1])

    window["event_day"] = np.arange(1, len(window) + 1)
    window["event_return_pct"] = window["close"] / start_close - 1.0
    window["event_id"] = event["event_id"]
    window["ticker"] = event["ticker"]
    window["move_type"] = event["move_type"]
    window["requested_start_date"] = start_date
    window["requested_end_date"] = end_date

    summary = {
        "event_id": event["event_id"],
        "ticker": event["ticker"],
        "move_type": event["move_type"],
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "actual_start_date": actual_start,
        "actual_end_date": actual_end,
        "source_row": event.get("source_row"),
        "status": "ok",
        "trading_days": len(window),
        "start_close": start_close,
        "end_close": end_close,
        "event_return_pct": end_close / start_close - 1.0,
        "window_high_pct": float(window["high"].max() / start_close - 1.0),
        "window_low_pct": float(window["low"].min() / start_close - 1.0),
        "max_drawdown_pct": float((window["close"] / window["close"].cummax() - 1.0).min()),
        "avg_daily_return_pct": float(window["pct_chg"].mean()),
        "realized_vol_window": float(window["pct_chg"].std(ddof=0) * np.sqrt(252)),
        "avg_volume_window": float(window["volume"].mean()),
        "volume_ratio_end_vs_start": _safe_ratio(
            window["volume"].iloc[-1],
            window["volume"].iloc[0],
        ),
        "up_day_ratio": float((window["pct_chg"] > 0).mean()),
        "gap_up_days": int((window["gap_pct"] > 0.01).sum()),
        "gap_down_days": int((window["gap_pct"] < -0.01).sum()),
    }

    numeric_columns = [
        column
        for column in window.columns
        if pd.api.types.is_numeric_dtype(window[column])
        and column not in {"event_day", "event_return_pct"}
    ]
    start_row = window.iloc[0]
    end_row = window.iloc[-1]
    for column in numeric_columns:
        start_value = _to_float_or_none(start_row[column])
        end_value = _to_float_or_none(end_row[column])
        summary[f"start_{column}"] = start_value
        summary[f"end_{column}"] = end_value
        summary[f"delta_{column}"] = (
            end_value - start_value
            if start_value is not None and end_value is not None
            else None
        )

    daily_df = window.reset_index().rename(columns={"index": "date"})
    return summary, daily_df


def save_analysis_results(
    summary_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    output_dir: str | Path,
    base_name: str = "stock_move_technicals",
) -> tuple[Path, Path]:
    """Save summary and daily analysis outputs to CSV."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    summary_path = directory / f"{base_name}_summary.csv"
    daily_path = directory / f"{base_name}_daily.csv"

    summary_df.to_csv(summary_path, index=False)
    daily_df.to_csv(daily_path, index=False)
    return summary_path, daily_path


def build_technical_frame(
    history_df: pd.DataFrame,
    benchmark_cache: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Compute a broad technical indicator set for a single ticker history."""
    df = _prepare_price_history(history_df)
    features = build_features(df[["Open", "High", "Low", "Close", "Volume"]])

    close = features["close"]
    high = features["high"]
    low = features["low"]
    volume = features["volume"]
    typical_price = (high + low + close) / 3.0
    volume_float = volume.astype(float)

    for period in SMA_PERIODS:
        features[f"sma_{period}"] = sma(close, period)
        features[f"close_vs_sma_{period}"] = close / features[f"sma_{period}"] - 1.0

    for period in EMA_PERIODS:
        features[f"ema_{period}"] = ema(close, period)
        features[f"close_vs_ema_{period}"] = close / features[f"ema_{period}"] - 1.0

    features["rsi_14"] = rsi(close, 14)
    features["rsi_21"] = rsi(close, 21)
    features["smoothed_rsi_ema21_rsi10"] = smoothed_rsi(close, ema_period=21, rsi_period=10)

    macd_fast = ema(close, 12)
    macd_slow = ema(close, 26)
    features["macd_line"] = macd_fast - macd_slow
    features["macd_signal"] = ema(features["macd_line"], 9)
    features["macd_hist"] = features["macd_line"] - features["macd_signal"]

    rolling_low_14 = low.rolling(14).min()
    rolling_high_14 = high.rolling(14).max()
    stochastic_range = rolling_high_14 - rolling_low_14
    features["stoch_k_14"] = 100.0 * (close - rolling_low_14) / stochastic_range.replace(0, np.nan)
    features["stoch_d_3"] = features["stoch_k_14"].rolling(3).mean()
    features["williams_r_14"] = (
        -100.0 * (rolling_high_14 - close) / stochastic_range.replace(0, np.nan)
    )

    mean_deviation = typical_price.rolling(20).apply(
        lambda values: np.mean(np.abs(values - values.mean())),
        raw=True,
    )
    typical_sma_20 = typical_price.rolling(20).mean()
    features["cci_20"] = (typical_price - typical_sma_20) / (0.015 * mean_deviation)

    features["adx_14"] = adx(df, 14)
    plus_di, minus_di = _directional_indicators(df, 14)
    features["plus_di_14"] = plus_di
    features["minus_di_14"] = minus_di

    features["atr_14"] = atr(df, 14)
    features["atr_pct_14"] = features["atr_14"] / close
    bb_mid, bb_upper, bb_lower, bb_bandwidth = bollinger_bands(close, 20, 2.0)
    features["bb_mid_20"] = bb_mid
    features["bb_upper_20"] = bb_upper
    features["bb_lower_20"] = bb_lower
    features["bb_bandwidth_20"] = bb_bandwidth
    features["bb_pct_b_20"] = percent_b(close, bb_upper, bb_lower)

    features["roc_5"] = close.pct_change(5)
    features["roc_10"] = close.pct_change(10)
    features["roc_20"] = close.pct_change(20)
    features["realized_vol_20"] = close.pct_change().rolling(20).std() * np.sqrt(252)
    features["volume_ratio_20"] = volume_float / volume_float.rolling(20).mean()
    features["volume_ratio_50"] = volume_float / volume_float.rolling(50).mean()
    features["volume_zscore_20"] = (
        (volume_float - volume_float.rolling(20).mean()) / volume_float.rolling(20).std()
    )
    features["vwap_20"] = (
        (typical_price * volume_float).rolling(20).sum() / volume_float.rolling(20).sum()
    )

    price_delta = close.diff().fillna(0.0)
    features["obv"] = (np.sign(price_delta) * volume_float).cumsum()
    money_flow_multiplier = (
        ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    )
    money_flow_volume = money_flow_multiplier * volume_float
    features["cmf_20"] = money_flow_volume.rolling(20).sum() / volume_float.rolling(20).sum()

    raw_money_flow = typical_price * volume_float
    positive_flow = raw_money_flow.where(typical_price > typical_price.shift(1), 0.0)
    negative_flow = raw_money_flow.where(typical_price < typical_price.shift(1), 0.0)
    money_ratio = positive_flow.rolling(14).sum() / negative_flow.rolling(14).sum()
    features["mfi_14"] = 100.0 - (100.0 / (1.0 + money_ratio))

    features["donchian_high_20"] = high.rolling(20).max()
    features["donchian_low_20"] = low.rolling(20).min()
    features["donchian_pos_20"] = (
        (close - features["donchian_low_20"])
        / (features["donchian_high_20"] - features["donchian_low_20"]).replace(0, np.nan)
    )

    features["gap_pct"] = gap_pct(df)
    features["trend_stack_bullish"] = (
        (close > features["ema_20"])
        & (features["ema_20"] > features["ema_50"])
        & (features["ema_50"] > features["ema_200"])
    ).astype(int)
    features["trend_stack_bearish"] = (
        (close < features["ema_20"])
        & (features["ema_20"] < features["ema_50"])
        & (features["ema_50"] < features["ema_200"])
    ).astype(int)

    if benchmark_cache:
        for symbol, benchmark_close in benchmark_cache.items():
            aligned = benchmark_close.reindex(features.index).ffill()
            features[f"price_to_{symbol.lower()}"] = close / aligned
            features[f"rs_{symbol.lower()}_20"] = close.pct_change(20) - aligned.pct_change(20)
            features[f"rs_{symbol.lower()}_50"] = close.pct_change(50) - aligned.pct_change(50)

    return features


def _load_price_history(ticker: str, start_date: pd.Timestamp) -> pd.DataFrame:
    """Load ticker history, downloading a broader window when local cache is insufficient."""
    history = _prepare_price_history(get_historical_data(ticker))
    lookback_floor = start_date - pd.Timedelta(days=370)

    if history.empty or history.index.min() > lookback_floor or history.index.max() < start_date:
        downloaded = download_historical(ticker, period="10y")
        prepared = _prepare_price_history(downloaded)
        if not prepared.empty:
            history = prepared

    if history.empty:
        raise ValueError(f"No historical data available for {ticker}.")
    return history


def _load_benchmark_cache() -> dict[str, pd.Series]:
    """Load benchmark close series when available."""
    cache: dict[str, pd.Series] = {}
    for symbol in BENCHMARKS:
        benchmark = _prepare_price_history(get_historical_data(symbol))
        if benchmark.empty:
            continue
        cache[symbol] = benchmark["Close"].rename(symbol)
    return cache


def _prepare_price_history(history_df: pd.DataFrame) -> pd.DataFrame:
    """Standardize OHLCV history into a clean, datetime-indexed frame."""
    if history_df is None or history_df.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    df = history_df.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.set_index("Date")

    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[df.index.notna()].sort_index()
    df = df[~df.index.duplicated(keep="last")]

    rename_map = {}
    for column in df.columns:
        normalized = _normalize_column_name(column)
        if normalized == "adj_close":
            rename_map[column] = "Adj Close"
        else:
            rename_map[column] = normalized.title()
    df = df.rename(columns=rename_map)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Price history missing required columns: {missing}")

    df = df[required + [column for column in df.columns if column not in required]]
    for column in required:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    return df


def _directional_indicators(
    df: pd.DataFrame,
    period: int,
) -> tuple[pd.Series, pd.Series]:
    """Return (+DI, -DI) using the same simple smoothing style as the local ADX helper."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
    )
    true_range = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    smoothed_tr = true_range.rolling(period).mean()
    plus_di = 100.0 * plus_dm.rolling(period).mean() / smoothed_tr
    minus_di = 100.0 * minus_dm.rolling(period).mean() / smoothed_tr
    return plus_di, minus_di


def _resolve_event_dates(
    row: pd.Series,
    start_col: str | None,
    end_col: str | None,
    range_col: str | None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Resolve event dates from separate columns or a combined time range."""
    start_date = pd.NaT
    end_date = pd.NaT

    if start_col and end_col:
        start_date = pd.to_datetime(row[start_col], errors="coerce")
        end_date = pd.to_datetime(row[end_col], errors="coerce")

    if range_col and (pd.isna(start_date) or pd.isna(end_date)):
        start_date, end_date = _parse_time_range(row[range_col])

    return start_date, end_date


def _parse_time_range(value: object) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Parse common time range strings like '2024-01-01 to 2024-01-15'."""
    if pd.isna(value):
        return pd.NaT, pd.NaT

    text = str(value).strip()
    matches = re.findall(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text)
    if len(matches) >= 2:
        return (
            pd.to_datetime(matches[0], errors="coerce"),
            pd.to_datetime(matches[1], errors="coerce"),
        )

    parts = re.split(r"\s+to\s+|:", text, maxsplit=1)
    if len(parts) == 2:
        return (
            pd.to_datetime(parts[0].strip(), errors="coerce"),
            pd.to_datetime(parts[1].strip(), errors="coerce"),
        )

    return pd.NaT, pd.NaT


def _normalize_move_type(value: object) -> str:
    """Normalize user move labels into 'rally' or 'down'."""
    if pd.isna(value):
        raise ValueError("move_type is missing.")

    key = _normalize_column_name(value)
    if key in MOVE_TYPE_MAP:
        return MOVE_TYPE_MAP[key]
    raise ValueError(f"Unsupported move_type '{value}'. Use rally/up or down/downfall.")


def _find_first_column(columns: Iterable[str], aliases: Iterable[str]) -> str | None:
    """Find the first matching column alias."""
    column_set = set(columns)
    for alias in aliases:
        if alias in column_set:
            return alias
    return None


def _normalize_column_name(value: object) -> str:
    """Convert a column name or label into lower snake case."""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _default_event_id(
    ticker: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    move_type: str,
    source_row: int,
) -> str:
    """Generate a deterministic event id when the file does not provide one."""
    return (
        f"{ticker}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_"
        f"{move_type}_{source_row + 1}"
    )


def _to_float_or_none(value: object) -> float | None:
    """Convert numeric-like values to float, preserving missing values as None."""
    if pd.isna(value):
        return None
    return float(value)


def _safe_ratio(numerator: object, denominator: object) -> float | None:
    """Safely compute numerator / denominator - 1 for scalar values."""
    if pd.isna(numerator) or pd.isna(denominator) or float(denominator) == 0.0:
        return None
    return float(numerator) / float(denominator) - 1.0
