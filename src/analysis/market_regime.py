"""
Enhanced Market Regime Classification
======================================
Extends regime detection with 3-state risk classification for position sizing and entry controls.

States:
- RiskOn: QQQ > MA200 AND MA200 rising → Full 2% risk, 10 positions max
- Neutral: QQQ > MA100 but MA200 flat/declining → 1% risk, 6 positions max  
- RiskOff: QQQ < MA200 AND declining → 0% new entries, exits only

Usage:
    from src.analysis.market_regime import get_position_regime, PositionRegime
    
    regime = get_position_regime(index_symbol="QQQ", as_of_date=date)
    # Returns PositionRegime.RISK_ON or .NEUTRAL or .RISK_OFF
"""

from enum import Enum
import pandas as pd
<<<<<<< HEAD
from utils.market_data import get_historical_data
=======
from src.data.market import get_historical_data
>>>>>>> feature/restructure-and-gap-strategy


class PositionRegime(Enum):
    """3-state market regime for position trading risk management."""
    RISK_ON = "risk_on"      # Full aggressive: 2% risk, 10 positions
    NEUTRAL = "neutral"        # Balanced: 1% risk, 6 positions
    RISK_OFF = "risk_off"      # Conservative: 0% new entries, exits only


def get_position_regime(as_of_date, index_symbol="QQQ"):
    """
    Classify position trading regime based on QQQ price and moving averages.
    
    Parameters:
    -----------
    as_of_date : datetime or str
        Date to classify regime for
    index_symbol : str
        Index to use, defaults to QQQ for position trading
        
    Returns:
    --------
    PositionRegime : RISK_ON, NEUTRAL, or RISK_OFF
    
    Logic:
    ------
    RISK_ON (full aggression):
        - QQQ > MA200
        - MA200 is rising (current > 20 bars ago)
        
    NEUTRAL (cautious):
        - QQQ > MA100 (intermediate support)
        - MA200 is flat or declining (QQQ above intermediate but long-term MA weak)
        
    RISK_OFF (defensive):
        - QQQ < MA200 (below major support)
        - MA200 is declining (confirmed downtrend)
    """
    
    data = get_historical_data(index_symbol)
    
    if data is None or data.empty:
        return PositionRegime.NEUTRAL  # Default to cautious
    
    # Filter to as_of_date
    if isinstance(data.index, pd.DatetimeIndex):
        data = data[data.index <= as_of_date]
    
    if data.empty:
        return PositionRegime.NEUTRAL
    
    close = data['Close']
    
    # Need 200+ bars for MA calculations
    if len(close) < 200:
        return PositionRegime.NEUTRAL
    
    # Calculate moving averages
    ma100 = close.rolling(100).mean()
    ma200 = close.rolling(200).mean()
    
    price = close.iloc[-1]
    ma100_current = ma100.iloc[-1]
    ma200_current = ma200.iloc[-1]
    
    # Check MA trend (slope over 20 days)
    if len(ma200) >= 20:
        ma200_past = ma200.iloc[-20]
        ma200_rising = ma200_current > ma200_past
    else:
        ma200_rising = False
    
    # ===== Classify Regime =====
    
    # RISK_ON: Price > MA200 AND MA200 rising
    if price > ma200_current and ma200_rising:
        return PositionRegime.RISK_ON
    
    # RISK_OFF: Price < MA200 AND MA200 declining
    elif price < ma200_current and not ma200_rising:
        return PositionRegime.RISK_OFF
    
    # NEUTRAL: Everything else
    #   - Price > MA100 but MA200 flat/declining
    #   - Price between MA100 and MA200
    else:
        return PositionRegime.NEUTRAL


def get_regime_params(regime):
    """
    Get position sizing and entry control parameters for a regime.
    
    Parameters:
    -----------
    regime : PositionRegime
        The market regime
        
    Returns:
    --------
    dict : Configuration with keys:
        - risk_per_trade_pct: % of capital per trade
        - max_positions: Maximum concurrent positions
        - allow_new_entries: Whether to open new positions
        - adx_threshold: Minimum ADX for entry
    """
    
    if regime == PositionRegime.RISK_ON:
        return {
            'risk_per_trade_pct': 2.0,
            'max_positions': 10,
            'allow_new_entries': True,
            'adx_threshold': 25,
            'partial_profit_targets': [2.5, 4.0],  # Partial exits at these R levels
            'time_stop_days': 120,  # 4 months max
        }
    elif regime == PositionRegime.NEUTRAL:
        return {
            'risk_per_trade_pct': 1.0,
            'max_positions': 6,
            'allow_new_entries': True,
            'adx_threshold': 20,
            'partial_profit_targets': [2.5, 4.0],
            'time_stop_days': 120,
        }
    else:  # RISK_OFF
        return {
            'risk_per_trade_pct': 0.0,
            'max_positions': 0,
            'allow_new_entries': False,
            'adx_threshold': 30,  # Never enters
            'partial_profit_targets': [2.5, 4.0],
            'time_stop_days': 120,
        }
