"""
src/patterns/detectors/ascending_triangle.py
=============================================
Ascending Triangle detector.

Conditions
----------
- Flat resistance ceiling: ≥ MIN_RESISTANCE_TOUCHES swing highs within RESISTANCE_TOLERANCE
- Rising support lows: ≥ MIN_SUPPORT_TOUCHES pivot lows, each higher than the last
- Pattern spans MIN_PATTERN_BARS to MAX_PATTERN_BARS
- Breakout: close above resistance with volume confirmation
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.patterns.detectors.base import BasePattern, PatternResult
from src.patterns.features.swings import Pivot, pivots_in_range
import src.patterns.config.ascending_triangle as cfg


class AscendingTriangle(BasePattern):

    @property
    def name(self) -> str:
        return "AscendingTriangle"

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

        # Use pivot list to find candidate resistance zones
        h_pivots = [p for p in pivots if p.kind == "H"]
        l_pivots = [p for p in pivots if p.kind == "L"]

        for i in range(len(h_pivots) - cfg.MIN_RESISTANCE_TOUCHES + 1):
            anchor = h_pivots[i]
            resistance = anchor.price

            # Collect highs near resistance
            touches = [
                p for p in h_pivots[i:]
                if abs(p.price - resistance) / (resistance + 1e-9) <= cfg.RESISTANCE_TOLERANCE
            ]
            if len(touches) < cfg.MIN_RESISTANCE_TOUCHES:
                continue

            pattern_start_date = touches[0].date
            pattern_end_date   = touches[-1].date

            # Pattern width check
            pat_start_idx = self._date_to_idx(df, pattern_start_date)
            pat_end_idx   = self._date_to_idx(df, pattern_end_date)
            if pat_start_idx is None or pat_end_idx is None:
                continue
            width = pat_end_idx - pat_start_idx
            if width < cfg.MIN_PATTERN_BARS or width > cfg.MAX_PATTERN_BARS:
                continue

            # Check for rising lows within the pattern window
            lows_in_range = [
                p for p in l_pivots
                if pattern_start_date <= p.date <= pattern_end_date
            ]
            if len(lows_in_range) < cfg.MIN_SUPPORT_TOUCHES:
                continue
            if not self._lows_rising(lows_in_range):
                continue

            pattern_low = min(p.price for p in lows_in_range)

            # ── Breakout bar ──────────────────────────────────────────────
            bo_idx = pat_end_idx + 1
            while bo_idx < n:
                bo_close = closes[bo_idx]
                if bo_close >= resistance * cfg.BREAKOUT_PIVOT_CLEARANCE:
                    vol_ok  = self._vol_confirmed(df, bo_idx, cfg.BREAKOUT_VOL_MULT)
                    cpos_ok = self._close_pos_ok(df, bo_idx, cfg.BREAKOUT_CLOSE_POS_MIN)
                    stop    = self._stop_below_pattern(pattern_low, buffer_pct=0.02)
                    quality = self._quality_score(
                        len(touches), len(lows_in_range), vol_ok, cpos_ok
                    )

                    results.append(PatternResult(
                        symbol=self.symbol,
                        pattern=self.name,
                        setup_start=pd.Timestamp(pattern_start_date),
                        setup_end=pd.Timestamp(dates[pat_end_idx]),
                        breakout_date=pd.Timestamp(dates[bo_idx]),
                        pivot_price=resistance,
                        pattern_low=pattern_low,
                        pattern_high=resistance,
                        stop_price=stop,
                        volume_confirmed=vol_ok,
                        quality_score=quality,
                        meta={
                            "resistance": round(resistance, 2),
                            "resistance_touches": len(touches),
                            "support_touches": len(lows_in_range),
                            "pattern_bars": width,
                        },
                    ))
                    break  # take first valid breakout for this setup

                # Invalidation: if price closes below pattern low, stop looking
                if lows[bo_idx] < pattern_low * 0.97:
                    break
                bo_idx += 1

        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _date_to_idx(self, df: pd.DataFrame, date: pd.Timestamp) -> int | None:
        try:
            loc = df.index.get_loc(date)
            return int(loc) if isinstance(loc, (int, np.integer)) else int(loc.start)
        except KeyError:
            # Find nearest date
            idx = df.index.searchsorted(date)
            return idx if idx < len(df) else None

    def _lows_rising(self, lows: list[Pivot]) -> bool:
        """Each successive pivot low must be higher than the previous."""
        for i in range(1, len(lows)):
            if lows[i].price <= lows[i - 1].price:
                return False
        return True

    def _quality_score(
        self,
        resistance_touches: int,
        support_touches: int,
        vol_confirmed: bool,
        close_pos_ok: bool,
    ) -> float:
        score = 50.0
        score += min((resistance_touches - 2) * 8, 16)   # more touches = cleaner
        score += min((support_touches - 2) * 8, 16)
        if vol_confirmed:
            score += 10
        if close_pos_ok:
            score += 8
        return min(score, 100.0)
