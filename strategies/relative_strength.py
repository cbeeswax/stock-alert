import pandas as pd
from utils.market_data import get_historical_data
from utils.ema_utils import compute_ema_incremental

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

        # --- Clean stock data ---
        stock_df = stock_df.copy()
        stock_df["Close"] = pd.to_numeric(stock_df["Close"], errors="coerce")
        stock_df.dropna(subset=["Close"], inplace=True)

        # --- Clean benchmark data ---
        benchmark_df = benchmark_df.copy()
        benchmark_df["Close"] = pd.to_numeric(benchmark_df["Close"], errors="coerce")
        benchmark_df.dropna(subset=["Close"], inplace=True)

        # --- Ensure enough data ---
        if len(stock_df) < lookback or len(benchmark_df) < lookback:
            return None

        # --- Compute returns ---
        stock_start = float(stock_df["Close"].iloc[-lookback])
        stock_end = float(stock_df["Close"].iloc[-1])
        benchmark_start = float(benchmark_df["Close"].iloc[-lookback])
        benchmark_end = float(benchmark_df["Close"].iloc[-1])

        stock_ret = (stock_end - stock_start) / stock_start
        benchmark_ret = (benchmark_end - benchmark_start) / benchmark_start

        rs_ratio = stock_ret - benchmark_ret

        # --- Only consider outperforming stocks ---
        if rs_ratio <= 0:
            return None

        # --- Score capped at 10 ---
        score = round(min(rs_ratio * 100, 10), 2)

        # --- Get EMA values (needed for pre_buy_check filters) ---
        ema_df = compute_ema_incremental(ticker)
        ema20 = ema50 = ema200 = 0
        if not ema_df.empty and len(ema_df) > 0:
            ema20 = ema_df["EMA20"].iloc[-1] if "EMA20" in ema_df.columns else 0
            ema50 = ema_df["EMA50"].iloc[-1] if "EMA50" in ema_df.columns else 0
            ema200 = ema_df["EMA200"].iloc[-1] if "EMA200" in ema_df.columns else 0

        return {
            "Ticker": ticker,
            "StockReturn%": round(stock_ret * 100, 2),
            "BenchmarkReturn%": round(benchmark_ret * 100, 2),
            "RS%": round(rs_ratio * 100, 2),
            "Score": score,
            "EMA20": ema20,
            "EMA50": ema50,
            "EMA200": ema200
        }

    except Exception as e:
        print(f"⚠️ [relative_strength] Error for {ticker}: {e}")
        return None
