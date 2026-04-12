"""
src/patterns/config/flat_base.py
"""
from src.patterns.config.shared import *  # noqa: F401,F403

FLAT_MIN_BARS       = 25    # ≥ 5 weeks
FLAT_MAX_BARS       = 65    # ≤ 13 weeks
FLAT_MAX_DEPTH_PCT  = 0.15  # base depth ≤ 15% high to low
FLAT_MAX_WEEKLY_RANGE_PCT = 0.10  # tight weekly closes ≤ 10% range
