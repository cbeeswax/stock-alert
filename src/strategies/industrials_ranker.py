"""
Industrials Relative Strength Ranker - Position Trading
========================================================
Scans for relative strength leaders in Industrials sector.

Entry Criteria:
- Sector: Industrials (XLI > MA200, rising)
- Relative Strength: RS >= +20% vs SPY (6-month)
- Trend: Price > MA50 > MA100 > MA200 (all three rising)
- ADX: Regime-adjusted (25+ in RiskOn, 20+ in Neutral)
- Entry: New 3-month high OR pullback to EMA21 breakout

Exit Rules:
- Stop Loss: 4.5 × ATR
- EMA21 Trail: 5 closes below (profit-gated at +0.75R)
- MA100 Trail: 8 closes below (after 60 days)
- Partial Profits: 40% @ 2.5R, 30% @ 4.0R
- Time Stop: 120 days

Position Sizing: 1.5% risk per trade
Max Positions: 3-5 per backtest period
Hold Period: 30-90 days
"""

import pandas as pd
import numpy as np
from src.data.market import get_historical_data
from src.data.indicators import compute_rsi
from src.analysis.sectors import get_ticker_sector


def calculate_relative_strength(ticker_df, sector_etf_df, lookback=126):
    """Calculate relative strength vs sector ETF (6 months)"""
    if ticker_df.empty or sector_etf_df.empty:
        return None
    
    # Align dates
    common_dates = ticker_df.index.intersection(sector_etf_df.index)
    if len(common_dates) < lookback:
        return None
    
    ticker_returns = ticker_df.loc[common_dates[-lookback:], 'Close'].pct_change().sum()
    etf_returns = sector_etf_df.loc[common_dates[-lookback:], 'Close'].pct_change().sum()
    
    rs = ((1 + ticker_returns) / (1 + etf_returns) - 1) * 100
    return rs


def scan_industrials(tickers, as_of_date, sector_etf_df, adx_threshold=25, rs_logged_tickers=None):
    """
    Scan for Industrials RS leaders.
    
    Args:
        tickers: List of tickers to scan
        as_of_date: Date to scan as of
        sector_etf_df: XLI historical data
        adx_threshold: Minimum ADX for entry
        rs_logged_tickers: Set to track logged tickers (for logging)
    
    Returns:
        List of entry signals
    """
    signals = []
    
    if rs_logged_tickers is None:
        rs_logged_tickers = set()
    
    for ticker in tickers:
        df = get_historical_data(ticker)
        if df.empty or len(df) < 252:
            continue
        
        # Filter to as_of_date
        df = df[df.index <= as_of_date]
        
        # Check sector
        sector = get_ticker_sector(ticker)
        if sector != "Industrials":
            continue
        
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]
        
        last_close = close.iloc[-1]
        
        # Skip price filters
        if last_close < 10 or last_close > 500:
            continue
        
        # Liquidity check
        avg_vol_20d = volume.rolling(20).mean().iloc[-1]
        dollar_volume = avg_vol_20d * last_close
        if dollar_volume < 5000000:  # $5M minimum
            continue
        
        # Calculate indicators
        ma50 = close.rolling(50).mean()
        ma100 = close.rolling(100).mean()
        ma200 = close.rolling(200).mean()
        ema21 = close.ewm(span=21).mean()
        
        # Calculate RSI and ADX
        rsi = compute_rsi(close, 14)
        atr = calculate_atr(df, 14)
        adx = calculate_adx(df, 14)
        
        # Relative Strength vs XLI
        rs = calculate_relative_strength(df, sector_etf_df, 126)
        
        # Entry filters
        price_above_ema = last_close > ema21.iloc[-1] if pd.notna(ema21.iloc[-1]) else False
        ma_stack = (last_close > ma50.iloc[-1] > ma100.iloc[-1] > ma200.iloc[-1]) if all([
            pd.notna(ma50.iloc[-1]), pd.notna(ma100.iloc[-1]), pd.notna(ma200.iloc[-1])
        ]) else False
        
        # All MAs rising
        mas_rising = True
        for ma in [ma50, ma100, ma200]:
            if len(ma) >= 20:
                ma_recent = ma.iloc[-1]
                ma_past = ma.iloc[-20]
                if not pd.notna(ma_recent) or not pd.notna(ma_past) or ma_recent <= ma_past:
                    mas_rising = False
                    break
        
        # Check if new 3-month high
        high_252 = high.rolling(63).max()
        is_high = last_close >= high_252.iloc[-1] * 0.99 if pd.notna(high_252.iloc[-1]) else False
        
        # Check for pullback to EMA21
        pullback_distance = abs(last_close - ema21.iloc[-1]) if pd.notna(ema21.iloc[-1]) else float('inf')
        atr_val = atr.iloc[-1] if pd.notna(atr.iloc[-1]) else 1.0
        is_near_ema = pullback_distance <= (1.0 * atr_val)
        
        strong_adx = adx.iloc[-1] >= adx_threshold if pd.notna(adx.iloc[-1]) else False
        
        # Entry decision
        can_enter = (
            ma_stack and 
            mas_rising and 
            strong_adx and 
            (is_high or is_near_ema) and
            rs is not None and rs >= 20.0  # RS >= +20%
        )
        
        if can_enter:
            # Calculate stop loss and entry
            atr_val = atr.iloc[-1] if pd.notna(atr.iloc[-1]) else (last_close * 0.02)
            stop_loss = last_close - (4.5 * atr_val)
            
            signal = {
                'Ticker': ticker,
                'Date': as_of_date,
                'Close': round(last_close, 2),
                'Entry': round(last_close, 2),
                'StopLoss': round(stop_loss, 2),
                'Strategy': 'Industrials_Ranker_Position',
                'Volume': int(volume.iloc[-1]),
                'Score': round(rs, 2) if rs else 0,
                'Direction': 'LONG',
                'MaxDays': 120,
                'RS_6mo': round(rs, 2) if rs else 0,
                'ADX14': round(adx.iloc[-1], 2) if pd.notna(adx.iloc[-1]) else 0,
            }
            signals.append(signal)
            
            if ticker not in rs_logged_tickers:
                print(f"   ✅ Industrials: {ticker} RS={rs:+.1f}% ADX={adx.iloc[-1]:.0f}")
                rs_logged_tickers.add(ticker)
    
    return signals


def calculate_atr(df, period=14):
    """Calculate ATR"""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    
    return tr.rolling(period).mean()


def calculate_adx(df, period=14):
    """Calculate ADX (Average Directional Index)"""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    
    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    
    # Directional Movement
    plus_dm = (high - high.shift(1)).clip(lower=0)
    minus_dm = (low.shift(1) - low).clip(lower=0)
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
    
    # Directional Indicator
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    
    # DX and ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(period).mean()
    
    return adx
