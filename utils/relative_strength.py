import pandas as pd
from utils.market_data import get_historical_data

def check_relative_strength(ticker, benchmark_df, lookback=50):
    """
    Checks if a stock is outperforming a benchmark (e.g., SPY/Nasdaq)
    over a lookback period.
    
    Returns a dict with performance metrics and a score if outperforming,
    else returns None.
    """
    try:
        stock_df = get_historical_data(ticker)
        if stock_df.empty or "Close" not in stock_df.columns:
            return None

        stock_df = stock_df.copy()
        stock_df["Close"] = pd.to_numeric(stock_df["Close"], errors="coerce")
        stock_df.dropna(subset=["Close"], inplace=True)

        # Ensure enough data
        if len(stock_df) < lookback or len(benchmark_df) < lookback:
            return None

        # Use last `lookback` rows for comparison
        stock_ret = (stock_df["Close"].iloc[-1] - stock_df["Close"].iloc[-lookback]) / stock_df["Close"].iloc[-lookback]
        benchmark_ret = (benchmark_df["Close"].iloc[-1] - benchmark_df["Close"].iloc[-lookback]) / benchmark_df["Close"].iloc[-lookback]

        rs_ratio = stock_ret - benchmark_ret

        # Only consider stocks outperforming benchmark
        if rs_ratio <= 0:
            return None

        # Simple score proportional to outperformance, capped at 10
        score = round(min(rs_ratio * 100, 10), 2)

        return {
            "Ticker": ticker,
            "StockReturn%": round(stock_ret * 100, 2),
            "BenchmarkReturn%": round(benchmark_ret * 100, 2),
            "RS%": round(rs_ratio * 100, 2),
            "Score": score
        }

    except Exception as e:
        print(f"⚠️ [relative_strength] Error for {ticker}: {e}")
        return None
