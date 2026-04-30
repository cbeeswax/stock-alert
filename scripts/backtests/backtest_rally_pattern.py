#!/usr/bin/env python
"""
Walk-forward backtest runner for RallyPatternStrategy.

This runner uses cached daily OHLCV history from data/historical, computes
features causally, warms up from the chosen start date, and blocks new entries
until the configured trade start date.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.rally_pattern_strategy import RallyPatternStrategy
from src.data.market import get_historical_data


DEFAULT_START = "2022-01-01"
DEFAULT_TRADE_START = "2022-02-01"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walk-forward backtest RallyPatternStrategy")
    parser.add_argument("--start", default=DEFAULT_START, help="Warmup start date YYYY-MM-DD")
    parser.add_argument(
        "--trade-start",
        default=DEFAULT_TRADE_START,
        help="First date allowed for new entries YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        default=pd.Timestamp.today().strftime("%Y-%m-%d"),
        help="Backtest end date YYYY-MM-DD",
    )
    parser.add_argument("--capital", type=float, default=100_000.0, help="Starting capital")
    parser.add_argument(
        "--max-stock-allocation",
        type=float,
        default=50_000.0,
        help="Maximum fresh capital allocated to any one stock for entries and add-ons.",
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=0,
        help="Maximum concurrent positions. Use 0 for no cap.",
    )
    parser.add_argument("--tickers", help="Comma-separated ticker list. Default: S&P 500 constituents.")
    parser.add_argument(
        "--strict-entry",
        action="store_true",
        help="Enable stricter optional entry rules.",
    )
    parser.add_argument("--atr-stop", action="store_true", help="Enable optional 2x ATR stop.")
    parser.add_argument("--time-stop", action="store_true", help="Enable optional 15-day time stop.")
    parser.add_argument(
        "--allocation-mode",
        choices=["baseline", "equal_weight_cap", "setup_tiered_cap", "hybrid_risk_capped"],
        default="baseline",
        help="Portfolio allocation mode for new entries.",
    )
    parser.add_argument(
        "--risk-sized",
        action="store_true",
        help="Backward-compatible alias for --allocation-mode hybrid_risk_capped.",
    )
    parser.add_argument(
        "--leader-reentry",
        action="store_true",
        help="Enable the super-leader reentry path.",
    )
    parser.add_argument(
        "--late-stage-leader",
        action="store_true",
        help="Enable the late-stage leader continuation path.",
    )
    parser.add_argument(
        "--aggressive-early-failure",
        action="store_true",
        help="Enable faster failed-followthrough exits for aggressive rally entries.",
    )
    parser.add_argument(
        "--bb-micro-failure",
        action="store_true",
        help="Enable short-support break + failed reclaim + Bollinger weakness exits for aggressive rally entries.",
    )
    parser.add_argument(
        "--medium-confirm-failure",
        action="store_true",
        help="Enable short-support break + failed reclaim + one extra weakness confirmation exits for aggressive rally entries.",
    )
    parser.add_argument(
        "--aggressive-starter-sizing",
        action="store_true",
        help="Start power_breakout and expansion_leader with smaller size, then allow top-ups after confirmation.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "reports" / "rally_pattern"),
        help="Directory for saved CSV outputs.",
    )
    parser.add_argument(
        "--base-name",
        default="rally_pattern_walkforward",
        help="Base filename prefix for saved outputs.",
    )
    return parser.parse_args()


def load_tickers(tickers_arg: str | None) -> list[str]:
    if tickers_arg:
        tickers = [ticker.strip().upper() for ticker in tickers_arg.split(",") if ticker.strip()]
    else:
        sp500_file = ROOT / "data" / "sp500_constituents.csv"
        if not sp500_file.exists():
            raise FileNotFoundError("data/sp500_constituents.csv not found. Pass --tickers explicitly.")
        tickers = pd.read_csv(sp500_file)["Symbol"].dropna().astype(str).str.upper().tolist()

    for benchmark in ("SPY", "QQQ"):
        if benchmark not in tickers:
            tickers.append(benchmark)
    return tickers


def load_history_frame(tickers: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        df = get_historical_data(ticker)
        if df.empty:
            continue
        local = df.copy()
        local.index = pd.to_datetime(local.index, errors="coerce")
        local = local[(local.index >= start) & (local.index <= end)].copy()
        if local.empty:
            continue
        local = local.reset_index().rename(columns={"index": "Date"})
        local["ticker"] = ticker
        rename_map = {}
        for column in local.columns:
            lower = str(column).strip().lower()
            if lower in {"open", "high", "low", "close", "volume"}:
                rename_map[column] = lower
        local = local.rename(columns=rename_map)
        needed = {"Date", "ticker", "open", "high", "low", "close", "volume"}
        missing = needed - set(local.columns)
        if missing:
            continue
        frames.append(local[["Date", "ticker", "open", "high", "low", "close", "volume"]])

    if not frames:
        raise ValueError("No historical data found for the requested ticker universe.")
    return pd.concat(frames, ignore_index=True)


def save_results(results: dict[str, pd.DataFrame], output_dir: Path, base_name: str) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "trades": output_dir / f"{base_name}_trades.csv",
        "holdings": output_dir / f"{base_name}_holdings.csv",
        "equity": output_dir / f"{base_name}_equity.csv",
        "scored": output_dir / f"{base_name}_scored.csv",
    }
    results["trades"].to_csv(paths["trades"], index=False)
    results["daily_holdings"].to_csv(paths["holdings"], index=False)
    results["equity_curve"].to_csv(paths["equity"], index=False)
    results["scored_data"].to_csv(paths["scored"], index=False)
    return paths


def print_summary(results: dict[str, pd.DataFrame], paths: dict[str, Path], initial_capital: float) -> None:
    trades = results["trades"]
    equity = results["equity_curve"]
    final_equity = float(equity["total_equity"].iloc[-1]) if not equity.empty else 0.0
    total_return = ((final_equity / initial_capital) - 1.0) if final_equity and initial_capital else 0.0

    print(f"Trades: {len(trades)}")
    print(f"Final equity: {final_equity:,.2f}")
    print(f"Total return: {total_return:.2%}")
    for label, path in paths.items():
        print(f"Saved {label}: {path}")


def main() -> int:
    args = parse_args()
    start = pd.Timestamp(args.start)
    trade_start = pd.Timestamp(args.trade_start)
    end = pd.Timestamp(args.end)

    if trade_start < start:
        raise ValueError("--trade-start must be on or after --start.")
    if end < trade_start:
        raise ValueError("--end must be on or after --trade-start.")

    tickers = load_tickers(args.tickers)
    raw_df = load_history_frame(tickers, start=start, end=end)

    strategy = RallyPatternStrategy(
        strict_entry=args.strict_entry,
        use_atr_stop=args.atr_stop,
        use_time_stop=args.time_stop,
        allocation_mode=("hybrid_risk_capped" if args.risk_sized else args.allocation_mode),
        max_allocation_per_stock=args.max_stock_allocation,
        enable_risk_position_sizing=args.risk_sized,
        enable_leader_reentry=args.leader_reentry,
        enable_late_stage_leaders=args.late_stage_leader,
        enable_aggressive_early_failure=args.aggressive_early_failure,
        enable_bb_micro_failure=args.bb_micro_failure,
        enable_medium_confirm_failure=args.medium_confirm_failure,
        enable_aggressive_starter_sizing=args.aggressive_starter_sizing,
    )
    results = strategy.backtest(
        raw_df,
        max_positions=args.max_positions,
        initial_capital=args.capital,
        start_date=start,
        end_date=end,
        trade_start_date=trade_start,
    )

    paths = save_results(results, Path(args.output_dir), args.base_name)
    print_summary(results, paths, args.capital)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
