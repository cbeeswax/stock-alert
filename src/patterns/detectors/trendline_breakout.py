"""
src/patterns/detectors/trendline_breakout.py
=============================================
Descending Trendline Breakout detector.

Conditions
----------
- At least MIN_TRENDLINE_TOUCHES swing highs fit a downward-sloping line
- Trendline slope is negative (downtrend)
- Pattern spans MIN_TRENDLINE_BARS to MAX_TRENDLINE_BARS
- Breakout: first close above the projected trendline value on that bar
  + volume confirmation
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.patterns.detectors.base import BasePattern, PatternResult
from src.patterns.features.swings import Pivot
import src.patterns.config.trendline_breakout as cfg


class TrendlineBreakout(BasePattern):

    @property
    def name(self) -> str:
        return "TrendlineBreakout"

    def detect(
        self,
        df: pd.DataFrame,
        pivots: list[Pivot],
    ) -> list[PatternResult]:
        results = []
        closes = df["close"].values
        lows   = df["low"].values
        dates  = df.index
        n = len(df)

        h_pivots = [p for p in pivots if p.kind == "H"]
        if len(h_pivots) < cfg.MIN_TRENDLINE_TOUCHES:
            return results

        # Try every pair of swing highs as the two anchor points of the trendline
        for i in range(len(h_pivots) - 1):
            for j in range(i + 1, len(h_pivots)):
                p1, p2 = h_pivots[i], h_pivots[j]

                idx1 = self._date_to_idx(df, p1.date)
                idx2 = self._date_to_idx(df, p2.date)
                if idx1 is None or idx2 is None:
                    continue

                width = idx2 - idx1
                if width < cfg.MIN_TRENDLINE_BARS or width > cfg.MAX_TRENDLINE_BARS:
                    continue

                # Fit line through (idx1, p1.price) → (idx2, p2.price)
                slope     = (p2.price - p1.price) / (idx2 - idx1 + 1e-9)
                intercept = p1.price - slope * idx1

                # Slope must be negative (downtrend)
                if slope >= cfg.SLOPE_MAX:
                    continue

                # Check that no swing high between i and j is above the line
                # (line should act as resistance — highs touch but don't exceed)
                touches = [p1, p2]
                valid = True
                for k in range(i + 1, j):
                    mid = h_pivots[k]
                    mid_idx = self._date_to_idx(df, mid.date)
                    if mid_idx is None:
                        continue
                    line_val = slope * mid_idx + intercept
                    # If a pivot is significantly above the line → line is not resistance
                    if mid.price > line_val * 1.01:
                        valid = False
                        break
                    # Count as touch if within 1%
                    if abs(mid.price - line_val) / (line_val + 1e-9) <= 0.01:
                        touches.append(mid)

                if not valid or len(touches) < cfg.MIN_TRENDLINE_TOUCHES:
                    continue

                pattern_low = float(lows[idx1:idx2 + 1].min())
                stop = self._stop_below_pattern(pattern_low, buffer_pct=0.02)

                # ── Breakout bar ──────────────────────────────────────────
                bo_idx = idx2 + 1
                while bo_idx < min(idx2 + 30, n):  # look up to 30 bars ahead
                    line_at_bo = slope * bo_idx + intercept
                    bo_close   = closes[bo_idx]

                    if bo_close >= line_at_bo * cfg.BREAKOUT_PIVOT_CLEARANCE:
                        vol_ok  = self._vol_confirmed(df, bo_idx, cfg.BREAKOUT_VOL_MULT)
                        cpos_ok = self._close_pos_ok(df, bo_idx, cfg.BREAKOUT_CLOSE_POS_MIN)
                        quality = self._quality_score(
                            len(touches), abs(slope), vol_ok, cpos_ok, width
                        )

                        results.append(PatternResult(
                            symbol=self.symbol,
                            pattern=self.name,
                            setup_start=pd.Timestamp(p1.date),
                            setup_end=pd.Timestamp(dates[idx2]),
                            breakout_date=pd.Timestamp(dates[bo_idx]),
                            pivot_price=round(line_at_bo, 2),
                            pattern_low=pattern_low,
                            pattern_high=p1.price,
                            stop_price=stop,
                            volume_confirmed=vol_ok,
                            quality_score=quality,
                            meta={
                                "slope": round(slope, 4),
                                "touches": len(touches),
                                "trendline_bars": width,
                                "anchor1": round(p1.price, 2),
                                "anchor2": round(p2.price, 2),
                                "line_at_breakout": round(line_at_bo, 2),
                            },
                        ))
                        break  # first valid breakout for this trendline

                    # Invalidation: new lower low far below pattern
                    if closes[bo_idx] < pattern_low * 0.95:
                        break
                    bo_idx += 1

        return results

    def _date_to_idx(self, df: pd.DataFrame, date: pd.Timestamp) -> int | None:
        try:
            loc = df.index.get_loc(date)
            return int(loc) if isinstance(loc, (int, np.integer)) else int(loc.start)
        except KeyError:
            idx = df.index.searchsorted(date)
            return idx if idx < len(df) else None

    def _quality_score(
        self,
        touches: int,
        slope_abs: float,
        vol_confirmed: bool,
        close_pos_ok: bool,
        trendline_bars: int,
    ) -> float:
        score = 50.0
        score += min((touches - 2) * 10, 20)   # more touches = cleaner line

        # Steeper downtrend breaking out = more momentum
        if slope_abs > 0.3:
            score += 10
        elif slope_abs > 0.1:
            score += 5

        if vol_confirmed:
            score += 10
        if close_pos_ok:
            score += 10

        return min(score, 100.0)
