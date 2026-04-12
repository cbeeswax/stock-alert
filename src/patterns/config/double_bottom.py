"""
src/patterns/config/double_bottom.py
"""
from src.patterns.config.shared import *  # noqa: F401,F403

BOTTOM_TOLERANCE_PCT  = 0.03   # two lows within 3% of each other
MIN_BARS_BETWEEN      = 20     # at least 4 weeks between the two lows
MAX_BARS_BETWEEN      = 100    # at most ~20 weeks
NECKLINE_BREAK        = True   # require close above neckline (middle peak)
SECOND_LOW_HIGHER     = True   # second low should be ≥ first low (not lower)
