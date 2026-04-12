"""
src/patterns/features/builder.py
==================================
Feature engine — adds all derived columns to a raw OHLCV DataFrame.

Call:
    df = build_features(df)

Input columns expected:  Open, High, Low, Close, Volume
All added columns are lowercase snake_case.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_EPS = 1e-9  # avoid divide-by-zero


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute and append all feature columns in-place (returns same df).

    Added columns
    -------------
    avg_vol_20, avg_vol_50
    tr, atr_14
    range_, body, close_pos
    pct_from_20d_high, pct_from_20d_low
    roll_high_20, roll_high_50, roll_high_130
    roll_low_20,  roll_low_50,  roll_low_130
    pct_chg
    """
    df = df.copy()

    # ── Normalise column names ────────────────────────────────────────────
    df.columns = [c.strip() for c in df.columns]
    col_map = {c: c.lower() for c in df.columns}
    df = df.rename(columns=col_map)

    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"build_features: missing columns {missing}")

    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]

    # ── Volume averages ───────────────────────────────────────────────────
    df["avg_vol_20"] = v.rolling(20, min_periods=1).mean()
    df["avg_vol_50"] = v.rolling(50, min_periods=1).mean()

    # ── True range / ATR-14 ───────────────────────────────────────────────
    prev_c = c.shift(1)
    df["tr"] = pd.concat(
        [h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1
    ).max(axis=1)
    df["atr_14"] = df["tr"].ewm(span=14, min_periods=1, adjust=False).mean()

    # ── Bar shape ─────────────────────────────────────────────────────────
    df["range_"] = h - l
    df["body"] = (c - o).abs()
    df["close_pos"] = (c - l) / (df["range_"] + _EPS)  # 0 = low, 1 = high

    # ── Rolling highs / lows ─────────────────────────────────────────────
    for n in (20, 50, 130):
        df[f"roll_high_{n}"] = h.rolling(n, min_periods=1).max()
        df[f"roll_low_{n}"]  = l.rolling(n, min_periods=1).min()

    # ── Distance from recent high / low ──────────────────────────────────
    df["pct_from_20d_high"] = (c - df["roll_high_20"]) / (df["roll_high_20"] + _EPS)
    df["pct_from_20d_low"]  = (c - df["roll_low_20"])  / (df["roll_low_20"]  + _EPS)

    # ── Daily percent change ──────────────────────────────────────────────
    df["pct_chg"] = c.pct_change()

    return df
