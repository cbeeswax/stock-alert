"""
src/patterns/signals/engine.py
================================
Signal engine — converts PatternResult → TradeSignal.

Applies shared breakout confirmation rules and computes:
  entry_price  (next open or breakout close)
  stop_loss
  target (initial measured-move estimate)
  position_size (shares) given risk_pct of equity

Usage
-----
    from src.patterns.signals.engine import SignalEngine
    engine = SignalEngine(equity=100_000, risk_pct=0.005)
    signals = engine.process(pattern_results, df)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.patterns.detectors.base import PatternResult
from src.patterns.config.shared import (
    BREAKOUT_PIVOT_CLEARANCE,
    BREAKOUT_VOL_MULT,
    BREAKOUT_CLOSE_POS_MIN,
    ENTRY_MODE,
    RISK_PER_TRADE_PCT,
    MAX_HOLDING_DAYS,
)

_EPS = 1e-9


# ── Output ────────────────────────────────────────────────────────────────────

@dataclass
class TradeSignal:
    """
    Ready-to-trade signal produced by the signal engine.
    Compatible with the existing stock-alert email / tracker format.
    """
    symbol:        str
    pattern:       str
    entry_price:   float
    stop_loss:     float
    target:        float           # initial measured-move target
    shares:        int
    risk_amount:   float           # $ at risk
    quality_score: float
    breakout_date: pd.Timestamp
    entry_mode:    Literal["next_open", "breakout_close"]
    pattern_result: PatternResult  # full detail for backtest / logging

    # Formatted for main.py / email.py compatibility
    @property
    def Ticker(self) -> str:       return self.symbol
    @property
    def Entry(self) -> float:      return self.entry_price
    @property
    def StopLoss(self) -> float:   return self.stop_loss
    @property
    def Target(self) -> float:     return self.target
    @property
    def Strategy(self) -> str:     return f"Pattern_{self.pattern}"
    @property
    def Score(self) -> float:      return self.quality_score
    @property
    def MaxDays(self) -> int:      return MAX_HOLDING_DAYS

    def __repr__(self) -> str:
        return (
            f"TradeSignal({self.symbol} {self.pattern} "
            f"entry={self.entry_price:.2f} stop={self.stop_loss:.2f} "
            f"target={self.target:.2f} shares={self.shares} "
            f"score={self.quality_score:.0f})"
        )


# ── Engine ────────────────────────────────────────────────────────────────────

class SignalEngine:

    def __init__(
        self,
        equity: float = 100_000,
        risk_pct: float = RISK_PER_TRADE_PCT / 100,
        entry_mode: Literal["next_open", "breakout_close"] = ENTRY_MODE,
        min_quality: float = 60.0,
        vol_mult: float = BREAKOUT_VOL_MULT,
        close_pos_min: float = BREAKOUT_CLOSE_POS_MIN,
    ):
        self.equity        = equity
        self.risk_pct      = risk_pct
        self.entry_mode    = entry_mode
        self.min_quality   = min_quality
        self.vol_mult      = vol_mult
        self.close_pos_min = close_pos_min

    def process(
        self,
        patterns: list[PatternResult],
        df: pd.DataFrame,
    ) -> list[TradeSignal]:
        """
        Convert a list of PatternResults into actionable TradeSignals.

        Filters applied:
        - quality_score ≥ min_quality
        - volume_confirmed (from pattern detector)
        - close_pos ≥ close_pos_min on breakout bar
        """
        signals = []

        for p in patterns:
            if p.quality_score < self.min_quality:
                continue
            if not p.volume_confirmed:
                continue

            # Find breakout bar in df
            bo_idx = self._find_bar(df, p.breakout_date)
            if bo_idx is None:
                continue

            # close_pos check on breakout bar
            if df.iloc[bo_idx].get("close_pos", 1.0) < self.close_pos_min:
                continue

            # Entry price
            if self.entry_mode == "next_open" and bo_idx + 1 < len(df):
                entry = float(df.iloc[bo_idx + 1]["open"])
                entry_date = df.index[bo_idx + 1]
            else:
                entry = float(df.iloc[bo_idx]["close"])
                entry_date = p.breakout_date

            stop   = p.stop_price
            risk_per_share = max(entry - stop, entry * 0.01)  # floor at 1%
            risk_amount    = self.equity * self.risk_pct

            shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
            # Hard cap: never exceed 25% of capital by market value
            if entry > 0:
                shares = min(shares, int(self.equity * 0.25 / entry))

            # Measured-move target = entry + pattern height
            pattern_height = p.pattern_high - p.pattern_low
            target = entry + pattern_height

            signals.append(TradeSignal(
                symbol=p.symbol,
                pattern=p.pattern,
                entry_price=round(entry, 2),
                stop_loss=round(stop, 2),
                target=round(target, 2),
                shares=shares,
                risk_amount=round(shares * risk_per_share, 2),
                quality_score=p.quality_score,
                breakout_date=p.breakout_date,
                entry_mode=self.entry_mode,
                pattern_result=p,
            ))

        # Sort by quality descending
        signals.sort(key=lambda s: s.quality_score, reverse=True)
        return signals

    def _find_bar(self, df: pd.DataFrame, date: pd.Timestamp) -> int | None:
        try:
            loc = df.index.get_loc(date)
            return int(loc)
        except KeyError:
            idx = df.index.searchsorted(date)
            return idx if idx < len(df) else None
