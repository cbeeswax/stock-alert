"""
Base Strategy Class
===================
Abstract base class for all trading strategies.
All strategies should inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import pandas as pd


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    
    All strategy implementations should inherit from this and implement
    the run() method to return a list of signal dictionaries.
    """
    
    name: str = "BaseStrategy"
    description: str = ""
    
    def __init__(self):
        """Initialize strategy."""
        pass
    
    @abstractmethod
    def run(self, tickers: List[str], as_of_date: pd.Timestamp = None) -> List[Dict[str, Any]]:
        """
        Run the strategy on a list of tickers.
        
        Args:
            tickers: List of ticker symbols to scan
            as_of_date: Date to run scan as of (for backtesting)
            
        Returns:
            List of signal dictionaries with required keys:
            - Ticker: Stock symbol
            - Close: Current close price
            - Score: Raw strategy score
            - Strategy: Strategy name
            - Volume: Latest volume
            - Date: Signal date
        """
        pass
    
    def validate_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Validate that a signal has all required fields.
        
        Args:
            signal: Signal dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_keys = {"Ticker", "Close", "Score", "Strategy", "Volume", "Date"}
        return all(key in signal for key in required_keys)
    
    def format_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format and validate signals before returning.
        
        Args:
            signals: List of signal dictionaries
            
        Returns:
            Validated list of signals
        """
        validated = []
        for signal in signals:
            if self.validate_signal(signal):
                validated.append(signal)
        
        return validated
