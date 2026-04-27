from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DivergenceSetup:
    direction: str
    first_pivot_idx: int
    second_pivot_idx: int
    trigger_level: float
    invalidation_level: float
    first_price: float
    second_price: float
    first_oscillator: float
    second_oscillator: float
    macd_bonus: float


def macd(
    series: pd.Series,
    *,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pd.DataFrame:
    close = pd.to_numeric(series, errors="coerce")
    ema_fast = close.ewm(span=fast_period, adjust=False).mean()
    ema_slow = close.ewm(span=slow_period, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=signal_period, adjust=False).mean()
    return pd.DataFrame(
        {
            "macd_line": macd_line,
            "macd_signal": macd_signal,
            "macd_hist": macd_line - macd_signal,
        },
        index=series.index,
    )


def find_pivot_lows(series: pd.Series, *, left_bars: int = 3, right_bars: int = 3) -> list[int]:
    return _find_pivots(series, left_bars=left_bars, right_bars=right_bars, kind="low")


def find_pivot_highs(series: pd.Series, *, left_bars: int = 3, right_bars: int = 3) -> list[int]:
    return _find_pivots(series, left_bars=left_bars, right_bars=right_bars, kind="high")


def find_bullish_divergence_setup(
    df: pd.DataFrame,
    oscillator: pd.Series,
    *,
    macd_frame: pd.DataFrame | None = None,
    price_low_col: str = "Low",
    price_high_col: str = "High",
    left_bars: int = 3,
    right_bars: int = 3,
    min_separation_bars: int = 5,
    max_pivot_lookback: int = 60,
) -> DivergenceSetup | None:
    return _find_divergence_setup(
        df,
        oscillator,
        macd_frame=macd_frame,
        direction="LONG",
        price_low_col=price_low_col,
        price_high_col=price_high_col,
        left_bars=left_bars,
        right_bars=right_bars,
        min_separation_bars=min_separation_bars,
        max_pivot_lookback=max_pivot_lookback,
    )


def find_bearish_divergence_setup(
    df: pd.DataFrame,
    oscillator: pd.Series,
    *,
    macd_frame: pd.DataFrame | None = None,
    price_low_col: str = "Low",
    price_high_col: str = "High",
    left_bars: int = 3,
    right_bars: int = 3,
    min_separation_bars: int = 5,
    max_pivot_lookback: int = 60,
) -> DivergenceSetup | None:
    return _find_divergence_setup(
        df,
        oscillator,
        macd_frame=macd_frame,
        direction="SHORT",
        price_low_col=price_low_col,
        price_high_col=price_high_col,
        left_bars=left_bars,
        right_bars=right_bars,
        min_separation_bars=min_separation_bars,
        max_pivot_lookback=max_pivot_lookback,
    )


def macd_confirmation_bonus(
    macd_frame: pd.DataFrame | None,
    *,
    first_idx: int,
    second_idx: int,
    direction: str,
) -> float:
    if macd_frame is None or macd_frame.empty:
        return 0.0

    try:
        hist_1 = float(macd_frame["macd_hist"].iloc[first_idx])
        hist_2 = float(macd_frame["macd_hist"].iloc[second_idx])
        hist_now = float(macd_frame["macd_hist"].iloc[-1])
        line_2 = float(macd_frame["macd_line"].iloc[second_idx])
        signal_2 = float(macd_frame["macd_signal"].iloc[second_idx])
        line_now = float(macd_frame["macd_line"].iloc[-1])
        signal_now = float(macd_frame["macd_signal"].iloc[-1])
    except (KeyError, IndexError, TypeError, ValueError):
        return 0.0

    values = (hist_1, hist_2, hist_now, line_2, signal_2, line_now, signal_now)
    if any(pd.isna(value) for value in values):
        return 0.0

    bonus = 0.0
    if direction == "LONG":
        if hist_2 > hist_1:
            bonus += 6.0
        if line_2 > signal_2:
            bonus += 4.0
        if hist_now > hist_2:
            bonus += 6.0
        if line_now > signal_now:
            bonus += 4.0
    else:
        if hist_2 < hist_1:
            bonus += 6.0
        if line_2 < signal_2:
            bonus += 4.0
        if hist_now < hist_2:
            bonus += 6.0
        if line_now < signal_now:
            bonus += 4.0

    return min(20.0, bonus)


def _find_divergence_setup(
    df: pd.DataFrame,
    oscillator: pd.Series,
    *,
    macd_frame: pd.DataFrame | None,
    direction: str,
    price_low_col: str,
    price_high_col: str,
    left_bars: int,
    right_bars: int,
    min_separation_bars: int,
    max_pivot_lookback: int,
) -> DivergenceSetup | None:
    if df is None or df.empty or len(df) < (left_bars + right_bars + min_separation_bars + 2):
        return None
    if price_low_col not in df.columns or price_high_col not in df.columns:
        return None

    oscillator_series = pd.to_numeric(oscillator, errors="coerce")
    price_lows = pd.to_numeric(df[price_low_col], errors="coerce")
    price_highs = pd.to_numeric(df[price_high_col], errors="coerce")
    current_idx = len(df) - 1
    cutoff_idx = max(0, current_idx - max_pivot_lookback)

    if direction == "LONG":
        pivot_indexes = [idx for idx in find_pivot_lows(price_lows, left_bars=left_bars, right_bars=right_bars) if idx >= cutoff_idx]
    else:
        pivot_indexes = [idx for idx in find_pivot_highs(price_highs, left_bars=left_bars, right_bars=right_bars) if idx >= cutoff_idx]

    if len(pivot_indexes) < 2:
        return None

    for second_idx in reversed(pivot_indexes[1:]):
        if second_idx >= current_idx:
            continue

        matching_first = [idx for idx in pivot_indexes if idx <= (second_idx - min_separation_bars)]
        for first_idx in reversed(matching_first):
            first_osc = float(oscillator_series.iloc[first_idx])
            second_osc = float(oscillator_series.iloc[second_idx])
            if pd.isna(first_osc) or pd.isna(second_osc):
                continue

            if direction == "LONG":
                first_price = float(price_lows.iloc[first_idx])
                second_price = float(price_lows.iloc[second_idx])
                if second_price >= first_price or second_osc <= first_osc:
                    continue
                trigger_slice = price_highs.iloc[second_idx:current_idx]
                invalidation_slice = price_lows.iloc[second_idx:current_idx]
            else:
                first_price = float(price_highs.iloc[first_idx])
                second_price = float(price_highs.iloc[second_idx])
                if second_price <= first_price or second_osc >= first_osc:
                    continue
                trigger_slice = price_lows.iloc[second_idx:current_idx]
                invalidation_slice = price_highs.iloc[second_idx:current_idx]

            if trigger_slice.empty or invalidation_slice.empty:
                continue

            bonus = macd_confirmation_bonus(
                macd_frame,
                first_idx=first_idx,
                second_idx=second_idx,
                direction=direction,
            )
            return DivergenceSetup(
                direction=direction,
                first_pivot_idx=first_idx,
                second_pivot_idx=second_idx,
                trigger_level=float(trigger_slice.max()) if direction == "LONG" else float(trigger_slice.min()),
                invalidation_level=float(invalidation_slice.min()) if direction == "LONG" else float(invalidation_slice.max()),
                first_price=first_price,
                second_price=second_price,
                first_oscillator=first_osc,
                second_oscillator=second_osc,
                macd_bonus=bonus,
            )

    return None


def _find_pivots(series: pd.Series, *, left_bars: int, right_bars: int, kind: str) -> list[int]:
    values = pd.to_numeric(series, errors="coerce")
    if len(values) < (left_bars + right_bars + 1):
        return []

    pivots: list[int] = []
    for idx in range(left_bars, len(values) - right_bars):
        center = values.iloc[idx]
        if pd.isna(center):
            continue

        left_slice = values.iloc[idx - left_bars:idx]
        right_slice = values.iloc[idx + 1: idx + right_bars + 1]
        window = values.iloc[idx - left_bars: idx + right_bars + 1]
        if left_slice.isna().any() or right_slice.isna().any() or window.isna().any():
            continue

        if kind == "low":
            is_pivot = (
                center == float(window.min())
                and center < float(left_slice.min())
                and center <= float(right_slice.min())
            )
        else:
            is_pivot = (
                center == float(window.max())
                and center > float(left_slice.max())
                and center >= float(right_slice.max())
            )

        if is_pivot:
            pivots.append(idx)

    return pivots
