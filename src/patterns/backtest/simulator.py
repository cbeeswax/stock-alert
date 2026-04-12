"""
src/patterns/backtest/simulator.py
=====================================
Event-driven daily bar trade simulator.

Shared across all 6 patterns. One trade model, consistent results.

Trade lifecycle
---------------
1. Entry at next_open after signal (or breakout_close)
2. Daily checks (in order of priority):
   a. Stop loss hit (low ≤ stop) → exit at stop (or open if gap-down)
   b. Partial profit at +PARTIAL_EXIT_PCT → sell PARTIAL_SIZE of shares
   c. Trail stop update (10-bar low or 2×ATR, tighter of the two post-partial)
   d. Max holding days → exit at close
3. End of data → exit at last close

Usage
-----
    sim = Simulator()
    trades = sim.run(signals, price_data)   # price_data: {symbol: df}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from src.patterns.signals.engine import TradeSignal
from src.patterns.config.shared import (
    PARTIAL_EXIT_PCT,
    PARTIAL_SIZE,
    TRAIL_LOOKBACK_BARS,
    TRAIL_ATR_MULT,
    MAX_HOLDING_DAYS,
    SLIPPAGE_BPS,
    COMMISSION_PER_SIDE,
)


# ── Trade record ──────────────────────────────────────────────────────────────

@dataclass
class TradeRecord:
    symbol:          str
    pattern:         str
    entry_date:      pd.Timestamp
    entry_price:     float
    exit_date:       pd.Timestamp | None   = None
    exit_price:      float | None          = None
    exit_reason:     str                   = ""
    shares_full:     int                   = 0
    shares_exited:   int                   = 0
    partial_done:    bool                  = False
    partial_price:   float | None          = None
    partial_date:    pd.Timestamp | None   = None
    stop_price:      float                 = 0.0
    quality_score:   float                 = 0.0
    holding_days:    int                   = 0
    pnl:             float                 = 0.0
    pnl_pct:         float                 = 0.0
    win:             bool                  = False

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ── Simulator ─────────────────────────────────────────────────────────────────

class Simulator:

    def __init__(
        self,
        partial_exit_pct:  float = PARTIAL_EXIT_PCT / 100,
        partial_size:      float = PARTIAL_SIZE,
        trail_lookback:    int   = TRAIL_LOOKBACK_BARS,
        trail_atr_mult:    float = TRAIL_ATR_MULT,
        max_holding_days:  int   = MAX_HOLDING_DAYS,
        slippage_bps:      float = SLIPPAGE_BPS,
        commission:        float = COMMISSION_PER_SIDE,
    ):
        self.partial_exit_pct = partial_exit_pct
        self.partial_size     = partial_size
        self.trail_lookback   = trail_lookback
        self.trail_atr_mult   = trail_atr_mult
        self.max_holding_days = max_holding_days
        self.slippage         = slippage_bps / 10_000
        self.commission       = commission

    # ── Public API ────────────────────────────────────────────────────────

    def run(
        self,
        signals: list[TradeSignal],
        price_data: dict[str, pd.DataFrame],
    ) -> list[TradeRecord]:
        """
        Simulate all signals. Returns a list of completed TradeRecords.

        price_data: {symbol: feature-enriched DataFrame with lowercase columns}
        """
        records = []
        for sig in signals:
            df = price_data.get(sig.symbol)
            if df is None or df.empty:
                continue
            record = self._simulate_one(sig, df)
            if record is not None:
                records.append(record)
        return records

    # ── Single trade ──────────────────────────────────────────────────────

    def _simulate_one(
        self,
        sig: TradeSignal,
        df: pd.DataFrame,
    ) -> TradeRecord | None:
        # Find entry bar
        entry_idx = self._find_idx(df, sig.breakout_date)
        if entry_idx is None:
            return None

        # Entry is next open after breakout bar
        if sig.entry_mode == "next_open":
            entry_idx += 1
        if entry_idx >= len(df):
            return None

        entry_row   = df.iloc[entry_idx]
        entry_price = float(entry_row["open"]) * (1 + self.slippage)
        entry_date  = df.index[entry_idx]

        stop   = sig.stop_loss
        shares = sig.shares
        if shares <= 0:
            return None

        rec = TradeRecord(
            symbol=sig.symbol,
            pattern=sig.pattern,
            entry_date=pd.Timestamp(entry_date),
            entry_price=entry_price,
            shares_full=shares,
            stop_price=stop,
            quality_score=sig.quality_score,
        )

        partial_shares = int(shares * self.partial_size)
        trail_stop     = stop

        # ── Daily bar loop ────────────────────────────────────────────────
        for day in range(1, self.max_holding_days + 1):
            bar_idx = entry_idx + day
            if bar_idx >= len(df):
                # End of data — exit at last close
                last = df.iloc[bar_idx - 1]
                exit_price = float(last["close"]) * (1 - self.slippage)
                return self._close_trade(rec, df.index[bar_idx - 1], exit_price, "EOD", day)

            row = df.iloc[bar_idx]
            o, h, l, c = (
                float(row["open"]), float(row["high"]),
                float(row["low"]),  float(row["close"])
            )
            atr = float(row.get("atr_14", 0))

            # a. Stop hit
            if l <= trail_stop:
                exit_price = min(o, trail_stop) * (1 - self.slippage)
                return self._close_trade(rec, df.index[bar_idx], exit_price, "STOP", day)

            # b. Partial profit
            if not rec.partial_done and h >= entry_price * (1 + self.partial_exit_pct):
                partial_price = entry_price * (1 + self.partial_exit_pct)
                rec.partial_done  = True
                rec.partial_price = round(partial_price, 2)
                rec.partial_date  = pd.Timestamp(df.index[bar_idx])
                # After partial, tighten trail
                shares = shares - partial_shares

            # c. Trail stop update
            if rec.partial_done:
                # Tighten trail after partial: 10-bar low or 2×ATR below close
                look_start = max(0, bar_idx - self.trail_lookback)
                ten_bar_low = float(df.iloc[look_start:bar_idx + 1]["low"].min())
                atr_trail   = c - self.trail_atr_mult * atr if atr > 0 else ten_bar_low
                new_trail   = max(ten_bar_low, atr_trail)
                trail_stop  = max(trail_stop, new_trail)

            # d. Max holding days
            if day == self.max_holding_days:
                exit_price = c * (1 - self.slippage)
                return self._close_trade(rec, df.index[bar_idx], exit_price, "MAX_DAYS", day)

        return None  # should not reach here

    # ── Helpers ───────────────────────────────────────────────────────────

    def _close_trade(
        self,
        rec: TradeRecord,
        exit_date,
        exit_price: float,
        reason: str,
        holding_days: int,
    ) -> TradeRecord:
        # Determine how many shares were actually remaining at final exit
        if rec.partial_done:
            partial_shares   = int(rec.shares_full * self.partial_size)
            remaining_shares = rec.shares_full - partial_shares
        else:
            partial_shares   = 0
            remaining_shares = rec.shares_full

        entry = rec.entry_price

        # Main (remaining) position P&L
        gross_pnl = (exit_price - entry) * remaining_shares
        gross_pnl -= self.commission * remaining_shares * 2

        # Partial leg P&L (already executed earlier)
        if rec.partial_price is not None and partial_shares > 0:
            gross_pnl += (rec.partial_price - entry) * partial_shares
            gross_pnl -= self.commission * partial_shares * 2

        rec.exit_date    = pd.Timestamp(exit_date)
        rec.exit_price   = round(exit_price, 2)
        rec.exit_reason  = reason
        rec.shares_exited = remaining_shares
        rec.holding_days  = holding_days
        rec.pnl          = round(gross_pnl, 2)
        rec.pnl_pct      = round((exit_price - entry) / (entry + 1e-9) * 100, 2)
        rec.win          = gross_pnl > 0
        return rec

    def _find_idx(self, df: pd.DataFrame, date: pd.Timestamp) -> int | None:
        try:
            loc = df.index.get_loc(date)
            return int(loc)
        except KeyError:
            idx = df.index.searchsorted(date)
            return idx if idx < len(df) else None
