"""
Market Regime Classifier
========================
Classifies market regime as BULL, SIDEWAYS, or BEAR based on price action and trend strength.
This module re-exports from utils for backward compatibility during migration.
"""
from utils.regime_classifier import (
    get_regime_label,
    get_regime_config,
    is_short_regime_ok,
)

__all__ = ["get_regime_label", "get_regime_config", "is_short_regime_ok"]
