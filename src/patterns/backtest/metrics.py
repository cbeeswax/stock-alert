"""
src/patterns/backtest/metrics.py
==================================
Backtest metrics — win rate, profit factor, expectancy, Sharpe, drawdown.

Usage
-----
    from src.patterns.backtest.metrics import compute_metrics, print_summary

    stats = compute_metrics(trade_records)
    print_summary(stats)
    per_pattern = compute_metrics(trade_records, group_by="pattern")
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Literal

import numpy as np
import pandas as pd

from src.patterns.backtest.simulator import TradeRecord


# ── Core metrics ─────────────────────────────────────────────────────────────

def compute_metrics(
    records: list[TradeRecord],
    group_by: Literal["all", "pattern", "symbol"] = "all",
) -> dict:
    """
    Compute performance metrics.

    Returns a dict (group_by='all') or dict-of-dicts (group_by='pattern'/'symbol').
    """
    if not records:
        return {}

    if group_by == "all":
        return _metrics_for(records)

    groups: dict[str, list[TradeRecord]] = defaultdict(list)
    for r in records:
        key = r.pattern if group_by == "pattern" else r.symbol
        groups[key].append(r)

    return {k: _metrics_for(v) for k, v in sorted(groups.items())}


def _metrics_for(records: list[TradeRecord]) -> dict:
    if not records:
        return {}

    pnls      = [r.pnl for r in records]
    pnl_pcts  = [r.pnl_pct for r in records]
    wins      = [r for r in records if r.win]
    losses    = [r for r in records if not r.win]
    hold_days = [r.holding_days for r in records]

    total       = len(records)
    win_count   = len(wins)
    loss_count  = len(losses)
    win_rate    = win_count / total if total else 0

    avg_win     = np.mean([r.pnl_pct for r in wins])   if wins   else 0.0
    avg_loss    = np.mean([r.pnl_pct for r in losses]) if losses else 0.0

    gross_profit = sum(r.pnl for r in wins)
    gross_loss   = abs(sum(r.pnl for r in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    expectancy  = win_rate * avg_win + (1 - win_rate) * avg_loss  # % per trade

    # Sharpe (annualised, daily returns proxy)
    if len(pnl_pcts) > 1:
        mean_r  = np.mean(pnl_pcts)
        std_r   = np.std(pnl_pcts, ddof=1)
        sharpe  = (mean_r / std_r * math.sqrt(252 / np.mean(hold_days))) if std_r > 0 else 0.0
    else:
        sharpe  = 0.0

    # Max drawdown on cumulative PnL curve
    cum_pnl    = np.cumsum(pnls)
    peak       = np.maximum.accumulate(cum_pnl)
    drawdown   = cum_pnl - peak
    max_dd     = float(drawdown.min())

    return {
        "trades":          total,
        "wins":            win_count,
        "losses":          loss_count,
        "win_rate":        round(win_rate * 100, 1),
        "avg_win_pct":     round(float(avg_win), 2),
        "avg_loss_pct":    round(float(avg_loss), 2),
        "profit_factor":   round(profit_factor, 2),
        "expectancy_pct":  round(float(expectancy), 2),
        "sharpe":          round(sharpe, 2),
        "max_drawdown":    round(max_dd, 2),
        "total_pnl":       round(sum(pnls), 2),
        "avg_hold_days":   round(float(np.mean(hold_days)), 1),
        "exit_reasons":    _count(r.exit_reason for r in records),
    }


def _count(iterable) -> dict:
    d: dict = {}
    for v in iterable:
        d[v] = d.get(v, 0) + 1
    return d


# ── Pretty print ──────────────────────────────────────────────────────────────

def print_summary(stats: dict, title: str = "Backtest Results") -> None:
    """Print a clean summary table to stdout."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

    if not stats:
        print("  No trades to report.")
        return

    # Top-level dict or grouped dict?
    if "trades" in stats:
        _print_block(stats)
    else:
        for pattern, s in stats.items():
            print(f"\n  ── {pattern} ──")
            _print_block(s, indent=4)

    print("=" * 60 + "\n")


def _print_block(s: dict, indent: int = 2) -> None:
    pad = " " * indent
    print(f"{pad}Trades:         {s.get('trades', 0):>6}")
    print(f"{pad}Win rate:       {s.get('win_rate', 0):>5.1f}%")
    print(f"{pad}Avg win:        {s.get('avg_win_pct', 0):>+6.2f}%")
    print(f"{pad}Avg loss:       {s.get('avg_loss_pct', 0):>+6.2f}%")
    print(f"{pad}Profit factor:  {s.get('profit_factor', 0):>6.2f}")
    print(f"{pad}Expectancy:     {s.get('expectancy_pct', 0):>+6.2f}% / trade")
    print(f"{pad}Sharpe:         {s.get('sharpe', 0):>6.2f}")
    print(f"{pad}Max drawdown:   ${s.get('max_drawdown', 0):>,.0f}")
    print(f"{pad}Total PnL:      ${s.get('total_pnl', 0):>,.0f}")
    print(f"{pad}Avg hold days:  {s.get('avg_hold_days', 0):>5.1f}")
    reasons = s.get("exit_reasons", {})
    if reasons:
        print(f"{pad}Exit reasons:   {reasons}")
