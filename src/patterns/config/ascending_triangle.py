"""
src/patterns/config/ascending_triangle.py
"""
from src.patterns.config.shared import *  # noqa: F401,F403

MIN_RESISTANCE_TOUCHES = 2    # flat ceiling needs ≥ 2 swing-high touches
MIN_SUPPORT_TOUCHES    = 2    # rising lows need ≥ 2 pivot lows
RESISTANCE_TOLERANCE   = 0.02 # swing highs within 2% of each other = flat ceiling
MIN_PATTERN_BARS       = 20   # at least 20 bars to form the triangle
MAX_PATTERN_BARS       = 100
