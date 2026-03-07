"""Data layer - fetching, caching, and calculating technical indicators"""

# Export commonly used functions
from .market import get_historical_data, get_market_cap
from .indicators import compute_ema_incremental, compute_rsi

__all__ = [
    "get_historical_data",
    "get_market_cap",
    "compute_ema_incremental",
    "compute_rsi",
]

