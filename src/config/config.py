"""
Configuration constants (email, ledger file paths, market cap thresholds).
"""
import os

MIN_MARKET_CAP = 1_000_000_000   # 1B USD

SP500_SOURCE = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies"
    "/main/data/constituents.csv"
)

EMAIL_SENDER   = os.getenv("EMAIL_SENDER")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

SMA_LEDGER_FILE   = "ledger.csv"
HIGHS_LEDGER_FILE = "highs_ledger.csv"

__all__ = [
    "MIN_MARKET_CAP",
    "SP500_SOURCE",
    "EMAIL_SENDER",
    "EMAIL_RECEIVER",
    "EMAIL_PASSWORD",
    "SMA_LEDGER_FILE",
    "HIGHS_LEDGER_FILE",
]
