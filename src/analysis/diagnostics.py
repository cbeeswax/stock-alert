"""
Diagnostic Utilities
====================
Tools for diagnosing and debugging strategy and trade issues.
"""

from typing import List, Dict, Any
import pandas as pd


def diagnose_signal_count(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Diagnose signal generation issues.
    
    Args:
        signals: List of signal dictionaries
        
    Returns:
        Diagnostic information
    """
    df = pd.DataFrame(signals) if signals else pd.DataFrame()
    
    return {
        'total_signals': len(signals),
        'unique_tickers': df['Ticker'].nunique() if 'Ticker' in df.columns else 0,
        'strategy_distribution': df['Strategy'].value_counts().to_dict() if 'Strategy' in df.columns else {},
        'avg_score': df['Score'].mean() if 'Score' in df.columns else 0,
    }


def diagnose_position_health(position_tracker) -> Dict[str, Any]:
    """
    Diagnose position tracker health.
    
    Args:
        position_tracker: PositionTracker instance
        
    Returns:
        Diagnostic information
    """
    positions = position_tracker.get_all_positions()
    
    return {
        'total_positions': len(positions),
        'open_tickers': list(positions.keys()),
        'by_strategy': _count_by_strategy(positions),
    }


def _count_by_strategy(positions: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """Count positions by strategy."""
    counts = {}
    for ticker, pos in positions.items():
        strategy = pos.get('strategy', 'Unknown')
        counts[strategy] = counts.get(strategy, 0) + 1
    return counts
