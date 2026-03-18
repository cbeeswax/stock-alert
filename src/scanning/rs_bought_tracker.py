"""
RelativeStrength Ranker - Bought Ticker Tracker
================================================
Maintains list of tickers recommended as buys by RelativeStrength_Ranker_Position.

Purpose:
- Prevent duplicate BUY alerts for same ticker
- Track pyramiding opportunities (+1.5R threshold)
- Track exit signals (time stops, trailing MA)
- Manage position lifecycle: bought → pyramided → closed

File format: data/rs_ranker_bought.json
{
  "TICKER": {
    "entry_date": "2026-01-15",
    "entry_price": 150.25,
    "status": "bought|pyramided|closed",
    "pyramids": [  # List of pyramid adds
      {"date": "2026-02-01", "price": 165.50, "amount": 0.5}
    ],
    "exit_date": "2026-03-10",
    "exit_price": 180.00,
    "exit_reason": "TimeStop_150d|EMA21_Trail|MA100_Trail|TargetHit",
    "profit_loss": 4500.00
  }
}
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class RSBoughtTracker:
    """Manages RelativeStrength_Ranker bought ticker list."""

    def __init__(self, file_path: str = "data/rs_ranker_bought.json"):
        """Initialize tracker."""
        self.file_path = Path(file_path)
        self.bought_tickers = {}
        self._load()

    def _load(self) -> None:
        """Load bought list from JSON file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r') as f:
                    self.bought_tickers = json.load(f)
            except Exception as e:
                print(f"⚠️  Error loading RS bought tracker: {e}")
                self.bought_tickers = {}
        else:
            self.bought_tickers = {}

    def _save(self) -> None:
        """Save bought list to JSON file."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w') as f:
                json.dump(self.bought_tickers, f, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving RS bought tracker: {e}")

    def add_bought(self, ticker: str, entry_date: str, entry_price: float) -> None:
        """
        Record a ticker as recommended for buy.
        Handles both new entries and re-entries after cooldown.

        Args:
            ticker: Stock ticker symbol
            entry_date: Date recommended (YYYY-MM-DD)
            entry_price: Entry price
        """
        self.bought_tickers[ticker] = {
            "entry_date": entry_date,
            "entry_price": entry_price,
            "status": "bought",
            "pyramids": [],
            "exit_date": None,
            "exit_price": None,
            "exit_reason": None,
            "profit_loss": None
        }
        self._save()

    def add_pyramid(self, ticker: str, date: str, price: float, size_pct: float = 0.5) -> None:
        """
        Record a pyramid add to existing position.

        Args:
            ticker: Stock ticker symbol
            date: Pyramid date (YYYY-MM-DD)
            price: Pyramid entry price
            size_pct: Size relative to original position (default 50%)
        """
        if ticker in self.bought_tickers:
            self.bought_tickers[ticker]["pyramids"].append({
                "date": date,
                "price": price,
                "amount": size_pct
            })
            # Mark as pyramided once first add is made
            if len(self.bought_tickers[ticker]["pyramids"]) == 1:
                self.bought_tickers[ticker]["status"] = "pyramided"
            self._save()

    def close_position(
        self,
        ticker: str,
        exit_date: str,
        exit_price: float,
        exit_reason: str,
        profit_loss: Optional[float] = None
    ) -> None:
        """
        Record position closure.

        Args:
            ticker: Stock ticker symbol
            exit_date: Exit date (YYYY-MM-DD)
            exit_price: Exit price
            exit_reason: Reason for exit (TimeStop_150d, EMA21_Trail, MA100_Trail, TargetHit, etc)
            profit_loss: Profit/loss in dollars (optional)
        """
        if ticker in self.bought_tickers:
            self.bought_tickers[ticker].update({
                "status": "closed",
                "exit_date": exit_date,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "profit_loss": profit_loss
            })
            self._save()

    def is_bought(self, ticker: str) -> bool:
        """Check if ticker is in active position (not closed)."""
        if ticker not in self.bought_tickers:
            return False
        status = self.bought_tickers[ticker].get("status")
        return status in ("bought", "pyramided")

    def is_closed(self, ticker: str) -> bool:
        """Check if ticker position is closed."""
        if ticker not in self.bought_tickers:
            return False
        return self.bought_tickers[ticker].get("status") == "closed"

    def can_buy_again(self, ticker: str, cooldown_days: int = 30, as_of_date=None) -> bool:
        """
        Check if a closed ticker can be recommended again (cooldown expired).
        
        Args:
            ticker: Stock ticker symbol
            cooldown_days: Number of days to wait before allowing re-entry (default 30)
            as_of_date: Date to check from (default: today). Used for backtesting.
        
        Returns:
            True if ticker can be traded again, False if still in cooldown
        """
        if not self.is_closed(ticker):
            return True  # Not closed, can trade
        
        # Closed - check cooldown
        ticker_data = self.bought_tickers.get(ticker)
        if not ticker_data or not ticker_data.get("exit_date"):
            return False  # No exit date, block it
        
        from datetime import datetime, timedelta
        import pandas as pd
        
        exit_date = datetime.strptime(ticker_data["exit_date"], "%Y-%m-%d")
        
        # Use provided date (for backtesting) or current date (for live)
        if as_of_date is not None:
            current_date = pd.to_datetime(as_of_date)
            if hasattr(current_date, 'to_pydatetime'):
                current_date = current_date.to_pydatetime()
        else:
            current_date = datetime.now()
        
        days_since_exit = (current_date - exit_date).days
        
        return days_since_exit >= cooldown_days

    def has_recent_stop(self, ticker: str, trading_days_lookback: int = 5, as_of_date=None) -> bool:
        """
        Check if ticker was stopped out recently (within N trading days).
        
        Args:
            ticker: Stock ticker symbol
            trading_days_lookback: Number of trading days to look back (default 5)
            as_of_date: Current date for calculation (default: today)
        
        Returns:
            True if ticker exited via StopLoss within the lookback period
        """
        if ticker not in self.bought_tickers:
            return False
        
        ticker_data = self.bought_tickers[ticker]
        exit_reason = ticker_data.get("exit_reason")
        exit_date = ticker_data.get("exit_date")
        
        # Only block if exit was a StopLoss
        if exit_reason != "StopLoss" or not exit_date:
            return False
        
        from datetime import datetime
        import pandas as pd
        
        exit_dt = datetime.strptime(exit_date, "%Y-%m-%d")
        
        # Use provided date or current date
        if as_of_date is not None:
            current_dt = pd.to_datetime(as_of_date)
            if hasattr(current_dt, 'to_pydatetime'):
                current_dt = current_dt.to_pydatetime()
        else:
            current_dt = datetime.now()
        
        # Calculate trading days since exit (rough: assume ~1 trading day per calendar day)
        trading_days_since = (current_dt - exit_dt).days
        
        return trading_days_since <= trading_days_lookback

    def get_bought_tickers(self) -> List[str]:
        """Get list of all active bought tickers (not closed)."""
        return [
            ticker for ticker, data in self.bought_tickers.items()
            if data.get("status") in ("bought", "pyramided")
        ]

    def get_ticker_info(self, ticker: str) -> Optional[Dict]:
        """Get full info for a ticker."""
        return self.bought_tickers.get(ticker)

    def get_summary(self) -> Dict:
        """Get summary statistics."""
        active = sum(1 for t in self.bought_tickers.values() if t.get("status") in ("bought", "pyramided"))
        closed = sum(1 for t in self.bought_tickers.values() if t.get("status") == "closed")
        total_profit = sum(
            t.get("profit_loss", 0) or 0
            for t in self.bought_tickers.values()
            if t.get("status") == "closed"
        )
        
        return {
            "total_recommendations": len(self.bought_tickers),
            "active_positions": active,
            "closed_positions": closed,
            "total_profit_closed": total_profit,
            "active_tickers": self.get_bought_tickers()
        }

    def clear_all(self) -> None:
        """Clear all data (use with caution)."""
        self.bought_tickers = {}
        self._save()
