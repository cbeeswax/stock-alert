"""
src/patterns/detectors/cup_and_handle.py
==========================================
Cup and Handle pattern detector.

Algorithm: O(p²) pivot-based instead of O(n³) raw-bar loops.
Uses alternating H→L→H pivot triplets to identify cup shape,
then a bounded linear scan for the handle.

Setup conditions
----------------
Cup:
  - Width: CUP_MIN_BARS to CUP_MAX_BARS trading days
  - U-shaped (not V-shaped): middle third of cup must be near the low
  - Depth: ≤ CUP_MAX_DEPTH_PCT from lip to bottom
  - Right lip ≈ left lip height (within 5%)

Handle:
  - Follows right side of cup
  - Width: HANDLE_MIN_BARS to HANDLE_MAX_BARS
  - Pullback: ≤ HANDLE_MAX_DEPTH_PCT from cup lip
  - Handle forms in upper half of the cup

Breakout:
  - Close > cup_lip × BREAKOUT_PIVOT_CLEARANCE
  - Volume ≥ avg_vol_20 × BREAKOUT_VOL_MULT
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.patterns.detectors.base import BasePattern, PatternResult
from src.patterns.features.swings import Pivot
import src.patterns.config.cup_and_handle as cfg


class CupAndHandle(BasePattern):

    @property
    def name(self) -> str:
        return "CupAndHandle"

    def detect(
        self,
        df: pd.DataFrame,
        pivots: list[Pivot],
    ) -> list[PatternResult]:
        results = []
        highs  = df["high"].values
        lows   = df["low"].values
        closes = df["close"].values
        dates  = df.index
        n = len(df)

        # Build index lookup: date → integer position (O(1) per lookup)
        date_to_idx = {d: i for i, d in enumerate(dates)}

        # ── Iterate over H→L→H pivot triplets (O(p²)) ────────────────────
        # The deduplicated pivot list alternates H/L, so every H is followed
        # by an L which is followed by an H — scan for that pattern.
        for i in range(len(pivots) - 2):
            left  = pivots[i]
            bottom = pivots[i + 1]
            right  = pivots[i + 2]

            if left.kind != "H" or bottom.kind != "L" or right.kind != "H":
                continue

            idx_left   = date_to_idx.get(left.date)
            idx_bottom = date_to_idx.get(bottom.date)
            idx_right  = date_to_idx.get(right.date)
            if idx_left is None or idx_bottom is None or idx_right is None:
                continue

            cup_width = idx_right - idx_left
            if cup_width < cfg.CUP_MIN_BARS or cup_width > cfg.CUP_MAX_BARS:
                continue

            left_lip  = left.price
            right_lip = right.price
            cup_low   = bottom.price

            # Left and right lips within 5%
            if abs(left_lip - right_lip) / (left_lip + 1e-9) > 0.05:
                continue

            cup_lip = (left_lip + right_lip) / 2

            # Depth check
            depth = (cup_lip - cup_low) / (cup_lip + 1e-9)
            if depth > cfg.CUP_MAX_DEPTH_PCT or depth < 0.08:
                continue

            # U-shape: middle third must be near the low
            third = max(1, cup_width // 3)
            mid_lows = lows[idx_left + third: idx_right - third]
            if len(mid_lows) > 0:
                mid_avg = mid_lows.mean()
                if (mid_avg - cup_low) / (cup_lip - cup_low + 1e-9) > 0.5:
                    continue  # V-shape

            # ── Handle: bounded scan O(HANDLE_MAX_BARS) ───────────────────
            handle_start = idx_right + 1
            for handle_end in range(
                handle_start + cfg.HANDLE_MIN_BARS - 1,
                min(handle_start + cfg.HANDLE_MAX_BARS, n - 1),
            ):
                handle_low = lows[handle_start:handle_end + 1].min()

                # Handle must stay in upper half of cup
                if handle_low < cup_low + (cup_lip - cup_low) * 0.5:
                    break

                h_depth = (cup_lip - handle_low) / (cup_lip + 1e-9)
                if h_depth > cfg.HANDLE_MAX_DEPTH_PCT:
                    break

                # ── Breakout bar ──────────────────────────────────────────
                bo_idx = handle_end + 1
                if bo_idx >= n:
                    break

                if closes[bo_idx] < cup_lip * cfg.BREAKOUT_PIVOT_CLEARANCE:
                    continue

                vol_ok  = self._vol_confirmed(df, bo_idx, cfg.BREAKOUT_VOL_MULT)
                cpos_ok = self._close_pos_ok(df, bo_idx, cfg.BREAKOUT_CLOSE_POS_MIN)
                stop    = self._stop_below_pattern(handle_low, buffer_pct=0.02)
                quality = self._quality_score(
                    depth, h_depth, vol_ok, cpos_ok, cup_width, handle_end - handle_start
                )

                results.append(PatternResult(
                    symbol=self.symbol,
                    pattern=self.name,
                    setup_start=pd.Timestamp(dates[idx_left]),
                    setup_end=pd.Timestamp(dates[handle_end]),
                    breakout_date=pd.Timestamp(dates[bo_idx]),
                    pivot_price=cup_lip,
                    pattern_low=cup_low,
                    pattern_high=cup_lip,
                    stop_price=stop,
                    volume_confirmed=vol_ok,
                    quality_score=quality,
                    meta={
                        "cup_bars": cup_width,
                        "cup_depth_pct": round(depth * 100, 1),
                        "handle_bars": handle_end - handle_start,
                        "handle_depth_pct": round(h_depth * 100, 1),
                        "left_lip": round(left_lip, 2),
                        "right_lip": round(right_lip, 2),
                        "cup_low": round(cup_low, 2),
                    },
                ))

        return results

    def _quality_score(
        self,
        cup_depth: float,
        handle_depth: float,
        vol_confirmed: bool,
        close_pos_ok: bool,
        cup_bars: int,
        handle_bars: int,
    ) -> float:
        score = 50.0
        if 0.15 <= cup_depth <= 0.30:
            score += 15
        elif cup_depth < 0.15:
            score += 5
        if handle_depth <= 0.06:
            score += 15
        elif handle_depth <= 0.10:
            score += 8
        if vol_confirmed:
            score += 10
        if close_pos_ok:
            score += 10
        if 30 <= cup_bars <= 60:
            score += 5
        if 5 <= handle_bars <= 10:
            score += 5
        return min(score, 100.0)

