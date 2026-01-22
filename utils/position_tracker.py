"""
Position Tracker Module
========================
Prevents duplicate positions in the same ticker.
Used by both backtester and live trading system.

Key Features:
- Track open positions (ticker, entry date, entry price)
- Block new signals for tickers already in position
- Update when positions are closed
- Persist state to JSON file (for live trading)
- In-memory tracking for backtesting
"""

import json
from pathlib import Path
from datetime import datetime
import pandas as pd


class PositionTracker:
    """
    Tracks open positions to prevent duplicate entries.

    Usage:
        # Backtesting mode (in-memory only)
        tracker = PositionTracker(mode="backtest")

        # Live mode (persistent file)
        tracker = PositionTracker(mode="live", file="data/open_positions.json")
    """

    def __init__(self, mode="backtest", file="data/open_positions.json"):
        """
        Initialize position tracker.

        Args:
            mode: "backtest" (in-memory) or "live" (persistent file)
            file: Path to JSON file for live mode
        """
        self.mode = mode
        self.file = Path(file)
        self.positions = {}  # {ticker: {entry_date, entry_price, strategy, ...}}

        if mode == "live" and self.file.exists():
            self._load_positions()

    def _load_positions(self):
        """Load positions from JSON file (live mode only)."""
        try:
            with open(self.file, 'r') as f:
                data = json.load(f)
                # Convert date strings back to datetime
                for ticker, pos in data.items():
                    if 'entry_date' in pos:
                        pos['entry_date'] = pd.to_datetime(pos['entry_date'])
                self.positions = data
        except Exception as e:
            print(f"⚠️ Error loading positions: {e}")
            self.positions = {}

    def _save_positions(self):
        """Save positions to JSON file (live mode only)."""
        if self.mode != "live":
            return

        try:
            # Convert datetime to string for JSON serialization
            data = {}
            for ticker, pos in self.positions.items():
                pos_copy = pos.copy()
                if 'entry_date' in pos_copy:
                    pos_copy['entry_date'] = str(pos_copy['entry_date'])
                data[ticker] = pos_copy

            self.file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving positions: {e}")

    def is_in_position(self, ticker, as_of_date=None):
        """
        Check if ticker already has an open position.

        Args:
            ticker: Stock ticker symbol
            as_of_date: Date to check (for backtesting). If None, just checks existence.

        Returns:
            bool: True if position exists and is open as of date, False otherwise
        """
        if ticker not in self.positions:
            return False

        # For live mode or no date specified, just check existence
        if as_of_date is None:
            return True

        # For backtesting, check if position is still open as of this date
        position = self.positions[ticker]
        entry_date = pd.to_datetime(position.get('entry_date'))
        exit_date = position.get('exit_date')

        # If no exit date, position is still open
        if exit_date is None:
            return True

        exit_date = pd.to_datetime(exit_date)

        # Position is open if: entry_date <= as_of_date < exit_date
        return entry_date <= pd.to_datetime(as_of_date) < exit_date

    def add_position(self, ticker, entry_date, entry_price, strategy, as_of_date=None, **kwargs):
        """
        Add a new position.

        Args:
            ticker: Stock ticker symbol
            entry_date: Date of entry (datetime or string)
            entry_price: Entry price
            strategy: Strategy name
            as_of_date: Date to check for duplicates (for backtesting)
            **kwargs: Additional fields (stop_loss, target, etc.)
        """
        # Use as_of_date if provided (backtesting), otherwise check current state (live)
        check_date = as_of_date if as_of_date else None
        if self.is_in_position(ticker, as_of_date=check_date):
            print(f"⚠️ Warning: {ticker} already has an open position!")
            return False

        self.positions[ticker] = {
            'entry_date': pd.to_datetime(entry_date),
            'entry_price': entry_price,
            'strategy': strategy,
            **kwargs
        }

        self._save_positions()
        return True

    def remove_position(self, ticker):
        """
        Remove a position (after exit).

        Args:
            ticker: Stock ticker symbol

        Returns:
            dict: Position data if existed, None otherwise
        """
        if ticker not in self.positions:
            return None

        position = self.positions.pop(ticker)
        self._save_positions()
        return position

    def get_position(self, ticker):
        """
        Get position details.

        Args:
            ticker: Stock ticker symbol

        Returns:
            dict: Position data or None
        """
        return self.positions.get(ticker)

    def get_all_positions(self):
        """
        Get all open positions.

        Returns:
            dict: All positions
        """
        return self.positions.copy()

    def get_open_tickers(self):
        """
        Get list of tickers with open positions.

        Returns:
            list: List of ticker symbols
        """
        return list(self.positions.keys())

    def clear_all(self):
        """Clear all positions (useful for backtesting)."""
        self.positions = {}
        self._save_positions()

    def get_position_count(self):
        """Get number of open positions."""
        return len(self.positions)

    def __str__(self):
        """String representation."""
        if not self.positions:
            return "No open positions"

        lines = [f"Open Positions ({len(self.positions)}):"]
        for ticker, pos in self.positions.items():
            entry_date = pos['entry_date']
            entry_price = pos['entry_price']
            strategy = pos.get('strategy', 'Unknown')
            lines.append(f"  {ticker}: ${entry_price:.2f} on {entry_date.date()} ({strategy})")

        return "\n".join(lines)


# =====================================
# Helper Functions
# =====================================

def filter_signals_by_position(signals, tracker):
    """
    Filter out signals for tickers already in position.

    Args:
        signals: List of signal dicts with 'Ticker' field
        tracker: PositionTracker instance

    Returns:
        list: Filtered signals (only tickers not in position)
    """
    if not signals:
        return []

    filtered = []
    skipped = []

    for signal in signals:
        ticker = signal.get('Ticker')
        if not ticker:
            continue

        if tracker.is_in_position(ticker):
            skipped.append(ticker)
        else:
            filtered.append(signal)

    if skipped:
        print(f"   🚫 Skipped {len(skipped)} signals (already in position): {', '.join(skipped[:5])}")
        if len(skipped) > 5:
            print(f"      ... and {len(skipped) - 5} more")

    return filtered


def filter_trades_by_position(trades_df, tracker, as_of_date=None):
    """
    Filter out trades for tickers already in position.

    Args:
        trades_df: DataFrame with 'Ticker' column
        tracker: PositionTracker instance
        as_of_date: Date to check positions (for backtesting)

    Returns:
        DataFrame: Filtered trades (only tickers not in position)
    """
    if trades_df.empty:
        return trades_df

    # Check each ticker if it's in position as of the date
    if as_of_date:
        open_tickers = [
            ticker for ticker in trades_df['Ticker'].unique()
            if tracker.is_in_position(ticker, as_of_date=as_of_date)
        ]
    else:
        open_tickers = tracker.get_open_tickers()

    if not open_tickers:
        return trades_df

    # Filter out trades for tickers already in position
    mask = ~trades_df['Ticker'].isin(open_tickers)
    filtered_df = trades_df[mask].copy()

    skipped = len(trades_df) - len(filtered_df)
    if skipped > 0:
        skipped_tickers = trades_df[~mask]['Ticker'].tolist()
        print(f"   🚫 Skipped {skipped} trade(s) (already in position): {', '.join(skipped_tickers[:5])}")
        if len(skipped_tickers) > 5:
            print(f"      ... and {len(skipped_tickers) - 5} more")

    return filtered_df
