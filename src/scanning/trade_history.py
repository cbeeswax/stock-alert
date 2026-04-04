"""
Trade History Ledger
====================
Maintains append-only ledger of all closed trades by strategy.
Used for P&L tracking, performance analysis, and audit trail.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


class TradeHistory:
    """Manages closed trades ledger (append-only)."""

    def __init__(self, file_path: str = "data/rs_ranker_trade_history.json"):
        """Initialize trade history.
        
        Args:
            file_path: Path to trade history JSON file
        """
        self.file_path = Path(file_path)
        self.trades = {}
        self._load()

    def _load(self) -> None:
        """Load trade history from JSON file, falling back to GCS if missing locally."""
        if not self.file_path.exists() and "backtest" not in str(self.file_path):
            from src.storage.gcs import download_file
            download_file(f"config/{self.file_path.name}", self.file_path)

        if self.file_path.exists():
            try:
                with open(self.file_path, 'r') as f:
                    self.trades = json.load(f)
            except Exception as e:
                print(f"⚠️ Error loading trade history: {e}")
                self.trades = {}
        else:
            self.trades = {}

    def _save(self) -> None:
        """Save trade history to JSON file and push to GCS."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w') as f:
                json.dump(self.trades, f, indent=2)
            if "backtest" not in str(self.file_path):
                from src.storage.gcs import upload_file
                upload_file(self.file_path, f"config/{self.file_path.name}")
        except Exception as e:
            print(f"⚠️ Error saving trade history: {e}")

    def append_trade(
        self,
        ticker: str,
        strategy: str,
        entry_date: str,
        entry_price: float,
        exit_date: str,
        exit_price: float,
        exit_reason: str,
        pnl: float,
        r_multiple: float,
        days_held: int
    ) -> None:
        """Append a closed trade to history.
        
        Args:
            ticker: Stock ticker symbol
            strategy: Strategy name (e.g., "RelativeStrength_Ranker_Position")
            entry_date: Entry date (YYYY-MM-DD)
            entry_price: Entry price
            exit_date: Exit date (YYYY-MM-DD)
            exit_price: Exit price
            exit_reason: Exit reason (StopLoss, TimeStop, TrailStop, etc)
            pnl: Profit/loss in dollars
            r_multiple: R-multiple (profit/risk)
            days_held: Number of days held
        """
        # Create unique trade ID
        trade_id = f"{ticker}_{strategy.split('_')[0]}_{entry_date.replace('-', '')}_{exit_date.replace('-', '')}"
        
        self.trades[trade_id] = {
            "ticker": ticker,
            "strategy": strategy,
            "entry_date": entry_date,
            "entry_price": entry_price,
            "exit_date": exit_date,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "pnl": round(pnl, 2),
            "r_multiple": round(r_multiple, 2),
            "days_held": days_held,
            "outcome": "Win" if pnl > 0 else "Loss"
        }
        self._save()

    def get_trades_by_strategy(self, strategy: str) -> List[Dict]:
        """Get all trades for a specific strategy.
        
        Args:
            strategy: Strategy name to filter by
            
        Returns:
            List of trades matching the strategy
        """
        return [
            trade for trade in self.trades.values()
            if trade.get('strategy') == strategy
        ]

    def get_p_and_l_summary(self, strategy: Optional[str] = None) -> Dict:
        """Get P&L summary, optionally filtered by strategy.
        
        Args:
            strategy: Optional strategy to filter by. If None, returns all.
            
        Returns:
            Dict with P&L metrics
        """
        # Filter trades
        if strategy:
            trades = self.get_trades_by_strategy(strategy)
        else:
            trades = list(self.trades.values())

        if not trades:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_r_multiple": 0.0,
                "avg_days_held": 0.0
            }

        wins = sum(1 for t in trades if t['outcome'] == 'Win')
        losses = len(trades) - wins
        total_pnl = sum(t['pnl'] for t in trades)
        avg_r = sum(t['r_multiple'] for t in trades) / len(trades) if trades else 0
        avg_days = sum(t['days_held'] for t in trades) / len(trades) if trades else 0

        return {
            "total_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(trades) * 100, 2) if trades else 0,
            "total_pnl": round(total_pnl, 2),
            "avg_r_multiple": round(avg_r, 2),
            "avg_days_held": round(avg_days, 1)
        }

    def get_all_trades(self) -> List[Dict]:
        """Get all trades in history."""
        return list(self.trades.values())
