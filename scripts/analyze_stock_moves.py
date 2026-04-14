#!/usr/bin/env python
"""
Analyze rally/down windows from an input event file and save technical snapshots.

Example input columns:
    ticker,start_date,end_date,move_type
    AAPL,2024-05-01,2024-06-15,rally

Accepted aliases:
    ticker/symbol/stock_name
    start_date + end_date, or a single time_range column
    move_type/direction/rally_or_down
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.stock_move_technicals import analyze_event_file, save_analysis_results


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze stock move windows and save a technical snapshot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/analyze_stock_moves.py --input data/events.csv
  python scripts/analyze_stock_moves.py --input data/events.csv --output-dir reports/stock_moves
  python scripts/analyze_stock_moves.py --input data/events.csv --base-name april_moves
        """,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a CSV, JSON, or Excel file with ticker/date range/move type columns.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(project_root / "reports" / "stock_moves"),
        help="Directory for saved CSV outputs.",
    )
    parser.add_argument(
        "--base-name",
        default="stock_move_technicals",
        help="Base filename prefix for the saved CSV outputs.",
    )
    args = parser.parse_args()

    summary_df, daily_df = analyze_event_file(args.input)
    summary_path, daily_path = save_analysis_results(
        summary_df,
        daily_df,
        output_dir=args.output_dir,
        base_name=args.base_name,
    )

    success_count = int((summary_df.get("status") == "ok").sum()) if not summary_df.empty else 0
    error_count = int((summary_df.get("status") == "error").sum()) if not summary_df.empty else 0

    print(f"Saved summary: {summary_path}")
    print(f"Saved daily detail: {daily_path}")
    print(f"Events analyzed: {success_count}")
    if error_count:
        print(f"Events with errors: {error_count}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
