"""
Test fixtures and mock data for unit and integration tests.

This module provides:
- Sample market data generators
- Mock strategies for testing
- Test data builders
- Mock API responses
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json


# ============================================================================
# MARKET DATA GENERATORS
# ============================================================================

class SampleDataBuilder:
    """Builder for creating sample market data with realistic patterns."""
    
    @staticmethod
    def generate_trend_data(
        days: int = 252,
        start_price: float = 100,
        trend: float = 0.0005,
        volatility: float = 0.02
    ) -> pd.DataFrame:
        """
        Generate realistic trending price data.
        
        Args:
            days: Number of trading days
            start_price: Starting price
            trend: Daily drift (e.g., 0.0005 for slight uptrend)
            volatility: Daily volatility (standard deviation)
            
        Returns:
            DataFrame with OHLCV data
        """
        dates = pd.date_range(start="2023-01-01", periods=days, freq="B")
        returns = np.random.normal(trend, volatility, days)
        close_prices = start_price * np.exp(np.cumsum(returns))
        
        data = {
            "Date": dates,
            "Close": close_prices,
            "Open": close_prices * (1 + np.random.normal(0, 0.005, days)),
            "High": np.maximum(close_prices, close_prices * (1 + abs(np.random.normal(0, 0.01, days)))),
            "Low": np.minimum(close_prices, close_prices * (1 - abs(np.random.normal(0, 0.01, days)))),
            "Volume": np.random.randint(1000000, 10000000, days),
        }
        
        df = pd.DataFrame(data)
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        return df
    
    @staticmethod
    def generate_consolidation_data(
        days: int = 252,
        consolidation_start: int = 100,
        consolidation_length: int = 20,
        breakout_day: int = None,
        base_price: float = 100
    ) -> pd.DataFrame:
        """Generate data with consolidation pattern for base testing."""
        if breakout_day is None:
            breakout_day = consolidation_start + consolidation_length + 10
        
        dates = pd.date_range(start="2023-01-01", periods=days, freq="B")
        closes = []
        
        for i in range(days):
            if i < consolidation_start:
                # Pre-consolidation: uptrend
                price = base_price + (i * 0.5)
            elif i < consolidation_start + consolidation_length:
                # Consolidation: tight range
                price = base_price + consolidation_start * 0.5 + np.random.normal(0, 0.3)
            elif i < breakout_day:
                # Post-consolidation, pre-breakout: still consolidating
                price = base_price + consolidation_start * 0.5 + np.random.normal(0, 0.3)
            else:
                # Breakout: strong uptrend
                price = base_price + consolidation_start * 0.5 + (i - breakout_day) * 1.5
            
            closes.append(price)
        
        data = {
            "Date": dates,
            "Close": closes,
            "Open": [c * (1 + np.random.normal(0, 0.003)) for c in closes],
            "High": [c * (1 + abs(np.random.normal(0, 0.01))) for c in closes],
            "Low": [c * (1 - abs(np.random.normal(0, 0.01))) for c in closes],
            "Volume": np.random.randint(1000000, 10000000, days),
        }
        
        return pd.DataFrame(data)


# ============================================================================
# MOCK STRATEGIES
# ============================================================================

class MockStrategy:
    """Base mock strategy for testing scanning logic."""
    
    def __init__(self, name: str):
        self.name = name
        self.signals = []
    
    def generate_signals(
        self,
        tickers: List[str],
        as_of_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Generate mock trading signals.
        
        Args:
            tickers: List of tickers to generate signals for
            as_of_date: Date for signals (default: today)
            
        Returns:
            List of signal dictionaries
        """
        if as_of_date is None:
            as_of_date = datetime.now()
        
        signals = []
        for ticker in tickers[:len(tickers)//3]:  # 1/3 of tickers get signals
            signals.append({
                "Ticker": ticker,
                "Date": as_of_date,
                "Strategy": self.name,
                "Entry": 100 + np.random.normal(0, 5),
                "StopLoss": 95 + np.random.normal(0, 2),
                "Target": 115 + np.random.normal(0, 5),
                "Score": np.random.uniform(6, 10),
                "Confidence": np.random.uniform(0.6, 0.95),
            })
        
        return signals


# ============================================================================
# TEST DATA BUILDERS
# ============================================================================

class PositionDataBuilder:
    """Builder for creating test position data."""
    
    @staticmethod
    def create_position(
        ticker: str,
        entry_price: float = 100,
        entry_date: datetime = None,
        strategy: str = "TestStrategy",
        stop_loss: float = 95,
        target: float = 115,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a mock position record."""
        if entry_date is None:
            entry_date = datetime.now()
        
        return {
            "ticker": ticker,
            "entry_price": entry_price,
            "entry_date": entry_date.isoformat() if isinstance(entry_date, datetime) else entry_date,
            "strategy": strategy,
            "stop_loss": stop_loss,
            "target": target,
            "max_days": kwargs.get("max_days", 150),
            "status": kwargs.get("status", "open"),
            **kwargs
        }
    
    @staticmethod
    def create_portfolio(
        positions: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a mock portfolio with multiple positions."""
        if positions is None:
            positions = [
                PositionDataBuilder.create_position("AAPL", 150, strategy="RS_Ranker"),
                PositionDataBuilder.create_position("MSFT", 340, strategy="High52"),
            ]
        
        portfolio = {}
        for pos in positions:
            ticker = pos["ticker"]
            portfolio[ticker] = {k: v for k, v in pos.items() if k != "ticker"}
        
        return portfolio


# ============================================================================
# MOCK API RESPONSES
# ============================================================================

class MockDataProvider:
    """Mock data provider for API responses."""
    
    @staticmethod
    def get_market_data(
        ticker: str,
        days: int = 252
    ) -> pd.DataFrame:
        """Mock market data retrieval."""
        return SampleDataBuilder.generate_trend_data(days)
    
    @staticmethod
    def get_multiple_market_data(
        tickers: List[str],
        days: int = 252
    ) -> Dict[str, pd.DataFrame]:
        """Mock bulk market data retrieval."""
        return {
            ticker: SampleDataBuilder.generate_trend_data(days)
            for ticker in tickers
        }
    
    @staticmethod
    def get_sp500_constituents() -> List[str]:
        """Mock S&P 500 constituents."""
        return [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
            "META", "TSLA", "BRK.B", "JNJ", "V",
            "MA", "PG", "UNH", "HD", "MCD",
            "NFLX", "PYPL", "AMD", "CRM", "ADBE"
        ]


# ============================================================================
# TEST ASSERTIONS HELPERS
# ============================================================================

class SignalAssertions:
    """Helpers for asserting on trading signals."""
    
    @staticmethod
    def assert_valid_signal(signal: Dict[str, Any]) -> bool:
        """Validate signal structure."""
        required_fields = [
            "Ticker", "Date", "Strategy", "Entry",
            "StopLoss", "Target", "Score"
        ]
        return all(field in signal for field in required_fields)
    
    @staticmethod
    def assert_signal_prices_valid(signal: Dict[str, Any]) -> bool:
        """Validate signal price relationships."""
        entry = signal.get("Entry", 0)
        stop = signal.get("StopLoss", 0)
        target = signal.get("Target", 0)
        
        # Stop should be below entry
        if not (stop < entry):
            return False
        
        # Target should be above entry
        if not (target > entry):
            return False
        
        # Risk/reward should be reasonable
        risk = entry - stop
        reward = target - entry
        
        return risk > 0 and reward > risk * 0.5  # At least 0.5:1 RR


# ============================================================================
# MARKET DATA EXPORTS
# ============================================================================

def get_sample_sp500_data() -> Dict[str, pd.DataFrame]:
    """Get sample S&P 500 data for all major stocks."""
    tickers = MockDataProvider.get_sp500_constituents()
    return MockDataProvider.get_multiple_market_data(tickers)


def get_sample_position_data() -> Dict[str, Any]:
    """Get sample position data."""
    builder = PositionDataBuilder()
    return builder.create_portfolio([
        builder.create_position("AAPL", 150, strategy="RelativeStrength_Ranker_Position"),
        builder.create_position("MSFT", 340, strategy="High52_Position"),
        builder.create_position("GOOGL", 140, strategy="BigBase_Breakout_Position"),
    ])
