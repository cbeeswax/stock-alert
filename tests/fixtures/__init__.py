"""
Test fixtures and mocks for unit and integration tests.

This package provides:
- sample_data: Sample market data generators and test data builders
- mocks: Mock objects for external dependencies (email, files, market data)
"""

from .sample_data import (
    SampleDataBuilder,
    MockStrategy,
    PositionDataBuilder,
    MockDataProvider,
    SignalAssertions,
    get_sample_sp500_data,
    get_sample_position_data,
)

from .mocks import (
    MockMarketDataProvider,
    MockEmailClient,
    MockFileSystem,
    MockStrategyExecutor,
    MockPositionTracker,
    MockConfig,
    mock_environment,
    create_mock_market_data,
    create_mock_signal,
)

__all__ = [
    # From sample_data
    "SampleDataBuilder",
    "MockStrategy",
    "PositionDataBuilder",
    "MockDataProvider",
    "SignalAssertions",
    "get_sample_sp500_data",
    "get_sample_position_data",
    # From mocks
    "MockMarketDataProvider",
    "MockEmailClient",
    "MockFileSystem",
    "MockStrategyExecutor",
    "MockPositionTracker",
    "MockConfig",
    "mock_environment",
    "create_mock_market_data",
    "create_mock_signal",
]
