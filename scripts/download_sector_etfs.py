"""
Download sector ETF historical data and build sector_map.json.

Sector ETFs used as benchmark proxies:
  XLK  Technology
  XLF  Financials
  XLV  Health Care
  XLE  Energy
  XLI  Industrials
  XLU  Utilities
  XLP  Consumer Staples
  XLY  Consumer Discretionary
  XLB  Materials
  XLRE Real Estate
  XLC  Communication Services

Run this script once to populate sector ETF CSVs and sector_map.json.
"""

import json
import os
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(r"C:\Users\pelac\Git\HistoricalData\historical")
SECTOR_MAP_PATH = REPO_ROOT / "data" / "predictor" / "sector_map.json"

SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLU", "XLP", "XLY", "XLB", "XLRE", "XLC"]

# ---------------------------------------------------------------------------
# Manual GICS sector assignments for our 178-ticker universe.
# Source: S&P GICS classifications as of 2025. Update as needed.
# ---------------------------------------------------------------------------

SECTOR_MAP: dict[str, str] = {
    # --- Technology (XLK) ---
    "AAPL": "XLK", "ADBE": "XLK", "ADI": "XLK", "ADP": "XLK", "AMAT": "XLK",
    "AMD": "XLK", "ANET": "XLK", "AVGO": "XLK", "CDW": "XLK", "CDNS": "XLK",
    "CRWD": "XLK", "CSCO": "XLK", "CTSH": "XLK", "DDOG": "XLK", "DELL": "XLK",
    "EPAM": "XLK", "ADSK": "XLK", "AKAM": "XLK", "APH": "XLK", "GLW": "XLK",
    "ACN": "XLK", "COIN": "XLK",

    # --- Communication Services (XLC) ---
    "GOOG": "XLC", "GOOGL": "XLC", "CMCSA": "XLC", "CHTR": "XLC",
    "EA": "XLC", "EBAY": "XLC", "DASH": "XLC",

    # --- Financials (XLF) ---
    "AIG": "XLF", "AJG": "XLF", "AMP": "XLF", "AON": "XLF", "AXP": "XLF",
    "BAC": "XLF", "BK": "XLF", "BLK": "XLF", "BRO": "XLF", "BX": "XLF",
    "C": "XLF", "CB": "XLF", "CBOE": "XLF", "CFG": "XLF", "CINF": "XLF",
    "COF": "XLF", "CPAY": "XLF", "ERIE": "XLF", "AFL": "XLF", "SCHW": "XLF",
    "APO": "XLF", "ACGL": "XLF",

    # --- Health Care (XLV) ---
    "ABBV": "XLV", "ABT": "XLV", "AMGN": "XLV", "BAX": "XLV", "BDX": "XLV",
    "BIIB": "XLV", "BMY": "XLV", "BSX": "XLV", "CAH": "XLV", "CI": "XLV",
    "CNC": "XLV", "COR": "XLV", "COO": "XLV", "CVS": "XLV", "DXCM": "XLV",
    "DHR": "XLV", "DVA": "XLV", "ELV": "XLV", "EW": "XLV", "ALGN": "XLV",
    "CRL": "XLV", "TECH": "XLV",

    # --- Energy (XLE) ---
    "APA": "XLE", "BKR": "XLE", "COP": "XLE", "CTRA": "XLE", "CVX": "XLE",
    "DVN": "XLE", "EOG": "XLE", "FANG": "XLE", "EQT": "XLE", "CF": "XLE",

    # --- Industrials (XLI) ---
    "AME": "XLI", "AOS": "XLI", "AXON": "XLI", "BA": "XLI", "BLDR": "XLI",
    "CARR": "XLI", "CAT": "XLI", "CHRW": "XLI", "CMI": "XLI", "CPRT": "XLI",
    "CSX": "XLI", "CTAS": "XLI", "DAL": "XLI", "DAY": "XLI", "DD": "XLI",
    "DE": "XLI", "DOV": "XLI", "EMR": "XLI", "ETN": "XLI", "GE": "XLI",
    "MMM": "XLI", "OTIS": "XLI", "PCAR": "XLI", "PWR": "XLI", "RTX": "XLI",
    "SWK": "XLI", "TT": "XLI", "UBER": "XLI", "UNP": "XLI", "UPS": "XLI",
    "VRSK": "XLI", "WAB": "XLI", "XYL": "XLI",

    # --- Utilities (XLU) ---
    "AEE": "XLU", "AEP": "XLU", "AES": "XLU", "ATO": "XLU", "CMS": "XLU",
    "CNP": "XLU", "D": "XLU", "DTE": "XLU", "DUK": "XLU", "ED": "XLU",
    "EIX": "XLU", "ETR": "XLU", "LNT": "XLU", "CEG": "XLU",

    # --- Consumer Staples (XLP) ---
    "ADM": "XLP", "AMCR": "XLP", "AVY": "XLP", "BG": "XLP", "CAG": "XLP",
    "CHD": "XLP", "CL": "XLP", "CLX": "XLP", "COST": "XLP", "CPB": "XLP",
    "CTVA": "XLP", "EL": "XLP", "GIS": "XLP", "HRL": "XLP", "HSY": "XLP",
    "KHC": "XLP", "KMB": "XLP", "KO": "XLP", "MKC": "XLP", "MO": "XLP",
    "MDLZ": "XLP", "PEP": "XLP", "PG": "XLP", "PM": "XLP", "SJM": "XLP",
    "STZ": "XLP", "SYY": "XLP", "TAP": "XLP", "TSN": "XLP", "WMT": "XLP",
    "MNST": "XLP",

    # --- Consumer Discretionary (XLY) ---
    "ABNB": "XLY", "AZO": "XLY", "BBY": "XLY", "BKNG": "XLY", "CCL": "XLY",
    "CMG": "XLY", "CZR": "XLY", "DECK": "XLY", "DG": "XLY", "DHI": "XLY",
    "DLTR": "XLY", "DPZ": "XLY", "DRI": "XLY", "EBAY": "XLY", "GPC": "XLY",
    "GM": "XLY", "HAS": "XLY", "HLT": "XLY", "KMX": "XLY", "LEN": "XLY",
    "LVS": "XLY", "MAR": "XLY", "MCD": "XLY", "MGM": "XLY", "NKE": "XLY",
    "ORLY": "XLY", "PHM": "XLY", "POOL": "XLY", "ROST": "XLY", "RCL": "XLY",
    "SBUX": "XLY", "TJX": "XLY", "TPR": "XLY", "TSLA": "XLY", "VFC": "XLY",
    "WHR": "XLY", "YUM": "XLY",

    # --- Materials (XLB) ---
    "ALB": "XLB", "BALL": "XLB", "DOW": "XLB", "ECL": "XLB", "EFX": "XLB",
    "EMN": "XLB", "FCX": "XLB", "IFF": "XLB", "LIN": "XLB", "LYB": "XLB",
    "MLM": "XLB", "MOS": "XLB", "NEM": "XLB", "NUE": "XLB", "PKG": "XLB",
    "PPG": "XLB", "SHW": "XLB", "VMC": "XLB",

    # --- Real Estate (XLRE) ---
    "AMT": "XLRE", "ARE": "XLRE", "AVB": "XLRE", "BXP": "XLRE", "CCI": "XLRE",
    "CBRE": "XLRE", "CPT": "XLRE", "DLR": "XLRE", "EQIX": "XLRE", "EQR": "XLRE",
    "ESS": "XLRE", "IRM": "XLRE", "KIM": "XLRE", "MAA": "XLRE", "O": "XLRE",
    "PSA": "XLRE", "PLD": "XLRE", "REG": "XLRE", "SBAC": "XLRE", "SPG": "XLRE",
    "SUI": "XLRE", "VTR": "XLRE", "VICI": "XLRE", "WY": "XLRE",

    # --- Catch-all for any remaining tickers ---
    "A": "XLV",       # Agilent - Health Care
    "ALL": "XLF",     # Allstate - Financials
    "ALLE": "XLI",    # Allegion - Industrials
    "AWK": "XLU",     # American Water - Utilities
    "BR": "XLK",      # Broadridge - Technology
    "CSGP": "XLRE",   # CoStar - Real Estate
    "DLR": "XLRE",    # Digital Realty - Real Estate
    "EG": "XLF",      # Everest Group - Financials
    "EFX": "XLI",     # Equifax - Industrials
    "ENPH": "XLK",    # Enphase - Technology
    "EQT": "XLE",     # EQT - Energy
    "FANG": "XLE",    # Diamondback - Energy
    "JNPR": "XLK",    # Juniper - Technology
    "LNT": "XLU",     # Alliant Energy - Utilities
    "XYZ": "XLK",     # Placeholder
}


def download_sector_etfs(start: str = "2021-01-01", end: str = "2026-04-05") -> None:
    """Download sector ETF historical data and save as CSVs."""
    for etf in SECTOR_ETFS:
        out_path = DATA_DIR / f"{etf}.csv"
        if out_path.exists():
            print(f"  {etf}: already exists, skipping")
            continue
        try:
            ticker = yf.Ticker(etf)
            hist = ticker.history(start=start, end=end, auto_adjust=True)
            if hist.empty:
                print(f"  {etf}: no data returned")
                continue
            hist.index = hist.index.tz_localize(None)
            df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.columns = ["open", "high", "low", "close", "volume"]
            df.index.name = "date"
            df.to_csv(out_path)
            print(f"  {etf}: saved {len(df)} rows → {out_path}")
            time.sleep(0.3)  # polite rate limiting
        except Exception as exc:
            print(f"  {etf}: ERROR — {exc}")


def write_sector_map() -> None:
    """Write sector_map.json with ticker → sector ETF mapping."""
    SECTOR_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Verify no duplicate assignments (a ticker shouldn't be in two sectors)
    seen: dict[str, str] = {}
    conflicts: list[str] = []
    for ticker, sector in SECTOR_MAP.items():
        if ticker in seen and seen[ticker] != sector:
            conflicts.append(f"{ticker}: {seen[ticker]} vs {sector}")
        seen[ticker] = sector

    if conflicts:
        print("WARNING — duplicate sector assignments:")
        for c in conflicts:
            print(f"  {c}")

    with open(SECTOR_MAP_PATH, "w") as f:
        json.dump(SECTOR_MAP, f, indent=2, sort_keys=True)
    print(f"Wrote sector_map.json with {len(SECTOR_MAP)} tickers → {SECTOR_MAP_PATH}")


if __name__ == "__main__":
    print("=== Downloading sector ETF data ===")
    download_sector_etfs()

    print("\n=== Writing sector_map.json ===")
    write_sector_map()

    print("\nDone. Run generate_snapshot.py to rebuild snapshots with sector RS.")
