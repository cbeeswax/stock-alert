"""
src/patterns/detectors/base.py
================================
Abstract base class and standardised output schema for all six
pattern detectors.

Every detector must:
  1. Inherit from BasePattern
  2. Implement detect(df, pivots) → list[PatternResult]
  3. Return PatternResult objects — nothing else

The signal engine and backtester only know about PatternResult,
so all six patterns are interchangeable downstream.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any

import pandas as pd

from src.patterns.features.swings import Pivot


# ── Output schema ─────────────────────────────────────────────────────────────

@dataclass
class PatternResult:
    """
    Standardised output from any pattern detector.

    Fields
    ------
    symbol          Ticker symbol
    pattern         Human-readable pattern name, e.g. "CupAndHandle"
    setup_start     First bar of the base/pattern
    setup_end       Last bar of the base (day before breakout)
    breakout_date   Date the breakout bar closes
    pivot_price     The breakout pivot level (cup lip, resistance, etc.)
    pattern_low     Lowest price within the pattern (used for stop)
    pattern_high    Highest price within the pattern
    stop_price      Suggested structural stop loss
    volume_confirmed  True if breakout bar volume ≥ threshold
    quality_score   0–100 — higher is cleaner setup
    meta            Dict of pattern-specific debug info (serialised to JSON)
    """
    symbol:           str
    pattern:          str
    setup_start:      pd.Timestamp
    setup_end:        pd.Timestamp
    breakout_date:    pd.Timestamp
    pivot_price:      float
    pattern_low:      float
    pattern_high:     float
    stop_price:       float
    volume_confirmed: bool
    quality_score:    float
    meta:             dict[str, Any] = field(default_factory=dict)

    # ── Convenience ──────────────────────────────────────────────────────
    @property
    def meta_json(self) -> str:
        return json.dumps(self.meta, default=str)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["meta_json"] = self.meta_json
        d.pop("meta", None)
        return d

    def __repr__(self) -> str:
        return (
            f"PatternResult({self.pattern} {self.symbol} "
            f"breakout={self.breakout_date.date()} "
            f"pivot={self.pivot_price:.2f} score={self.quality_score:.0f})"
        )


# ── Abstract base detector ────────────────────────────────────────────────────

class BasePattern(ABC):
    """
    All six detectors inherit from this.

    Subclass contract
    -----------------
    - Call super().__init__() or pass symbol explicitly.
    - Implement detect().
    - Use self._vol_confirmed() and self._stop_below_pattern() helpers.
    """

    def __init__(self, symbol: str = ""):
        self.symbol = symbol

    @property
    @abstractmethod
    def name(self) -> str:
        """Short pattern name used in PatternResult.pattern."""

    @abstractmethod
    def detect(
        self,
        df: pd.DataFrame,
        pivots: list[Pivot],
    ) -> list[PatternResult]:
        """
        Scan df for valid setups.

        Parameters
        ----------
        df      : feature-enriched DataFrame (output of build_features + add_swings)
        pivots  : deduplicated alternating pivot list from get_pivot_list(df)

        Returns
        -------
        List of PatternResult — empty list if no valid setup found.
        """

    # ── Shared helpers ────────────────────────────────────────────────────

    def _vol_confirmed(
        self,
        df: pd.DataFrame,
        bar_idx: int,
        vol_mult: float = 1.8,
    ) -> bool:
        """Return True if volume on bar_idx ≥ vol_mult × avg_vol_20."""
        if bar_idx >= len(df):
            return False
        row = df.iloc[bar_idx]
        avg = row.get("avg_vol_20", 0)
        vol = row.get("volume", 0)
        return avg > 0 and vol >= avg * vol_mult

    def _close_pos_ok(
        self,
        df: pd.DataFrame,
        bar_idx: int,
        min_pos: float = 0.7,
    ) -> bool:
        """Return True if close_pos on bar_idx ≥ min_pos."""
        if bar_idx >= len(df):
            return False
        return float(df.iloc[bar_idx].get("close_pos", 0)) >= min_pos

    def _stop_below_pattern(
        self,
        pattern_low: float,
        buffer_pct: float = 0.02,
    ) -> float:
        """Default structural stop: slightly below the pattern's lowest point."""
        return pattern_low * (1 - buffer_pct)
