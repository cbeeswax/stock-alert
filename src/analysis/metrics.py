"""
Trade Metrics and Scoring
==========================
Calculate performance metrics for trades and strategies.
"""

from typing import Dict, Any, List
import pandas as pd


def calculate_r_multiple(entry: float, exit: float, stop_loss: float) -> float:
    """
    Calculate R-multiple for a trade.
    
    R = (Exit - Entry) / (Entry - Stop Loss)
    
    Args:
        entry: Entry price
        exit: Exit price
        stop_loss: Stop loss price
        
    Returns:
        R-multiple (positive = profit, negative = loss)
    """
    risk = entry - stop_loss
    if risk == 0:
        return 0
    
    profit = exit - entry
    return profit / risk


def calculate_win_rate(trades: pd.DataFrame) -> float:
    """
    Calculate win rate from trades.
    
    Args:
        trades: DataFrame with trade results
        
    Returns:
        Win rate (0.0 to 1.0)
    """
    if len(trades) == 0:
        return 0.0
    
    winners = len(trades[trades['R_Multiple'] > 0])
    return winners / len(trades)


def calculate_expectancy(trades: pd.DataFrame) -> float:
    """
    Calculate expectancy (average R-multiple).
    
    Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
    
    Args:
        trades: DataFrame with trade results
        
    Returns:
        Average R-multiple per trade
    """
    if len(trades) == 0:
        return 0.0
    
    return trades['R_Multiple'].mean()


def calculate_max_consecutive_losses(trades: pd.DataFrame) -> int:
    """
    Calculate maximum consecutive losing trades.
    
    Args:
        trades: DataFrame with trade results
        
    Returns:
        Maximum consecutive losses
    """
    if len(trades) == 0:
        return 0
    
    is_loss = trades['R_Multiple'] <= 0
    consecutive = (is_loss != is_loss.shift()).cumsum()
    loss_streaks = consecutive[is_loss].value_counts()
    
    return loss_streaks.max() if len(loss_streaks) > 0 else 0
