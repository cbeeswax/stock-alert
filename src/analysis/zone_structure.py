from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ZoneSnapshot:
    close: float
    prior_short_high: float
    prior_short_low: float
    prior_long_high: float
    prior_long_low: float
    short_zone_width_pct: float
    long_zone_width_pct: float
    short_zone_position: float
    long_zone_position: float
    room_to_short_ceiling_pct: float
    room_to_long_ceiling_pct: float
    room_to_short_floor_pct: float
    room_to_long_floor_pct: float
    in_short_seller_zone: bool
    in_long_seller_zone: bool
    in_short_demand_zone: bool
    in_long_demand_zone: bool


def add_zone_columns(
    df: pd.DataFrame,
    *,
    high_col: str,
    low_col: str,
    close_col: str,
    group_col: str | None = None,
    windows: Iterable[int] = (20, 60),
    seller_zone_fraction: float = 0.2,
    demand_zone_fraction: float = 0.2,
) -> pd.DataFrame:
    working = df.copy()
    for window in windows:
        prior_high = _rolling_series(
            working,
            column=high_col,
            window=window,
            group_col=group_col,
            reducer="max",
        )
        prior_low = _rolling_series(
            working,
            column=low_col,
            window=window,
            group_col=group_col,
            reducer="min",
        )
        zone_width = _safe_divide(prior_high - prior_low, working[close_col].abs(), 0.0)
        zone_position = _safe_divide(working[close_col] - prior_low, (prior_high - prior_low).abs(), 0.0)
        room_to_high = _safe_divide(prior_high - working[close_col], working[close_col].abs(), 0.0)
        room_to_low = _safe_divide(working[close_col] - prior_low, working[close_col].abs(), 0.0)

        working[f"prior_{window}bar_high"] = prior_high
        working[f"prior_{window}bar_low"] = prior_low
        working[f"zone_width_{window}"] = zone_width
        working[f"zone_pos_{window}"] = zone_position
        working[f"room_to_{window}bar_high"] = room_to_high
        working[f"room_to_{window}bar_low"] = room_to_low
        working[f"in_{window}bar_seller_zone"] = zone_position >= (1.0 - seller_zone_fraction)
        working[f"in_{window}bar_demand_zone"] = zone_position <= demand_zone_fraction
    return working


def build_zone_snapshot(
    df: pd.DataFrame,
    *,
    close_col: str = "Close",
    high_col: str = "High",
    low_col: str = "Low",
    short_window: int = 20,
    long_window: int = 60,
    seller_zone_fraction: float = 0.2,
    demand_zone_fraction: float = 0.2,
) -> ZoneSnapshot | None:
    if df is None or df.empty or close_col not in df.columns or high_col not in df.columns or low_col not in df.columns:
        return None

    working = add_zone_columns(
        df.copy(),
        high_col=high_col,
        low_col=low_col,
        close_col=close_col,
        group_col=None,
        windows=(short_window, long_window),
        seller_zone_fraction=seller_zone_fraction,
        demand_zone_fraction=demand_zone_fraction,
    )
    row = working.iloc[-1]
    return ZoneSnapshot(
        close=float(row[close_col]),
        prior_short_high=float(row[f"prior_{short_window}bar_high"]),
        prior_short_low=float(row[f"prior_{short_window}bar_low"]),
        prior_long_high=float(row[f"prior_{long_window}bar_high"]),
        prior_long_low=float(row[f"prior_{long_window}bar_low"]),
        short_zone_width_pct=float(row[f"zone_width_{short_window}"]),
        long_zone_width_pct=float(row[f"zone_width_{long_window}"]),
        short_zone_position=float(row[f"zone_pos_{short_window}"]),
        long_zone_position=float(row[f"zone_pos_{long_window}"]),
        room_to_short_ceiling_pct=float(row[f"room_to_{short_window}bar_high"]),
        room_to_long_ceiling_pct=float(row[f"room_to_{long_window}bar_high"]),
        room_to_short_floor_pct=float(row[f"room_to_{short_window}bar_low"]),
        room_to_long_floor_pct=float(row[f"room_to_{long_window}bar_low"]),
        in_short_seller_zone=bool(row[f"in_{short_window}bar_seller_zone"]),
        in_long_seller_zone=bool(row[f"in_{long_window}bar_seller_zone"]),
        in_short_demand_zone=bool(row[f"in_{short_window}bar_demand_zone"]),
        in_long_demand_zone=bool(row[f"in_{long_window}bar_demand_zone"]),
    )


def long_zone_broken(close: float, zone_low: float, tolerance_pct: float = 0.0) -> bool:
    if zone_low <= 0:
        return False
    return close < (zone_low * (1.0 - tolerance_pct))


def short_zone_broken(close: float, zone_high: float, tolerance_pct: float = 0.0) -> bool:
    if zone_high <= 0:
        return False
    return close > (zone_high * (1.0 + tolerance_pct))


def _rolling_series(
    df: pd.DataFrame,
    *,
    column: str,
    window: int,
    group_col: str | None,
    reducer: str,
) -> pd.Series:
    if group_col and group_col in df.columns:
        grouped = df.groupby(group_col, sort=False)[column]
        transform = lambda series: series.shift(1).rolling(window, min_periods=1)
        if reducer == "max":
            return grouped.transform(lambda series: transform(series).max()).fillna(0.0)
        return grouped.transform(lambda series: transform(series).min()).fillna(0.0)

    series = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    rolled = series.shift(1).rolling(window, min_periods=1)
    if reducer == "max":
        return rolled.max().fillna(0.0)
    return rolled.min().fillna(0.0)


def _safe_divide(numerator: pd.Series | np.ndarray, denominator: pd.Series | np.ndarray, default: float) -> pd.Series:
    numerator_arr = np.asarray(numerator, dtype=float)
    denominator_arr = np.asarray(denominator, dtype=float)
    result = np.full_like(numerator_arr, default, dtype=float)
    valid = np.abs(denominator_arr) > 1e-12
    result[valid] = numerator_arr[valid] / denominator_arr[valid]
    return pd.Series(result, index=getattr(numerator, "index", None))
