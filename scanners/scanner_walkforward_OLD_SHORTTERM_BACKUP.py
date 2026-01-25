import pandas as pd
from utils.market_data import get_historical_data
from utils.ema_utils import compute_rsi, compute_bollinger_bands, compute_percent_b
from core.pre_buy_check import compute_adx
from utils.sector_utils import get_ticker_sector
from config.trading_config import (
    MAX_ENTRY_GAP_PCT,
    TECHMOMENTUM_INDEX,
    TECHMOMENTUM_PULLBACK_ATR_MULTIPLE,
    TECHMOMENTUM_RSI_MIN,
    TECHMOMENTUM_RELATIVE_STRENGTH_THRESHOLD,
    TECHMOMENTUM_SECTORS,
    TECHMOMENTUM_MIN_LIQUIDITY
)


def run_scan_as_of(as_of_date, tickers):
    """
    Walk-forward scanner using ONLY data available up to as_of_date.
    Returns signals compatible with pre_buy_check().
    """
    # Convert as_of_date to timestamp first
    as_of_date = pd.to_datetime(as_of_date)

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

    # -------------------------------------------------
    # TechMomentum: QQQ/NASDAQ regime filter (SMA200)
    # -------------------------------------------------
    techmomentum_regime_ok = False
    qqq_df = pd.DataFrame()  # Initialize empty DataFrame

    try:
        qqq_df = get_historical_data(TECHMOMENTUM_INDEX)
        if not qqq_df.empty and isinstance(qqq_df.index, pd.DatetimeIndex):
            qqq_df = qqq_df[qqq_df.index <= as_of_date]

            if len(qqq_df) >= 220:  # Need 200 + 20 days for comparison
                qqq_close = qqq_df["Close"].iloc[-1]
                qqq_sma200 = qqq_df["Close"].rolling(200).mean().iloc[-1]
                qqq_sma200_20d_ago = qqq_df["Close"].rolling(200).mean().iloc[-21]  # 20 days ago

                # Regime condition: Index > SMA200 AND SMA200 rising over 20 days
                techmomentum_regime_ok = (
                    qqq_close > qqq_sma200 and
                    qqq_sma200 > qqq_sma200_20d_ago
                )
    except Exception as e:
        # If QQQ data is missing or invalid, TechMomentum regime is False
        # print(f"Warning: Could not load QQQ data for TechMomentum regime filter: {e}")
        techmomentum_regime_ok = False
        qqq_df = pd.DataFrame()  # Ensure it's empty on error

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

        # 🆕 GAP FILTER: Skip if stock gapped too much on signal day
        # (Avoids buying extended after big gaps)
        if len(df) >= 2:
            prev_close = close.iloc[-2]
            current_close = close.iloc[-1]
            gap_pct = abs((current_close - prev_close) / prev_close * 100)

            if gap_pct > MAX_ENTRY_GAP_PCT:
                continue  # Skip this ticker - gapped too much

        # -------------------------------
        # Indicators (AS-OF DATE ONLY)
        # -------------------------------
        ema10 = close.ewm(span=10).mean()
        ema20 = close.ewm(span=20).mean()
        ema50 = close.ewm(span=50).mean()
        ema200 = close.ewm(span=200).mean()
        rsi14 = compute_rsi(close, 14)

        last_close = close.iloc[-1]

        # ==========================================================
        # EMA Crossover Strategy (🔧 COMPLETELY REDESIGNED)
        # ==========================================================
        # 🔧 SIMPLIFIED: EMA10/20 crossover (not EMA5/10)
        # 🔧 TIGHTER FILTERS: ADX 30+, RSI 55-70, Vol 1.5x
        # 🔧 PULLBACK ENTRY: Price near EMA20
        # 🔧 WEEKLY TREND: Must be above weekly EMA50
        if True:  # Always check (no pre-filter)
            # ========================================
            # 🔧 STEP 1: Detect EMA10/20 Crossover (Last 2 Days)
            # ========================================
            cross_detected = False
            for i in range(1, 3):  # Only last 2 days (tighter window)
                if ema10.iloc[-i] <= ema20.iloc[-i] and ema10.iloc[-i+1] > ema20.iloc[-i+1]:
                    cross_detected = True
                    break

            # ========================================
            # 🔧 STEP 2: Verify Cascading Pattern
            # ========================================
            cascading_pattern = (
                ema10.iloc[-1] > ema20.iloc[-1] > ema50.iloc[-1]
            )

            # ========================================
            # 🔧 STEP 3: Pullback Filter (Price Near EMA20)
            # ========================================
            pullback = abs(df['Close'].iloc[-1] - ema20.iloc[-1]) / ema20.iloc[-1] < 0.005  # Within 0.5%

            # ========================================
            # 🔧 STEP 4: Weekly EMA50 Trend Filter
            # ========================================
            # Resample to weekly and check weekly EMA50
            try:
                weekly_close = df['Close'].resample('W').last()
                if len(weekly_close) >= 50:
                    weekly_ema50 = weekly_close.ewm(span=50, adjust=False).mean()
                    above_weekly_ema50 = df['Close'].iloc[-1] > weekly_ema50.iloc[-1]
                else:
                    above_weekly_ema50 = True  # Skip if not enough weekly data
            except:
                above_weekly_ema50 = True  # Skip if resampling fails

            crossover_type = "Cascading" if cross_detected and cascading_pattern else "None"
            crossover_bonus = 25 if crossover_type == "Cascading" else 0

            # ========================================
            # 🔧 STEP 5: Tightened Filters
            # ========================================
            adx = compute_adx(df)
            adx_value = adx.iloc[-1] if len(adx) > 0 else 0

            avg_vol = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()
            vol_ratio = volume.iloc[-1] / max(avg_vol, 1)

            rsi_value = rsi14.iloc[-1]

            # 🔧 MUCH TIGHTER FILTERS (can be relaxed to ADX 25 if too few trades)
            trend_strong = adx_value >= 30              # Strong trend required
            rsi_healthy = 55 <= rsi_value <= 70         # Momentum range
            volume_confirmed = vol_ratio >= 1.5         # Above-average volume

            # All conditions must be met
            if all([
                cross_detected,
                cascading_pattern,
                pullback,
                above_weekly_ema50,
                trend_strong,
                rsi_healthy,
                volume_confirmed
            ]):
                # ========================================
                # 🔧 SIMPLIFIED SCORING SYSTEM
                # ========================================
                # Base score: 75 points
                adx_score = min((adx_value - 30) / 20, 1.0) * 25      # 0-25 points
                rsi_score = min((rsi_value - 55) / 15, 1.0) * 25      # 0-25 points
                volume_score = min((vol_ratio - 1.5) / 1.5, 1.0) * 25 # 0-25 points

                # Cascading bonus: 25 points
                quality_score = adx_score + rsi_score + volume_score + crossover_bonus  # Max 100

                signals.append({
                    "Ticker": ticker,
                    "Strategy": "EMA Crossover",
                    "Price": round(last_close, 2),
                    "AsOfDate": as_of_date,
                    "EMA10": round(ema10.iloc[-1], 2),
                    "EMA20": round(ema20.iloc[-1], 2),
                    "EMA50": round(ema50.iloc[-1], 2),
                    "RSI14": round(rsi_value, 2),
                    "ADX14": round(adx_value, 2),
                    "VolumeRatio": round(vol_ratio, 2),
                    "CrossoverType": crossover_type,
                    "CrossoverBonus": round(crossover_bonus, 2),
                    "Score": round(quality_score, 2),
                    "MarketRegime": market_regime,
                })

        # ==========================================================
        # 52-Week High Strategy (🔧 MUCH TIGHTER FILTERS)
        # ==========================================================
        high_52w = close.rolling(252).max().iloc[-1]
        current_price = last_close

        # 🔧 TRUE BREAKOUT: Within 0.5% of 52W high (not 2%)
        near_52w_high = current_price >= high_52w * 0.995  # Within 0.5%

        # 🔧 REQUIRE 3 CONSECUTIVE HIGHER CLOSES
        if len(close) >= 4:
            higher_closes = (
                close.iloc[-1] > close.iloc[-2] and
                close.iloc[-2] > close.iloc[-3] and
                close.iloc[-3] > close.iloc[-4]
            )
        else:
            higher_closes = False

        if near_52w_high and higher_closes:
            # Calculate indicators
            adx = compute_adx(df)
            adx_value = adx.iloc[-1] if len(adx) > 0 else 0

            avg_vol = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()
            vol_ratio = volume.iloc[-1] / max(avg_vol, 1)

            rsi_value = rsi14.iloc[-1]

            # 🔧 MUCH TIGHTER FILTERS (can be relaxed to ADX 25-30 if too few trades)
            trend_strong = adx_value >= 35              # Very strong trend
            rsi_momentum = 55 <= rsi_value <= 75        # Strong momentum range
            volume_surge = vol_ratio >= 2.5             # 2.5x volume required

            if all([trend_strong, rsi_momentum, volume_surge]):
                # Simplified scoring
                proximity_score = (current_price / high_52w - 0.995) / 0.005 * 50  # Max 50 pts
                momentum_score = min((adx_value - 35) / 15, 1.0) * 25              # Max 25 pts
                volume_score = min((vol_ratio - 2.5) / 2.5, 1.0) * 25              # Max 25 pts
                quality_score = proximity_score + momentum_score + volume_score     # Max 100 pts

                signals.append({
                    "Ticker": ticker,
                    "Strategy": "52-Week High",
                    "Price": round(last_close, 2),
                    "AsOfDate": as_of_date,
                    "High52W": round(high_52w, 2),
                    "RSI14": round(rsi_value, 2),
                    "ADX14": round(adx_value, 2),
                    "VolumeRatio": round(vol_ratio, 2),
                    "Score": round(quality_score, 2),
                    "CrossoverType": "N/A",
                    "CrossoverBonus": 0,
                    "MarketRegime": market_regime,
                })

        # ==========================================================
        # Consolidation Breakout Strategy (🔧 MUCH TIGHTER)
        # ==========================================================
        # 🔧 7-day range < 3%, breakout > 2% above range, vol >= 3x, ADX >= 25
        if len(df) >= 7:
            high_7d = high.iloc[-7:].max()
            low_7d = low.iloc[-7:].min()
            range_7d = high_7d - low_7d
            range_pct = range_7d / last_close

            # Breakout strength
            breakout_pct = (last_close - high_7d) / high_7d

            # Volume confirmation
            avg_vol = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()
            vol_ratio = volume.iloc[-1] / max(avg_vol, 1)

            # 🔧 MUCH TIGHTER consolidation and breakout conditions
            tight_consolidation = range_pct < 0.03      # 7-day range < 3% (was 20-day < 8%)
            strong_breakout = breakout_pct > 0.02       # Breakout > 2% above range
            huge_volume = vol_ratio >= 3.0              # 3x volume (was 1.5x)

            if tight_consolidation and strong_breakout and huge_volume:
                # Calculate indicators
                adx = compute_adx(df)
                adx_value = adx.iloc[-1] if len(adx) > 0 else 0
                rsi_value = rsi14.iloc[-1]

                # 🔧 TIGHTER FILTERS
                trend_strong = adx_value >= 25          # Strong trend (was 20)

                if trend_strong:
                    # Simplified scoring
                    consolidation_score = (0.03 - range_pct) / 0.03 * 40  # Max 40 pts
                    breakout_score = min(breakout_pct / 0.05, 1.0) * 30   # Max 30 pts
                    volume_score = min((vol_ratio - 3.0) / 3.0, 1.0) * 30 # Max 30 pts
                    quality_score = consolidation_score + breakout_score + volume_score  # Max 100

                    signals.append({
                        "Ticker": ticker,
                        "Strategy": "Consolidation Breakout",
                        "Price": round(last_close, 2),
                        "AsOfDate": as_of_date,
                        "Range7DPct": round(range_pct * 100, 2),
                        "BreakoutPct": round(breakout_pct * 100, 2),
                        "ADX14": round(adx_value, 2),
                        "VolumeRatio": round(vol_ratio, 2),
                        "Score": round(quality_score, 2),
                        "CrossoverType": "N/A",
                        "CrossoverBonus": 0,
                        "MarketRegime": market_regime,
                })

        # ==========================================================
        # Mean Reversion Strategy (🔧 ADJUSTED)
        # ==========================================================
        # Entry: Price > EMA20 > EMA50, RSI(2) < 12
        # Exit: RSI(2) > 65 OR Close > MA5 (1 day)
        # Expected: 75-80% win rate, 3-5 day holding

        # Calculate RSI(2) - very sensitive, catches extreme oversold
        rsi2 = compute_rsi(close, 2)

        # Need enough data
        if len(df) >= 200:
            rsi2_value = rsi2.iloc[-1]
            rsi14_value = rsi14.iloc[-1]

            # 🔧 ADJUSTED Entry Rules:
            # 1. Price ABOVE EMA20 (uptrend filter)
            # 2. EMA20 ABOVE EMA50 (strong uptrend)
            # 3. RSI(2) below 12 (oversold) - Was 10 (loosened slightly)
            # 4. RSI(14) below 55 (not overbought on longer timeframe)
            uptrend = last_close > ema20.iloc[-1]
            strong_uptrend = ema20.iloc[-1] > ema50.iloc[-1]
            oversold = rsi2_value < 12  # 🔧 Was 10 (slightly looser)
            rsi14_ok = rsi14_value < 55  # Not overbought on longer TF

            if uptrend and strong_uptrend and oversold and rsi14_ok:
                # Calculate volume and ADX
                avg_vol = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()
                vol_ratio = volume.iloc[-1] / max(avg_vol, 1)

                adx = compute_adx(df)
                adx_value = adx.iloc[-1] if len(adx) > 0 else 0

                # Filters (moderate)
                volume_adequate = vol_ratio >= 0.8  # Normal volume
                trend_exists = adx_value >= 20      # Trending market

                if volume_adequate and trend_exists:
                    # 🔧 Simplified scoring
                    oversold_score = (12 - rsi2_value) * 5  # Max 60 points (RSI 0 = 60 pts)
                    uptrend_score = min((last_close - ema20.iloc[-1]) / ema20.iloc[-1] * 100, 1.0) * 20  # Max 20 pts
                    volume_score = min(vol_ratio / 2.0, 1.0) * 10  # Max 10 pts
                    trend_score = min(adx_value / 30, 1.0) * 10  # Max 10 pts

                    mr_quality_score = oversold_score + uptrend_score + volume_score + trend_score  # Max 100

                    signals.append({
                        "Ticker": ticker,
                        "Strategy": "Mean Reversion",
                        "Price": round(last_close, 2),
                        "AsOfDate": as_of_date,
                        "EMA20": round(ema20.iloc[-1], 2),
                        "EMA50": round(ema50.iloc[-1], 2),
                        "RSI2": round(rsi2_value, 2),
                        "RSI14": round(rsi14_value, 2),
                        "ADX14": round(adx_value, 2),
                        "VolumeRatio": round(vol_ratio, 2),
                        "Score": round(mr_quality_score, 2),
                        "CrossoverType": "N/A",
                        "CrossoverBonus": 0,
                        "MarketRegime": market_regime,
                    })

        # ==========================================================
        # Bollinger Band Strategies
        # ==========================================================
        # Calculate Bollinger Bands (20-period, 2 std dev)
        middle_band, upper_band, lower_band, bandwidth = compute_bollinger_bands(close, period=20, std_dev=2)

        if len(df) >= 20 and not bandwidth.isna().iloc[-1]:
            # Current values
            bb_middle = middle_band.iloc[-1]
            bb_upper = upper_band.iloc[-1]
            bb_lower = lower_band.iloc[-1]
            bb_width = bandwidth.iloc[-1]

            # Calculate %B
            percent_b = compute_percent_b(close, upper_band, lower_band)
            percent_b_value = percent_b.iloc[-1]

            # Calculate volume for all BB strategies
            avg_vol = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()
            vol_ratio = volume.iloc[-1] / max(avg_vol, 1)

            # ==========================================================
            # Strategy 1: BB Squeeze (🔧 MUCH TIGHTER)
            # ==========================================================
            # Entry: 2 closes above upper band + huge volume + tight squeeze
            # Setup: BandWidth at 6-month low (squeeze indicator)

            # 🔧 Check if bandwidth is at 6-month low × 1.10 (was 1.05)
            if len(bandwidth) >= 126:  # 6 months ≈ 126 trading days
                bandwidth_6m_low = bandwidth.iloc[-126:].min()
                is_squeeze = bb_width <= bandwidth_6m_low * 1.10  # 🔧 Was 1.05
            else:
                # Fallback: check if bandwidth is at lowest in available data
                is_squeeze = bb_width <= bandwidth.min() * 1.10

            # 🔧 REQUIRE 2 CONSECUTIVE CLOSES ABOVE UPPER BAND (was 1)
            if len(close) >= 2:
                # Use upper_band Series directly for previous value
                bb_upper_prev = upper_band.iloc[-2]

                two_closes_above = (
                    close.iloc[-1] > bb_upper and
                    close.iloc[-2] > bb_upper_prev
                )
            else:
                two_closes_above = False

            # 🔧 HUGE VOLUME REQUIRED: 2.5x (was 1.5x)
            volume_surge = vol_ratio >= 2.5

            # 🔧 RE-ENABLED with much tighter filters
            if is_squeeze and two_closes_above and volume_surge:
                # Calculate indicators
                adx = compute_adx(df)
                adx_value = adx.iloc[-1] if len(adx) > 0 else 0

                # 🔧 MUCH TIGHTER FILTERS
                trend_strong = adx_value >= 25  # Strong trend (was 20)

                if trend_strong:
                    # 🔧 Simplified scoring
                    squeeze_score = min((1 - bb_width / bandwidth.rolling(126).mean().iloc[-1]) * 100, 40)  # Max 40 pts
                    breakout_strength = min(((last_close - bb_upper) / bb_upper * 100) * 10, 30)  # Max 30 pts
                    volume_score = min((vol_ratio - 2.5) / 2.5, 1.0) * 30  # Max 30 pts

                    bb_squeeze_score = squeeze_score + breakout_strength + volume_score  # Max 100

                    signals.append({
                        "Ticker": ticker,
                        "Strategy": "BB Squeeze",
                        "Price": round(last_close, 2),
                        "AsOfDate": as_of_date,
                        "BB_Upper": round(bb_upper, 2),
                        "BB_Lower": round(bb_lower, 2),
                        "BandWidth": round(bb_width, 2),
                        "ADX14": round(adx_value, 2),
                        "VolumeRatio": round(vol_ratio, 2),
                        "Score": round(bb_squeeze_score, 2),
                        "CrossoverType": "N/A",
                        "CrossoverBonus": 0,
                        "MarketRegime": market_regime,
                    })

            # ==========================================================
            # Strategy 2: %B Mean Reversion
            # ==========================================================
            # Entry: %B < 0.15, RSI2 < 20, RSI14 < 35 (triple confirmation)
            # Exit: %B > 0.4 (faster exit)
            # Expected: 75-80% win rate with tight filters

            # Calculate MA200 for uptrend filter
            ma200 = close.rolling(200).mean()
            rsi2 = compute_rsi(close, 2)

            if len(df) >= 200 and not ma200.isna().iloc[-1]:
                ma200_value = ma200.iloc[-1]
                rsi2_value = rsi2.iloc[-1]
                rsi14_value = rsi14.iloc[-1]

                # 🔧 MUCH TIGHTER Entry Rules (triple oversold confirmation):
                # 1. %B < 0.15 (extreme oversold on BB)
                # 2. RSI(2) < 20 (extreme oversold short-term)
                # 3. RSI(14) < 35 (oversold longer-term)
                # 4. Price ABOVE 200-day MA (uptrend filter)
                bb_extreme_oversold = percent_b_value < 0.15  # 🔧 Was 0.2
                rsi2_oversold = rsi2_value < 20               # 🔧 New
                rsi14_oversold = rsi14_value < 35              # 🔧 Was 40
                in_uptrend = last_close > ma200_value

                if bb_extreme_oversold and rsi2_oversold and rsi14_oversold and in_uptrend:
                    # Calculate ADX and volume
                    adx = compute_adx(df)
                    adx_value = adx.iloc[-1] if len(adx) > 0 else 0

                    avg_vol = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()
                    vol_ratio = volume.iloc[-1] / max(avg_vol, 1)

                    # Moderate filters
                    volume_adequate = vol_ratio >= 0.8  # Normal volume
                    trend_exists = adx_value >= 20      # Trending market

                    if volume_adequate and trend_exists:
                        # 🔧 Simplified scoring (triple confirmation = high quality)
                        bb_score = (0.15 - percent_b_value) * 200    # Max 30 pts (%B at 0)
                        rsi2_score = (20 - rsi2_value) * 2           # Max 40 pts (RSI2 at 0)
                        rsi14_score = (35 - rsi14_value) * 0.857     # Max 30 pts (RSI14 at 0)

                        percent_b_mr_score = min(bb_score + rsi2_score + rsi14_score, 100)  # Max 100

                        signals.append({
                            "Ticker": ticker,
                            "Strategy": "%B Mean Reversion",
                            "Price": round(last_close, 2),
                            "AsOfDate": as_of_date,
                            "BB_Upper": round(bb_upper, 2),
                            "BB_Lower": round(bb_lower, 2),
                            "PercentB": round(percent_b_value, 2),
                            "RSI2": round(rsi2_value, 2),
                            "RSI14": round(rsi14_value, 2),
                            "ADX14": round(adx_value, 2),
                            "VolumeRatio": round(vol_ratio, 2),
                            "Score": round(percent_b_mr_score, 2),
                            "CrossoverType": "N/A",
                            "CrossoverBonus": 0,
                            "MarketRegime": market_regime,
                        })

            # ==========================================================
            # Strategy 3: Bollinger + RSI Combo (🔧 TRIPLE CONFIRMATION)
            # ==========================================================
            # Entry: %B < 0.2, RSI14 < 30, RSI2 < 15, Above MA50 & MA200
            # Exit: %B > 0.6 OR RSI14 > 60 (faster exits)
            # Expected: 80% win rate with triple confirmation + dual uptrend filters

            # Calculate MA50 and MA200
            ma50 = close.rolling(50).mean()
            ma200 = close.rolling(200).mean()
            rsi2 = compute_rsi(close, 2)

            if len(df) >= 200 and not ma50.isna().iloc[-1] and not ma200.isna().iloc[-1]:
                ma50_value = ma50.iloc[-1]
                ma200_value = ma200.iloc[-1]
                rsi2_value = rsi2.iloc[-1]
                rsi14_value = rsi14.iloc[-1]

                # 🔧 TRIPLE CONFIRMATION Entry Rules:
                # 1. %B < 0.2 (extreme oversold on BB)
                # 2. RSI(14) < 30 (oversold longer-term)
                # 3. RSI(2) < 15 (extreme oversold short-term)
                # 4. Price > MA50 (medium-term uptrend)
                # 5. Price > MA200 (long-term uptrend)
                bb_oversold = percent_b_value < 0.2      # 🔧 Was 0.3
                rsi14_oversold = rsi14_value < 30         # 🔧 Was 35
                rsi2_extreme = rsi2_value < 15            # 🔧 New (triple confirmation)
                above_ma50 = last_close > ma50_value      # 🔧 Required (not optional)
                above_ma200 = last_close > ma200_value    # 🔧 Required (not optional)

                if bb_oversold and rsi14_oversold and rsi2_extreme and above_ma50 and above_ma200:
                    # Calculate ADX and volume
                    adx = compute_adx(df)
                    adx_value = adx.iloc[-1] if len(adx) > 0 else 0

                    avg_vol = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()
                    vol_ratio = volume.iloc[-1] / max(avg_vol, 1)

                    # Moderate filters
                    volume_adequate = vol_ratio >= 0.8  # Normal volume
                    trend_exists = adx_value >= 20      # Trending market

                    if volume_adequate and trend_exists:
                        # 🔧 Simplified scoring (triple confirmation = very high quality)
                        bb_score = (0.2 - percent_b_value) * 150      # Max 30 pts (%B at 0)
                        rsi14_score = (30 - rsi14_value) * 1.33       # Max 40 pts (RSI14 at 0)
                        rsi2_score = (15 - rsi2_value) * 2            # Max 30 pts (RSI2 at 0)

                        bb_rsi_combo_score = min(bb_score + rsi14_score + rsi2_score, 100)  # Max 100

                        signals.append({
                            "Ticker": ticker,
                            "Strategy": "BB+RSI Combo",
                            "Price": round(last_close, 2),
                            "AsOfDate": as_of_date,
                            "BB_Upper": round(bb_upper, 2),
                            "BB_Lower": round(bb_lower, 2),
                            "PercentB": round(percent_b_value, 2),
                            "RSI2": round(rsi2_value, 2),
                            "RSI14": round(rsi14_value, 2),
                            "MA50": round(ma50_value, 2),
                            "MA200": round(ma200_value, 2),
                            "ADX14": round(adx_value, 2),
                            "VolumeRatio": round(vol_ratio, 2),
                            "Score": round(bb_rsi_combo_score, 2),
                            "CrossoverType": "N/A",
                            "CrossoverBonus": 0,
                            "MarketRegime": market_regime,
                        })

        # ==========================================================
        # TechMomentum_Swing_30_60 Strategy
        # ==========================================================
        # Medium-term momentum swings in tech stocks (20-60 trading days)
        # Entry: Pullback to EMA20 with RSI ≥ 40, then resumption
        # Exit: ATR-based trailing stop, max 60 days

        # Check if ticker is in tech/communication services sectors
        ticker_sector = get_ticker_sector(ticker)
        is_tech_sector = ticker_sector in TECHMOMENTUM_SECTORS

        # Only scan if QQQ regime is bullish AND ticker is in tech sectors
        if techmomentum_regime_ok and is_tech_sector and len(df) >= 200:
            # Calculate indicators
            sma50 = close.rolling(50).mean()
            sma100 = close.rolling(100).mean()
            sma200 = close.rolling(200).mean()

            if not sma50.isna().iloc[-1] and not sma100.isna().iloc[-1] and not sma200.isna().iloc[-1]:
                current_sma50 = sma50.iloc[-1]
                current_sma100 = sma100.iloc[-1]
                current_sma200 = sma200.iloc[-1]

                # Calculate ATR for pullback detection
                high_arr = high.values
                low_arr = low.values
                close_arr = close.values

                # True Range calculation
                tr = pd.Series([
                    max(
                        high_arr[i] - low_arr[i],
                        abs(high_arr[i] - close_arr[i-1]) if i > 0 else 0,
                        abs(low_arr[i] - close_arr[i-1]) if i > 0 else 0
                    )
                    for i in range(len(close_arr))
                ], index=close.index)
                atr14 = tr.rolling(14).mean()

                if not atr14.isna().iloc[-1]:
                    current_atr = atr14.iloc[-1]

                    # ========================================
                    # STEP 1: Trend Conditions
                    # ========================================
                    trend_condition_1 = last_close > current_sma100
                    trend_condition_2 = current_sma50 > current_sma100

                    # SMA100 rising over 20 days
                    if len(sma100) >= 21:
                        sma100_20d_ago = sma100.iloc[-21]
                        trend_condition_3 = current_sma100 > sma100_20d_ago
                    else:
                        trend_condition_3 = False

                    trend_ok = trend_condition_1 and trend_condition_2 and trend_condition_3

                    if trend_ok:
                        # ========================================
                        # STEP 2: Relative Strength Filter
                        # ========================================
                        # Calculate 60-day return for stock
                        if len(close) >= 60 and not qqq_df.empty:
                            close_60d_ago = close.iloc[-60]
                            r60_stock = (last_close / close_60d_ago) - 1.0

                            # Calculate 60-day return for index (QQQ)
                            qqq_recent = qqq_df[qqq_df.index <= as_of_date]
                            if len(qqq_recent) >= 60:
                                qqq_close_60d_ago = qqq_recent["Close"].iloc[-60]
                                qqq_close_current = qqq_recent["Close"].iloc[-1]
                                r60_index = (qqq_close_current / qqq_close_60d_ago) - 1.0

                                # Relative strength condition: stock outperforms index by 5%+
                                relative_strength_ok = r60_stock >= (r60_index + TECHMOMENTUM_RELATIVE_STRENGTH_THRESHOLD)

                                if relative_strength_ok:
                                    # ========================================
                                    # STEP 3: Pullback Detection (Yesterday)
                                    # ========================================
                                    # Check if YESTERDAY was a pullback day
                                    # We need at least 2 days of data to check yesterday
                                    if len(df) >= 2:
                                        yesterday_close = close.iloc[-2]
                                        yesterday_low = low.iloc[-2]
                                        yesterday_ema20 = ema20.iloc[-2]
                                        yesterday_rsi14 = rsi14.iloc[-2]
                                        yesterday_high = high.iloc[-2]

                                        # Condition A: Price within 1 × ATR of EMA20
                                        proximity_condition = (
                                            abs(yesterday_close - yesterday_ema20) <= (1.0 * current_atr) or
                                            yesterday_low <= (yesterday_ema20 + 1.0 * current_atr)
                                        )

                                        # Condition B: RSI(14) ≥ 40 (no deep momentum break)
                                        rsi_condition = yesterday_rsi14 >= TECHMOMENTUM_RSI_MIN

                                        pullback_detected = proximity_condition and rsi_condition

                                        if pullback_detected:
                                            # ========================================
                                            # STEP 4: Entry Trigger (Today)
                                            # ========================================
                                            # Today's close > yesterday's high (bullish confirmation)
                                            bullish_resumption = last_close > yesterday_high

                                            # Close still > EMA20
                                            above_ema20 = last_close > ema20.iloc[-1]

                                            entry_trigger = bullish_resumption and above_ema20

                                            if entry_trigger:
                                                # ========================================
                                                # Volume and liquidity check
                                                # ========================================
                                                avg_vol_20d = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()
                                                avg_price_20d = close.rolling(20).mean().iloc[-1]
                                                dollar_volume_20d = avg_vol_20d * avg_price_20d

                                                # Must meet minimum liquidity threshold ($20M+ average 20-day dollar volume)
                                                if dollar_volume_20d >= TECHMOMENTUM_MIN_LIQUIDITY:
                                                    # Calculate quality score
                                                    # Based on: trend strength, relative strength, proximity to EMA20, RSI
                                                    trend_strength = (current_sma50 - current_sma100) / current_sma100 * 100
                                                    trend_score = min(trend_strength * 10, 30)  # Max 30 pts

                                                    rs_excess = (r60_stock - r60_index - TECHMOMENTUM_RELATIVE_STRENGTH_THRESHOLD) * 100
                                                    rs_score = min(rs_excess * 2, 30)  # Max 30 pts

                                                    pullback_depth = abs(yesterday_close - yesterday_ema20) / current_atr
                                                    proximity_score = (1.0 - pullback_depth) * 20  # Max 20 pts (closer = better)

                                                    rsi_score = min((yesterday_rsi14 - 40) / 20 * 20, 20)  # Max 20 pts

                                                    quality_score = trend_score + rs_score + proximity_score + rsi_score

                                                    signals.append({
                                                        "Ticker": ticker,
                                                        "Strategy": "TechMomentum_Swing_30_60",
                                                        "Price": round(last_close, 2),
                                                        "AsOfDate": as_of_date,
                                                        "EMA20": round(ema20.iloc[-1], 2),
                                                        "SMA50": round(current_sma50, 2),
                                                        "SMA100": round(current_sma100, 2),
                                                        "SMA200": round(current_sma200, 2),
                                                        "RSI14": round(rsi14.iloc[-1], 2),
                                                        "ATR14": round(current_atr, 2),
                                                        "R60_Stock": round(r60_stock * 100, 2),
                                                        "R60_Index": round(r60_index * 100, 2),
                                                        "RelativeStrength": round((r60_stock - r60_index) * 100, 2),
                                                        "Score": round(quality_score, 2),
                                                        "CrossoverType": "N/A",
                                                        "CrossoverBonus": 0,
                                                        "MarketRegime": "QQQ_BULLISH",
                                                    })

    return signals
