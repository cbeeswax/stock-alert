from pathlib import Path
import pandas as pd
import yfinance as yf

DATA_DIR = Path("data/historical")

def get_market_cap(ticker):
    """
    Retrieves market capitalization from yfinance safely.
    """
    try:
        info = yf.Ticker(ticker).info
        if not info:
            print(f"⚠️ [market_data.py] No info returned for {ticker}")
            return 0
        market_cap = info.get("marketCap", 0)
        if isinstance(market_cap, pd.Series):
            market_cap = market_cap.iloc[-1]
        return float(market_cap or 0)
    except Exception as e:
        print(f"⚠️ [market_data.py] Error getting market cap for {ticker}: {e}")
        return 0


def get_historical_data(ticker):
    file = DATA_DIR / f"{ticker}.csv"

    if not file.exists():
        return pd.DataFrame()

    df = pd.read_csv(file, index_col=0, parse_dates=True)
    return df.sort_index()