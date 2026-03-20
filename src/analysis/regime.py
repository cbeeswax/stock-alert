"""
Market Regime Classifier
========================
Classifies market regime as BULL, SIDEWAYS, or BEAR based on price action and trend strength.
"""

import pandas as pd
from src.data.market import get_historical_data
from src.config.settings import (
    SHORT_REGIME_INDEX,
    SHORT_REGIME_MA_PERIOD,
    SHORT_REGIME_SLOPE_LOOKBACK,
    SHORT_REGIME_ADX_PERIOD,
    SHORT_REGIME_ADX_SMOOTH,
    SHORT_REGIME_SIDEWAYS_ADX_MAX,
    SHORT_CFG_BULL,
    SHORT_CFG_SIDEWAYS,
    SHORT_CFG_BEAR,
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
    """
    if index_symbol is None:
        index_symbol = SHORT_REGIME_INDEX

    regime_data = get_historical_data(index_symbol)

    if regime_data is None or regime_data.empty:
        return "sideways"

    if isinstance(regime_data.index, pd.DatetimeIndex):
        regime_data = regime_data[regime_data.index <= as_of_date]

    if regime_data.empty:
        return "sideways"

    close = regime_data['Close']
    high = regime_data['High']
    low = regime_data['Low']

    if len(close) < SHORT_REGIME_MA_PERIOD:
        return "sideways"

    regime_ma = close.rolling(SHORT_REGIME_MA_PERIOD).mean()
    ma_current = regime_ma.iloc[-1]
    price = close.iloc[-1]

    price_above_ma = price > ma_current
    price_below_ma = price < ma_current

    if len(regime_ma) >= SHORT_REGIME_SLOPE_LOOKBACK:
        ma_past = regime_ma.iloc[-SHORT_REGIME_SLOPE_LOOKBACK]
        ma_rising = ma_current > ma_past
        ma_flat_or_down = ma_current <= ma_past
    else:
        ma_rising = False
        ma_flat_or_down = True

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(SHORT_REGIME_ADX_PERIOD).mean()

    plus_dm = (high - high.shift(1)).clip(lower=0)
    minus_dm = (low.shift(1) - low).clip(lower=0)
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

    plus_di = 100 * (plus_dm.rolling(SHORT_REGIME_ADX_PERIOD).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(SHORT_REGIME_ADX_PERIOD).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(SHORT_REGIME_ADX_SMOOTH).mean()

    adx_current = 20 if (adx.empty or pd.isna(adx.iloc[-1])) else adx.iloc[-1]
    strong_trend = adx_current >= SHORT_REGIME_SIDEWAYS_ADX_MAX

    if price_above_ma and ma_rising:
        return "bull"
    elif price_below_ma and ma_flat_or_down and strong_trend:
        return "bear"
    else:
        return "sideways"


def get_regime_config(regime):
    """Get SHORT configuration dictionary for a given regime."""
    if regime == "bull":
        return SHORT_CFG_BULL
    elif regime == "sideways":
        return SHORT_CFG_SIDEWAYS
    elif regime == "bear":
        return SHORT_CFG_BEAR
    else:
        return SHORT_CFG_SIDEWAYS


def is_short_regime_ok(regime, allow_bull_shorts=True):
    """Check if shorts are allowed in current regime."""
    if allow_bull_shorts:
        return True
    else:
        return regime in ("sideways", "bear")

__all__ = ["get_regime_label", "get_regime_config", "is_short_regime_ok"]
