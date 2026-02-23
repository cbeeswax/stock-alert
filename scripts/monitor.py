#!/usr/bin/env python
"""
Position Monitor Entry Point

Monitors open trading positions for:
- Exit signals (stop loss, time-based exits)
- Partial profit opportunities
- Pyramid/add-on opportunities
- Risk management warnings

Usage:
    python scripts/monitor.py                          # Monitor all positions
    python scripts/monitor.py --ticker AAPL            # Monitor specific position
    python scripts/monitor.py --positions-file custom.json  # Use custom positions file
    python scripts/monitor.py --summary                # Show summary only
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.position_management.tracker import PositionTracker
from src.position_management.monitor import monitor_positions
from src.config.settings import POSITION_MAX_TOTAL, POSITION_MAX_PER_STRATEGY


def display_header():
    """Display monitor header."""
    print("\n" + "=" * 80)
    print("📊 POSITION MONITOR")
    print("=" * 80)
    print(f"📅 Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")


def display_position_summary(tracker: PositionTracker):
    """Display summary of all positions."""
    count = tracker.get_position_count()
    print(f"📊 Open Positions: {count}/{POSITION_MAX_TOTAL}\n")
    
    if count == 0:
        print("   ✅ No open positions\n")
        return
    
    print(tracker)


def get_strategy_counts(tracker: PositionTracker) -> dict:
    """Get position count by strategy."""
    counts = {}
    for ticker, pos in tracker.get_all_positions().items():
        strategy = pos.get('strategy', 'Unknown')
        counts[strategy] = counts.get(strategy, 0) + 1
    return counts


def display_strategy_allocation(tracker: PositionTracker):
    """Display positions by strategy."""
    counts = get_strategy_counts(tracker)
    
    if not counts:
        return
    
    print("\n📈 Allocation by Strategy:")
    for strategy in sorted(counts.keys()):
        current = counts[strategy]
        max_allowed = POSITION_MAX_PER_STRATEGY.get(strategy, 5)
        pct = (current / max_allowed * 100) if max_allowed > 0 else 0
        
        # Progress bar
        bar_length = 20
        filled = int(bar_length * current / max_allowed) if max_allowed > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)
        
        print(f"   {strategy:<35} {current:>2}/{max_allowed:<2} [{bar}] {pct:>5.1f}%")


def display_action_signals(action_signals: dict):
    """Display action signals from monitoring."""
    total_actions = (
        len(action_signals['exits']) +
        len(action_signals['partials']) +
        len(action_signals['pyramids'])
    )
    
    if total_actions == 0:
        print("\n✅ All positions healthy - no action signals")
        return
    
    print(f"\n⚠️  {total_actions} ACTION(S) DETECTED:\n")
    
    # Exits (highest priority)
    if action_signals['exits']:
        print(f"🚨 EXITS ({len(action_signals['exits'])}):")
        for exit_sig in action_signals['exits']:
            ticker = exit_sig['ticker']
            reason = exit_sig['reason']
            action = exit_sig['action']
            print(f"   {ticker}: {reason}")
            print(f"   → {action}\n")
    
    # Partial profits
    if action_signals['partials']:
        print(f"💰 PARTIAL PROFITS ({len(action_signals['partials'])}):")
        for partial in action_signals['partials']:
            ticker = partial['ticker']
            reason = partial['reason']
            action = partial['action']
            print(f"   {ticker}: {reason}")
            print(f"   → {action}\n")
    
    # Pyramid opportunities
    if action_signals['pyramids']:
        print(f"📈 PYRAMID OPPORTUNITIES ({len(action_signals['pyramids'])}):")
        for pyramid in action_signals['pyramids']:
            ticker = pyramid['ticker']
            reason = pyramid['reason']
            action = pyramid['action']
            print(f"   {ticker}: {reason}")
            print(f"   → {action}\n")
    
    # Warnings
    if action_signals['warnings']:
        print(f"\n⚠️  Warnings ({len(action_signals['warnings'])}):")
        for warning in action_signals['warnings']:
            message = warning.get('message', warning.get('ticker', 'Unknown'))
            print(f"   {message}")


def display_position_details(
    ticker: str,
    tracker: PositionTracker,
    action_signals: dict
):
    """Display details for a specific position."""
    position = tracker.get_position(ticker)
    
    if not position:
        print(f"❌ Position not found: {ticker}")
        return
    
    print(f"\n📍 Position Details: {ticker}")
    print("=" * 80)
    print(f"   Entry Price: ${position.get('entry_price', 'N/A'):.2f}")
    print(f"   Entry Date: {position.get('entry_date', 'N/A')}")
    print(f"   Strategy: {position.get('strategy', 'N/A')}")
    print(f"   Stop Loss: ${position.get('stop_loss', 'N/A'):.2f}")
    print(f"   Target: ${position.get('target', 'N/A'):.2f}")
    print(f"   Max Days: {position.get('max_days', 'N/A')}")
    print(f"   Status: {position.get('status', 'Open')}")
    
    # Check for action signals on this position
    ticker_signals = []
    for signal_type in ['exits', 'partials', 'pyramids']:
        for signal in action_signals.get(signal_type, []):
            if signal.get('ticker') == ticker:
                ticker_signals.append((signal_type.rstrip('s'), signal))
    
    if ticker_signals:
        print(f"\n⚠️  Action Signals:")
        for signal_type, signal in ticker_signals:
            print(f"   {signal_type.upper()}: {signal.get('reason', 'N/A')}")
            print(f"   → {signal.get('action', 'N/A')}")


def main():
    """Main entry point for position monitor."""
    parser = argparse.ArgumentParser(
        description="Position Trading Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/monitor.py                          # Monitor all positions
  python scripts/monitor.py --ticker AAPL            # Monitor specific position
  python scripts/monitor.py --summary                # Summary only
  python scripts/monitor.py --positions-file data/positions.json  # Custom file
        """
    )
    
    parser.add_argument(
        "--positions-file",
        default="data/open_positions.json",
        help="Path to positions file (default: data/open_positions.json)"
    )
    parser.add_argument(
        "--ticker",
        help="Monitor specific ticker"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary only (no detailed signals)"
    )
    
    args = parser.parse_args()
    
    # Display header
    display_header()
    
    # Initialize tracker
    try:
        tracker = PositionTracker(mode="live", file=args.positions_file)
    except Exception as e:
        print(f"❌ Error loading positions: {e}")
        return 1
    
    # Display positions
    display_position_summary(tracker)
    
    # If no positions, exit
    if tracker.get_position_count() == 0:
        print("=" * 80)
        print("✨ Monitor Complete")
        print("=" * 80)
        return 0
    
    # Get action signals
    action_signals = monitor_positions(tracker)
    
    # Display strategy allocation
    display_strategy_allocation(tracker)
    
    # Display action signals
    if not args.summary:
        display_action_signals(action_signals)
    
    # If specific ticker requested, show details
    if args.ticker:
        display_position_details(args.ticker, tracker, action_signals)
    
    print("\n" + "=" * 80)
    print("✨ Monitor Complete")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
