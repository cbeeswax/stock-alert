#!/usr/bin/env python
"""
Backtest Pattern Strategies
=============================
CLI to run any of the 6 pattern detectors over S&P 500 history.

Usage
-----
    # All patterns, full history
    python scripts/backtest_patterns.py

    # Single pattern
    python scripts/backtest_patterns.py --pattern CupAndHandle

    # Date range + walk-forward validation
    python scripts/backtest_patterns.py --start 2020-01-01 --end 2024-12-31 --walkforward

    # Specific tickers
    python scripts/backtest_patterns.py --tickers AAPL,MSFT,NVDA

    # Minimum quality filter
    python scripts/backtest_patterns.py --min-quality 70
"""

import sys
import argparse
import time
from pathlib import Path

import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.market import get_historical_data
from src.patterns.features.builder import build_features
from src.patterns.features.swings import add_swings, get_pivot_list
from src.patterns.signals.engine import SignalEngine
from src.patterns.backtest.simulator import Simulator
from src.patterns.backtest.metrics import compute_metrics, print_summary
from src.patterns.config.shared import SWING_K

# ── Pattern registry ──────────────────────────────────────────────────────────

def get_detectors(names: list[str] | None = None):
    from src.patterns.detectors.cup_and_handle      import CupAndHandle
    from src.patterns.detectors.high_tight_flag     import HighTightFlag
    from src.patterns.detectors.flat_base           import FlatBase
    from src.patterns.detectors.ascending_triangle  import AscendingTriangle
    from src.patterns.detectors.double_bottom       import DoubleBottom
    from src.patterns.detectors.trendline_breakout  import TrendlineBreakout

    all_detectors = {
        "CupAndHandle":       CupAndHandle,
        "HighTightFlag":      HighTightFlag,
        "FlatBase":           FlatBase,
        "AscendingTriangle":  AscendingTriangle,
        "DoubleBottom":       DoubleBottom,
        "TrendlineBreakout":  TrendlineBreakout,
    }
    if names:
        return {k: v for k, v in all_detectors.items() if k in names}
    return all_detectors


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backtest pattern detection strategies")
    parser.add_argument("--pattern",     help="Pattern name(s), comma-separated. Default: all 6")
    parser.add_argument("--tickers",     help="Comma-separated tickers. Default: S&P 500")
    parser.add_argument("--start",       default="2022-01-01", help="Backtest start date")
    parser.add_argument("--end",         default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    parser.add_argument("--min-quality", type=float, default=60.0, help="Min quality score filter")
    parser.add_argument("--equity",      type=float, default=100_000)
    parser.add_argument("--walkforward", action="store_true", help="Run walk-forward validation")
    parser.add_argument("--save",        action="store_true", help="Save trade log to reports/patterns/")
    args = parser.parse_args()

    start_dt = pd.Timestamp(args.start)
    end_dt   = pd.Timestamp(args.end)

    # ── Load tickers ──────────────────────────────────────────────────────
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    else:
        sp500_file = project_root / "data" / "sp500_constituents.csv"
        if not sp500_file.exists():
            print("⚠️  sp500_constituents.csv not found — using a small test set")
            tickers = ["AAPL", "MSFT", "NVDA", "META", "GOOGL",
                       "AMZN", "TSLA", "AMD", "CRM", "NFLX"]
        else:
            tickers = pd.read_csv(sp500_file)["Symbol"].tolist()

    # ── Load price data ───────────────────────────────────────────────────
    print(f"\n📥 Loading data for {len(tickers)} tickers…")
    price_data: dict[str, pd.DataFrame] = {}
    for i, ticker in enumerate(tickers, 1):
        try:
            df = get_historical_data(ticker)
            if not df.empty:
                price_data[ticker] = df
        except Exception:
            pass
        if i % 100 == 0:
            print(f"   [{i}/{len(tickers)}] loaded")

    print(f"   ✅ {len(price_data)} symbols loaded\n")

    # ── Select patterns ───────────────────────────────────────────────────
    pattern_names = [p.strip() for p in args.pattern.split(",")] if args.pattern else None
    detectors = get_detectors(pattern_names)
    print(f"🔍 Running {len(detectors)} pattern(s): {', '.join(detectors)}\n")
    print(f"📅 Range: {args.start} → {args.end}")
    print(f"⚙️  Min quality: {args.min_quality}  |  Equity: ${args.equity:,.0f}\n")

    # ── Build features once per symbol ────────────────────────────────────
    print("⚙️  Building features…")
    enriched: dict[str, pd.DataFrame] = {}
    for symbol, df in price_data.items():
        try:
            df_f = build_features(df)
            df_f = add_swings(df_f, k=SWING_K)
            enriched[symbol] = df_f
        except Exception as e:
            print(f"   ⚠️  {symbol}: {e}")
    print(f"   ✅ {len(enriched)} symbols enriched\n")

    engine = SignalEngine(equity=args.equity, min_quality=args.min_quality)
    sim    = Simulator()
    all_records = []

    # ── Run each detector ─────────────────────────────────────────────────
    for det_name, DetClass in detectors.items():
        print(f"🔎 {det_name}…")
        t0 = time.time()
        pattern_records = []
        symbols = list(enriched.keys())
        total_symbols = len(symbols)

        for sym_idx, symbol in enumerate(symbols, 1):
            df = enriched[symbol]
            sliced = df.loc[(df.index >= start_dt) & (df.index <= end_dt)]
            if len(sliced) < 60:
                continue

            pivots = get_pivot_list(sliced)
            det = DetClass(symbol=symbol)
            try:
                patterns = det.detect(sliced, pivots)
            except Exception as e:
                print(f"   ⚠️  {symbol}: {e}")
                continue

            signals = engine.process(patterns, sliced)
            records = sim.run(signals, {symbol: sliced})
            pattern_records.extend(records)

            if sym_idx % 50 == 0 or sym_idx == total_symbols:
                elapsed = time.time() - t0
                print(
                    f"   [{sym_idx:>4}/{total_symbols}] "
                    f"{elapsed:>5.1f}s  {len(pattern_records)} signals so far"
                )

        elapsed = time.time() - t0
        stats = compute_metrics(pattern_records)
        print_summary(stats, title=f"{det_name}  ({len(pattern_records)} trades, {elapsed:.1f}s)")
        all_records.extend(pattern_records)

    # ── Combined summary ──────────────────────────────────────────────────
    if len(detectors) > 1:
        print_summary(
            compute_metrics(all_records, group_by="pattern"),
            title="All Patterns — by Pattern",
        )

    # ── Walk-forward ──────────────────────────────────────────────────────
    if args.walkforward and len(detectors) == 1:
        det_name, DetClass = next(iter(detectors.items()))
        print(f"\n🔄 Walk-forward validation: {det_name}")
        from src.patterns.backtest.walk_forward import WalkForward
        wf = WalkForward(equity=args.equity, min_quality=args.min_quality)
        wf_results = wf.run(DetClass(), enriched, start=args.start, end=args.end)
        wf.print_summary(wf_results)

    # ── Save trade log ────────────────────────────────────────────────────
    if args.save and all_records:
        out_dir = project_root / "reports" / "patterns"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts  = pd.Timestamp.today().strftime("%Y%m%d_%H%M")
        out = out_dir / f"trades_{ts}.csv"
        pd.DataFrame([r.to_dict() for r in all_records]).to_csv(out, index=False)
        print(f"\n💾 Trade log saved → {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
