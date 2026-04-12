"""
src/patterns/config/shared.py
==============================
Shared breakout confirmation rules and trade model defaults.
All six pattern detectors import from here first, then override as needed.
"""

# ── Breakout confirmation ─────────────────────────────────────────────────────
BREAKOUT_PIVOT_CLEARANCE = 1.005   # close must be > pivot × this
BREAKOUT_VOL_MULT        = 1.8     # volume must be ≥ avg_vol_20 × this
BREAKOUT_CLOSE_POS_MIN   = 0.7     # close in top 30% of bar's range

# ── Entry / invalidation ─────────────────────────────────────────────────────
ENTRY_MODE          = "next_open"   # "next_open" | "breakout_close"
INVALIDATION_BARS   = 3             # close back below pivot within N bars → invalid

# ── Trade model ──────────────────────────────────────────────────────────────
RISK_PER_TRADE_PCT  = 0.5           # % of equity risked per trade (0.5–1.0)
PARTIAL_EXIT_PCT    = 15.0          # take partial profits at +15%
PARTIAL_SIZE        = 0.5           # sell this fraction at partial target
TRAIL_LOOKBACK_BARS = 10            # trailing stop = N-bar low
TRAIL_ATR_MULT      = 2.0           # or 2×ATR (whichever is tighter)
MAX_HOLDING_DAYS    = 40
SLIPPAGE_BPS        = 10            # basis points
COMMISSION_PER_SIDE = 0.0           # $ per share — set to broker rate

# ── Pivot engine ─────────────────────────────────────────────────────────────
SWING_K             = 5             # N-bar pivot window (k=5 for daily)
