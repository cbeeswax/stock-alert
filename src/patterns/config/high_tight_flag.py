"""
src/patterns/config/high_tight_flag.py
"""
from src.patterns.config.shared import *  # noqa: F401,F403

# Pole
POLE_MIN_GAIN_PCT   = 1.0    # ≥ 100% gain from pole base to pole top
POLE_MAX_BARS       = 40     # pole forms in ≤ 40 trading days (~8 weeks)

# Flag
FLAG_MAX_BARS       = 25     # flag consolidation ≤ 25 bars (~5 weeks)
FLAG_MAX_DEPTH_PCT  = 0.25   # flag pulls back ≤ 25% from pole top
FLAG_MIN_DEPTH_PCT  = 0.05   # must pull back at least 5%

# Tightness bonus (higher quality_score)
FLAG_TIGHT_RANGE_PCT = 0.10  # weekly range ≤ 10% of pole top = tight flag
