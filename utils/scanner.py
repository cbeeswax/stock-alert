import time
import pandas as pd
import yfinance as yf
from config import MIN_MARKET_CAP, SP500_SOURCE
from utils.market_data import get_market_cap, get_historical_data
from utils.ema_signals import get_ema_signals
from utils.high_52w_strategy import score_52week_high_stock, is_52w_watchlist_candidate
from utils.consolidation_breakout import check_consolidation_breakout
from utils.relative_strength import check_relative_strength
from utils.ema_utils import compute_ema_incremental, compute_rsi

BACKOFF_BASE = 2
MAX_RETRIES = 5

def run_scan(test_mode=False):
    """
    Runs the complete SMA/EMA crossover + 52-week high + consolidation + relative strength scan.
    Sequential, with exponential backoff and retry.
    Includes Market Regime Filter using SPY EMA200.
    """

    print("🚀 Running full stock scan...")

    # Load S&P500 tickers
    sp500 = pd.read_csv(SP500_SOURCE)
    tickers = sp500["Symbol"].tolist()
    if test_mode:
        tickers = tickers[:15]

    # --- Initialize output lists ---
    ema_list = []
    high_list = []
    watchlist_highs = []
    consolidation_list = []
    rs_list = []

    # --- Download benchmark for relative strength & market regime ---
    benchmark_df = yf.download("SPY", period="1y", interval="1d")
    if benchmark_df.empty:
        print("⚠️ Failed to download SPY data. Defaulting to allow breakouts.")
        market_bullish = True
    else:
        benchmark_df["EMA200"] = benchmark_df["Close"].ewm(span=200, adjust=False).mean()
        spy_latest = float(benchmark_df["Close"].iloc[-1])
        spy_ema200 = float(benchmark_df["EMA200"].iloc[-1])

        market_bullish = spy_latest > spy_ema200
        if market_bullish:
            print(f"📊 Market Regime: Bullish | SPY Close: {spy_latest:.2f}, EMA200: {spy_ema200:.2f}")
        else:
            print(f"📊 Market Regime: Bearish | SPY Close: {spy_latest:.2f}, EMA200: {spy_ema200:.2f}. Breakouts will be skipped.")

    # --- Iterate tickers ---
    for ticker in tickers:
        # --- Market Cap Check ---
        attempt, market_cap = 0, None
        while attempt < MAX_RETRIES:
            market_cap = get_market_cap(ticker)
            if market_cap and market_cap > MIN_MARKET_CAP:
                break
            wait = BACKOFF_BASE ** attempt
            print(f"⚠️ [scanner.py] Retry {attempt+1} for {ticker} market cap in {wait}s")
            time.sleep(wait)
            attempt += 1
        else:
            print(f"⚠️ [scanner.py] Skipping {ticker} due to low/missing market cap")
            continue

        # --- EMA Signal ---
        try:
            ema_result = get_ema_signals(ticker)
            if ema_result:
                ema_result["Strategy"] = "EMA Crossover"  # <-- assign here
                ema_list.append(ema_result)
        except Exception as e:
            print(f"⚠️ [scanner.py] Error processing EMA for {ticker}: {e}")

        # --- 52-Week High & Consolidation Breakout (only if market bullish) ---
        if market_bullish:
            # 52-Week High
            try:
                df = get_historical_data(ticker)
                if df.empty or "Close" not in df.columns:
                    continue
                df = df.copy()
                df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
                df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
                df.dropna(subset=["Close"], inplace=True)

                close_today = df["Close"].iloc[-1]
                high_52w = df["Close"].rolling(252, min_periods=1).max().iloc[-1]
                pct_from_high = (close_today - high_52w) / high_52w * 100

                ema20 = df["Close"].ewm(span=20, adjust=False).mean().iloc[-1]
                ema50 = df["Close"].ewm(span=50, adjust=False).mean().iloc[-1]
                ema200 = df["Close"].ewm(span=200, adjust=False).mean().iloc[-1]

                avg_vol50 = df["Volume"].rolling(50).mean().iloc[-1]
                vol_ratio = df["Volume"].iloc[-1] / max(avg_vol50, 1)

                rsi14 = compute_rsi(df["Close"], 14).iloc[-1]

                row = {
                    "Ticker": ticker,
                    "Close": close_today,
                    "High52": high_52w,
                    "PctFrom52High": pct_from_high,
                    "EMA20": ema20,
                    "EMA50": ema50,
                    "EMA200": ema200,
                    "VolumeRatio": vol_ratio,
                    "RSI14": rsi14,
                    "Strategy": "52-Week High"  # <-- assign here
                }

                score = score_52week_high_stock(row)
                if score is not None:
                    row["Score"] = score
                    high_list.append(row)
                elif is_52w_watchlist_candidate(row):
                    watchlist_highs.append(row)

            except Exception as e:
                print(f"⚠️ [scanner.py] Error processing 52-week high for {ticker}: {e}")

            # Consolidation Breakout
            try:
                cons_result = check_consolidation_breakout(ticker)
                if cons_result:
                    cons_result["Strategy"] = "Consolidation Breakout"  # <-- assign here
                    consolidation_list.append(cons_result)
            except Exception as e:
                print(f"⚠️ [scanner.py] Error processing consolidation breakout for {ticker}: {e}")
        else:
            print(f"⏭️ Skipping {ticker} breakouts due to bearish market")

        # --- Relative Strength (always check) ---
        try:
            rs_result = check_relative_strength(ticker, benchmark_df)
            if rs_result:
                rs_result["Strategy"] = "Relative Strength"  # <-- assign here
                rs_list.append(rs_result)
        except Exception as e:
            print(f"⚠️ [scanner.py] Error processing relative strength for {ticker}: {e}")

    # --- Summary ---
    print("✅ Scan completed!")
    print(f"📈 EMA Crossovers: {len(ema_list)} stocks")
    print(f"🔥 52-week Highs (BUY-READY): {len(high_list)} stocks")
    print(f"👀 52-week Highs (WATCHLIST): {len(watchlist_highs)} stocks")
    print(f"🔥 Consolidation Breakouts: {len(consolidation_list)} stocks")
    print(f"🚀 Relative Strength Leaders: {len(rs_list)} stocks")

    # --- RETURN ALL LISTS ---
    return ema_list, high_list, watchlist_highs, consolidation_list, rs_list
