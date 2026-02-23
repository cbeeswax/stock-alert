"""Analysis - backtesting and performance metrics"""

from .metrics import calculate_r_multiple, calculate_win_rate, calculate_expectancy
from .diagnostics import diagnose_signal_count, diagnose_position_health

__all__ = [
    "calculate_r_multiple",
    "calculate_win_rate",
    "calculate_expectancy",
    "diagnose_signal_count",
    "diagnose_position_health",
]

