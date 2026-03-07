#!/usr/bin/env python
"""
Position Management CLI

Interactive tool for managing trading positions:
- View all open positions
- Add new positions manually
- Close positions with profit/loss
- Update position details
- Export position history

Usage:
    python scripts/manage_positions.py                 # Interactive menu
    python scripts/manage_positions.py --list          # List all positions
    python scripts/manage_positions.py --add AAPL      # Add new position
    python scripts/manage_positions.py --close AAPL    # Close position
    python scripts/manage_positions.py --export csv    # Export to CSV
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.position_management.tracker import PositionTracker


def display_menu():
    """Display interactive menu."""
    print("\n" + "=" * 80)
    print("📊 POSITION MANAGEMENT MENU")
    print("=" * 80)
    print("""
1. View all positions
2. Add new position
3. Close position
4. Update position
5. Export positions
6. Exit
    """)


def prompt_yes_no(prompt: str) -> bool:
    """Prompt for yes/no response."""
    while True:
        response = input(f"{prompt} (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Invalid response. Please enter 'y' or 'n'.")


def prompt_float(prompt: str, min_val: float = None) -> float:
    """Prompt for float input."""
    while True:
        try:
            value = float(input(f"{prompt}: ").strip())
            if min_val is not None and value < min_val:
                print(f"Value must be >= {min_val}")
                continue
            return value
        except ValueError:
            print("Invalid input. Please enter a number.")


def prompt_int(prompt: str, min_val: int = None) -> int:
    """Prompt for integer input."""
    while True:
        try:
            value = int(input(f"{prompt}: ").strip())
            if min_val is not None and value < min_val:
                print(f"Value must be >= {min_val}")
                continue
            return value
        except ValueError:
            print("Invalid input. Please enter a number.")


def prompt_string(prompt: str) -> str:
    """Prompt for string input."""
    while True:
        value = input(f"{prompt}: ").strip()
        if value:
            return value
        print("Input cannot be empty.")


def display_positions(tracker: PositionTracker):
    """Display all open positions."""
    positions = tracker.get_all_positions()
    
    if not positions:
        print("\n✅ No open positions")
        return
    
    print("\n" + "=" * 80)
    print("📊 OPEN POSITIONS")
    print("=" * 80 + "\n")
    
    print(f"{'Ticker':<8} {'Entry':<10} {'Entry Date':<15} {'Stop':<10} {'Target':<10} {'Strategy':<35}")
    print("-" * 90)
    
    for ticker, pos in sorted(positions.items()):
        entry = pos.get('entry_price', 0)
        entry_date = pos.get('entry_date', '')
        if isinstance(entry_date, str):
            entry_date = entry_date[:10]  # Format: YYYY-MM-DD
        else:
            entry_date = str(entry_date)[:10]
        stop = pos.get('stop_loss', 0)
        target = pos.get('target', 0)
        strategy = pos.get('strategy', 'Unknown')[:35]
        
        print(f"{ticker:<8} ${entry:<9.2f} {entry_date:<15} ${stop:<9.2f} ${target:<9.2f} {strategy:<35}")
    
    print(f"\nTotal Positions: {len(positions)}")


def add_position(tracker: PositionTracker):
    """Interactively add a new position."""
    print("\n" + "=" * 80)
    print("➕ ADD NEW POSITION")
    print("=" * 80 + "\n")
    
    ticker = prompt_string("Ticker").upper()
    
    if tracker.get_position(ticker):
        print(f"⚠️  Position already exists for {ticker}")
        return
    
    entry_price = prompt_float("Entry Price", min_val=0.01)
    stop_loss = prompt_float("Stop Loss Price", min_val=0.01)
    target = prompt_float("Target Price", min_val=0.01)
    
    if stop_loss >= entry_price:
        print("❌ Stop loss must be below entry price")
        return
    
    if target <= entry_price:
        print("❌ Target must be above entry price")
        return
    
    max_days = prompt_int("Max Days to Hold", min_val=1)
    
    print("\nAvailable Strategies:")
    strategies = [
        "RelativeStrength_Ranker_Position",
        "High52_Position",
        "BigBase_Breakout_Position",
        "Manual"
    ]
    for i, strat in enumerate(strategies, 1):
        print(f"  {i}. {strat}")
    
    while True:
        choice = prompt_int("Select strategy (1-4)", min_val=1)
        if 1 <= choice <= 4:
            strategy = strategies[choice - 1]
            break
        print("Invalid choice")
    
    # Confirm
    print(f"\nAdding position:")
    print(f"  Ticker: {ticker}")
    print(f"  Entry: ${entry_price:.2f}")
    print(f"  Stop: ${stop_loss:.2f}")
    print(f"  Target: ${target:.2f}")
    print(f"  Max Days: {max_days}")
    print(f"  Strategy: {strategy}")
    
    if not prompt_yes_no("\nConfirm?"):
        print("Cancelled")
        return
    
    success = tracker.add_position(
        ticker=ticker,
        entry_date=datetime.now(),
        entry_price=entry_price,
        strategy=strategy,
        stop_loss=stop_loss,
        target=target,
        max_days=max_days
    )
    
    if success:
        print(f"✅ Position added for {ticker}")
    else:
        print(f"❌ Failed to add position for {ticker}")


def close_position(tracker: PositionTracker):
    """Interactively close a position."""
    print("\n" + "=" * 80)
    print("❌ CLOSE POSITION")
    print("=" * 80 + "\n")
    
    positions = tracker.get_all_positions()
    if not positions:
        print("✅ No open positions")
        return
    
    # Show positions
    tickers = sorted(positions.keys())
    for i, ticker in enumerate(tickers, 1):
        pos = positions[ticker]
        entry = pos.get('entry_price', 0)
        print(f"  {i}. {ticker:<8} (Entry: ${entry:.2f})")
    
    while True:
        choice = prompt_int("Select position (1-{})".format(len(tickers)), min_val=1)
        if 1 <= choice <= len(tickers):
            ticker = tickers[choice - 1]
            break
        print("Invalid choice")
    
    exit_price = prompt_float("Exit Price", min_val=0.01)
    
    pos = positions[ticker]
    entry = pos.get('entry_price', 0)
    profit = exit_price - entry
    profit_pct = (profit / entry * 100) if entry > 0 else 0
    
    print(f"\nClosing {ticker}:")
    print(f"  Entry: ${entry:.2f}")
    print(f"  Exit: ${exit_price:.2f}")
    print(f"  P/L: ${profit:.2f} ({profit_pct:+.2f}%)")
    
    if not prompt_yes_no("Confirm close?"):
        print("Cancelled")
        return
    
    success = tracker.close_position(ticker, exit_price)
    
    if success:
        print(f"✅ Position closed for {ticker}")
    else:
        print(f"❌ Failed to close position for {ticker}")


def update_position(tracker: PositionTracker):
    """Interactively update position details."""
    print("\n" + "=" * 80)
    print("✏️ UPDATE POSITION")
    print("=" * 80 + "\n")
    
    positions = tracker.get_all_positions()
    if not positions:
        print("✅ No open positions")
        return
    
    tickers = sorted(positions.keys())
    for i, ticker in enumerate(tickers, 1):
        print(f"  {i}. {ticker}")
    
    while True:
        choice = prompt_int("Select position (1-{})".format(len(tickers)), min_val=1)
        if 1 <= choice <= len(tickers):
            ticker = tickers[choice - 1]
            break
        print("Invalid choice")
    
    pos = positions[ticker]
    print(f"\nCurrent values for {ticker}:")
    print(f"  1. Stop Loss: ${pos.get('stop_loss', 0):.2f}")
    print(f"  2. Target: ${pos.get('target', 0):.2f}")
    print(f"  3. Max Days: {pos.get('max_days', 150)}")
    
    while True:
        choice = prompt_int("Select field to update (1-3)", min_val=1)
        if 1 <= choice <= 3:
            break
        print("Invalid choice")
    
    if choice == 1:
        new_value = prompt_float("New Stop Loss Price", min_val=0.01)
        pos['stop_loss'] = new_value
        print(f"✅ Stop loss updated to ${new_value:.2f}")
    elif choice == 2:
        new_value = prompt_float("New Target Price", min_val=0.01)
        pos['target'] = new_value
        print(f"✅ Target updated to ${new_value:.2f}")
    elif choice == 3:
        new_value = prompt_int("New Max Days", min_val=1)
        pos['max_days'] = new_value
        print(f"✅ Max days updated to {new_value}")
    
    # Save changes
    tracker.save_positions()
    print(f"✅ Changes saved")


def export_positions(tracker: PositionTracker):
    """Export positions to file."""
    print("\n" + "=" * 80)
    print("💾 EXPORT POSITIONS")
    print("=" * 80 + "\n")
    
    print("Export format:")
    print("  1. CSV")
    print("  2. JSON")
    
    while True:
        choice = prompt_int("Select format (1-2)", min_val=1)
        if 1 <= choice <= 2:
            break
    
    filename = prompt_string("Output filename (without extension)")
    
    positions = tracker.get_all_positions()
    
    if choice == 1:
        # CSV export
        filename += ".csv"
        try:
            import pandas as pd
            df = pd.DataFrame.from_dict(positions, orient='index')
            df.to_csv(filename)
            print(f"✅ Exported to {filename}")
        except Exception as e:
            print(f"❌ Export failed: {e}")
    else:
        # JSON export
        filename += ".json"
        try:
            # Convert datetime objects to strings for JSON
            export_data = {}
            for ticker, pos in positions.items():
                export_data[ticker] = {
                    k: str(v) if isinstance(v, datetime) else v
                    for k, v in pos.items()
                }
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
            print(f"✅ Exported to {filename}")
        except Exception as e:
            print(f"❌ Export failed: {e}")


def interactive_mode(tracker: PositionTracker):
    """Run interactive menu mode."""
    while True:
        display_menu()
        choice = input("Select option (1-6): ").strip()
        
        if choice == '1':
            display_positions(tracker)
        elif choice == '2':
            add_position(tracker)
        elif choice == '3':
            close_position(tracker)
        elif choice == '4':
            update_position(tracker)
        elif choice == '5':
            export_positions(tracker)
        elif choice == '6':
            print("\n✨ Goodbye!")
            break
        else:
            print("Invalid option")


def main():
    """Main entry point for position manager."""
    parser = argparse.ArgumentParser(
        description="Position Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/manage_positions.py                 # Interactive menu
  python scripts/manage_positions.py --list          # List all positions
  python scripts/manage_positions.py --add AAPL      # Add new position
  python scripts/manage_positions.py --close AAPL    # Close position
        """
    )
    
    parser.add_argument(
        "--positions-file",
        default="data/open_positions.json",
        help="Path to positions file"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all positions"
    )
    parser.add_argument(
        "--add",
        metavar="TICKER",
        help="Add new position"
    )
    parser.add_argument(
        "--close",
        metavar="TICKER",
        help="Close position"
    )
    parser.add_argument(
        "--export",
        metavar="FORMAT",
        choices=["csv", "json"],
        help="Export positions"
    )
    
    args = parser.parse_args()
    
    # Initialize tracker
    try:
        tracker = PositionTracker(mode="live", file=args.positions_file)
    except Exception as e:
        print(f"❌ Error loading positions: {e}")
        return 1
    
    # Handle command-line arguments
    if args.list:
        display_positions(tracker)
    elif args.add:
        # Simplified add for CLI
        print(f"Use interactive mode for adding positions")
        return 1
    elif args.close:
        # Simplified close for CLI
        print(f"Use interactive mode for closing positions")
        return 1
    elif args.export:
        print(f"Use interactive mode for exporting")
        return 1
    else:
        # Interactive mode
        print("\n" + "=" * 80)
        print("📊 POSITION MANAGEMENT CLI")
        print("=" * 80)
        interactive_mode(tracker)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
