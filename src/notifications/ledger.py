"""
Ledger utilities for tracking SMA crossovers and 52-week highs.
"""
import os
import pandas as pd

SMA_LEDGER_FILE   = "ledger.csv"
HIGHS_LEDGER_FILE = "highs_ledger.csv"


def load_ledger(file):
    if os.path.exists(file):
        date_col = "CrossoverDate" if "ledger" in file else "HighDate"
        return pd.read_csv(file, parse_dates=[date_col])
    if "ledger" in file:
        return pd.DataFrame(columns=["Ticker", "SMA20", "SMA50", "SMA200", "CrossoverDate"])
    return pd.DataFrame(columns=["Ticker", "Company", "Close", "HighDate"])


def save_ledger(df, file):
    df.to_csv(file, index=False)


def update_sma_ledger(ticker, crossover_info):
    ledger = load_ledger(SMA_LEDGER_FILE)
    if ticker in ledger["Ticker"].values:
        if crossover_info["SMA20"] < crossover_info["SMA50"]:
            ledger = ledger[ledger["Ticker"] != ticker]
            save_ledger(ledger, SMA_LEDGER_FILE)
        return ledger
    new_row = {
        "Ticker": ticker,
        "SMA20": crossover_info["SMA20"],
        "SMA50": crossover_info["SMA50"],
        "SMA200": crossover_info["SMA200"],
        "CrossoverDate": crossover_info["CrossoverDate"],
    }
    ledger = pd.concat([ledger, pd.DataFrame([new_row]).dropna(axis=1, how="all")], ignore_index=True)
    save_ledger(ledger, SMA_LEDGER_FILE)
    return ledger


def update_highs_ledger(ticker, company, close, date):
    highs_ledger = load_ledger(HIGHS_LEDGER_FILE)
    if ticker in highs_ledger["Ticker"].values:
        return highs_ledger
    new_row = {"Ticker": ticker, "Company": company, "Close": close, "HighDate": date}
    highs_ledger = pd.concat(
        [highs_ledger, pd.DataFrame([new_row]).dropna(axis=1, how="all")], ignore_index=True
    )
    save_ledger(highs_ledger, HIGHS_LEDGER_FILE)
    return highs_ledger


__all__ = [
    "load_ledger",
    "save_ledger",
    "update_sma_ledger",
    "update_highs_ledger",
    "SMA_LEDGER_FILE",
    "HIGHS_LEDGER_FILE",
]
