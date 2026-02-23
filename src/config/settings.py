"""
Central Trading Configuration
=============================
Single source of truth for all trading parameters.
Consolidates all strategy, risk, and regime settings.
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
POSITION_RISK_PER_TRADE_PCT = 2.0  # 2.0% of equity per trade
POSITION_MAX_TOTAL = 20            # Max 20 total positions

# Per-Strategy Position Limits
POSITION_MAX_PER_STRATEGY = {
    "RelativeStrength_Ranker_Position": 10,   # ACTIVE: 48.5% WR, 2.52R, $497k profit
    "High52_Position": 0,                      # DISABLED
    "BigBase_Breakout_Position": 0,           # DISABLED
    "EMA_Crossover_Position": 0,              # DISABLED
    "TrendContinuation_Position": 0,          # DISABLED
    "MeanReversion_Position": 0,              # DISABLED
    "%B_MeanReversion_Position": 0,           # DISABLED
    "ShortWeakRS_Retrace_Position": 0,        # DISABLED
    "LeaderPullback_Short_Position": 0,       # DISABLED
    "MegaCap_WeeklySlide_Short": 0,           # DISABLED
}

POSITION_MAX_PER_STRATEGY_DEFAULT = 5

# Time Horizons
POSITION_MAX_DAYS_SHORT = 90       # Mean reversion styles (60-90 days)
POSITION_MAX_DAYS_LONG = 120       # Momentum/breakout styles (60-120 days)

# Partial Profits
POSITION_PARTIAL_ENABLED = True
POSITION_PARTIAL_SIZE = 0.3              # 30% (runner = 70%)
POSITION_PARTIAL_R_TRIGGER_LOW = 2.0     # Most strategies
POSITION_PARTIAL_R_TRIGGER_MID = 2.5     # High52, BigBase
POSITION_PARTIAL_R_TRIGGER_HIGH = 3.0    # RS_Ranker

# =============================================================================
# PYRAMIDING (ADD TO WINNERS)
# =============================================================================

POSITION_PYRAMID_ENABLED = True
POSITION_PYRAMID_R_TRIGGER = 1.5      # Add after +1.5R profit
POSITION_PYRAMID_SIZE = 0.5           # 50% of original position size
POSITION_PYRAMID_MAX_ADDS = 3         # Maximum 3 add-ons per position
POSITION_PYRAMID_PULLBACK_EMA = 21    # Must pull back to 21-day EMA
POSITION_PYRAMID_PULLBACK_ATR = 1.0   # Within 1 ATR of EMA21

# =============================================================================
# STRATEGY PRIORITY (DEDUPLICATION)
# =============================================================================

STRATEGY_PRIORITY = {
    "BigBase_Breakout_Position": 1,
    "RelativeStrength_Ranker_Position": 2,
    "TrendContinuation_Position": 3,
    "EMA_Crossover_Position": 4,
    "High52_Position": 5,
    "MeanReversion_Position": 6,
    "%B_MeanReversion_Position": 7,
}

# =============================================================================
# STRATEGY-SPECIFIC PARAMETERS
# =============================================================================

# 1. EMA_CROSSOVER_POSITION
EMA_CROSS_POS_VOLUME_MULT = 1.5
EMA_CROSS_POS_STOP_ATR_MULT = 3.5
EMA_CROSS_POS_PARTIAL_R = 2.0
EMA_CROSS_POS_PARTIAL_SIZE = 0.3
EMA_CROSS_POS_TRAIL_MA = 100
EMA_CROSS_POS_TRAIL_DAYS = 5
EMA_CROSS_POS_MAX_DAYS = 120

# 2. MEANREVERSION_POSITION
MR_POS_RSI_OVERSOLD = 38
MR_POS_RS_THRESHOLD = 0.15
MR_POS_STOP_ATR_MULT = 3.5
MR_POS_PARTIAL_R = 2.0
MR_POS_PARTIAL_SIZE = 0.3
MR_POS_TRAIL_MA = 50
MR_POS_TRAIL_DAYS = 5
MR_POS_MAX_DAYS = 90

# 3. %B_MEANREVERSION_POSITION
PERCENT_B_POS_OVERSOLD = 0.12
PERCENT_B_POS_RSI_OVERSOLD = 38
PERCENT_B_POS_STOP_ATR_MULT = 3.5
PERCENT_B_POS_PARTIAL_R = 2.0
PERCENT_B_POS_PARTIAL_SIZE = 0.3
PERCENT_B_POS_TRAIL_MA = 50
PERCENT_B_POS_TRAIL_DAYS = 5
PERCENT_B_POS_MAX_DAYS = 90

# 4. HIGH52_POSITION
HIGH52_POS_RS_MIN = 0.30
HIGH52_POS_VOLUME_MULT = 2.5
HIGH52_POS_ADX_MIN = 30
HIGH52_POS_STOP_ATR_MULT = 4.5
HIGH52_POS_PARTIAL_R = 2.5
HIGH52_POS_PARTIAL_SIZE = 0.3
HIGH52_POS_TRAIL_MA = 100
HIGH52_POS_TRAIL_DAYS = 8
HIGH52_POS_MAX_DAYS = 150

# 5. BIGBASE_BREAKOUT_POSITION
BIGBASE_MIN_WEEKS = 14
BIGBASE_MAX_RANGE_PCT = 0.22
BIGBASE_RS_MIN = 0.15
BIGBASE_VOLUME_MULT = 1.5
BIGBASE_STOP_ATR_MULT = 4.5
BIGBASE_PARTIAL_R = 4.0
BIGBASE_PARTIAL_SIZE = 0.3
BIGBASE_TRAIL_MA = 200
BIGBASE_TRAIL_DAYS = 10
BIGBASE_MAX_DAYS = 180

# 6. TRENDCONTINUATION_POSITION
TREND_CONT_MA_LOOKBACK = 150
TREND_CONT_MA_RISING_DAYS = 20
TREND_CONT_RS_THRESHOLD = 0.25
TREND_CONT_RSI_MIN = 45
TREND_CONT_PULLBACK_EMA = 21
TREND_CONT_PULLBACK_ATR = 1.0
TREND_CONT_STOP_ATR_MULT = 3.5
TREND_CONT_PARTIAL_R = 2.0
TREND_CONT_PARTIAL_SIZE = 0.3
TREND_CONT_TRAIL_MA = 50
TREND_CONT_TRAIL_DAYS = 5
TREND_CONT_MAX_DAYS = 90

# 7. RELATIVESTRENGTH_RANKER_POSITION
RS_RANKER_SECTORS = ["Information Technology", "Communication Services"]
RS_RANKER_TOP_N = 10
RS_RANKER_RS_THRESHOLD = 0.30
RS_RANKER_STOP_ATR_MULT = 4.5
RS_RANKER_PARTIAL_R = 3.0
RS_RANKER_PARTIAL_SIZE = 0.3
RS_RANKER_TRAIL_MA = 100
RS_RANKER_TRAIL_DAYS = 10
RS_RANKER_MAX_DAYS = 150

# =============================================================================
# INDEX REGIME FILTERS
# =============================================================================

REGIME_INDEX = "QQQ"
REGIME_BULL_MA = 200
REGIME_BULL_MA_RISING_DAYS = 0
REGIME_BEAR_MA = 200
REGIME_BEAR_MA_FALLING_DAYS = 0
REGIME_INDEX_ALT = "SPY"

# =============================================================================
# LIQUIDITY & UNIVERSE FILTERS
# =============================================================================

MIN_LIQUIDITY_USD = 30_000_000
MIN_PRICE = 10.0
MAX_PRICE = 999999.0

TECH_SECTORS = ["Information Technology", "Communication Services"]

# =============================================================================
# BACKTEST SETTINGS
# =============================================================================

BACKTEST_START_DATE = "2022-01-01"
BACKTEST_SCAN_FREQUENCY = "B"  # "B" = daily, "W-MON" = weekly Monday

# =============================================================================
# EMAIL & NOTIFICATION SETTINGS
# =============================================================================

MIN_NORM_SCORE = 7.0           # Minimum normalized score to send email
MAX_TRADES_EMAIL = 5           # Maximum trades in email alert

# =============================================================================
# LEGACY SETTINGS (KEPT FOR BACKWARD COMPATIBILITY)
# =============================================================================

CAPITAL_PER_TRADE = 20_000
RISK_REWARD_RATIO = 2
MAX_HOLDING_DAYS = 120
PARTIAL_EXIT_ENABLED = True
PARTIAL_EXIT_SIZE = 0.4
MAX_TRADES_PER_SCAN = 10
MAX_OPEN_POSITIONS = 25
REQUIRE_CONFIRMATION_BAR = False
MIN_HOLDING_DAYS = 0
CATASTROPHIC_LOSS_THRESHOLD = 999
MAX_ENTRY_GAP_PCT = 999
ADX_THRESHOLD = 30
RSI_MIN = 30
RSI_MAX = 70
VOLUME_MULTIPLIER = 2.5
PRICE_ABOVE_EMA20_MIN = 0.95
PRICE_ABOVE_EMA20_MAX = 1.10

# =============================================================================
# SHORT STRATEGY SETTINGS (from config/trading_config.py)
# =============================================================================

SHORT_ENABLED = False
SHORT_MAX_POSITIONS = 5
SHORT_MAX_EQUITY_PCT = 0.30
SHORT_RISK_PER_TRADE_PCT = 1.5
SHORT_REGIME_INDEX = "QQQ"
SHORT_REGIME_MA_PERIOD = 200
SHORT_REGIME_SLOPE_LOOKBACK = 20
SHORT_REGIME_ADX_PERIOD = 14
SHORT_REGIME_ADX_SMOOTH = 14
SHORT_REGIME_SIDEWAYS_ADX_MAX = 25

SHORT_REJECTION_MA = 50
SHORT_REJECTION_TOLERANCE = 0.02

SHORT_CFG_BULL = {}
SHORT_CFG_SIDEWAYS = {}
SHORT_CFG_BEAR = {}

# =============================================================================
# REGIME CLASSIFICATION
# =============================================================================

REGIME_INDEX = "QQQ"
REGIME_BULL_MA = 200
REGIME_BEAR_MA = 200

# =============================================================================
# ADDITIONAL POSITION TRADING CONFIGS
# =============================================================================

RS_RANKER_SECTORS = ["Information Technology", "Communication Services"]
RS_RANKER_TOP_N = 10
RS_RANKER_RS_THRESHOLD = 0.30
RS_RANKER_STOP_ATR_MULT = 2.0
RS_RANKER_MAX_DAYS = 120
RS_RANKER_PARTIAL_R = 2.5
RS_RANKER_PARTIAL_SIZE = 0.3

HIGH52_POS_RS_MIN = 0.30
HIGH52_POS_VOLUME_MULT = 1.5
HIGH52_POS_ADX_MIN = 25
HIGH52_POS_STOP_ATR_MULT = 2.0
HIGH52_POS_MAX_DAYS = 120
HIGH52_POS_PARTIAL_R = 2.5
HIGH52_POS_PARTIAL_SIZE = 0.3

BIGBASE_MIN_WEEKS = 8
BIGBASE_MAX_RANGE_PCT = 0.05
BIGBASE_RS_MIN = 0.30
BIGBASE_VOLUME_MULT = 1.5
BIGBASE_STOP_ATR_MULT = 2.0
BIGBASE_MAX_DAYS = 120
BIGBASE_PARTIAL_R = 3.0
BIGBASE_PARTIAL_SIZE = 0.3

MR_POS_RSI_OVERSOLD = 38
MR_POS_RS_THRESHOLD = 0.15
MR_POS_STOP_ATR_MULT = 3.5
MR_POS_MAX_DAYS = 90

PERCENT_B_POS_OVERSOLD = -0.5
PERCENT_B_POS_RSI_OVERSOLD = 40
PERCENT_B_POS_STOP_ATR_MULT = 3.0
PERCENT_B_POS_MAX_DAYS = 90

EMA_CROSS_POS_VOLUME_MULT = 1.5
EMA_CROSS_POS_STOP_ATR_MULT = 3.5
EMA_CROSS_POS_MAX_DAYS = 120

TREND_CONT_MA_LOOKBACK = 50
TREND_CONT_MA_RISING_DAYS = 20
TREND_CONT_RS_THRESHOLD = 0.20
TREND_CONT_RSI_MIN = 40
TREND_CONT_PULLBACK_EMA = 21
TREND_CONT_PULLBACK_ATR = 1.0
TREND_CONT_STOP_ATR_MULT = 2.5
TREND_CONT_MAX_DAYS = 120

MIN_PRICE = 5.0
MAX_PRICE = 999.0

TECH_SECTORS = ["Information Technology", "Communication Services"]

