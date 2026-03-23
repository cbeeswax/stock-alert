"""
src/ta — Technical Analysis Engine
====================================
Pure math library. No I/O, no config, no trading logic.
All functions are stateless and fully unit-testable in isolation.

Usage:
    from src.ta.indicators.momentum import rsi, smoothed_rsi
    from src.ta.indicators.moving_averages import ema, sma
    from src.ta.indicators.volatility import atr, bollinger_bands
    from src.ta.indicators.trend import adx
    from src.ta.indicators.gaps import gap_pct, is_gap_up, is_gap_down
    from src.ta.timeframes import get_weekly_trend
"""
from src.ta.indicators.moving_averages import ema, sma
from src.ta.indicators.momentum import rsi, smoothed_rsi
from src.ta.indicators.volatility import atr, atr_latest, bollinger_bands, percent_b
from src.ta.indicators.trend import adx, adx_latest
from src.ta.indicators.gaps import gap_pct, is_gap_up, is_gap_down, gap_fill_level

__all__ = [
    "ema", "sma",
    "rsi", "smoothed_rsi",
    "atr", "atr_latest", "bollinger_bands", "percent_b",
    "adx", "adx_latest",
    "gap_pct", "is_gap_up", "is_gap_down", "gap_fill_level",
]
