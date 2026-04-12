"""
src/strategies/pattern_scanner.py
====================================
Live scanner integration — wraps all 6 pattern detectors as a single
strategy compatible with the existing stock-alert scanner/registry.

Plugs into main.py exactly like any other strategy:
  scan(ticker, df, as_of_date) → signal dict or None

The scanner runs this once per ticker at EOD. If any pattern fires on
the most recent bar, it returns the highest-quality signal.

Exit conditions use a simple structural stop + ATR trail —
the same logic as other position strategies.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from src.strategies.base import BaseStrategy
from src.patterns.features.builder import build_features
from src.patterns.features.swings import add_swings, get_pivot_list
from src.patterns.signals.engine import SignalEngine
from src.patterns.config.shared import SWING_K, MAX_HOLDING_DAYS, TRAIL_ATR_MULT


# Lazy-import all 6 detectors (avoids circular import at module level)
def _all_detectors():
    from src.patterns.detectors.cup_and_handle      import CupAndHandle
    from src.patterns.detectors.high_tight_flag     import HighTightFlag
    from src.patterns.detectors.flat_base           import FlatBase
    from src.patterns.detectors.ascending_triangle  import AscendingTriangle
    from src.patterns.detectors.double_bottom       import DoubleBottom
    from src.patterns.detectors.trendline_breakout  import TrendlineBreakout
    return [
        CupAndHandle,
        HighTightFlag,
        FlatBase,
        AscendingTriangle,
        DoubleBottom,
        TrendlineBreakout,
    ]


class PatternScanner(BaseStrategy):
    """
    Live scanner for all 6 classic chart patterns.

    Returns at most one signal per ticker per day — the highest-scoring
    pattern that fires on the current bar.
    """

    name        = "Pattern_Scanner"
    description = "Cup&Handle / HTF / Flat Base / Ascending Triangle / Double Bottom / Trendline BO"

    def __init__(
        self,
        equity: float = 100_000,
        min_quality: float = 60.0,
        swing_k: int = SWING_K,
    ):
        super().__init__()
        self.equity      = equity
        self.min_quality = min_quality
        self.swing_k     = swing_k
        self._engine     = SignalEngine(equity=equity, min_quality=min_quality)
        self._detectors  = [D() for D in _all_detectors()]

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        as_of_date: pd.Timestamp = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Scan one ticker. Returns the best signal dict or None.
        """
        if len(df) < 60:
            return None

        try:
            df_f = build_features(df)
            df_f = add_swings(df_f, k=self.swing_k)
            pivots = get_pivot_list(df_f)
        except Exception:
            return None

        today_idx = len(df_f) - 1
        today     = df_f.index[today_idx]

        best = None
        for det in self._detectors:
            det.symbol = ticker
            try:
                patterns = det.detect(df_f, pivots)
            except Exception:
                continue

            # Only patterns whose breakout is today (current bar)
            todays = [p for p in patterns if p.breakout_date == today]
            if not todays:
                continue

            signals = self._engine.process(todays, df_f)
            for sig in signals:
                if best is None or sig.quality_score > best.quality_score:
                    best = sig

        if best is None:
            return None

        # Format as standard signal dict (matches existing pre_buy_check expectations)
        return {
            "Ticker":      ticker,
            "Strategy":    "Pattern_Scanner",
            "PatternName": best.pattern,           # e.g. "CupAndHandle" — for reporting
            "Close":       float(df_f.iloc[-1]["close"]),
            "Entry":       best.entry_price,
            "StopLoss":    best.stop_loss,
            "Target":      best.target,
            "Score":       best.quality_score,
            "Volume":      float(df_f.iloc[-1]["volume"]),
            "Date":        str(today.date()),
            "Priority":    max(1, int(100 - best.quality_score)),
            "MaxDays":     MAX_HOLDING_DAYS,
            "PatternMeta": best.pattern_result.meta_json,
        }

    def get_exit_conditions(
        self,
        position: Dict[str, Any],
        df: pd.DataFrame,
        current_date: pd.Timestamp,
    ) -> Optional[Dict[str, Any]]:
        """
        Exit conditions:
        - Hard stop: close ≤ stop_loss
        - ATR trail: stop ratchets up with 2×ATR below recent close
        - Max holding days: 40
        """
        if df.empty:
            return None

        try:
            df_f = build_features(df)
        except Exception:
            df_f = df

        entry_date  = pd.Timestamp(position.get("entry_date", current_date))
        entry_price = float(position.get("entry_price", 0))
        stop_loss   = float(position.get("stop_loss", 0))
        holding_days = (current_date - entry_date).days

        current_close = float(df_f.iloc[-1]["close"])
        atr           = float(df_f.iloc[-1].get("atr_14", 0))

        # Max holding days
        if holding_days >= MAX_HOLDING_DAYS:
            return {"reason": "MAX_DAYS", "exit_price": current_close}

        # Hard stop
        if current_close <= stop_loss:
            return {"reason": "STOP_LOSS", "exit_price": min(current_close, stop_loss)}

        # Tighten stop via ATR trail (ratchet only up)
        if atr > 0:
            atr_trail = current_close - TRAIL_ATR_MULT * atr
            if atr_trail > stop_loss:
                position["stop_loss"] = round(atr_trail, 2)

        return None
