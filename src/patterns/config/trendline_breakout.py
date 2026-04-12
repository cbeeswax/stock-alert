"""
src/patterns/config/trendline_breakout.py
"""
from src.patterns.config.shared import *  # noqa: F401,F403

MIN_TRENDLINE_TOUCHES = 2     # at least 2 swing-high touches on the descending line
MAX_TRENDLINE_BARS    = 120   # trendline spans at most ~6 months
MIN_TRENDLINE_BARS    = 20    # at least 4 weeks of downtrend
SLOPE_MAX             = -0.001  # line must be sloping downward (negative slope per bar)
