"""
src/patterns/config/cup_and_handle.py
"""
from src.patterns.config.shared import *  # noqa: F401,F403

# Cup shape
CUP_MIN_BARS       = 30     # minimum cup width in trading days
CUP_MAX_BARS       = 150    # maximum cup width
CUP_MAX_DEPTH_PCT  = 0.35   # cup depth must be ≤ 35% from lip to bottom

# Handle shape
HANDLE_MAX_BARS    = 15     # handle width ≤ 15 bars
HANDLE_MAX_DEPTH_PCT = 0.12 # handle pullback ≤ 12% from cup lip
HANDLE_MIN_BARS    = 3      # handle needs at least 3 bars

# Breakout
PIVOT_PRICE        = "cup_lip"  # breakout above the cup's right-side high
