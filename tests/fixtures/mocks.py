"""
Mock objects for testing without external dependencies.

This module provides:
- Mock market data providers
- Mock email clients
- Mock file system objects
- Mock strategy executors
"""

from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ============================================================================
# MOCK MARKET DATA PROVIDERS
# ============================================================================

class MockMarketDataProvider:
    """Mock provider for market data without network calls."""
    
    def __init__(self, default_data: pd.DataFrame = None):
        self.data = default_data or self._create_default_data()
        self.call_history = []
    
    def _create_default_data(self) -> pd.DataFrame:
        """Create default sample data."""
        dates = pd.date_range(start="2023-01-01", periods=252, freq="B")
        return pd.DataFrame({
            "Date": dates,
            "Open": 100 + np.random.normal(0, 2, 252),
            "High": 105 + np.random.normal(0, 2, 252),
            "Low": 95 + np.random.normal(0, 2, 252),
            "Close": 100 + np.random.normal(0, 2, 252),
            "Volume": np.random.randint(1000000, 10000000, 252),
        })
    
    def get_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Mock data retrieval."""
        self.call_history.append({"ticker": ticker, "kwargs": kwargs})
        return self.data.copy()
    
    def get_multiple_data(self, tickers: List[str], **kwargs) -> Dict[str, pd.DataFrame]:
        """Mock bulk data retrieval."""
        self.call_history.append({"tickers": tickers, "kwargs": kwargs})
        return {ticker: self.data.copy() for ticker in tickers}


# ============================================================================
# MOCK EMAIL CLIENT
# ============================================================================

class MockEmailClient:
    """Mock email client that captures sent emails."""
    
    def __init__(self):
        self.sent_emails = []
        self.should_fail = False
    
    def send(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: str = None,
        **kwargs
    ) -> bool:
        """Mock email sending."""
        if self.should_fail:
            raise Exception("Mock email failure")
        
        email = {
            "to": to,
            "subject": subject,
            "body": body,
            "html_body": html_body,
            "timestamp": datetime.now(),
            **kwargs
        }
        self.sent_emails.append(email)
        return True
    
    def get_sent_emails(self) -> List[Dict[str, Any]]:
        """Get all sent emails."""
        return self.sent_emails
    
    def clear(self):
        """Clear sent emails."""
        self.sent_emails = []


# ============================================================================
# MOCK FILE SYSTEM
# ============================================================================

class MockFileSystem:
    """Mock file system for testing file I/O."""
    
    def __init__(self):
        self.files: Dict[str, str] = {}
        self.directories: List[str] = []
    
    def write_file(self, path: str, content: str):
        """Mock file write."""
        self.files[path] = content
    
    def read_file(self, path: str) -> str:
        """Mock file read."""
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        return self.files[path]
    
    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        return path in self.files
    
    def mkdir(self, path: str):
        """Mock directory creation."""
        self.directories.append(path)
    
    def delete_file(self, path: str):
        """Mock file deletion."""
        if path in self.files:
            del self.files[path]


# ============================================================================
# MOCK STRATEGY
# ============================================================================

class MockStrategyExecutor:
    """Mock strategy executor for testing scanning logic."""
    
    def __init__(self, name: str = "MockStrategy"):
        self.name = name
        self.call_count = 0
        self.last_call_args = None
        self.mock_signals = []
    
    def scan(
        self,
        data: pd.DataFrame,
        ticker: str = None,
        as_of_date: datetime = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Mock strategy scan."""
        self.call_count += 1
        self.last_call_args = {
            "data": data,
            "ticker": ticker,
            "as_of_date": as_of_date,
            **kwargs
        }
        
        # Return mock signals if configured
        if self.mock_signals:
            return self.mock_signals
        
        # Return empty signals by default
        return []
    
    def set_mock_signals(self, signals: List[Dict[str, Any]]):
        """Set mock signals to return."""
        self.mock_signals = signals
    
    def get_call_count(self) -> int:
        """Get number of times scan was called."""
        return self.call_count
    
    def reset(self):
        """Reset call history."""
        self.call_count = 0
        self.last_call_args = None
        self.mock_signals = []


# ============================================================================
# MOCK POSITION TRACKER
# ============================================================================

class MockPositionTracker:
    """Mock position tracker for testing position management."""
    
    def __init__(self):
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.actions = []
    
    def add_position(self, ticker: str, **kwargs) -> bool:
        """Mock add position."""
        self.positions[ticker] = {
            "ticker": ticker,
            "added_at": datetime.now(),
            **kwargs
        }
        self.actions.append(("add", ticker, kwargs))
        return True
    
    def close_position(self, ticker: str, exit_price: float = None) -> bool:
        """Mock close position."""
        if ticker in self.positions:
            pos = self.positions.pop(ticker)
            self.actions.append(("close", ticker, {"exit_price": exit_price}))
            return True
        return False
    
    def get_position(self, ticker: str) -> Dict[str, Any]:
        """Mock get position."""
        return self.positions.get(ticker)
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Mock get all positions."""
        return self.positions.copy()
    
    def get_position_count(self) -> int:
        """Mock position count."""
        return len(self.positions)
    
    def get_actions(self) -> List[tuple]:
        """Get all recorded actions."""
        return self.actions
    
    def clear(self):
        """Clear all positions and actions."""
        self.positions = {}
        self.actions = []


# ============================================================================
# MOCK CONFIG
# ============================================================================

class MockConfig:
    """Mock configuration object."""
    
    def __init__(self, **kwargs):
        self.config = {
            "position_max_total": 20,
            "position_max_per_strategy": {
                "RelativeStrength_Ranker_Position": 10,
                "High52_Position": 6,
                "BigBase_Breakout_Position": 4,
            },
            "position_risk_per_trade_pct": 2.0,
            "position_initial_equity": 100000,
            "regime_index": "QQQ",
            "universal_qqq_bull_ma": 100,
            "min_volume": 500000,
            "min_price": 5.0,
        }
        self.config.update(kwargs)
    
    def get(self, key: str, default=None):
        """Get config value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set config value."""
        self.config[key] = value
    
    def __getitem__(self, key: str):
        """Get config value via bracket notation."""
        return self.config[key]
    
    def __setitem__(self, key: str, value: Any):
        """Set config value via bracket notation."""
        self.config[key] = value


# ============================================================================
# CONTEXT MANAGERS FOR MOCKING
# ============================================================================

def mock_environment(overrides: Dict[str, Any] = None):
    """
    Context manager for mocking environment variables.
    
    Usage:
        with mock_environment({"DEBUG": "true"}):
            # Run tests with DEBUG=true
            pass
    """
    import os
    from contextlib import contextmanager
    
    @contextmanager
    def _mock_env():
        saved = {}
        overrides_dict = overrides or {}
        
        try:
            # Save original values and set new ones
            for key, value in overrides_dict.items():
                saved[key] = os.environ.get(key)
                os.environ[key] = str(value)
            
            yield
        finally:
            # Restore original values
            for key, original_value in saved.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value
    
    return _mock_env()


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_mock_market_data(
    days: int = 252,
    start_price: float = 100,
    trend: float = 0.0005,
    volatility: float = 0.02
) -> pd.DataFrame:
    """Factory function for creating mock market data."""
    dates = pd.date_range(start="2023-01-01", periods=days, freq="B")
    returns = np.random.normal(trend, volatility, days)
    close_prices = start_price * np.exp(np.cumsum(returns))
    
    return pd.DataFrame({
        "Date": dates,
        "Open": close_prices * (1 + np.random.normal(0, 0.005, days)),
        "High": close_prices * (1 + abs(np.random.normal(0, 0.01, days))),
        "Low": close_prices * (1 - abs(np.random.normal(0, 0.01, days))),
        "Close": close_prices,
        "Volume": np.random.randint(1000000, 10000000, days),
    })


def create_mock_signal(
    ticker: str = "TEST",
    entry: float = 100,
    stop: float = 95,
    target: float = 115,
    **kwargs
) -> Dict[str, Any]:
    """Factory function for creating mock trading signals."""
    return {
        "Ticker": ticker,
        "Date": datetime.now(),
        "Entry": entry,
        "StopLoss": stop,
        "Target": target,
        "Score": 7.5,
        "Confidence": 0.75,
        "Strategy": "MockStrategy",
        **kwargs
    }
