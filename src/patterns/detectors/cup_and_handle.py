"""
src/patterns/detectors/cup_and_handle.py
==========================================
Cup and Handle pattern detector.

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
        highs = df["high"].values
        lows  = df["low"].values
        closes = df["close"].values
        dates  = df.index

        n = len(df)

        # Slide a window looking for a cup shape
        for cup_start in range(0, n - cfg.CUP_MIN_BARS - cfg.HANDLE_MIN_BARS):
            for cup_end in range(
                cup_start + cfg.CUP_MIN_BARS,
                min(cup_start + cfg.CUP_MAX_BARS, n - cfg.HANDLE_MIN_BARS),
            ):
                left_lip  = highs[cup_start]
                right_lip = highs[cup_end]
                cup_low   = lows[cup_start:cup_end + 1].min()

                # Left and right lips must be roughly equal (within 5%)
                if abs(left_lip - right_lip) / (left_lip + 1e-9) > 0.05:
                    continue

                # Cup lip = average of the two lips
                cup_lip = (left_lip + right_lip) / 2

                # Depth check
                depth = (cup_lip - cup_low) / (cup_lip + 1e-9)
                if depth > cfg.CUP_MAX_DEPTH_PCT:
                    continue
                if depth < 0.08:  # too shallow — probably not a real base
                    continue

                # U-shape check: mid-section (middle third) should be near the low
                third = max(1, (cup_end - cup_start) // 3)
                mid_slice = lows[cup_start + third: cup_end - third]
                if len(mid_slice) == 0:
                    continue
                mid_avg = mid_slice.mean()
                if (mid_avg - cup_low) / (cup_lip - cup_low + 1e-9) > 0.5:
                    continue  # V-shape — mid section too high

                # ── Handle search ─────────────────────────────────────────
                handle_start = cup_end + 1
                for handle_end in range(
                    handle_start + cfg.HANDLE_MIN_BARS - 1,
                    min(handle_start + cfg.HANDLE_MAX_BARS, n - 1),
                ):
                    handle_low = lows[handle_start:handle_end + 1].min()

                    # Handle must stay in upper half of cup
                    if handle_low < cup_low + (cup_lip - cup_low) * 0.5:
                        break  # went too deep — no point extending handle

                    # Handle depth from cup lip
                    h_depth = (cup_lip - handle_low) / (cup_lip + 1e-9)
                    if h_depth > cfg.HANDLE_MAX_DEPTH_PCT:
                        break

                    # ── Breakout bar ──────────────────────────────────────
                    bo_idx = handle_end + 1
                    if bo_idx >= n:
                        break

                    bo_close = closes[bo_idx]
                    if bo_close < cup_lip * cfg.BREAKOUT_PIVOT_CLEARANCE:
                        continue

                    vol_ok = self._vol_confirmed(df, bo_idx, cfg.BREAKOUT_VOL_MULT)
                    cpos_ok = self._close_pos_ok(df, bo_idx, cfg.BREAKOUT_CLOSE_POS_MIN)

                    pattern_low = cup_low
                    stop = self._stop_below_pattern(handle_low, buffer_pct=0.02)

                    quality = self._quality_score(
                        depth, h_depth, vol_ok, cpos_ok,
                        cup_end - cup_start, handle_end - handle_start,
                    )

                    results.append(PatternResult(
                        symbol=self.symbol,
                        pattern=self.name,
                        setup_start=pd.Timestamp(dates[cup_start]),
                        setup_end=pd.Timestamp(dates[handle_end]),
                        breakout_date=pd.Timestamp(dates[bo_idx]),
                        pivot_price=cup_lip,
                        pattern_low=pattern_low,
                        pattern_high=cup_lip,
                        stop_price=stop,
                        volume_confirmed=vol_ok,
                        quality_score=quality,
                        meta={
                            "cup_bars": cup_end - cup_start,
                            "cup_depth_pct": round(depth * 100, 1),
                            "handle_bars": handle_end - handle_start,
                            "handle_depth_pct": round(h_depth * 100, 1),
                            "left_lip": round(left_lip, 2),
                            "right_lip": round(right_lip, 2),
                            "cup_low": round(cup_low, 2),
                        },
                    ))

        return results

    # ── Quality scoring ───────────────────────────────────────────────────────

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

        # Ideal cup depth 15–30%
        if 0.15 <= cup_depth <= 0.30:
            score += 15
        elif cup_depth < 0.15:
            score += 5  # shallow but acceptable

        # Tight handle is better
        if handle_depth <= 0.06:
            score += 15
        elif handle_depth <= 0.10:
            score += 8

        # Volume on breakout
        if vol_confirmed:
            score += 10

        # Close near top of bar
        if close_pos_ok:
            score += 10

        # Ideal cup width 6–12 weeks (30–60 bars)
        if 30 <= cup_bars <= 60:
            score += 5

        # Ideal handle 1–2 weeks (5–10 bars)
        if 5 <= handle_bars <= 10:
            score += 5

        return min(score, 100.0)
