"""
src/patterns/detectors/double_bottom.py
========================================
Double Bottom (W-bottom) detector.

Conditions
----------
- Two pivot lows within BOTTOM_TOLERANCE_PCT of each other
- Separated by MIN_BARS_BETWEEN to MAX_BARS_BETWEEN bars
- Second low ≥ first low (ideally slightly higher)
- Middle peak forms the neckline
- Breakout: close above neckline with volume confirmation
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.patterns.detectors.base import BasePattern, PatternResult
from src.patterns.features.swings import Pivot
import src.patterns.config.double_bottom as cfg


class DoubleBottom(BasePattern):

    @property
    def name(self) -> str:
        return "DoubleBottom"

    def detect(
        self,
        df: pd.DataFrame,
        pivots: list[Pivot],
    ) -> list[PatternResult]:
        results = []
        closes = df["close"].values
        highs  = df["high"].values
        dates  = df.index
        n = len(df)

        l_pivots = [p for p in pivots if p.kind == "L"]
        h_pivots = [p for p in pivots if p.kind == "H"]

        for i in range(len(l_pivots) - 1):
            first  = l_pivots[i]
            second = l_pivots[i + 1]

            # Both lows close in price
            diff = abs(first.price - second.price) / (first.price + 1e-9)
            if diff > cfg.BOTTOM_TOLERANCE_PCT:
                continue

            # Second low must not be lower (no lower low allowed)
            if cfg.SECOND_LOW_HIGHER and second.price < first.price:
                continue

            # Separation in bars
            idx1 = self._date_to_idx(df, first.date)
            idx2 = self._date_to_idx(df, second.date)
            if idx1 is None or idx2 is None:
                continue
            separation = idx2 - idx1
            if separation < cfg.MIN_BARS_BETWEEN or separation > cfg.MAX_BARS_BETWEEN:
                continue

            # Find neckline = highest close between the two lows
            between_highs = highs[idx1:idx2 + 1]
            neckline_offset = int(np.argmax(between_highs))
            neckline_price  = float(between_highs[neckline_offset])
            neckline_idx    = idx1 + neckline_offset

            # Neckline must be a real middle peak (higher than both lows)
            if neckline_price <= max(first.price, second.price) * 1.02:
                continue

            pattern_low = min(first.price, second.price)
            stop = self._stop_below_pattern(pattern_low, buffer_pct=0.02)

            # ── Breakout bar (close above neckline) ───────────────────────
            bo_idx = idx2 + 1
            while bo_idx < n:
                bo_close = closes[bo_idx]

                # Invalidation: new lower low
                if bo_close < pattern_low * (1 - cfg.BOTTOM_TOLERANCE_PCT):
                    break

                if cfg.NECKLINE_BREAK and bo_close >= neckline_price * cfg.BREAKOUT_PIVOT_CLEARANCE:
                    vol_ok  = self._vol_confirmed(df, bo_idx, cfg.BREAKOUT_VOL_MULT)
                    cpos_ok = self._close_pos_ok(df, bo_idx, cfg.BREAKOUT_CLOSE_POS_MIN)
                    quality = self._quality_score(
                        diff, second.price >= first.price, vol_ok, cpos_ok, separation
                    )

                    results.append(PatternResult(
                        symbol=self.symbol,
                        pattern=self.name,
                        setup_start=pd.Timestamp(first.date),
                        setup_end=pd.Timestamp(dates[idx2]),
                        breakout_date=pd.Timestamp(dates[bo_idx]),
                        pivot_price=neckline_price,
                        pattern_low=pattern_low,
                        pattern_high=neckline_price,
                        stop_price=stop,
                        volume_confirmed=vol_ok,
                        quality_score=quality,
                        meta={
                            "first_low": round(first.price, 2),
                            "second_low": round(second.price, 2),
                            "neckline": round(neckline_price, 2),
                            "low_diff_pct": round(diff * 100, 1),
                            "separation_bars": separation,
                            "second_higher": second.price >= first.price,
                        },
                    ))
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
        low_diff: float,
        second_higher: bool,
        vol_confirmed: bool,
        close_pos_ok: bool,
        separation_bars: int,
    ) -> float:
        score = 50.0

        # Tighter double bottom = cleaner
        if low_diff <= 0.01:
            score += 20
        elif low_diff <= 0.02:
            score += 12
        elif low_diff <= 0.03:
            score += 5

        # Second bottom slightly higher is textbook
        if second_higher:
            score += 10

        if vol_confirmed:
            score += 10
        if close_pos_ok:
            score += 10

        # Ideal separation 4–12 weeks
        if 20 <= separation_bars <= 60:
            score += 5

        return min(score, 100.0)
