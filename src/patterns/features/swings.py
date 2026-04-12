"""
src/patterns/features/swings.py
================================
N-bar pivot detection engine.

A swing high at bar t means high[t] is the maximum of the window
[t-k .. t+k].  A swing low is the symmetric minimum.

Usage
-----
    from src.patterns.features.swings import add_swings, get_pivot_list

    df = add_swings(df, k=5)          # adds swing_high, swing_low columns
    pivots = get_pivot_list(df)       # [(date, price, type), ...]
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Literal

# ── Pivot dataclass ───────────────────────────────────────────────────────────

@dataclass
class Pivot:
    date: pd.Timestamp
    price: float
    kind: Literal["H", "L"]

    def __repr__(self) -> str:
        return f"Pivot({self.kind} {self.price:.2f} @ {self.date.date()})"


# ── Core detection ────────────────────────────────────────────────────────────

def add_swings(df: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    """
    Append swing_high and swing_low boolean columns to df.

    Parameters
    ----------
    df : DataFrame with lowercase 'high' and 'low' columns
         (run build_features first, or ensure columns are lower-cased)
    k  : look-back / look-forward window in bars (default 5)

    Look-ahead note
    ---------------
    A symmetric k-bar window means pivot at bar i is confirmed only once
    bar i+k has passed.  We mask the last k bars so that detected pivots
    represent what would have been *known* at the time of each bar.
    This eliminates look-ahead bias in both live scans and backtests.

    Returns
    -------
    Same df with two new columns:
        swing_high  bool  — bar is a local high pivot (confirmed, no look-ahead)
        swing_low   bool  — bar is a local low pivot  (confirmed, no look-ahead)
    """
    h = df["high"].values
    l = df["low"].values
    n = len(h)

    sh = np.zeros(n, dtype=bool)
    sl = np.zeros(n, dtype=bool)

    # Only mark pivot at bar i if both i-k and i+k are in range.
    # The loop naturally stops at n-k, so bar i+k exists in the slice.
    # Masking last k bars: in a rolling/walk-forward context, bars near
    # the window edge haven't had k future bars pass yet — they'd be
    # confirmed in the *next* window step, not the current one.
    for i in range(k, n - k):
        window_h = h[i - k: i + k + 1]
        window_l = l[i - k: i + k + 1]
        if h[i] == window_h.max():
            sh[i] = True
        if l[i] == window_l.min():
            sl[i] = True

    # Mask: the most recent k bars cannot be confirmed pivot highs/lows
    # because their right-side confirmation window extends beyond "now".
    # Without this, patterns detected near the slice end carry look-ahead bias.
    if k > 0:
        sh[n - k:] = False
        sl[n - k:] = False

    df = df.copy()
    df["swing_high"] = sh
    df["swing_low"]  = sl

    # Store pivot price (NaN when not a pivot — convenient for plotting)
    df["swing_high_price"] = np.where(sh, df["high"], np.nan)
    df["swing_low_price"]  = np.where(sl, df["low"],  np.nan)

    return df


def get_pivot_list(df: pd.DataFrame) -> list[Pivot]:
    """
    Return a time-ordered list of Pivot objects from a df that has
    already had add_swings() applied.

    Alternates H/L in the list (removes consecutive same-type pivots
    by keeping only the more extreme one) — useful for pattern detection
    that requires alternating pivots.
    """
    rows = []
    for idx, row in df.iterrows():
        if row.get("swing_high"):
            rows.append(Pivot(date=pd.Timestamp(idx), price=float(row["high"]), kind="H"))
        if row.get("swing_low"):
            rows.append(Pivot(date=pd.Timestamp(idx), price=float(row["low"]), kind="L"))

    rows.sort(key=lambda p: p.date)
    return _deduplicate_pivots(rows)


def _deduplicate_pivots(pivots: list[Pivot]) -> list[Pivot]:
    """
    When two consecutive pivots are the same type (H/H or L/L), keep
    only the more extreme one (higher high, lower low).
    """
    if not pivots:
        return []

    result: list[Pivot] = [pivots[0]]
    for p in pivots[1:]:
        last = result[-1]
        if p.kind == last.kind:
            # Same type — keep the more extreme
            if p.kind == "H" and p.price >= last.price:
                result[-1] = p
            elif p.kind == "L" and p.price <= last.price:
                result[-1] = p
        else:
            result.append(p)

    return result


def pivots_in_range(
    pivots: list[Pivot],
    start: pd.Timestamp,
    end: pd.Timestamp,
    kind: Literal["H", "L", "both"] = "both",
) -> list[Pivot]:
    """Filter pivot list to a date range and optional type."""
    return [
        p for p in pivots
        if start <= p.date <= end and (kind == "both" or p.kind == kind)
    ]
