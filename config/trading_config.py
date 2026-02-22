"""
Long-Term Position Trading Configuration
=========================================
Complete configuration for 7 long-term position strategies (60-120 day holds).
Target: 8-20 trades/year total, aiming for 2-10R per trade.

STRATEGY SUITE:
1. EMA_Crossover_Position
2. MeanReversion_Position
3. %B_MeanReversion_Position
4. High52_Position
5. BigBase_Breakout_Position
6. TrendContinuation_Position
7. RelativeStrength_Ranker_Position
"""

# =============================================================================
# GLOBAL POSITION TRADING SETTINGS
# =============================================================================

# Universal Filters (Applied to ALL active strategies)
UNIVERSAL_RS_MIN = 0.30               # Minimum +30% RS vs QQQ for ALL strategies
UNIVERSAL_ADX_MIN = 30                # Minimum ADX(14) >= 30 for strong trends
UNIVERSAL_VOLUME_MULT = 2.5           # Minimum 2.5x volume surge for ALL strategies
UNIVERSAL_ALL_MAS_RISING = True       # MA50, MA100, MA200 all must be rising
UNIVERSAL_QQQ_BULL_MA = 100           # QQQ > 100-MA (stronger than 200-MA)
UNIVERSAL_QQQ_MA_RISING_DAYS = 20     # QQQ MA100 must be rising over 20 days

# Risk Management
POSITION_INITIAL_EQUITY = 100000   # Starting equity for position sizing ($100k default)
POSITION_RISK_PER_TRADE_PCT = 2.0  # 2.0% of equity per trade (up from 1.5%)
POSITION_MAX_TOTAL = 20            # Max 20 total positions (focused on 3 strategies)

# Per-Strategy Position Limits (FOCUSED ON PROVEN WINNERS ONLY)
POSITION_MAX_PER_STRATEGY = {
    # ACTIVE STRATEGIES (1 proven winner)
    "RelativeStrength_Ranker_Position": 10,   # PROVEN: 48.5% WR, 2.52R, $497k profit
    "High52_Position": 0,                      # DISABLED: 33% WR, negative expectancy (even ultra-selective)
    "BigBase_Breakout_Position": 0,           # DISABLED: 10% WR, negative expectancy

    # DISABLED STRATEGIES (broken - churning or insufficient data)
    "EMA_Crossover_Position": 0,              # 1 trade only, -1.00R
    "TrendContinuation_Position": 0,          # 30.4% WR unacceptable, churning
    "MeanReversion_Position": 0,              # 0.26R avg, 135 trades churning
    "%B_MeanReversion_Position": 0,           # 0.05R avg, essentially breakeven

    # EXPERIMENTAL SHORT STRATEGIES (disabled for now)
    "ShortWeakRS_Retrace_Position": 0,        # Weak-RS trend shorts (bear/sideways)
    "LeaderPullback_Short_Position": 0,       # Leader pullback shorts (bull only)
    "MegaCap_WeeklySlide_Short": 0,           # Mega-cap weekly slide shorts (max 2 concurrent)
}

# Fallback for compatibility
POSITION_MAX_PER_STRATEGY_DEFAULT = 5

# Time Horizons
POSITION_MAX_DAYS_SHORT = 90       # Mean reversion styles (60-90 days)
POSITION_MAX_DAYS_LONG = 120       # Momentum/breakout styles (60-120 days)

# Partial Profits (30-50% at 2-2.5R)
POSITION_PARTIAL_ENABLED = True
POSITION_PARTIAL_SIZE = 0.3              # 30% (runner = 70%)
POSITION_PARTIAL_R_TRIGGER_LOW = 2.0     # Most strategies
POSITION_PARTIAL_R_TRIGGER_MID = 2.5     # High52, BigBase
POSITION_PARTIAL_R_TRIGGER_HIGH = 3.0    # RS_Ranker

# =============================================================================
# PYRAMIDING (ADD TO WINNERS)
# =============================================================================

POSITION_PYRAMID_ENABLED = True
POSITION_PYRAMID_R_TRIGGER = 1.5      # Add after +1.5R profit (FASTER - was 2.0)
POSITION_PYRAMID_SIZE = 0.5           # 50% of original position size
POSITION_PYRAMID_MAX_ADDS = 3         # Maximum 3 add-ons per position (INCREASED - was 2)
POSITION_PYRAMID_PULLBACK_EMA = 21    # Must pull back to 21-day EMA
POSITION_PYRAMID_PULLBACK_ATR = 1.0   # Within 1 ATR of EMA21

# =============================================================================
# STRATEGY PRIORITY (DEDUPLICATION)
# =============================================================================

STRATEGY_PRIORITY = {
    "BigBase_Breakout_Position": 1,           # Highest - rarest, biggest moves
    "RelativeStrength_Ranker_Position": 2,
    "TrendContinuation_Position": 3,
    "EMA_Crossover_Position": 4,
    "High52_Position": 5,
    "MeanReversion_Position": 6,
    "%B_MeanReversion_Position": 7,
}

# =============================================================================
# 1. EMA_CROSSOVER_POSITION (60-120 DAYS)
# =============================================================================

EMA_CROSS_POS_VOLUME_MULT = 1.5           # Volume ≥ 1.5x avg
EMA_CROSS_POS_STOP_ATR_MULT = 3.5         # Stop: entry - 3.5× ATR(14)
EMA_CROSS_POS_PARTIAL_R = 2.0             # Partial at 2R
EMA_CROSS_POS_PARTIAL_SIZE = 0.3          # 30% (runner = 70%)
EMA_CROSS_POS_TRAIL_MA = 100              # Trail with MA100 (NOT EMA!)
EMA_CROSS_POS_TRAIL_DAYS = 5              # 5 closes below MA100 to exit
EMA_CROSS_POS_MAX_DAYS = 120

# =============================================================================
# 2. MEANREVERSION_POSITION (60-90 DAYS)
# =============================================================================

MR_POS_RSI_OVERSOLD = 38                  # RSI14 < 38
MR_POS_RS_THRESHOLD = 0.15                # 6-mo RS > index +15%
MR_POS_STOP_ATR_MULT = 3.5                # Stop: entry - 3.5× ATR(14)
MR_POS_PARTIAL_R = 2.0                    # Partial at 2R (NO RSI exits!)
MR_POS_PARTIAL_SIZE = 0.3                 # 30% (runner = 70%)
MR_POS_TRAIL_MA = 50                      # Trail with MA50 (NOT EMA!)
MR_POS_TRAIL_DAYS = 5                     # 5 closes below MA50 to exit
MR_POS_MAX_DAYS = 90

# =============================================================================
# 3. %B_MEANREVERSION_POSITION (60-90 DAYS)
# =============================================================================

PERCENT_B_POS_OVERSOLD = 0.12             # %B < 0.12
PERCENT_B_POS_RSI_OVERSOLD = 38           # RSI14 < 38
PERCENT_B_POS_STOP_ATR_MULT = 3.5         # Stop: entry - 3.5× ATR(14)
PERCENT_B_POS_PARTIAL_R = 2.0             # Partial at 2R (NO %B exits!)
PERCENT_B_POS_PARTIAL_SIZE = 0.3          # 30% (runner = 70%)
PERCENT_B_POS_TRAIL_MA = 50               # Trail with MA50 (NOT EMA21!)
PERCENT_B_POS_TRAIL_DAYS = 5              # 5 closes below MA50 to exit
PERCENT_B_POS_MAX_DAYS = 90

# =============================================================================
# 4. HIGH52_POSITION (60-120 DAYS)
# =============================================================================

HIGH52_POS_RS_MIN = 0.30                  # Minimum 30% RS vs QQQ (LEADERS ONLY - was 0.20)
HIGH52_POS_VOLUME_MULT = 2.5              # Single-day ≥ 2.5× 50-day avg (CONVICTION - was 1.8 5-day avg)
HIGH52_POS_ADX_MIN = 30                   # Minimum ADX(14) >= 30 for momentum confirmation
HIGH52_POS_STOP_ATR_MULT = 4.5            # Stop: entry - 4.5× ATR(20) (WIDER - was 3.5)
HIGH52_POS_PARTIAL_R = 2.5                # Partial at 2.5R
HIGH52_POS_PARTIAL_SIZE = 0.3             # 30% (runner = 70%)
HIGH52_POS_TRAIL_MA = 100                 # Trail with 100-day MA (WIDER - was 50)
HIGH52_POS_TRAIL_DAYS = 8                 # 8 closes below to exit (MORE PATIENCE - was 3)
HIGH52_POS_MAX_DAYS = 150                 # Max 150 days (EXTENDED - was 120)

# =============================================================================
# 5. BIGBASE_BREAKOUT_POSITION (60-120 DAYS) - NEW
# =============================================================================

BIGBASE_MIN_WEEKS = 14                    # Minimum 14 weeks consolidation (BALANCED - was 16)
BIGBASE_MAX_RANGE_PCT = 0.22              # Max 22% range (HH-LL)/LL (LOOSER - was 0.20)
BIGBASE_RS_MIN = 0.15                     # Minimum 15% RS vs QQQ (STRONG - was 0.20)
BIGBASE_VOLUME_MULT = 1.5                 # 5-day avg ≥ 1.5× 50-day avg (SUSTAINED - was 1.8)
BIGBASE_STOP_ATR_MULT = 4.5               # Stop: entry - 4.5× ATR(20) (WIDER - was 3.5)
BIGBASE_PARTIAL_R = 4.0                   # Partial at 4R (HOME RUN - was 2.5R)
BIGBASE_PARTIAL_SIZE = 0.3                # 30% (runner = 70%)
BIGBASE_TRAIL_MA = 200                    # Trail with 200-day MA (WIDEST - was 50)
BIGBASE_TRAIL_DAYS = 10                   # 10 closes below to exit (MAX PATIENCE - was 4)
BIGBASE_MAX_DAYS = 180                    # Max 180 days (EXTENDED - was 120)

# =============================================================================
# 6. TRENDCONTINUATION_POSITION (60-90 DAYS) - NEW
# =============================================================================

TREND_CONT_MA_LOOKBACK = 150              # 150-day MA
TREND_CONT_MA_RISING_DAYS = 20            # MA rising over 20 days
TREND_CONT_RS_THRESHOLD = 0.25            # 6-mo RS > index +25%
TREND_CONT_RSI_MIN = 45                   # RSI14 ≥ 45 on pullback
TREND_CONT_PULLBACK_EMA = 21              # Pullback to 21-day EMA
TREND_CONT_PULLBACK_ATR = 1.0             # Within 1 ATR
TREND_CONT_STOP_ATR_MULT = 3.5            # Stop: entry - 3.5× ATR
TREND_CONT_PARTIAL_R = 2.0                # Partial at 2R
TREND_CONT_PARTIAL_SIZE = 0.3             # 30% (runner = 70%)
TREND_CONT_TRAIL_MA = 50                  # Trail with MA50 (NOT EMA34!)
TREND_CONT_TRAIL_DAYS = 5                 # 5 closes below MA50 to exit
TREND_CONT_MAX_DAYS = 90

# =============================================================================
# 7. RELATIVESTRENGTH_RANKER_POSITION (60-120 DAYS) - NEW
# =============================================================================

RS_RANKER_SECTORS = ["Information Technology", "Communication Services"]
RS_RANKER_TOP_N = 10                      # Take top 10 RS stocks daily
RS_RANKER_RS_THRESHOLD = 0.30             # RS > +30% vs QQQ
RS_RANKER_STOP_ATR_MULT = 4.5             # Stop: entry - 4.5× ATR(20) (WIDER - was 3.5)
RS_RANKER_PARTIAL_R = 3.0                 # Partial at 3R (highest)
RS_RANKER_PARTIAL_SIZE = 0.3              # 30% (runner = 70%)
RS_RANKER_TRAIL_MA = 100                  # Trail with 100-day MA (WIDER - was 50)
RS_RANKER_TRAIL_DAYS = 10                 # 10 closes below to exit (MORE PATIENCE - was 3)
RS_RANKER_MAX_DAYS = 150                  # Max 150 days (EXTENDED - was 120)

# =============================================================================
# INDEX REGIME FILTERS
# =============================================================================

# Primary Index (QQQ for tech-focused strategies)
REGIME_INDEX = "QQQ"
REGIME_BULL_MA = 200                      # Bullish: close > 200-day MA
REGIME_BULL_MA_RISING_DAYS = 0            # MA rising (0 = just above)
REGIME_BEAR_MA = 200                      # Bearish: close < 200-day MA
REGIME_BEAR_MA_FALLING_DAYS = 0           # MA falling

# Alternative Index (SPY for broad market)
REGIME_INDEX_ALT = "SPY"

# =============================================================================
# LIQUIDITY & UNIVERSE FILTERS
# =============================================================================

MIN_LIQUIDITY_USD = 30_000_000           # $30M avg 20-day dollar volume
MIN_PRICE = 10.0                         # Minimum $10 per share
MAX_PRICE = 999999.0                     # No max price

# Sector filters (for RS_Ranker and other tech strategies)
TECH_SECTORS = ["Information Technology", "Communication Services"]

# =============================================================================
# BACKTEST SETTINGS
# =============================================================================

BACKTEST_START_DATE = "2022-01-01"
BACKTEST_SCAN_FREQUENCY = "B"             # Daily business days
                                          # Options: "B" (daily), "W-MON", "W-FRI"

# =============================================================================
# LEGACY SETTINGS (DEPRECATED - KEPT FOR COMPATIBILITY)
# =============================================================================

# Old short-term settings - no longer used
CAPITAL_PER_TRADE = 20_000               # Replaced by position sizing calc
RISK_REWARD_RATIO = 2                    # Replaced by strategy-specific R targets
MAX_HOLDING_DAYS = 120                   # Replaced by strategy-specific max days
PARTIAL_EXIT_ENABLED = True              # Now POSITION_PARTIAL_ENABLED
PARTIAL_EXIT_SIZE = 0.4                  # Now POSITION_PARTIAL_SIZE
MAX_TRADES_PER_SCAN = 10                 # Replaced by per-strategy limits
MAX_OPEN_POSITIONS = 25                  # Replaced by POSITION_MAX_TOTAL
REQUIRE_CONFIRMATION_BAR = False         # Position trading enters immediately
MIN_HOLDING_DAYS = 0                     # No minimum for position trading
CATASTROPHIC_LOSS_THRESHOLD = 999        # Stop loss only
MAX_ENTRY_GAP_PCT = 999                  # No gap filter for position trading

# Legacy pre_buy_check.py constants (for backward compatibility)
ADX_THRESHOLD = 30                       # Now UNIVERSAL_ADX_MIN
RSI_MIN = 30                             # Old RSI filter (not used in position trading)
RSI_MAX = 70                             # Old RSI filter (not used in position trading)
VOLUME_MULTIPLIER = 2.5                  # Now UNIVERSAL_VOLUME_MULT
PRICE_ABOVE_EMA20_MIN = 0.95             # Old EMA filter (not used in position trading)
PRICE_ABOVE_EMA20_MAX = 1.10             # Old EMA filter (not used in position trading)

# =============================================================================
# NOTES
# =============================================================================

"""
LONG-TERM POSITION TRADING APPROACH:
------------------------------------
• Risk: 1.5% per trade (vs 1% short-term)
• Holding: 60-120 days (vs 3-60 days)
• Frequency: 8-20 trades/year (vs 50-200/year)
• Target: 2-10R per trade (vs 0.5-2R)
• Positions: Max 25 total, 5 per strategy
• Pyramiding: Add 50% size after +2R on pullback to EMA21

STRATEGY CHARACTERISTICS:
-------------------------
1. EMA_Crossover_Position: Trend following with index confirmation
2. MeanReversion_Position: Long-term uptrend oversold bounces
3. %B_MeanReversion_Position: Bollinger Band oversold in uptrends
4. High52_Position: Top RS breakouts to new highs
5. BigBase_Breakout_Position: Multi-month base breakouts (RARE)
6. TrendContinuation_Position: Pullback entries in strong trends
7. RelativeStrength_Ranker_Position: Top 10 RS daily ranking system

EXPECTED OUTCOMES:
------------------
• 8-20 total trades per year
• 35-50% win rate
• 2-10R average per trade
• 60-120 day average holding period
• Target: 100k → 300-400k over 3-4 years
"""

# =============================================================================
# SHORT STRATEGY CONFIGURATION - REGIME-BASED (EXPERIMENTAL)
# =============================================================================

"""
SHORT STRATEGY: ShortWeakRS_Retrace_Position (Regime-Based)
===========================================================
Adaptive short strategy with different parameters for BULL, SIDEWAYS, and BEAR regimes.

REGIME CLASSIFICATION:
----------------------
1. BULL: QQQ > 200-MA AND 200-MA rising
   - Most selective shorts (hedge/tactical only)
   - Tightest stops, fastest exits, highest RSI threshold

2. SIDEWAYS: QQQ ADX < 25 (low trend strength)
   - Range-bound mean reversion
   - Medium selectivity, quick profit-taking

3. BEAR: QQQ < 200-MA AND 200-MA declining AND ADX >= 25
   - Primary offensive shorting
   - Broadest participation, widest stops, longer holds

ADAPTIVE BEHAVIOR:
------------------
• BULL regime: Only short extremely weak names (RS ≤ -15%), very overbought (RSI 70-80)
  Exit fast (1.5R partial, 20d early exit, 30d max)

• SIDEWAYS regime: Short weak names (RS ≤ -10%), moderate overbought (RSI 65-75)
  Quick profit-taking (1.2R partial, 15d early exit, 20d max)

• BEAR regime: Broadly short weak names (RS ≤ -5%), normal overbought (RSI 55-70)
  Let winners run (2.0R partial, 30d early exit, 45d max)
"""

# Main switch
SHORT_ENABLED = False

# Portfolio limits (apply across all regimes)
SHORT_MAX_POSITIONS = 5                 # Max 5 concurrent short positions
SHORT_MAX_EQUITY_PCT = 0.30             # Max 30% of equity in shorts
SHORT_RISK_PER_TRADE_PCT = 1.5          # 1.5% risk per short (lower than longs)

# =============================================================================
# REGIME CLASSIFICATION PARAMETERS
# =============================================================================

SHORT_REGIME_INDEX = "QQQ"              # Index to classify (QQQ or SPY)
SHORT_REGIME_MA_PERIOD = 200            # Long-term trend MA
SHORT_REGIME_SLOPE_LOOKBACK = 20        # Slope window (days)

SHORT_REGIME_ADX_PERIOD = 14            # ADX calculation period
SHORT_REGIME_ADX_SMOOTH = 14            # ADX smoothing period
SHORT_REGIME_SIDEWAYS_ADX_MAX = 25      # ADX threshold for sideways market

# Common entry parameters (apply to all regimes)
SHORT_REJECTION_MA = 50                 # Rally to 50-MA rejection point
SHORT_REJECTION_TOLERANCE = 0.02        # Within 2% of 50-MA

# =============================================================================
# BULL REGIME CONFIG (Extremely Selective - Hedge/Tactical Only)
# =============================================================================

SHORT_CFG_BULL = {
    "RS_MAX": -0.15,                    # Stock must underperform QQQ by ≥15%

    "MA_PERIOD": 100,
    "MA_DECLINING_DAYS": 5,             # ma100 declining over 5 days

    "REQUIRE_WICK": False,              # Not required initially
    "WICK_MIN": 0.01,                   # 1% upper wick if enabled
    "REQUIRE_LOWER_HIGH": False,        # Not required initially

    "RSI_MIN": 70,                      # Classic overbought
    "RSI_MAX": 80,

    "MAX_ATR_PCT": 0.05,                # ATR/price ≤ 5%
    "MIN_VOL_MULT": 1.0,                # Volume ≥ 1.0× 50d avg

    "STOP_ATR_MULT": 1.5,               # Tight stop
    "STOP_BUFFER_ATR": 0.25,

    "PARTIAL_R": 1.5,                   # Fast profit-taking
    "PARTIAL_SIZE": 0.5,

    "TRAIL_EMA": 20,
    "TRAIL_DAYS": 3,
    "TRAIL_ONLY_AFTER_PARTIAL": True,

    "EARLY_EXIT_DAYS": 20,              # Exit if not working by day 20
    "EARLY_EXIT_R_THRESHOLD": 1.0,      # Must be +1R to stay past 20 days

    "MAX_DAYS": 30,                     # Quick exits in bull market
}

# =============================================================================
# SIDEWAYS REGIME CONFIG (Range-Trade Mean Reversion)
# =============================================================================

SHORT_CFG_SIDEWAYS = {
    "RS_MAX": -0.10,                    # Broader participation

    "MA_PERIOD": 100,
    "MA_DECLINING_DAYS": 0,             # Allow flat ma100

    "REQUIRE_WICK": False,
    "WICK_MIN": 0.0,
    "REQUIRE_LOWER_HIGH": False,

    "RSI_MIN": 65,
    "RSI_MAX": 75,

    "MAX_ATR_PCT": 0.07,                # ATR/price ≤ 7%
    "MIN_VOL_MULT": 1.0,

    "STOP_ATR_MULT": 1.5,
    "STOP_BUFFER_ATR": 0.25,

    "PARTIAL_R": 1.2,                   # Very fast profit-taking
    "PARTIAL_SIZE": 0.5,

    "TRAIL_EMA": 20,
    "TRAIL_DAYS": 3,
    "TRAIL_ONLY_AFTER_PARTIAL": True,

    "EARLY_EXIT_DAYS": 15,              # Quick exits in range
    "EARLY_EXIT_R_THRESHOLD": 0.5,      # Lower threshold

    "MAX_DAYS": 20,                     # Very short holds
}

# =============================================================================
# BEAR REGIME CONFIG (Primary Offensive Shorting)
# =============================================================================

SHORT_CFG_BEAR = {
    "RS_MAX": -0.05,                    # Broad participation

    "MA_PERIOD": 100,
    "MA_DECLINING_DAYS": 10,            # ma100 declining over 10 days

    "REQUIRE_WICK": False,
    "WICK_MIN": 0.0,
    "REQUIRE_LOWER_HIGH": False,

    "RSI_MIN": 55,                      # Lower threshold in bear market
    "RSI_MAX": 70,

    "MAX_ATR_PCT": 0.10,                # ATR/price ≤ 10% (allow more volatility)
    "MIN_VOL_MULT": 1.0,

    "STOP_ATR_MULT": 2.0,               # Wider stop
    "STOP_BUFFER_ATR": 0.25,

    "PARTIAL_R": 2.0,                   # Let winners run
    "PARTIAL_SIZE": 0.5,

    "TRAIL_EMA": 20,
    "TRAIL_DAYS": 3,
    "TRAIL_ONLY_AFTER_PARTIAL": True,

    "EARLY_EXIT_DAYS": 30,
    "EARLY_EXIT_R_THRESHOLD": 1.0,

    "MAX_DAYS": 45,                     # Longer holds in bear market
}

# =============================================================================
# LEADER PULLBACK SHORT CONFIG (Bull/Sideways Markets - Tactical Overlay)
# =============================================================================

"""
LEADER PULLBACK SHORT: Catch exhaustion in extended leaders
============================================================
Targets strong stocks (RS ≥ +5%) that are extended above MA50 and showing
exhaustion at resistance. This is a TACTICAL OVERLAY that runs in BULL and
SIDEWAYS markets and is completely separate from the weak-RS trend shorts.

CONCEPT:
--------
• Active in BULL/SIDEWAYS regimes (configurable)
• Target LEADERS (RS ≥ +5%), not laggards
• Stock must be extended (≥15% above MA50)
• RSI overbought (>70) then crosses down
• Failed breakout at resistance (high > prior high, close back below)
• Enter on first close below 20-day MA

RISK PROFILE:
-------------
• Smaller size: 0.5% risk (vs 1.5% for trend shorts)
• Max 2 positions (tactical overlay, not core strategy)
• Fast exits: 15 day max hold
• Quick profit-taking: 1.5R partial

EXAMPLES:
---------
• MSFT rallies 20% in 2 months, extends 18% above MA50, fails breakout at $420
• ORCL runs to new highs, RSI 78, fails to hold breakout, closes below 20-MA
• NVDA parabolic move exhausts at $500, closes below 20-MA after failed breakout
"""

LEADER_SHORT_CFG_BULL = {
    # Strategy control
    "ENABLED": True,                    # Only active when regime == "bull"
    "DEBUG_MODE": False,                # Set to True for debugging (disables context & variants)

    # =============================================================================
    # UNIVERSE FILTERS (Large, liquid leaders only)
    # =============================================================================
    "MIN_MARKET_CAP": 20_000_000_000,   # Min $20B market cap (Perplexity: large cap)
    "MIN_DOLLAR_VOLUME": 100_000_000,   # Min $100M daily dollar volume (Perplexity: high liquidity)
    "MIN_PRICE": 30,                    # Min $30 price (avoid low-price stocks)

    # Sector whitelist (offensive/cyclical sectors that lead and fall hard)
    "SECTOR_WHITELIST": [
        "Technology",
        "Communication Services",
        "Consumer Discretionary",
        "Financials",              # Banks, brokers, asset managers only
        "Industrials",             # Cyclical industrials
    ],

    # Sector blacklist (defensive sectors - avoid slow movers)
    "SECTOR_BLACKLIST": [
        "Energy",                  # e.g., CVX - too slow, mean-reverting
        "Consumer Staples",        # Defensive
        "Utilities",               # Defensive, low volatility
        "Real Estate",             # REITs - different dynamics
        "Healthcare",              # Too defensive (e.g., MCK)
        "Materials",               # Gold miners (e.g., NEM), commodities
    ],

    # =============================================================================
    # LEADER CONTEXT (Relative strength)
    # =============================================================================
    "RS_MIN": 0.00,                     # Baseline RS (will use percentile instead)
    "RS_PERCENTILE_MIN": 80,            # Top 20% relative strength (Perplexity: >= 80)
    "RS_LOOKBACK": 100,                 # 100-day RS calculation

    # =============================================================================
    # HISTORICAL EXTENSION (Must have been extended recently)
    # =============================================================================
    "EXTENSION_MA50": 50,
    "EXTENSION_MA100": 100,
    "EXTENSION_HISTORICAL_MIN_MA50": 1.08,  # Was ≥ 8% above MA50 in last 30 bars
    "EXTENSION_HISTORICAL_MIN_MA100": 1.12, # OR was ≥ 12% above MA100 in last 30 bars
    "EXTENSION_LOOKBACK": 30,           # Check last 30 bars for extension

    # Current bar: just need to be above MAs (not hugely extended)
    "EXTENSION_CURRENT_MIN_MA50": 1.00, # Close >= MA50
    "EXTENSION_CURRENT_MIN_MA100": 1.00,# OR close >= MA100

    # =============================================================================
    # LIQUIDITY ZONE DETECTION (Consolidation before breakdown)
    # =============================================================================
    "ZONE_LOOKBACK": 20,                # Last 20 bars to define zone high/low
    "ZONE_COMPRESSION_ATR_MULT": 10.0,  # Zone range must be <= 10 * ATR20 (loose filter)
    "ZONE_MIN_BARS": 0,                 # Keep disabled - too strict
    "ZONE_CONSOLIDATION_THRESHOLD": 0.8,# Bar range < 0.8 * ATR20 to count as consolidating

    # =============================================================================
    # ENTRY SIGNALS (Flexible OR-based variants)
    # =============================================================================

    # CORE CONDITIONS (always required):
    # 1. close < zone_low (zone break)
    # 2. volume_today >= 1.2 * avgVol20 (base volume requirement)
    # 3. Not a hammer (close not in top 30% of range)

    "CORE_VOLUME_MULT": 1.2,            # Today's volume >= 1.2x avg (core requirement)

    # ENTRY VARIANTS (need core + ANY ONE of these):

    # Variant A: Core only (simplest - just zone break with volume)
    "VARIANT_A_ENABLED": True,

    # Variant B: Core + impulsive weakness
    "VARIANT_B_ENABLED": True,
    "GAP_BELOW_ZONE": True,             # Gap open below zone_low
    "WIDE_RANGE_ATR_MULT": 1.2,         # True range >= 1.2 * ATR20
    "CLOSE_BELOW_OPEN": True,           # Red bar (close < open)

    # Variant C: Core + big volume spike (RSI already in context, no need to duplicate)
    "VARIANT_C_ENABLED": True,
    "RSI_PERIOD": 14,
    "RSI_CLIMAX": 65,                   # Used in context filter (not variant C)
    "RSI_LOOKBACK": 20,                 # Used in context filter (not variant C)
    "BIG_VOLUME_MULT": 1.5,             # Today's volume >= 1.5x avg

    # Reject hammer reversals (applies to all variants)
    "REJECT_HAMMER": True,              # Reject if close in top 30% of range
    "HAMMER_THRESHOLD": 0.70,           # (close - low) / (high - low) > 0.70

    # =============================================================================
    # STOP PLACEMENT (Logical level above zone)
    # =============================================================================
    "STOP_ABOVE_ZONE_HIGH": True,       # Initial stop above zone_high
    "STOP_BUFFER_PCT": 0.01,            # 1% buffer above zone_high
    "STOP_ALSO_MA20": True,             # Also consider MA20 for stop
    "STOP_ALSO_SWING_HIGH": True,       # Also consider recent swing high

    # =============================================================================
    # EXITS (Keep existing - working well)
    # =============================================================================
    "PARTIAL_R": 2.0,                   # Take 50% off at +2R
    "PARTIAL_SIZE": 0.5,                # 50% partial (runner = 50%)

    "TRAIL_EMA": None,                  # DISABLED - trail cuts winners
    "TRAIL_DAYS": None,
    "TRAIL_ATR_BUFFER": None,

    "EARLY_EXIT_DAYS": 20,              # Exit at 20d if R <= 0
    "EARLY_EXIT_R_THRESHOLD": 0.0,      # Must be profitable to continue

    "MAX_DAYS": 40,                     # Hard time stop at 40 days

    # Portfolio limits
    "MAX_POSITIONS": 10,                # Max 3 concurrent (Perplexity: 2-3)
    "RISK_PER_TRADE_PCT": 0.35,         # 0.25-0.5% risk per trade (Perplexity recommendation)
}

# Allowed regimes for leader pullback shorts
LEADER_SHORT_ALLOWED_REGIMES = ("bull", "sideways")

# Strategy priority (lowest - shorts filled after all longs)
STRATEGY_PRIORITY["ShortWeakRS_Retrace_Position"] = 100
STRATEGY_PRIORITY["LeaderPullback_Short_Position"] = 101  # Even lower (fill last)
STRATEGY_PRIORITY["MegaCap_WeeklySlide_Short"] = 102  # Lowest priority

# ============================================================================
# Strategy 10: MegaCap Weekly Slide SHORT (New Module)
# ============================================================================
MEGACAP_WEEKLY_SLIDE_CFG = {
    # Strategy control
    "ENABLED": False,  # Disabled with all other short strategies
    "DEBUG_MODE": False,

    # Universe (hard-coded mega-caps)
    "SYMBOLS": ["MSFT", "ORCL", "META", "AAPL", "NVDA", "GOOGL", "AMZN", "AVGO", "ADBE", "CRM"],
    "MIN_PRICE": 30,
    "MIN_DOLLAR_VOLUME": 100_000_000,  # $100M

    # Weekly context indicators
    "WEEKLY_MA10": 10,
    "WEEKLY_MA20": 20,
    "WEEKLY_RSI_PERIOD": 14,
    "WEEKLY_RSI_THRESHOLD": 50,
    "WEEKLY_OFF_HIGH_PCT": 0.90,  # 10% off 52-week high
    "WEEKLY_HIGH_LOOKBACK": 52,   # weeks

    # Daily entry conditions
    "DAILY_MA20": 20,
    "DAILY_LOW_LOOKBACK": 10,  # days (exclude today)
    "DAILY_VOLUME_MULT": 1.1,
    "DAILY_VOLUME_PERIOD": 20,

    # Position sizing & limits
    "RISK_PER_TRADE_PCT": 0.5,  # 0.5% risk
    "MAX_POSITIONS": 2,  # Max 2 concurrent in this module
    "ONE_PER_SYMBOL": True,
    "COOLDOWN_DAYS": 10,  # Days to wait after exit before re-entering same symbol

    # Stop placement
    "STOP_SWING_HIGH_LOOKBACK": 10,  # days
    "STOP_BUFFER_PCT": 0.01,  # 1% above stop level

    # Exits
    "PARTIAL_R": 2.0,
    "PARTIAL_SIZE": 0.5,  # 50% at +2R
    "BREAKEVEN_AFTER_PARTIAL": True,
    "MAX_DAYS": 50,  # Hard time stop
    "TRAIL_EMA": None,  # No trailing stop
    "EARLY_EXIT_DAYS": None,  # No 20d early exit
}
