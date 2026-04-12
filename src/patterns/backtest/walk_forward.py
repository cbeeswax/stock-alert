"""
src/patterns/backtest/walk_forward.py
=======================================
Walk-forward validation.

Splits history into rolling train/test windows.
Runs the detector + simulator on each window independently.
Compares in-sample vs out-of-sample performance to detect overfitting.

Default:  12-month train window, 3-month test window, step 3 months.

Usage
-----
    wf = WalkForward(train_months=12, test_months=3, step_months=3)
    results = wf.run(detector, price_data, start="2020-01-01", end="2024-12-31")
    wf.print_summary(results)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src.patterns.detectors.base import BasePattern
from src.patterns.features.builder import build_features
from src.patterns.features.swings import add_swings, get_pivot_list
from src.patterns.signals.engine import SignalEngine
from src.patterns.backtest.simulator import Simulator
from src.patterns.backtest.metrics import compute_metrics
from src.patterns.config.shared import SWING_K


@dataclass
class WFWindow:
    window_id:    int
    train_start:  pd.Timestamp
    train_end:    pd.Timestamp
    test_start:   pd.Timestamp
    test_end:     pd.Timestamp
    train_stats:  dict
    test_stats:   dict
    degradation:  float   # (train_expectancy - test_expectancy) / train_expectancy


class WalkForward:

    def __init__(
        self,
        train_months: int = 12,
        test_months:  int = 3,
        step_months:  int = 3,
        equity:       float = 100_000,
        min_quality:  float = 60.0,
        swing_k:      int   = SWING_K,
    ):
        self.train_months = train_months
        self.test_months  = test_months
        self.step_months  = step_months
        self.equity       = equity
        self.min_quality  = min_quality
        self.swing_k      = swing_k

    def run(
        self,
        detector: BasePattern,
        price_data: dict[str, pd.DataFrame],
        start: str = "2020-01-01",
        end:   str  = "2024-12-31",
    ) -> list[WFWindow]:
        """
        Run walk-forward over all symbols in price_data.

        Returns one WFWindow per time window.
        """
        start_dt = pd.Timestamp(start)
        end_dt   = pd.Timestamp(end)

        windows = self._build_windows(start_dt, end_dt)
        results = []

        for wid, (tr_s, tr_e, te_s, te_e) in enumerate(windows, 1):
            print(
                f"  Window {wid}: train {tr_s.date()}→{tr_e.date()} | "
                f"test {te_s.date()}→{te_e.date()}"
            )

            train_records = self._run_slice(detector, price_data, tr_s, tr_e)
            test_records  = self._run_slice(detector, price_data, te_s, te_e)

            train_stats = compute_metrics(train_records)
            test_stats  = compute_metrics(test_records)

            tr_exp = train_stats.get("expectancy_pct", 0)
            te_exp = test_stats.get("expectancy_pct", 0)
            degradation = (
                (tr_exp - te_exp) / abs(tr_exp)
                if tr_exp and abs(tr_exp) > 1e-6 else 0.0
            )

            results.append(WFWindow(
                window_id=wid,
                train_start=tr_s, train_end=tr_e,
                test_start=te_s,  test_end=te_e,
                train_stats=train_stats,
                test_stats=test_stats,
                degradation=round(degradation * 100, 1),
            ))

        return results

    def print_summary(self, windows: list[WFWindow]) -> None:
        print("\n" + "=" * 70)
        print(f"  Walk-Forward Results  ({len(windows)} windows)")
        print("=" * 70)
        print(f"  {'Win':>3} {'Train WR%':>9} {'Train E%':>9} {'Test WR%':>9} {'Test E%':>9} {'Degrad%':>9}")
        print("  " + "-" * 56)
        for w in windows:
            tr = w.train_stats
            te = w.test_stats
            print(
                f"  {w.window_id:>3} "
                f"{tr.get('win_rate',0):>9.1f} "
                f"{tr.get('expectancy_pct',0):>+9.2f} "
                f"{te.get('win_rate',0):>9.1f} "
                f"{te.get('expectancy_pct',0):>+9.2f} "
                f"{w.degradation:>+9.1f}%"
            )

        # Overall out-of-sample stats
        all_test_trades = sum(w.test_stats.get("trades", 0) for w in windows)
        avg_degrad = sum(w.degradation for w in windows) / len(windows) if windows else 0
        print("  " + "-" * 56)
        print(f"  Total OOS trades: {all_test_trades}")
        print(f"  Avg degradation:  {avg_degrad:+.1f}%")
        if avg_degrad < 20:
            print("  ✅ Low degradation — strategy generalises well")
        elif avg_degrad < 50:
            print("  ⚠️  Moderate degradation — consider parameter relaxation")
        else:
            print("  ❌ High degradation — likely overfit to in-sample data")
        print("=" * 70 + "\n")

    # ── Internal ──────────────────────────────────────────────────────────

    def _run_slice(
        self,
        detector: BasePattern,
        price_data: dict[str, pd.DataFrame],
        start: pd.Timestamp,
        end:   pd.Timestamp,
    ):
        from src.patterns.backtest.simulator import Simulator
        from src.patterns.signals.engine import SignalEngine

        engine = SignalEngine(equity=self.equity, min_quality=self.min_quality)
        sim    = Simulator()
        all_records = []

        for symbol, full_df in price_data.items():
            # Include a 3-month lookback buffer so rolling features and pivots
            # formed just before `start` are available — but we only use data
            # up to `end` (no future leakage into this window).
            buf_start = start - pd.DateOffset(months=3)
            sliced = full_df.loc[
                (full_df.index >= buf_start) & (full_df.index <= end)
            ].copy()
            if len(sliced) < 60:
                continue

            # add_swings already masks the last k bars, so pivots near `end`
            # that would require future bars to confirm are excluded.
            # Together with the hard `end` cutoff above, this guarantees
            # no look-ahead: every detected pattern only uses data ≤ end.
            df = build_features(sliced)
            df = add_swings(df, k=self.swing_k)
            pivots = get_pivot_list(df)

            detector.symbol = symbol
            patterns = detector.detect(df, pivots)
            # Keep only patterns whose breakout falls within the window
            # (the buffer period patterns are excluded)
            patterns = [p for p in patterns if start <= p.breakout_date <= end]

            signals = engine.process(patterns, df)
            records = sim.run(signals, {symbol: df})
            all_records.extend(records)

        return all_records

    def _build_windows(
        self,
        start: pd.Timestamp,
        end:   pd.Timestamp,
    ) -> list[tuple]:
        windows = []
        cursor = start
        while True:
            tr_s = cursor
            tr_e = tr_s + pd.DateOffset(months=self.train_months) - pd.DateOffset(days=1)
            te_s = tr_e + pd.DateOffset(days=1)
            te_e = te_s + pd.DateOffset(months=self.test_months) - pd.DateOffset(days=1)
            if te_e > end:
                break
            windows.append((tr_s, tr_e, te_s, te_e))
            cursor += pd.DateOffset(months=self.step_months)
        return windows
