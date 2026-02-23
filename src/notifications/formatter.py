"""
Alert Formatter
===============
Format trading data into notification-ready messages.
"""

from typing import List, Dict, Any
import pandas as pd


def format_trade_for_email(trade: Dict[str, Any]) -> str:
    """
    Format a single trade for email display.
    
    Args:
        trade: Trade dictionary with price and strategy info
        
    Returns:
        Formatted string for email
    """
    ticker = trade.get('Ticker', 'N/A')
    entry = trade.get('Entry', 0)
    strategy = trade.get('Strategy', 'Unknown')
    score = trade.get('Score', 0)
    
    return f"{ticker} @ ${entry:.2f} ({strategy}) - Score: {score:.1f}"


def format_trades_for_email(trades_df: pd.DataFrame) -> List[str]:
    """
    Format multiple trades for email display.
    
    Args:
        trades_df: DataFrame of trades
        
    Returns:
        List of formatted trade strings
    """
    if trades_df.empty:
        return []
    
    return [format_trade_for_email(row) for _, row in trades_df.iterrows()]
