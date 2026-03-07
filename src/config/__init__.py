"""Configuration module - central place for all trading parameters"""

from .settings import *  # noqa: F401, F403

__all__ = [
    # Global settings
    "UNIVERSAL_RS_MIN",
    "UNIVERSAL_ADX_MIN",
    "UNIVERSAL_VOLUME_MULT",
    "UNIVERSAL_ALL_MAS_RISING",
    "UNIVERSAL_QQQ_BULL_MA",
    "UNIVERSAL_QQQ_MA_RISING_DAYS",
    # Risk management
    "POSITION_INITIAL_EQUITY",
    "POSITION_RISK_PER_TRADE_PCT",
    "POSITION_MAX_TOTAL",
    "POSITION_MAX_PER_STRATEGY",
    "POSITION_MAX_DAYS_SHORT",
    "POSITION_MAX_DAYS_LONG",
    # Pyramiding
    "POSITION_PYRAMID_ENABLED",
    "POSITION_PYRAMID_R_TRIGGER",
    "POSITION_PYRAMID_SIZE",
    "POSITION_PYRAMID_MAX_ADDS",
    # Strategy-specific
    "RS_RANKER_SECTORS",
    "RS_RANKER_TOP_N",
    "RS_RANKER_RS_THRESHOLD",
    "RS_RANKER_STOP_ATR_MULT",
    "RS_RANKER_MAX_DAYS",
    # Regime
    "REGIME_INDEX",
    "REGIME_BULL_MA",
    # Filters
    "MIN_LIQUIDITY_USD",
    "TECH_SECTORS",
    # Backtest
    "BACKTEST_START_DATE",
    "BACKTEST_SCAN_FREQUENCY",
    # Email
    "MIN_NORM_SCORE",
    "MAX_TRADES_EMAIL",
]

