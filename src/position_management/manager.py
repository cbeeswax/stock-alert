#!/usr/bin/env python3
"""
Position Management Tool
========================
Manage open positions for live trading.

Usage:
    python manage_positions.py list                    # Show all positions
    python manage_positions.py add AAPL 150.00        # Add position
    python manage_positions.py remove AAPL             # Remove position
    python manage_positions.py clear                   # Clear all positions
    python manage_positions.py count                   # Count positions
"""

import sys
from datetime import datetime
from src.position_management.tracker import PositionTracker



def main():
    tracker = PositionTracker(mode="live", file="data/open_positions.json")

    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    # =====================================
    # LIST - Show all positions
    # =====================================
    if command == "list":
        positions = tracker.get_all_positions()
        if not positions:
            print("📭 No open positions")
            return

        print(f"\n📊 Open Positions ({len(positions)}):")
        print("=" * 80)
        print(f"{'Ticker':<8} {'Entry $':<10} {'Entry Date':<12} {'Strategy':<20} {'Stop $':<10} {'Target $':<10}")
        print("-" * 80)

        for ticker, pos in positions.items():
            entry_price = pos.get('entry_price', 0)
            entry_date = pos.get('entry_date', 'N/A')
            strategy = pos.get('strategy', 'Unknown')
            stop_loss = pos.get('stop_loss', 0)
            target = pos.get('target', 0)

            # Format date
            if isinstance(entry_date, str):
                try:
                    entry_date = datetime.fromisoformat(entry_date).date()
                except:
                    pass

            print(f"{ticker:<8} ${entry_price:<9.2f} {str(entry_date):<12} {strategy:<20} ${stop_loss:<9.2f} ${target:<9.2f}")

        print("=" * 80)

    # =====================================
    # COUNT - Count positions
    # =====================================
    elif command == "count":
        count = tracker.get_position_count()
        print(f"📊 Open Positions: {count}")

    # =====================================
    # ADD - Add new position
    # =====================================
    elif command == "add":
        if len(sys.argv) < 4:
            print("❌ Usage: python manage_positions.py add TICKER ENTRY_PRICE [STRATEGY] [STOP] [TARGET]")
            print("   Example: python manage_positions.py add AAPL 150.00 \"EMA Crossover\" 147.50 155.00")
            return

        ticker = sys.argv[2].upper()
        try:
            entry_price = float(sys.argv[3])
        except ValueError:
            print(f"❌ Invalid entry price: {sys.argv[3]}")
            return

        strategy = sys.argv[4] if len(sys.argv) > 4 else "Manual Entry"

        stop_loss = 0
        if len(sys.argv) > 5:
            try:
                stop_loss = float(sys.argv[5])
            except ValueError:
                print(f"⚠️ Invalid stop loss: {sys.argv[5]}, using 0")

        target = 0
        if len(sys.argv) > 6:
            try:
                target = float(sys.argv[6])
            except ValueError:
                print(f"⚠️ Invalid target: {sys.argv[6]}, using 0")

        # Check if already in position
        if tracker.is_in_position(ticker):
            print(f"⚠️ {ticker} already has an open position!")
            existing = tracker.get_position(ticker)
            print(f"   Existing: ${existing['entry_price']:.2f} on {existing['entry_date']}")
            response = input("   Replace? (y/n): ")
            if response.lower() != 'y':
                print("❌ Cancelled")
                return
            tracker.remove_position(ticker)

        # Add position
        success = tracker.add_position(
            ticker=ticker,
            entry_date=datetime.now(),
            entry_price=entry_price,
            strategy=strategy,
            stop_loss=stop_loss,
            target=target
        )

        if success:
            print(f"✅ Added position: {ticker} @ ${entry_price:.2f}")
            if stop_loss > 0:
                print(f"   Stop Loss: ${stop_loss:.2f} | Target: ${target:.2f}")
        else:
            print(f"❌ Failed to add position")

    # =====================================
    # REMOVE - Remove position
    # =====================================
    elif command == "remove":
        if len(sys.argv) < 3:
            print("❌ Usage: python manage_positions.py remove TICKER")
            print("   Example: python manage_positions.py remove AAPL")
            return

        ticker = sys.argv[2].upper()

        if not tracker.is_in_position(ticker):
            print(f"⚠️ {ticker} is not in open positions")
            return

        position = tracker.remove_position(ticker)
        if position:
            print(f"✅ Removed position: {ticker}")
            print(f"   Entry: ${position['entry_price']:.2f} on {position['entry_date']}")
        else:
            print(f"❌ Failed to remove position")

    # =====================================
    # CLEAR - Clear all positions
    # =====================================
    elif command == "clear":
        count = tracker.get_position_count()
        if count == 0:
            print("📭 No positions to clear")
            return

        print(f"⚠️ This will remove all {count} open position(s)")
        response = input("   Are you sure? (y/n): ")
        if response.lower() != 'y':
            print("❌ Cancelled")
            return

        tracker.clear_all()
        print(f"✅ Cleared all positions")

    # =====================================
    # HELP
    # =====================================
    elif command == "help":
        print_help()

    else:
        print(f"❌ Unknown command: {command}")
        print_help()


def print_help():
    print("""
Position Management Tool
========================

Commands:
    list                                  Show all open positions
    count                                 Count open positions
    add TICKER PRICE [STRATEGY] [STOP] [TARGET]
                                         Add new position
    remove TICKER                         Remove position
    clear                                 Clear all positions
    help                                  Show this help

Examples:
    # List positions
    python manage_positions.py list

    # Add position
    python manage_positions.py add AAPL 150.00
    python manage_positions.py add MSFT 310.50 "EMA Crossover" 305.00 320.00

    # Remove position
    python manage_positions.py remove AAPL

    # Clear all
    python manage_positions.py clear

Workflow:
    1. Run main.py to get new signals (skips tickers in position)
    2. Enter trades in your broker
    3. Add positions: python manage_positions.py add TICKER PRICE
    4. When you exit: python manage_positions.py remove TICKER
    5. Next day: Run main.py again (won't suggest same tickers)
""")


if __name__ == "__main__":
    main()
