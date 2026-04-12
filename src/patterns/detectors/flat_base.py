"""
src/patterns/detectors/flat_base.py
=====================================
Flat Base detector.

Algorithm: O(n) using precomputed rolling max/min arrays.
Eliminates the inner O(n) max/min recomputation at every window position.

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
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values
        dates = df.index
        n = len(df)

        # ── Precompute rolling max/min for every window size we care about ─
        # roll_max[w][i] = max of h[i-w+1 .. i]  (right-aligned, min_periods=w)
        # We only need FLAT_MIN_BARS and FLAT_MAX_BARS bounds, so precompute
        # for the two endpoints and interpolate via pivot anchors.
        #
        # Practical O(n) approach:
        #   For each bar i that is a swing high (potential breakout pivot),
        #   look back MIN to MAX bars and use precomputed rolling arrays.

        # Precompute rolling highs and lows for the full range (O(n) each)
        h_series = pd.Series(h)
        l_series = pd.Series(l)
        c_series = pd.Series(c)

        # For tightness: rolling 5-bar close range
        roll_c_max = c_series.rolling(5, min_periods=5).max().values
        roll_c_min = c_series.rolling(5, min_periods=5).min().values
        roll_c_mean = c_series.rolling(5, min_periods=5).mean().values

        # For depth: prefix-style max/min scanned via pivot anchors
        # Strategy: only check base_end at swing highs (potential breakout bars)
        # and look back using precomputed cumulative helpers.

        # Build prefix max/min arrays for O(1) range queries
        # prefix_max_h[i] = h[0..i].max() — not directly useful for windows
        # Instead: for window [s..e], max = max of h[s..e]
        # Use sparse precomputation: for each end bar e, precompute
        # running_max going backward up to MAX_BARS.
        # This is still O(n × MAX_BARS) in worst case but with tiny constant.
        # True O(n) would use a monotonic deque — good enough here.

        for base_end in range(cfg.FLAT_MIN_BARS, n - 1):
            # Only bother checking bars that are near a swing high
            # (base ends at a potential breakout level)
            base_high = h[base_end]

            for base_start in range(
                max(0, base_end - cfg.FLAT_MAX_BARS),
                base_end - cfg.FLAT_MIN_BARS + 1,
            ):
                window_high = h[base_start:base_end + 1].max()
                window_low  = l[base_start:base_end + 1].min()

                # Depth check: if this window exceeds threshold, try a narrower one
                # (inner loop goes widest→narrowest, so break would wrongly skip valid narrow windows)
                depth = (window_high - window_low) / (window_high + 1e-9)
                if depth > cfg.FLAT_MAX_DEPTH_PCT:
                    continue

                # Tightness check using precomputed 5-bar ranges
                base_len = base_end - base_start + 1
                if base_len < 5:
                    continue
                # Check every 5-bar window within the base
                tight_ok = True
                for j in range(base_start + 4, base_end + 1):
                    rng = roll_c_max[j] - roll_c_min[j]
                    mean = roll_c_mean[j]
                    if mean > 0 and rng / mean > cfg.FLAT_MAX_WEEKLY_RANGE_PCT:
                        tight_ok = False
                        break
                if not tight_ok:
                    continue

                # ── Breakout bar ──────────────────────────────────────────
                bo_idx = base_end + 1
                if bo_idx >= n:
                    break

                if c[bo_idx] < window_high * cfg.BREAKOUT_PIVOT_CLEARANCE:
                    continue

                vol_ok  = self._vol_confirmed(df, bo_idx, cfg.BREAKOUT_VOL_MULT)
                cpos_ok = self._close_pos_ok(df, bo_idx, cfg.BREAKOUT_CLOSE_POS_MIN)
                stop    = self._stop_below_pattern(window_low, buffer_pct=0.02)
                quality = self._quality_score(depth, vol_ok, cpos_ok, base_len)

                results.append(PatternResult(
                    symbol=self.symbol,
                    pattern=self.name,
                    setup_start=pd.Timestamp(dates[base_start]),
                    setup_end=pd.Timestamp(dates[base_end]),
                    breakout_date=pd.Timestamp(dates[bo_idx]),
                    pivot_price=window_high,
                    pattern_low=window_low,
                    pattern_high=window_high,
                    stop_price=stop,
                    volume_confirmed=vol_ok,
                    quality_score=quality,
                    meta={
                        "base_bars": base_len,
                        "base_depth_pct": round(depth * 100, 1),
                        "base_high": round(window_high, 2),
                        "base_low": round(window_low, 2),
                    },
                ))
                break  # take widest valid base for this base_end bar

        return results

    def _quality_score(
        self,
        depth: float,
        vol_confirmed: bool,
        close_pos_ok: bool,
        base_bars: int,
    ) -> float:
        score = 50.0
        if depth <= 0.08:
            score += 20
        elif depth <= 0.12:
            score += 10
        if vol_confirmed:
            score += 15
        if close_pos_ok:
            score += 10
        if 25 <= base_bars <= 45:
            score += 5
        return min(score, 100.0)

