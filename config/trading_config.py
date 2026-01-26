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

    # EXPERIMENTAL SHORT STRATEGY (disabled by default - testing phase)
    "ShortWeakRS_Retrace_Position": 5,        # EXPERIMENTAL: Not yet backtested
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
BACKTEST_SCAN_FREQUENCY = "W-MON"         # Weekly Monday (position trading)
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
# SHORT STRATEGY CONFIGURATION (EXPERIMENTAL - DISABLED BY DEFAULT)
# =============================================================================

"""
SHORT STRATEGY: ShortWeakRS_Retrace_Position
============================================
Counter-trend short strategy for bull/sideways markets.
Targets weak stocks (low RS) that rally into resistance and fail.

CONCEPT:
--------
• Only run in bull/sideways markets (not deep bear)
• Short weak stocks (RS ≤ -15%) that rally to 50-MA and reject
• Take partial profits at +2.5R, trail remainder with EMA21
• Hard time stop at 45 days (don't sit short forever in bull market)
• Max 30% portfolio exposure to shorts (remain long-biased)

ENTRY CONDITIONS:
-----------------
1. Market: QQQ above rising 100-MA (bull/sideways)
2. Stock: Price < declining 100-MA (downtrend)
3. Weakness: RS ≤ -15% vs QQQ (underperforming)
4. Rally: High touches 50-MA but close below
5. Rejection: RSI 55-65 (mild overbought in downtrend)

EXIT CONDITIONS:
----------------
1. Stop Loss: Above recent swing high or 50-MA + 3× ATR
2. Partial: 40% at +2.5R
3. Trail: 3 consecutive closes above EMA21 (inverted)
4. Time: Hard stop at 45 days

RISK MANAGEMENT:
----------------
• Lower risk per trade: 1.5% (vs 2.0% for longs)
• Max positions: 5 concurrent shorts
• Max exposure: 30% of equity
• No shorts on tickers already held long
"""

# Main switch (DISABLED by default - enable only after thorough backtesting)
SHORT_ENABLED = True

# Portfolio limits
SHORT_MAX_POSITIONS = 5                 # Max 5 concurrent short positions
SHORT_MAX_EQUITY_PCT = 0.30             # Max 30% of equity in shorts (remain long-biased)
SHORT_RISK_PER_TRADE_PCT = 1.5          # 1.5% risk per short (lower than longs)

# Entry filters
SHORT_RS_MAX = -0.15                    # RS ≤ -15% (weak vs QQQ)
SHORT_MA_PERIOD = 100                   # Price < declining 100-MA
SHORT_MA_DECLINING_DAYS = 10            # MA must be declining over 10 days
SHORT_REJECTION_MA = 50                 # Rally to 50-MA rejection point
SHORT_REJECTION_TOLERANCE = 0.02        # Within 2% of 50-MA counts as "touch"
SHORT_REJECTION_RSI_MIN = 55            # RSI 55-65 for rally rejection
SHORT_REJECTION_RSI_MAX = 65

# Position sizing & stops
SHORT_STOP_ATR_MULT = 3.0               # Stop: entry + 3× ATR(14) (tighter than longs)
SHORT_STOP_BUFFER_ATR = 0.5             # Additional buffer above swing high

# Exit rules
SHORT_PARTIAL_R = 2.5                   # Partial profit at +2.5R
SHORT_PARTIAL_SIZE = 0.4                # 40% partial (more aggressive than longs)
SHORT_TRAIL_EMA = 21                    # Trail with 21-EMA
SHORT_TRAIL_DAYS = 3                    # Exit if 3 consecutive closes above EMA21
SHORT_MAX_DAYS = 45                     # Hard time stop at 45 days

# Strategy priority (lowest - shorts filled after all longs)
STRATEGY_PRIORITY["ShortWeakRS_Retrace_Position"] = 100
