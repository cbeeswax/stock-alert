"""
Sector filtering utilities for strategy-specific universe selection
This module re-exports from utils for backward compatibility during migration.
"""
from utils.sector_utils import get_sp500_data, get_tickers_by_sector, get_ticker_sector

__all__ = ["get_sp500_data", "get_tickers_by_sector", "get_ticker_sector"]
