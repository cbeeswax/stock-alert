"""
src/patterns/detectors/flat_base.py
=====================================
Flat Base detector.

Conditions
----------
- Base spans FLAT_MIN_BARS to FLAT_MAX_BARS trading days
- Base depth (high to low) ≤ FLAT_MAX_DEPTH_PCT
- Tight closes: rolling weekly range stays ≤ FLAT_MAX_WEEKLY_RANGE_PCT
- Breakout: close above base high with volume confirmation
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.patterns.detectors.base import BasePattern, PatternResult
from src.patterns.features.swings import Pivot
import src.patterns.config.flat_base as cfg


class FlatBase(BasePattern):

    @property
    def name(self) -> str:
        return "FlatBase"

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

        for base_start in range(0, n - cfg.FLAT_MIN_BARS - 1):
            for base_end in range(
                base_start + cfg.FLAT_MIN_BARS,
                min(base_start + cfg.FLAT_MAX_BARS, n - 1),
            ):
                base_high = highs[base_start:base_end + 1].max()
                base_low  = lows[base_start:base_end + 1].min()

                # Depth check
                depth = (base_high - base_low) / (base_high + 1e-9)
                if depth > cfg.FLAT_MAX_DEPTH_PCT:
                    break  # exceeded max depth — extend won't help

                # Tightness: every rolling 5-bar window must be tight
                if not self._is_tight(closes[base_start:base_end + 1]):
                    continue

                # ── Breakout bar ──────────────────────────────────────────
                bo_idx = base_end + 1
                if bo_idx >= n:
                    break

                bo_close = closes[bo_idx]
                if bo_close < base_high * cfg.BREAKOUT_PIVOT_CLEARANCE:
                    continue

                vol_ok  = self._vol_confirmed(df, bo_idx, cfg.BREAKOUT_VOL_MULT)
                cpos_ok = self._close_pos_ok(df, bo_idx, cfg.BREAKOUT_CLOSE_POS_MIN)

                stop   = self._stop_below_pattern(base_low, buffer_pct=0.02)
                quality = self._quality_score(depth, vol_ok, cpos_ok, base_end - base_start)

                results.append(PatternResult(
                    symbol=self.symbol,
                    pattern=self.name,
                    setup_start=pd.Timestamp(dates[base_start]),
                    setup_end=pd.Timestamp(dates[base_end]),
                    breakout_date=pd.Timestamp(dates[bo_idx]),
                    pivot_price=base_high,
                    pattern_low=base_low,
                    pattern_high=base_high,
                    stop_price=stop,
                    volume_confirmed=vol_ok,
                    quality_score=quality,
                    meta={
                        "base_bars": base_end - base_start,
                        "base_depth_pct": round(depth * 100, 1),
                        "base_high": round(base_high, 2),
                        "base_low": round(base_low, 2),
                    },
                ))

        return results

    def _is_tight(self, closes: np.ndarray, window: int = 5) -> bool:
        """Every rolling 5-bar close range must be ≤ FLAT_MAX_WEEKLY_RANGE_PCT."""
        for i in range(len(closes) - window + 1):
            w = closes[i:i + window]
            rng = (w.max() - w.min()) / (w.mean() + 1e-9)
            if rng > cfg.FLAT_MAX_WEEKLY_RANGE_PCT:
                return False
        return True

    def _quality_score(
        self,
        depth: float,
        vol_confirmed: bool,
        close_pos_ok: bool,
        base_bars: int,
    ) -> float:
        score = 50.0

        if depth <= 0.08:
            score += 20  # very tight base
        elif depth <= 0.12:
            score += 10

        if vol_confirmed:
            score += 15
        if close_pos_ok:
            score += 10

        # Ideal 5–9 weeks
        if 25 <= base_bars <= 45:
            score += 5

        return min(score, 100.0)
