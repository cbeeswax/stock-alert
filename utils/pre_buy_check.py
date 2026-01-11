import pandas as pd
import numpy as np
from utils.market_data import get_historical_data
from utils.ema_utils import compute_rsi

def compute_adx(df, period=14):
    """
    Compute ADX (Average Directional Index) for trend strength.
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    plus_dm = high.diff()
    minus_dm = low.diff() * -1

    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    adx = dx.rolling(period).mean()
    return adx

def calculate_atr(df, period=14):
    """
    ATR for stop/target calculation
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    return atr.iloc[-1] if not atr.empty else 0

def pre_buy_check(combined_signals, rr_ratio=2):
    """
    Apply pre-buy filters to all strategy signals and calculate
    entry, stop, target levels using ATR + R:R.
    """
    trades = []

    for s in combined_signals:
        ticker = s['Ticker']
        strategy = s.get('Strategy','Unknown')

        df = get_historical_data(ticker)
        if df.empty or len(df) < 30:
            continue

        df = df.tail(60)  # last 60 days
        close = df['Close'].iloc[-1]

        # ATR-based stop and target
        atr = calculate_atr(df)
        if atr == 0:
            atr = close * 0.02  # fallback 2%

        entry = close
        stop = entry - atr
        target = entry + rr_ratio * (entry - stop)

        # Additional EMA filters for EMA strategy
        if strategy == 'EMA Crossover':
            df['RSI14'] = compute_rsi(df['Close'], 14)
            df['ADX14'] = compute_adx(df)
            trend_ok = s['EMA20'] > s['EMA50'] > s['EMA200']
            rsi_ok = 45 <= df['RSI14'].iloc[-1] <= 72
            adx_ok = df['ADX14'].iloc[-1] >= 20
            if not all([trend_ok, rsi_ok, adx_ok]):
                continue  # skip if EMA trend filter fails

        trades.append({
            'Ticker': ticker,
            'Strategy': strategy,
            'Entry': round(entry,2),
            'StopLoss': round(stop,2),
            'Target': round(target,2),
            'Score': s.get('Score',0)
        })

    df_trades = pd.DataFrame(trades)
    if not df_trades.empty:
        df_trades = df_trades.sort_values(by='Score', ascending=False)
    return df_trades
