"""
Configuration module
This module re-exports from config for backward compatibility during migration.
"""
from config.config import (
    MIN_MARKET_CAP,
    SP500_SOURCE,
    EMAIL_SENDER,
    EMAIL_RECEIVER,
    EMAIL_PASSWORD,
    SMA_LEDGER_FILE,
    HIGHS_LEDGER_FILE,
)

__all__ = [
    "MIN_MARKET_CAP",
    "SP500_SOURCE",
    "EMAIL_SENDER",
    "EMAIL_RECEIVER",
    "EMAIL_PASSWORD",
    "SMA_LEDGER_FILE",
    "HIGHS_LEDGER_FILE",
]
