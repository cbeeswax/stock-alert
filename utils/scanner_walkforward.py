import pandas as pd
from utils.market_data import get_historical_data
from utils.ema_utils import compute_rsi


def run_scan_as_of(as_of_date, tickers):
    """
    Walk-forward scanner using ONLY data available up to as_of_date.
    Returns signals compatible with pre_buy_check().
    """
    # -------------------------------------------------
    # Market regime (SPY EMA200) — WALK-FORWARD SAFE
    # -------------------------------------------------
    spy_df = get_historical_data("SPY")
    spy_df = spy_df[spy_df.index <= as_of_date]

    market_regime = "BULLISH"
    if len(spy_df) >= 200:
        spy_ema200 = spy_df["Close"].ewm(span=200).mean().iloc[-1]
        spy_close = spy_df["Close"].iloc[-1]
        market_regime = "BULLISH" if spy_close >= spy_ema200 else "BEARISH"

    as_of_date = pd.to_datetime(as_of_date)
    signals = []

    for ticker in tickers:
        df = get_historical_data(ticker)
        if df.empty:
            continue

        # 🔒 CRITICAL: cut all future data
        df = df[df.index <= as_of_date]

        # Need enough candles for EMA200 + RSI
        if len(df) < 220:
            continue

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # -------------------------------
        # Indicators (AS-OF DATE ONLY)
        # -------------------------------
        ema20 = close.ewm(span=20).mean()
        ema50 = close.ewm(span=50).mean()
        ema200 = close.ewm(span=200).mean()
        rsi14 = compute_rsi(close, 14)

        last_close = close.iloc[-1]

        # ==========================================================
        # EMA Crossover Strategy
        # ==========================================================
        if ema20.iloc[-1] > ema50.iloc[-1] > ema200.iloc[-1]:
            signals.append({
                "Ticker": ticker,
                "Strategy": "EMA Crossover",
                "Price": round(last_close, 2),
                "AsOfDate": as_of_date,
                "EMA20": round(ema20.iloc[-1], 2),
                "EMA50": round(ema50.iloc[-1], 2),
                "EMA200": round(ema200.iloc[-1], 2),
                "RSI14": round(rsi14.iloc[-1], 2),
                "MarketRegime": market_regime,
            })

        # ==========================================================
        # 52-Week High Strategy
        # ==========================================================
        high_52w = close.rolling(252).max().iloc[-1]
        pct_from_high = (last_close - high_52w) / high_52w * 100

        if pct_from_high > -5 and rsi14.iloc[-1] > 50:
            signals.append({
                "Ticker": ticker,
                "Strategy": "52-Week High",
                "Price": round(last_close, 2),
                "AsOfDate": as_of_date,
                "Score": round(100 + pct_from_high, 2),
                "MarketRegime": market_regime,
            })

        # ==========================================================
        # Consolidation Breakout Strategy
        # ==========================================================
        range_pct = (high.iloc[-20:].max() - low.iloc[-20:].min()) / last_close
        vol_ratio = volume.iloc[-1] / max(volume.iloc[-20:].mean(), 1)

        if range_pct < 0.08 and vol_ratio > 1.5:
            signals.append({
                "Ticker": ticker,
                "Strategy": "Consolidation Breakout",
                "Price": round(last_close, 2),
                "AsOfDate": as_of_date,
                "Score": round((1 - range_pct) * vol_ratio, 2),
                "MarketRegime": market_regime,
            })

    return signals
