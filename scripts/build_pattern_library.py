"""
Build the pattern library from 2022-2025 historical data.

Usage:
    python scripts/build_pattern_library.py

This analyzes every stock × every week in 2022-2025, computing 20+ daily indicators
and tracking which indicator combinations predicted positive next-week returns.
Takes ~10-20 minutes depending on number of tickers.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analysis.predictor.pattern_learner import build_pattern_library

DATA_DIR = os.environ.get(
    "HISTORICAL_DATA_DIR",
    r"C:\Users\pelac\Git\HistoricalData\historical",
)

if __name__ == "__main__":
    print("Building pattern library from 2022-2025 daily OHLCV data...")
    print(f"Data directory: {DATA_DIR}\n")
    library = build_pattern_library(
        data_dir=DATA_DIR,
        train_start="2022-01-01",
        train_end="2025-12-31",
        min_pattern_count=5,
        win_threshold=0.01,
        verbose=True,
    )
    print(f"\nDone. Library has {library['total_setups']:,} training setups.")
    print("\nTop 10 most predictive features (highest win-rate variance across buckets):")
    for feat, imp in list(library["feature_importance"].items())[:10]:
        print(f"  {feat:25s}  {imp:.4f}")

    print("\nBest performing patterns (min 20 samples, highest win rate):")
    patterns = library.get("patterns", {})
    top_patterns = sorted(
        [(k, v) for k, v in patterns.items() if v["count"] >= 20],
        key=lambda x: -x[1]["win_rate"]
    )[:5]
    for fp_key, p in top_patterns:
        print(f"  WR={p['win_rate']:.0%} | count={p['count']} | avg_pnl={p['avg_pnl']:+.1f}%")
        for condition in fp_key.split("|")[:5]:
            print(f"    {condition}")
        print()

    print("Worst performing patterns (highest failure rate):")
    bot_patterns = sorted(
        [(k, v) for k, v in patterns.items() if v["count"] >= 20],
        key=lambda x: x[1]["win_rate"]
    )[:5]
    for fp_key, p in bot_patterns:
        print(f"  WR={p['win_rate']:.0%} | count={p['count']} | avg_pnl={p['avg_pnl']:+.1f}%")
        for condition in fp_key.split("|")[:5]:
            print(f"    {condition}")
        print()
