"""
src/patterns/detectors/high_tight_flag.py
==========================================
High Tight Flag detector.

Algorithm: O(p×c) using precomputed rolling min array.
- Precompute rolling min once: O(n)
- For each swing high pivot (potential pole top): O(p)
  - O(1) pole base lookup via precomputed array
  - O(FLAG_MAX_BARS) bounded flag scan

Pole:   stock gains ≥ 100% in ≤ POLE_MAX_BARS trading days
Flag:   tight consolidation of FLAG_MAX_DEPTH_PCT off pole top
        lasting FLAG_MIN_BARS to FLAG_MAX_BARS
Breakout: close above flag top with volume confirmation
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.patterns.detectors.base import BasePattern, PatternResult
from src.patterns.features.swings import Pivot
import src.patterns.config.high_tight_flag as cfg


class HighTightFlag(BasePattern):

    @property
    def name(self) -> str:
        return "HighTightFlag"

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

        # ── Precompute rolling min of lows (O(n)) ────────────────────────
        # roll_min_low[i] = min of lows[i - POLE_MAX_BARS .. i]
        roll_min_low = (
            pd.Series(lows)
            .rolling(cfg.POLE_MAX_BARS, min_periods=1)
            .min()
            .values
        )

        # Build date → index map for pivot lookup
        date_to_idx = {d: i for i, d in enumerate(dates)}

        # ── Iterate over swing high pivots as pole tops (O(p)) ────────────
        h_pivots = [p for p in pivots if p.kind == "H"]

        for pv in h_pivots:
            pole_end = date_to_idx.get(pv.date)
            if pole_end is None or pole_end < cfg.POLE_MAX_BARS:
                continue

            pole_top  = highs[pole_end]
            # O(1): pole base = min low in the lookback window
            pole_base = float(roll_min_low[pole_end])

            if pole_base <= 0:
                continue

            gain = (pole_top - pole_base) / pole_base
            if gain < cfg.POLE_MIN_GAIN_PCT:
                continue

            # ── Flag search: bounded O(FLAG_MAX_BARS) ─────────────────────
            flag_start = pole_end + 1
            for flag_end in range(
                flag_start + cfg.FLAG_MIN_BARS - 1,
                min(flag_start + cfg.FLAG_MAX_BARS, n - 1),
            ):
                flag_high = highs[flag_start:flag_end + 1].max()
                flag_low  = lows[flag_start:flag_end + 1].min()

                depth = (pole_top - flag_low) / (pole_top + 1e-9)
                if depth > cfg.FLAG_MAX_DEPTH_PCT:
                    break
                if depth < cfg.FLAG_MIN_DEPTH_PCT:
                    continue

                flag_range_pct = (flag_high - flag_low) / (pole_top + 1e-9)
                is_tight = flag_range_pct <= cfg.FLAG_TIGHT_RANGE_PCT

                bo_idx = flag_end + 1
                if bo_idx >= n:
                    break

                if closes[bo_idx] < flag_high * cfg.BREAKOUT_PIVOT_CLEARANCE:
                    continue

                vol_ok  = self._vol_confirmed(df, bo_idx, cfg.BREAKOUT_VOL_MULT)
                cpos_ok = self._close_pos_ok(df, bo_idx, cfg.BREAKOUT_CLOSE_POS_MIN)
                stop    = self._stop_below_pattern(flag_low, buffer_pct=0.02)

                # Find pole base bar index for setup_start
                pole_base_idx = max(0, pole_end - cfg.POLE_MAX_BARS)
                quality = self._quality_score(gain, depth, is_tight, vol_ok, cpos_ok)

                results.append(PatternResult(
                    symbol=self.symbol,
                    pattern=self.name,
                    setup_start=pd.Timestamp(dates[pole_base_idx]),
                    setup_end=pd.Timestamp(dates[flag_end]),
                    breakout_date=pd.Timestamp(dates[bo_idx]),
                    pivot_price=flag_high,
                    pattern_low=flag_low,
                    pattern_high=pole_top,
                    stop_price=stop,
                    volume_confirmed=vol_ok,
                    quality_score=quality,
                    meta={
                        "pole_gain_pct": round(gain * 100, 1),
                        "pole_bars": pole_end - pole_base_idx,
                        "flag_bars": flag_end - flag_start,
                        "flag_depth_pct": round(depth * 100, 1),
                        "flag_range_pct": round(flag_range_pct * 100, 1),
                        "is_tight": is_tight,
                        "pole_top": round(pole_top, 2),
                    },
                ))

        return results

    def _quality_score(
        self,
        pole_gain: float,
        flag_depth: float,
        is_tight: bool,
        vol_confirmed: bool,
        close_pos_ok: bool,
    ) -> float:
        score = 50.0
        if pole_gain >= 2.0:
            score += 20
        elif pole_gain >= 1.5:
            score += 12
        elif pole_gain >= 1.0:
            score += 5
        if is_tight:
            score += 15
        if flag_depth <= 0.10:
            score += 10
        elif flag_depth <= 0.15:
            score += 5
        if vol_confirmed:
            score += 10
        if close_pos_ok:
            score += 10
        return min(score, 100.0)

