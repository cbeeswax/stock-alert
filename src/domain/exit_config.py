"""
Exit Configuration Hierarchy
=============================
Regime-specific exit rules, profit gates, and partial profit levels.

Allows different strategies to have different exit behaviors based on market regime.
Each regime defines:
- Profit gates (when to activate certain exit rules)
- Partial profit targets and sizes
- Trailing stops and conditions
- Time stops

Usage:
    from src.domain.exit_config import ExitConfig, get_exit_config_for_regime
    from src.analysis.market_regime import PositionRegime
    
    regime = PositionRegime.RISK_ON
    config = get_exit_config_for_regime(regime)
    
    # Check if EMA21 exit is gated
    if position.open_profit_r < config.ema21_profit_gate_r:
        skip_ema21_exit = True
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class ExitConfig:
    """
    Exit rules configuration for a specific regime.
    
    Attributes:
    -----------
    profit_gate_r : float
        Profit gates (in R-multiples) before activating certain exit rules.
        E.g., 0.75 means don't use EMA21 trail until +0.75R profit reached.
        
    partial_targets : List[Tuple[float, float]]
        [(R-level, % to exit), ...]
        E.g., [(2.5, 40), (4.0, 30)] means exit 40% at +2.5R, 30% at +4.0R
        
    ema21_trail_bars : int
        Number of consecutive closes below EMA21 to trigger exit.
        0 = disabled
        
    ma100_trail_bars : int
        Number of consecutive closes below MA100 to trigger exit.
        0 = disabled
        
    ma100_trail_start_bar : int
        Don't start MA100 trail counting until this many bars after entry.
        
    time_stop_days : int
        Exit if position open longer than this many days.
        0 = no time stop
        
    stop_loss_atr_multiple : float
        Stop loss is placed at entry - (stop_loss_atr_multiple * ATR)
        
    allow_pyramid : bool
        Whether pyramiding is allowed in this regime.
    """
    profit_gate_r: float = 0.75
    partial_targets: List[Tuple[float, float]] = None  # [(R, %), ...]
    ema21_trail_bars: int = 5
    ma100_trail_bars: int = 8
    ma100_trail_start_bar: int = 60
    time_stop_days: int = 120
    stop_loss_atr_multiple: float = 4.5
    allow_pyramid: bool = True
    
    def __post_init__(self):
        """Set defaults for mutable defaults."""
        if self.partial_targets is None:
            self.partial_targets = [(2.5, 40), (4.0, 30)]


def get_exit_config_for_regime(regime):
    """
    Get exit configuration for a market regime.
    
    Parameters:
    -----------
    regime : PositionRegime
        The market regime (RISK_ON, NEUTRAL, RISK_OFF)
        
    Returns:
    --------
    ExitConfig : Exit rules for the regime
    """
    from src.analysis.market_regime import PositionRegime
    
    if regime == PositionRegime.RISK_ON:
        # Aggressive: Profit-gated EMA21, dual-stage partials, long time window
        return ExitConfig(
            profit_gate_r=0.75,
            partial_targets=[(2.5, 40), (4.0, 30)],
            ema21_trail_bars=5,      # Only activate after +0.75R
            ma100_trail_bars=8,
            ma100_trail_start_bar=60,
            time_stop_days=120,
            stop_loss_atr_multiple=4.5,
            allow_pyramid=True
        )
    
    elif regime == PositionRegime.NEUTRAL:
        # Balanced: Profit-gated EMA21, conservative partials, moderate time window
        return ExitConfig(
            profit_gate_r=0.75,
            partial_targets=[(2.5, 40), (4.0, 30)],
            ema21_trail_bars=5,
            ma100_trail_bars=8,
            ma100_trail_start_bar=60,
            time_stop_days=120,
            stop_loss_atr_multiple=4.5,
            allow_pyramid=True
        )
    
    else:  # RISK_OFF
        # Defensive: Only manage exits, no new entries
        return ExitConfig(
            profit_gate_r=0.0,       # Always exit on rules
            partial_targets=[(2.5, 40), (4.0, 30)],
            ema21_trail_bars=5,
            ma100_trail_bars=8,
            ma100_trail_start_bar=60,
            time_stop_days=120,
            stop_loss_atr_multiple=4.5,
            allow_pyramid=False      # No new pyramids in downtrend
        )


# For backward compatibility with current backtester
DEFAULT_EXIT_CONFIG = ExitConfig(
    profit_gate_r=0.75,
    partial_targets=[(2.5, 40), (4.0, 30)],
    ema21_trail_bars=5,
    ma100_trail_bars=8,
    ma100_trail_start_bar=60,
    time_stop_days=120,
    stop_loss_atr_multiple=4.5,
    allow_pyramid=True
)
