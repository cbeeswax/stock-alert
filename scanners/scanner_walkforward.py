"""
Long-Term Position Trading Scanner
===================================
Complete scanner for 7 position strategies (60-120 day holds).
Target: 8-20 trades/year total across all strategies.

STRATEGIES:
1. EMA_Crossover_Position
2. MeanReversion_Position
3. %B_MeanReversion_Position
4. High52_Position
5. BigBase_Breakout_Position
6. TrendContinuation_Position
7. RelativeStrength_Ranker_Position
"""

import pandas as pd
import numpy as np
from utils.market_data import get_historical_data
from utils.ema_utils import compute_rsi, compute_bollinger_bands, compute_percent_b
from utils.sector_utils import get_ticker_sector
from config.trading_config import (
    # Global settings
    POSITION_RISK_PER_TRADE_PCT,
    POSITION_MAX_PER_STRATEGY,
    POSITION_MAX_TOTAL,
    MIN_LIQUIDITY_USD,
    MIN_PRICE,
    MAX_PRICE,
    REGIME_INDEX,
    REGIME_BULL_MA,
    REGIME_BEAR_MA,
    STRATEGY_PRIORITY,
    TECH_SECTORS,

    # Universal filters
    UNIVERSAL_RS_MIN,
    UNIVERSAL_ADX_MIN,
    UNIVERSAL_VOLUME_MULT,
    UNIVERSAL_ALL_MAS_RISING,
    UNIVERSAL_QQQ_BULL_MA,
    UNIVERSAL_QQQ_MA_RISING_DAYS,

    # Strategy 1: EMA_Crossover_Position
    EMA_CROSS_POS_VOLUME_MULT,
    EMA_CROSS_POS_STOP_ATR_MULT,
    EMA_CROSS_POS_MAX_DAYS,

    # Strategy 2: MeanReversion_Position
    MR_POS_RSI_OVERSOLD,
    MR_POS_RS_THRESHOLD,
    MR_POS_MAX_DAYS,

    # Strategy 3: %B_MeanReversion_Position
    PERCENT_B_POS_OVERSOLD,
    PERCENT_B_POS_RSI_OVERSOLD,
    PERCENT_B_POS_STOP_ATR_MULT,
    PERCENT_B_POS_MAX_DAYS,

    # Strategy 4: High52_Position
    HIGH52_POS_RS_PERCENTILE,
    HIGH52_POS_VOLUME_MULT,
    HIGH52_POS_STOP_ATR_MULT,
    HIGH52_POS_MAX_DAYS,

    # Strategy 5: BigBase_Breakout_Position
    BIGBASE_MIN_WEEKS,
    BIGBASE_MAX_RANGE_PCT,
    BIGBASE_RS_MIN,
    BIGBASE_VOLUME_MULT,
    BIGBASE_STOP_ATR_MULT,
    BIGBASE_MAX_DAYS,

    # Strategy 6: TrendContinuation_Position
    TREND_CONT_MA_LOOKBACK,
    TREND_CONT_MA_RISING_DAYS,
    TREND_CONT_RS_THRESHOLD,
    TREND_CONT_RSI_MIN,
    TREND_CONT_PULLBACK_EMA,
    TREND_CONT_PULLBACK_ATR,
    TREND_CONT_STOP_ATR_MULT,
    TREND_CONT_MAX_DAYS,

    # Strategy 7: RelativeStrength_Ranker_Position
    RS_RANKER_SECTORS,
    RS_RANKER_TOP_N,
    RS_RANKER_RS_THRESHOLD,
    RS_RANKER_STOP_ATR_MULT,
    RS_RANKER_MAX_DAYS,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    return atr


def calculate_relative_strength(stock_df, index_df, days=126):
    """
    Calculate 6-month (126 trading days) relative strength vs index
    Returns: RS value (e.g., 0.15 = stock outperformed by 15%)
    """
    if len(stock_df) < days or len(index_df) < days:
        return None

    stock_return = (stock_df["Close"].iloc[-1] / stock_df["Close"].iloc[-days]) - 1.0
    index_return = (index_df["Close"].iloc[-1] / index_df["Close"].iloc[-days]) - 1.0

    return stock_return - index_return


def check_regime_bullish(index_df, ma_period=200):
    """Check if index is in bullish regime (close > MA)"""
    if len(index_df) < ma_period:
        return False

    close = index_df["Close"].iloc[-1]
    ma = index_df["Close"].rolling(ma_period).mean().iloc[-1]

    return close > ma


def check_regime_bearish(index_df, ma_period=200):
    """Check if index is in bearish regime (close < MA falling)"""
    if len(index_df) < ma_period + 20:
        return False

    close = index_df["Close"].iloc[-1]
    ma_current = index_df["Close"].rolling(ma_period).mean().iloc[-1]
    ma_20d_ago = index_df["Close"].rolling(ma_period).mean().iloc[-21]

    return close < ma_current and ma_current < ma_20d_ago


def check_ma_rising(df, period, lookback_days):
    """Check if MA is rising over lookback days"""
    if len(df) < period + lookback_days:
        return False

    ma_current = df["Close"].rolling(period).mean().iloc[-1]
    ma_past = df["Close"].rolling(period).mean().iloc[-lookback_days-1]

    return ma_current > ma_past


def calculate_adx(df, period=14):
    """Calculate ADX (Average Directional Index) for trend strength"""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    # Calculate +DM and -DM
    plus_dm = high.diff()
    minus_dm = low.diff() * -1

    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    # Calculate True Range
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    # Calculate smoothed TR and DMs
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

    # Calculate DX and ADX
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    adx = dx.rolling(period).mean()

    return adx


def check_all_mas_rising(df, lookback_days=20):
    """Check if MA50, MA100, and MA200 are ALL rising over lookback period"""
    if len(df) < 200 + lookback_days:
        return False

    ma50 = df["Close"].rolling(50).mean()
    ma100 = df["Close"].rolling(100).mean()
    ma200 = df["Close"].rolling(200).mean()

    ma50_rising = ma50.iloc[-1] > ma50.iloc[-lookback_days]
    ma100_rising = ma100.iloc[-1] > ma100.iloc[-lookback_days]
    ma200_rising = ma200.iloc[-1] > ma200.iloc[-lookback_days]

    return ma50_rising and ma100_rising and ma200_rising


# =============================================================================
# MAIN SCANNER FUNCTION
# =============================================================================

def run_scan_as_of(as_of_date, tickers):
    """
    Walk-forward scanner for long-term position strategies.
    Returns signals with priority ordering for deduplication.
    """
    as_of_date = pd.to_datetime(as_of_date)

    # -------------------------------------------------
    # Load index data for regime filters
    # -------------------------------------------------
    qqq_df = get_historical_data(REGIME_INDEX)
    if not qqq_df.empty and isinstance(qqq_df.index, pd.DatetimeIndex):
        qqq_df = qqq_df[qqq_df.index <= as_of_date]
    else:
        qqq_df = pd.DataFrame()

    # Check regime (STRONGER: QQQ > 100-MA AND MA100 rising)
    qqq_bull_basic = check_regime_bullish(qqq_df, UNIVERSAL_QQQ_BULL_MA) if not qqq_df.empty else False
    qqq_ma_rising = check_ma_rising(qqq_df, UNIVERSAL_QQQ_BULL_MA, UNIVERSAL_QQQ_MA_RISING_DAYS) if not qqq_df.empty else False
    is_bull_regime = qqq_bull_basic and qqq_ma_rising
    is_bear_regime = check_regime_bearish(qqq_df, REGIME_BEAR_MA) if not qqq_df.empty else False

    signals = []

    # -------------------------------------------------
    # Scan each ticker for all strategies
    # -------------------------------------------------
    for ticker in tickers:
        df = get_historical_data(ticker)
        if df.empty:
            continue

        # Cut future data
        df = df[df.index <= as_of_date]

        # Need sufficient history
        if len(df) < 252:  # 1 year minimum
            continue

        # Basic data
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]
        last_close = close.iloc[-1]

        # Skip if price too low/high
        if last_close < MIN_PRICE or last_close > MAX_PRICE:
            continue

        # Liquidity check
        avg_vol_20d = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else 0
        dollar_volume = avg_vol_20d * last_close
        if dollar_volume < MIN_LIQUIDITY_USD:
            continue

        # Calculate common indicators
        ema20 = close.ewm(span=20).mean()
        ema21 = close.ewm(span=21).mean()
        ema34 = close.ewm(span=34).mean()
        ema50 = close.ewm(span=50).mean()
        ema100 = close.ewm(span=100).mean()
        ma50 = close.rolling(50).mean()
        ma100 = close.rolling(100).mean()
        ma150 = close.rolling(150).mean()
        ma200 = close.rolling(200).mean()

        rsi14 = compute_rsi(close, 14)
        atr14 = calculate_atr(df, 14)
        atr20 = calculate_atr(df, 20)
        adx14 = calculate_adx(df, 14)

        # Relative strength vs index
        rs_6mo = calculate_relative_strength(df, qqq_df, 126) if not qqq_df.empty else None

        # Universal filters (pre-calculate for all strategies)
        all_mas_rising = check_all_mas_rising(df, UNIVERSAL_QQQ_MA_RISING_DAYS) if UNIVERSAL_ALL_MAS_RISING else True
        strong_adx = adx14.iloc[-1] >= UNIVERSAL_ADX_MIN if not pd.isna(adx14.iloc[-1]) else False

        # =====================================================================
        # STRATEGY 1: EMA_CROSSOVER_POSITION
        # =====================================================================
        # Entry: Strong trend, EMA20 crosses above EMA50 + new 50-day high
        # Regime: Bull (QQQ > 200-MA)
        # =====================================================================
        if is_bull_regime and len(df) >= 100:
            try:
                # Check for EMA20 crossing EMA50 in last 3 days
                ema20_crossed_ema50 = False
                for i in range(1, 4):
                    if i < len(ema20) and ema20.iloc[-i] <= ema50.iloc[-i] and ema20.iloc[-i+1] > ema50.iloc[-i+1]:
                        ema20_crossed_ema50 = True
                        break

                if ema20_crossed_ema50:
                    # MULTI-MONTH TREND FILTERS (Position Trading)
                    # Stacked MAs: Price > 50 > 100 > 200
                    stacked_mas = (last_close > ma50.iloc[-1] and
                                   ma50.iloc[-1] > ma100.iloc[-1] and
                                   ma100.iloc[-1] > ma200.iloc[-1])

                    # 50-day MA rising over 20 days
                    ma50_rising = check_ma_rising(df, 50, 20)

                    # Strong RS requirement (vs QQQ)
                    strong_rs = rs_6mo is not None and rs_6mo >= 0.20  # +20% vs QQQ

                    # New 50-day high
                    high_50d = high.rolling(50).max().iloc[-1]
                    is_new_high = last_close >= high_50d * 0.995  # Within 0.5%

                    # Volume confirmation
                    vol_ratio = volume.iloc[-1] / max(avg_vol_20d, 1)
                    volume_confirmed = vol_ratio >= EMA_CROSS_POS_VOLUME_MULT

                    if all([stacked_mas, ma50_rising, strong_rs, is_new_high, volume_confirmed]):
                        # Calculate stop and quality score
                        current_atr = atr14.iloc[-1]
                        stop_price = last_close - (EMA_CROSS_POS_STOP_ATR_MULT * current_atr)

                        # Quality score
                        trend_strength = (ma50.iloc[-1] - ma100.iloc[-1]) / ma100.iloc[-1] * 100
                        score = min(trend_strength * 5, 50)  # Max 50
                        score += min(vol_ratio / EMA_CROSS_POS_VOLUME_MULT * 25, 25)  # Max 25
                        score += 25 if rs_6mo and rs_6mo > 0 else 0  # Bonus for positive RS

                        signals.append({
                            "Ticker": ticker,
                            "Strategy": "EMA_Crossover_Position",
                            "Priority": STRATEGY_PRIORITY["EMA_Crossover_Position"],
                            "Price": round(last_close, 2),
                            "StopPrice": round(stop_price, 2),
                            "ATR14": round(current_atr, 2),
                            "Score": round(score, 2),
                            "AsOfDate": as_of_date,
                            "MaxDays": EMA_CROSS_POS_MAX_DAYS,
                        })
            except Exception:
                pass

        # =====================================================================
        # STRATEGY 2: MEANREVERSION_POSITION
        # =====================================================================
        # Entry: Long-term uptrend, RSI14 < 38, price near EMA50, then breakout
        # =====================================================================
        if is_bull_regime and len(df) >= 150 and rs_6mo is not None:
            try:
                # Long-term uptrend
                close_above_ma150 = last_close > ma150.iloc[-1]
                ma150_rising = check_ma_rising(df, 150, 20)
                strong_rs = rs_6mo >= MR_POS_RS_THRESHOLD

                # Oversold condition
                rsi_oversold = rsi14.iloc[-1] < MR_POS_RSI_OVERSOLD
                near_ema50 = abs(last_close - ema50.iloc[-1]) / ema50.iloc[-1] < 0.03  # Within 3%

                # Trigger: Close back above EMA50 and prior high
                close_above_ema50 = last_close > ema50.iloc[-1]
                if len(high) >= 2:
                    close_above_prior_high = last_close > high.iloc[-2]
                else:
                    close_above_prior_high = False

                if all([close_above_ma150, ma150_rising, strong_rs, (rsi_oversold or near_ema50),
                       close_above_ema50, close_above_prior_high]):
                    # Calculate weekly swing low for stop
                    if len(low) >= 10:
                        weekly_swing_low = low.iloc[-10:].min()
                        # Weekly ATR approximation
                        weekly_atr = atr14.iloc[-1] * 1.5
                        stop_price = weekly_swing_low - (1.5 * weekly_atr)
                    else:
                        stop_price = last_close - (3 * atr14.iloc[-1])

                    # Quality score
                    score = min(rs_6mo / MR_POS_RS_THRESHOLD * 40, 60)  # Max 60
                    score += (MR_POS_RSI_OVERSOLD - rsi14.iloc[-1]) * 2  # Lower RSI = higher score

                    signals.append({
                        "Ticker": ticker,
                        "Strategy": "MeanReversion_Position",
                        "Priority": STRATEGY_PRIORITY["MeanReversion_Position"],
                        "Price": round(last_close, 2),
                        "StopPrice": round(stop_price, 2),
                        "ATR14": round(atr14.iloc[-1], 2),
                        "RSI14": round(rsi14.iloc[-1], 2),
                        "RS_6mo": round(rs_6mo * 100, 2),
                        "Score": round(score, 2),
                        "AsOfDate": as_of_date,
                        "MaxDays": MR_POS_MAX_DAYS,
                    })
            except Exception:
                pass

        # =====================================================================
        # STRATEGY 3: %B_MEANREVERSION_POSITION
        # =====================================================================
        # Entry: %B < 0.12, RSI14 < 38, then close above lower BB
        # =====================================================================
        if is_bull_regime and len(df) >= 150:
            try:
                # Calculate Bollinger Bands
                middle_band, upper_band, lower_band, bandwidth = compute_bollinger_bands(close, period=20, std_dev=2)
                percent_b = compute_percent_b(close, upper_band, lower_band)

                if not percent_b.isna().iloc[-1]:
                    percent_b_value = percent_b.iloc[-1]

                    # Long-term uptrend
                    close_above_ma150 = last_close > ma150.iloc[-1]
                    ma150_rising = check_ma_rising(df, 150, 20)

                    # Oversold conditions
                    percent_b_oversold = percent_b_value < PERCENT_B_POS_OVERSOLD
                    rsi_oversold = rsi14.iloc[-1] < PERCENT_B_POS_RSI_OVERSOLD

                    # Trigger: Close back above lower BB and prior high
                    close_above_lower_bb = last_close > lower_band.iloc[-1]
                    if len(high) >= 2:
                        close_above_prior_high = last_close > high.iloc[-2]
                    else:
                        close_above_prior_high = False

                    if all([close_above_ma150, ma150_rising, percent_b_oversold, rsi_oversold,
                           close_above_lower_bb, close_above_prior_high]):
                        # Stop
                        stop_price = last_close - (PERCENT_B_POS_STOP_ATR_MULT * atr14.iloc[-1])

                        # Quality score
                        score = (PERCENT_B_POS_OVERSOLD - percent_b_value) * 500  # Max 60
                        score += (PERCENT_B_POS_RSI_OVERSOLD - rsi14.iloc[-1]) * 1.5  # Max 40

                        signals.append({
                            "Ticker": ticker,
                            "Strategy": "%B_MeanReversion_Position",
                            "Priority": STRATEGY_PRIORITY["%B_MeanReversion_Position"],
                            "Price": round(last_close, 2),
                            "StopPrice": round(stop_price, 2),
                            "ATR14": round(atr14.iloc[-1], 2),
                            "PercentB": round(percent_b_value, 2),
                            "RSI14": round(rsi14.iloc[-1], 2),
                            "Score": round(score, 2),
                            "AsOfDate": as_of_date,
                            "MaxDays": PERCENT_B_POS_MAX_DAYS,
                        })
            except Exception:
                pass

        # =====================================================================
        # STRATEGY 4: HIGH52_POSITION (ACTIVE)
        # =====================================================================
        # Entry: Top 30% RS, new 52-week high, 2.5x volume, ADX 30+, all MAs rising
        # =====================================================================
        if is_bull_regime and len(df) >= 252 and rs_6mo is not None:
            try:
                # VOLATILITY FILTER (Skip overly volatile stocks prone to whipsaw)
                daily_returns = close.pct_change()
                volatility_20d = daily_returns.rolling(20).std().iloc[-1] if len(daily_returns) >= 20 else 0
                if volatility_20d > 0.04:  # More than 4% daily volatility
                    continue  # Too volatile, skip

                # MULTI-MONTH TREND FILTERS
                # Stacked MAs: Price > 50 > 100 > 200
                stacked_mas = (last_close > ma50.iloc[-1] and
                               ma50.iloc[-1] > ma100.iloc[-1] and
                               ma100.iloc[-1] > ma200.iloc[-1])

                # New 52-week high
                high_52w = high.rolling(252).max().iloc[-1]
                is_new_52w_high = last_close >= high_52w * 0.998  # Within 0.2%

                # UNIVERSAL FILTERS (STRONGER)
                strong_rs = rs_6mo >= UNIVERSAL_RS_MIN  # 30% minimum

                # Volume surge (HIGHER)
                avg_vol_50d = volume.rolling(50).mean().iloc[-1] if len(volume) >= 50 else avg_vol_20d
                vol_ratio = volume.iloc[-1] / max(avg_vol_50d, 1)
                volume_surge = vol_ratio >= UNIVERSAL_VOLUME_MULT  # 2.5x minimum

                # RELAXED: Removed all_mas_rising filter (was too restrictive - only 2 trades in 3+ years)
                if all([stacked_mas, is_new_52w_high, strong_rs,
                       volume_surge, strong_adx]):
                    # Stop
                    stop_price = last_close - (HIGH52_POS_STOP_ATR_MULT * atr20.iloc[-1])

                    # Quality score
                    score = min(rs_6mo / 0.30 * 50, 70)  # Max 70
                    score += min((vol_ratio / HIGH52_POS_VOLUME_MULT) * 30, 30)

                    signals.append({
                        "Ticker": ticker,
                        "Strategy": "High52_Position",
                        "Priority": STRATEGY_PRIORITY["High52_Position"],
                        "Price": round(last_close, 2),
                        "StopPrice": round(stop_price, 2),
                        "ATR20": round(atr20.iloc[-1], 2),
                        "RS_6mo": round(rs_6mo * 100, 2),
                        "VolumeRatio": round(vol_ratio, 2),
                        "Score": round(score, 2),
                        "AsOfDate": as_of_date,
                        "MaxDays": HIGH52_POS_MAX_DAYS,
                    })
            except Exception:
                pass

        # =====================================================================
        # STRATEGY 5: BIGBASE_BREAKOUT_POSITION (ACTIVE - RARE HOME RUNS)
        # =====================================================================
        # Entry: 14+ week consolidation (≤22% range), 6-mo high breakout, RS 15%+, 1.5x 5-day vol
        # Note: NO ADX requirement (consolidations have low ADX by definition)
        # =====================================================================
        if is_bull_regime and len(df) >= 140:  # 14+ weeks * 5 days + buffer
            try:
                # Check 14-week (70-day) base
                lookback_days = BIGBASE_MIN_WEEKS * 5
                if len(df) >= lookback_days:
                    base_high = high.iloc[-lookback_days:].max()
                    base_low = low.iloc[-lookback_days:].min()
                    base_range_pct = (base_high - base_low) / base_low

                    # Tight base (≤22% range - controlled consolidation)
                    is_tight_base = base_range_pct <= BIGBASE_MAX_RANGE_PCT

                    # MULTI-MONTH TREND FILTERS
                    # Base must be above 200-day MA (long-term uptrend)
                    above_200ma = last_close > ma200.iloc[-1]

                    # RS requirement - strong performers (15%+ outperformance)
                    strong_rs = rs_6mo is not None and rs_6mo >= BIGBASE_RS_MIN

                    # New 6-month high breakout
                    high_6mo = high.rolling(126).max().iloc[-1]
                    is_breakout = last_close >= high_6mo * 0.998

                    # Volume confirmation: 5-day average (sustained, not spike)
                    avg_vol_50d = volume.rolling(50).mean().iloc[-1] if len(volume) >= 50 else avg_vol_20d
                    vol_5d_avg = volume.iloc[-5:].mean() if len(volume) >= 5 else volume.iloc[-1]
                    vol_ratio = vol_5d_avg / max(avg_vol_50d, 1)
                    volume_surge = vol_ratio >= BIGBASE_VOLUME_MULT  # 1.5x 5-day avg (sustained interest)

                    # RELAXED: Removed all_mas_rising and ADX filters
                    # ADX is LOW during consolidation, rises AFTER breakout (catches it too late)
                    if all([is_tight_base, above_200ma, strong_rs,
                           is_breakout, volume_surge]):
                        # Stop: ATR-based from entry (aligned with backtester)
                        stop_price = last_close - (BIGBASE_STOP_ATR_MULT * atr20.iloc[-1])

                        # Quality score (HIGH - this is rare!)
                        score = 80  # Base score
                        score += (BIGBASE_MAX_RANGE_PCT - base_range_pct) / BIGBASE_MAX_RANGE_PCT * 10
                        score += min((vol_ratio / BIGBASE_VOLUME_MULT) * 10, 10)

                        signals.append({
                            "Ticker": ticker,
                            "Strategy": "BigBase_Breakout_Position",
                            "Priority": STRATEGY_PRIORITY["BigBase_Breakout_Position"],
                            "Price": round(last_close, 2),
                            "StopPrice": round(stop_price, 2),
                            "ATR14": round(atr14.iloc[-1], 2),
                            "BaseRangePct": round(base_range_pct * 100, 2),
                            "VolumeRatio": round(vol_ratio, 2),
                            "Score": round(score, 2),
                            "AsOfDate": as_of_date,
                            "MaxDays": BIGBASE_MAX_DAYS,
                        })
            except Exception:
                pass

        # =====================================================================
        # STRATEGY 6: TRENDCONTINUATION_POSITION (NEW)
        # =====================================================================
        # Entry: Strong trend, 150-MA rising, pullback to 21-EMA, then resume
        # =====================================================================
        if is_bull_regime and len(df) >= 150 and rs_6mo is not None:
            try:
                # MULTI-MONTH TREND FILTERS
                # Stacked MAs: Price > 50 > 100 > 150 > 200
                stacked_mas = (last_close > ma50.iloc[-1] and
                               ma50.iloc[-1] > ma100.iloc[-1] and
                               ma100.iloc[-1] > ma150.iloc[-1] and
                               ma150.iloc[-1] > ma200.iloc[-1])

                # 150-MA rising over 20 days
                ma150_rising = check_ma_rising(df, 150, TREND_CONT_MA_RISING_DAYS)

                # Very strong RS (>+25% vs QQQ - already strong)
                strong_rs = rs_6mo >= TREND_CONT_RS_THRESHOLD

                # Pullback to 21-EMA
                ema21_value = ema21.iloc[-1]
                pullback_distance = abs(last_close - ema21_value) / ema21_value
                near_ema21 = pullback_distance <= (TREND_CONT_PULLBACK_ATR * atr14.iloc[-1] / last_close)

                # RSI not too weak
                rsi_ok = rsi14.iloc[-1] >= TREND_CONT_RSI_MIN

                # Trigger: Close > prior high AND > 21-EMA
                close_above_ema21 = last_close > ema21_value
                if len(high) >= 2:
                    close_above_prior_high = last_close > high.iloc[-2]
                else:
                    close_above_prior_high = False

                if all([stacked_mas, ma150_rising, strong_rs,
                       near_ema21, rsi_ok, close_above_ema21, close_above_prior_high]):
                    # Stop: Swing low or 3x ATR
                    swing_low = low.iloc[-10:].min() if len(low) >= 10 else last_close
                    stop_atr = last_close - (TREND_CONT_STOP_ATR_MULT * atr14.iloc[-1])
                    stop_price = max(swing_low, stop_atr)  # Most conservative

                    # Quality score
                    score = min((rs_6mo / TREND_CONT_RS_THRESHOLD) * 50, 70)  # Max 70
                    score += min((rsi14.iloc[-1] - TREND_CONT_RSI_MIN) / 20 * 30, 30)

                    signals.append({
                        "Ticker": ticker,
                        "Strategy": "TrendContinuation_Position",
                        "Priority": STRATEGY_PRIORITY["TrendContinuation_Position"],
                        "Price": round(last_close, 2),
                        "StopPrice": round(stop_price, 2),
                        "ATR14": round(atr14.iloc[-1], 2),
                        "RS_6mo": round(rs_6mo * 100, 2),
                        "RSI14": round(rsi14.iloc[-1], 2),
                        "Score": round(score, 2),
                        "AsOfDate": as_of_date,
                        "MaxDays": TREND_CONT_MAX_DAYS,
                    })
            except Exception:
                pass

        # =====================================================================
        # STRATEGY 7: RELATIVESTRENGTH_RANKER_POSITION (ACTIVE - BEST PERFORMER)
        # =====================================================================
        # Entry: Tech stocks, RS > +30%, new 3-mo high or pullback, ADX 30+, all MAs rising
        # =====================================================================
        if is_bull_regime and rs_6mo is not None:
            try:
                # Check if ticker is in tech sectors
                ticker_sector = get_ticker_sector(ticker)
                is_tech = ticker_sector in RS_RANKER_SECTORS

                if is_tech:
                    # VOLATILITY FILTER (Skip overly volatile stocks prone to whipsaw)
                    daily_returns = close.pct_change()
                    volatility_20d = daily_returns.rolling(20).std().iloc[-1] if len(daily_returns) >= 20 else 0
                    if volatility_20d > 0.04:  # More than 4% daily volatility
                        continue  # Too volatile, skip

                    # MULTI-MONTH TREND FILTERS
                    # Stacked MAs: Price > 50 > 100 > 200
                    stacked_mas = (last_close > ma50.iloc[-1] and
                                   ma50.iloc[-1] > ma100.iloc[-1] and
                                   ma100.iloc[-1] > ma200.iloc[-1])

                    # UNIVERSAL FILTERS (STRONGER)
                    strong_rs = rs_6mo >= UNIVERSAL_RS_MIN  # 30% minimum

                    # Trigger options:
                    # Option A: New 3-month high
                    high_3mo = high.rolling(63).max().iloc[-1] if len(high) >= 63 else 0
                    is_3mo_high = last_close >= high_3mo * 0.995

                    # Option B: Pullback to 21-EMA then close above
                    near_ema21 = abs(last_close - ema21.iloc[-1]) / ema21.iloc[-1] < 0.02  # Within 2%
                    if len(high) >= 2:
                        close_above_prior = last_close > high.iloc[-2]
                    else:
                        close_above_prior = False
                    pullback_breakout = near_ema21 and close_above_prior

                    if all([stacked_mas, all_mas_rising, strong_rs,
                           (is_3mo_high or pullback_breakout), strong_adx]):
                        # Stop
                        stop_price = last_close - (RS_RANKER_STOP_ATR_MULT * atr20.iloc[-1])

                        # Quality score (high for top RS)
                        score = min((rs_6mo / RS_RANKER_RS_THRESHOLD) * 100, 100)

                        signals.append({
                            "Ticker": ticker,
                            "Strategy": "RelativeStrength_Ranker_Position",
                            "Priority": STRATEGY_PRIORITY["RelativeStrength_Ranker_Position"],
                            "Price": round(last_close, 2),
                            "StopPrice": round(stop_price, 2),
                            "ATR20": round(atr20.iloc[-1], 2),
                            "RS_6mo": round(rs_6mo * 100, 2),
                            "Score": round(score, 2),
                            "AsOfDate": as_of_date,
                            "MaxDays": RS_RANKER_MAX_DAYS,
                        })
            except Exception:
                pass

    # -------------------------------------------------
    # Post-processing: Sort by priority then score
    # -------------------------------------------------
    if signals:
        # Sort by priority (lower = higher priority) then by score (higher = better)
        signals_df = pd.DataFrame(signals)
        signals_df = signals_df.sort_values(
            by=["Priority", "Score"],
            ascending=[True, False]
        )
        signals = signals_df.to_dict("records")

    return signals
