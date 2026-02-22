"""
Market Regime Classifier
========================
Classifies market regime as BULL, SIDEWAYS, or BEAR based on price action and trend strength.

Usage:
    from utils.regime_classifier import get_regime_label

    regime = get_regime_label(index_symbol="QQQ", as_of_date=date)
    # Returns: "bull" | "sideways" | "bear"
"""

import pandas as pd
from utils.market_data import get_historical_data
from config.trading_config import (
    SHORT_REGIME_INDEX,
    SHORT_REGIME_MA_PERIOD,
    SHORT_REGIME_SLOPE_LOOKBACK,
    SHORT_REGIME_ADX_PERIOD,
    SHORT_REGIME_ADX_SMOOTH,
    SHORT_REGIME_SIDEWAYS_ADX_MAX,
)


def get_regime_label(as_of_date, index_symbol=None):
    """
    Classify market regime as BULL, SIDEWAYS, or BEAR.

    Parameters:
    -----------
    as_of_date : datetime or str
        Date to classify regime for
    index_symbol : str, optional
        Index to use ("QQQ" or "SPY"). Defaults to SHORT_REGIME_INDEX from config.

    Returns:
    --------
    str : "bull", "sideways", or "bear"

    Regime Rules:
    -------------
    BULL: price > MA200 AND MA200 rising
    BEAR: price < MA200 AND MA200 declining AND ADX >= 25 (strong downtrend)
    SIDEWAYS: everything else (low trend strength or ambiguous)
    """
    if index_symbol is None:
        index_symbol = SHORT_REGIME_INDEX

    # Fetch regime data (need at least 250 days for 200-MA)
    regime_data = get_historical_data(index_symbol)

    if regime_data is None or regime_data.empty:
        # Default to sideways if no data
        return "sideways"

    # Filter to as_of_date (get data up to and including as_of_date)
    if isinstance(regime_data.index, pd.DatetimeIndex):
        regime_data = regime_data[regime_data.index <= as_of_date]

    if regime_data.empty:
        return "sideways"

    close = regime_data['Close']
    high = regime_data['High']
    low = regime_data['Low']

    # Need at least 200 bars for MA
    if len(close) < SHORT_REGIME_MA_PERIOD:
        return "sideways"

    # =========================================================================
    # 1. Price vs 200-MA
    # =========================================================================

    regime_ma = close.rolling(SHORT_REGIME_MA_PERIOD).mean()
    ma_current = regime_ma.iloc[-1]
    price = close.iloc[-1]

    price_above_ma = price > ma_current
    price_below_ma = price < ma_current

    # =========================================================================
    # 2. MA Slope Direction
    # =========================================================================

    if len(regime_ma) >= SHORT_REGIME_SLOPE_LOOKBACK:
        ma_past = regime_ma.iloc[-SHORT_REGIME_SLOPE_LOOKBACK]
        ma_rising = ma_current > ma_past
        ma_flat_or_down = ma_current <= ma_past
    else:
        ma_rising = False
        ma_flat_or_down = True

    # =========================================================================
    # 3. ADX (Trend Strength)
    # =========================================================================

    # Calculate True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(SHORT_REGIME_ADX_PERIOD).mean()

    # Calculate +DM and -DM
    plus_dm = (high - high.shift(1)).clip(lower=0)
    minus_dm = (low.shift(1) - low).clip(lower=0)
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

    # Calculate +DI and -DI
    plus_di = 100 * (plus_dm.rolling(SHORT_REGIME_ADX_PERIOD).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(SHORT_REGIME_ADX_PERIOD).mean() / atr)

    # Calculate DX and ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(SHORT_REGIME_ADX_SMOOTH).mean()

    if adx.empty or pd.isna(adx.iloc[-1]):
        adx_current = 20  # Default to weak trend
    else:
        adx_current = adx.iloc[-1]

    strong_trend = adx_current >= SHORT_REGIME_SIDEWAYS_ADX_MAX
    weak_trend = adx_current < SHORT_REGIME_SIDEWAYS_ADX_MAX

    # =========================================================================
    # 4. Classify Regime
    # =========================================================================

    # BULL: Price above rising MA
    if price_above_ma and ma_rising:
        return "bull"

    # BEAR: Price below declining MA with strong trend
    elif price_below_ma and ma_flat_or_down and strong_trend:
        return "bear"

    # SIDEWAYS: Everything else (weak trend or ambiguous)
    else:
        return "sideways"


def get_regime_config(regime):
    """
    Get SHORT configuration dictionary for a given regime.

    Parameters:
    -----------
    regime : str
        "bull", "sideways", or "bear"

    Returns:
    --------
    dict : Configuration dictionary for the regime
    """
    from config.trading_config import SHORT_CFG_BULL, SHORT_CFG_SIDEWAYS, SHORT_CFG_BEAR

    if regime == "bull":
        return SHORT_CFG_BULL
    elif regime == "sideways":
        return SHORT_CFG_SIDEWAYS
    elif regime == "bear":
        return SHORT_CFG_BEAR
    else:
        # Default to sideways if unknown regime
        return SHORT_CFG_SIDEWAYS


def is_short_regime_ok(regime, allow_bull_shorts=True):
    """
    Check if shorts are allowed in current regime.

    Parameters:
    -----------
    regime : str
        "bull", "sideways", or "bear"
    allow_bull_shorts : bool, optional
        If True, allow shorts in bull markets (with strict filters)
        If False, only allow shorts in sideways/bear markets

    Returns:
    --------
    bool : True if shorts allowed in this regime
    """
    if allow_bull_shorts:
        # Allow shorts in all regimes (but use strict filters in bull)
        return True
    else:
        # Only allow shorts in sideways/bear markets
        return regime in ("sideways", "bear")
