"""
Pytest configuration and shared fixtures for all tests.

This module provides:
- Common pytest fixtures for unit and integration tests
- Mock data generators for testing strategies and scanning
- Database and file fixtures for isolated testing
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import json
import tempfile

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


# ============================================================================
# SESSION-LEVEL FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def test_data_dir():
    """Provide path to test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def project_root():
    """Provide path to project root."""
    return Path(__file__).parent.parent


# ============================================================================
# SAMPLE DATA GENERATORS
# ============================================================================

@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing."""
    dates = pd.date_range(start="2023-01-01", periods=252, freq="B")
    data = {
        "Date": dates,
        "Open": np.random.uniform(100, 150, 252),
        "High": np.random.uniform(150, 160, 252),
        "Low": np.random.uniform(90, 100, 252),
        "Close": np.random.uniform(100, 150, 252),
        "Volume": np.random.randint(1000000, 10000000, 252),
    }
    df = pd.DataFrame(data)
    df["Close"] = df["Close"].rolling(window=5).mean().fillna(df["Close"])
    return df


@pytest.fixture
def sample_price_series():
    """Generate a simple price series for indicator testing."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="B")
    prices = 100 + np.cumsum(np.random.normal(0, 1, 100))
    return pd.DataFrame({
        "Date": dates,
        "Close": prices
    })


@pytest.fixture
def sample_sp500_tickers():
    """Generate sample S&P 500 tickers for testing."""
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK.B", "JNJ", "V",
        "MA", "PG", "UNH", "HD", "MCD",
        "NFLX", "PYPL", "AMD", "CRM", "ADBE"
    ]


@pytest.fixture
def sample_portfolio_data():
    """Generate sample portfolio data for position tracking."""
    return {
        "AAPL": {
            "entry_price": 150.00,
            "entry_date": datetime.now() - timedelta(days=10),
            "strategy": "RelativeStrength_Ranker_Position",
            "stop_loss": 145.00,
            "target": 165.00,
            "max_days": 150
        },
        "MSFT": {
            "entry_price": 340.00,
            "entry_date": datetime.now() - timedelta(days=5),
            "strategy": "High52_Position",
            "stop_loss": 330.00,
            "target": 360.00,
            "max_days": 150
        },
        "GOOGL": {
            "entry_price": 140.00,
            "entry_date": datetime.now() - timedelta(days=3),
            "strategy": "BigBase_Breakout_Position",
            "stop_loss": 135.00,
            "target": 155.00,
            "max_days": 100
        }
    }


# ============================================================================
# MOCK OBJECTS & UTILITIES
# ============================================================================

@pytest.fixture
def mock_market_data(sample_ohlcv_data):
    """Create mock market data with OHLCV values."""
    return sample_ohlcv_data


@pytest.fixture
def temp_json_file():
    """Create a temporary JSON file for testing file I/O."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({}, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Date,Close,Volume\n2023-01-01,100,1000000\n")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


# ============================================================================
# CONFIGURATION FIXTURES
# ============================================================================

@pytest.fixture
def test_config():
    """Provide test configuration values."""
    return {
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


# ============================================================================
# STRATEGY TESTING FIXTURES
# ============================================================================

@pytest.fixture
def relative_strength_params():
    """Provide parameters for RelativeStrength strategy testing."""
    return {
        "lookback_weeks": 52,
        "ma_period": 50,
        "rsi_period": 14,
        "rsi_threshold": 40,
        "ma_offset_pct": 0.02,
    }


@pytest.fixture
def high52_params():
    """Provide parameters for High52 strategy testing."""
    return {
        "lookback_weeks": 52,
        "bb_length": 20,
        "bb_std": 2,
        "ma_period": 50,
    }


@pytest.fixture
def bigbase_params():
    """Provide parameters for BigBase strategy testing."""
    return {
        "lookback_weeks": 52,
        "consolidation_length": 10,
        "min_consolidation_length": 5,
        "bb_length": 20,
        "bb_std": 2,
    }


# ============================================================================
# MARKER REGISTRATION
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test (deselect with '-m \"not unit\"')"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "strategy: mark test as strategy-specific"
    )
