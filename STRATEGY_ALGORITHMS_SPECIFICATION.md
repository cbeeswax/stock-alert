# Trading Strategy Algorithms - Complete Specification

**System**: Walk-forward backtesting stock trading system (2022-2026)
**Problem**: Cascading crossover strategy has 18.8% WR (expected 65%)
**Overall Performance**: 543 trades, 37.75% WR, 0.40R avg, 51.6% stop loss rate

---

## Table of Contents
1. [Van Tharp Expectancy Scoring System](#van-tharp-expectancy-scoring-system)
2. [Strategy Deduplication & Priority](#strategy-deduplication--priority)
3. [Stop Loss Placement by Strategy](#stop-loss-placement-by-strategy)
4. [Strategy 1: EMA Crossover (Cascading)](#strategy-1-ema-crossover-cascading)
5. [Strategy 2: 52-Week High](#strategy-2-52-week-high)
6. [Strategy 3: Mean Reversion (RSI-2)](#strategy-3-mean-reversion-rsi-2)
7. [Strategy 4: Consolidation Breakout](#strategy-4-consolidation-breakout)
8. [Strategy 5: %B Mean Reversion](#strategy-5-b-mean-reversion)
9. [Strategy 6: BB+RSI Combo](#strategy-6-bbrsi-combo)
10. [Strategy 7: BB Squeeze](#strategy-7-bb-squeeze)
11. [Exit Logic (Global)](#exit-logic-global)
12. [Risk Management](#risk-management)
13. [Cascading Issue Analysis](#cascading-issue-analysis)

---

## Van Tharp Expectancy Scoring System

### Purpose
Rank all signals by combining **signal quality** with **strategy profitability** based on actual backtest results.

### Formula
```
FinalScore = Quality × Expectancy × 10
```

Where:
- **Quality** = Normalized raw score (0-1)
- **Expectancy** = (WinRate × AvgWin) - ((1 - WinRate) × |AvgLoss|)
- **× 10** = Readability scaling

### Strategy Metrics (From Actual Backtest 2022-2026, 661 trades)

```python
STRATEGY_METRICS = {
    # Format: (Win Rate, Avg Win R-Multiple, Avg Loss R-Multiple)

    "Mean Reversion": (0.75, 0.87, -0.52),      # 60 trades, 75% WR, 0.52R expectancy ✅ WORKING
    "52-Week High": (0.30, 2.00, -0.32),        # 503 trades, 30.2% WR, 0.38R expectancy
    "Consolidation Breakout": (0.22, 2.00, -0.32), # 49 trades, 22.4% WR, 0.20R expectancy
    "EMA Crossover": (0.15, 2.00, -0.30),       # 48 trades, 14.6% WR, 0.29R expectancy ❌ BROKEN
    "BB Squeeze": (0.10, 1.50, -1.00),          # 1 trade, 0% WR, -1.00R
    "%B Mean Reversion": (0.50, 0.80, -0.80),   # Not enough trades yet (re-enabled with fixes)
    "BB+RSI Combo": (0.50, 0.90, -0.80),        # Not enough trades yet (re-enabled with fixes)
}
```

### Score Normalization Ranges

```python
ranges = {
    "EMA Crossover": (50, 100),           # Base: 75 pts + Crossover bonus: 25 pts
    "52-Week High": (6, 12),              # Simple scoring
    "Consolidation Breakout": (4, 10),    # Range + volume based
    "BB Squeeze": (50, 100),              # Squeeze + breakout + volume
    "Mean Reversion": (40, 100),          # RSI(2) based: Max 100 pts
    "%B Mean Reversion": (40, 100),       # %B based: Max 100 pts
    "BB+RSI Combo": (50, 100),            # Double confirmation: Max 100 pts
}

# Normalization:
quality = (raw_score - low) / (high - low)
quality = clamp(quality, 0, 1)
```

### Example Calculation

**Signal: Mean Reversion with Raw Score 85**

1. Quality = (85 - 40) / (100 - 40) = 45/60 = **0.75**
2. Expectancy = (0.75 × 0.87) - (0.25 × 0.52) = 0.6525 - 0.13 = **0.5225R**
3. FinalScore = 0.75 × 0.5225 × 10 = **3.92**

---

## Strategy Deduplication & Priority

If the same ticker has multiple signals, only the **highest priority** strategy is kept:

```python
priority = {
    "EMA Crossover": 7,          # Highest (expected 65% WR)
    "BB+RSI Combo": 6,           # Double confirmation
    "Mean Reversion": 5,         # Proven 75% WR
    "%B Mean Reversion": 5,      # Mean reversion variant
    "52-Week High": 4,           # Momentum
    "BB Squeeze": 3,             # Volatility breakout
    "Consolidation Breakout": 2, # Weak momentum
    "Relative Strength": 1,      # Lowest
}
```

**Rationale**: Higher win rate strategies get priority when conflicts occur.

---

## Stop Loss Placement by Strategy

All stops are **ATR-based** to adapt to volatility:

```python
# Calculate 14-day ATR
atr = calculate_atr(df, period=14)

# Stop placement by strategy type
if strategy in ["52-Week High", "Consolidation Breakout"]:
    stop = entry - 1.5 * atr  # Momentum strategies

elif strategy == "EMA Crossover":
    stop = entry - 1.5 * atr  # 🔧 WIDENED from 1.0 ATR (was too tight)

elif strategy == "Mean Reversion":
    stop = entry - 2.0 * atr  # Wider for mean reversion (buying weakness)

elif strategy == "BB Squeeze":
    stop = entry - 1.5 * atr  # Momentum breakout

elif strategy == "%B Mean Reversion":
    stop = entry - 2.0 * atr  # Wider for mean reversion

elif strategy == "BB+RSI Combo":
    stop = entry - 1.5 * atr  # Double confirmation provides confidence

else:
    stop = entry - 1.2 * atr  # Default
```

**Target Calculation**:
```python
risk_reward_ratio = 3.0  # From config
target = entry + risk_reward_ratio * (entry - stop)
```

---

## Strategy 1: EMA Crossover (Cascading)

### Concept
Detect when fast EMAs (5, 10) cross above slow EMAs (20, 50) in a "cascading" pattern, indicating strong bullish momentum.

### Entry Conditions

**Step 1: Detect Cascading Crossover**
```python
# Calculate EMAs
ema5 = df['Close'].ewm(span=5, adjust=False).mean()
ema10 = df['Close'].ewm(span=10, adjust=False).mean()
ema20 = df['Close'].ewm(span=20, adjust=False).mean()
ema50 = df['Close'].ewm(span=50, adjust=False).mean()

# Check for cascading pattern (all EMAs in order)
cascading_pattern = (
    ema5.iloc[-1] > ema10.iloc[-1] > ema20.iloc[-1] > ema50.iloc[-1]
)

# Detect recent crossover (EMA5 crossed EMA10 in last 5 days)
cross_detected = False
for i in range(1, 6):
    if ema5.iloc[-i] <= ema10.iloc[-i] and ema5.iloc[-i+1] > ema10.iloc[-i+1]:
        cross_detected = True
        break

has_cascading_crossover = cascading_pattern and cross_detected
```

**Step 2: Apply Filters** (🔧 LOOSENED in recent fix)
```python
# Calculate indicators
adx = compute_adx(df, period=14)
rsi = compute_rsi(df['Close'], period=14)
vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]

# Filter conditions
trend_strong = adx.iloc[-1] >= 20        # 🔧 Was 25 (loosened)
rsi_healthy = 45 <= rsi.iloc[-1] <= 70   # 🔧 Was 50-66 (loosened)
volume_confirmed = vol_ratio >= 1.2      # 🔧 Was 1.5 (loosened)
price_above_ema20 = df['Close'].iloc[-1] > ema20.iloc[-1]

# All filters must pass
signal_valid = (
    has_cascading_crossover and
    trend_strong and
    rsi_healthy and
    volume_confirmed and
    price_above_ema20
)
```

### Scoring Algorithm

```python
if signal_valid:
    # Base score components
    trend_score = min(adx_value / 50, 1.0) * 25  # Max 25 pts
    rsi_score = (rsi_value - 50) / 20 * 25       # Max 25 pts (RSI 50-70)
    volume_score = min(vol_ratio / 2.0, 1.0) * 25 # Max 25 pts

    base_score = trend_score + rsi_score + volume_score  # Max 75 pts

    # Cascading bonus
    crossover_bonus = 25  # Fixed bonus for cascading pattern

    raw_score = base_score + crossover_bonus  # Max 100 pts
```

### Exit Conditions

1. **Target Hit**: Price >= entry + 3.0 × (entry - stop)
2. **Stop Loss**: Price <= entry - 1.5 × ATR (🔧 WIDENED from 1.0 ATR)
3. **Trailing Stop**: If profit >= 1.5R, trail at 1.0R
4. **Max Days**: 30 days

### Current Performance
- **16 trades, 18.8% WR** (up from 14.6% before fixes)
- Expected: 65% WR (user's historical observation)
- **Exit breakdown**: 66.7% hit stop loss in previous backtest
- **Problem**: Still broken despite widening stop and loosening filters

### Hypothesis: Why It's Broken
1. **Detection Logic**: May be detecting false cascading patterns
2. **Market Regime**: 2022-2026 had choppy markets, crossovers get whipsawed
3. **Entry Timing**: Entering after crossover means EMAs are close together, any pullback triggers stop
4. **Historical Context**: User's 65% WR may have been in different market conditions (2010s bull market)

---

## Strategy 2: 52-Week High

### Concept
Buy stocks breaking out to new 52-week highs with strong momentum.

### Entry Conditions

```python
# Calculate 52-week high (252 trading days)
high_52w = df['High'].rolling(252).max()
current_price = df['Close'].iloc[-1]

# Breakout detection
near_52w_high = current_price >= high_52w.iloc[-1] * 0.98  # Within 2% of 52W high

# Filters (STRICT for momentum)
adx = compute_adx(df, period=14)
vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]

trend_strong = adx.iloc[-1] >= 25      # Strong trend required
volume_surge = vol_ratio >= 1.5        # 50% above average volume

signal_valid = near_52w_high and trend_strong and volume_surge
```

### Scoring Algorithm

```python
if signal_valid:
    # Simple scoring based on momentum strength
    proximity_score = (current_price / high_52w.iloc[-1]) * 6  # Max 6 pts
    trend_score = min(adx_value / 50, 1.0) * 3                 # Max 3 pts
    volume_score = min(vol_ratio / 3.0, 1.0) * 3               # Max 3 pts

    raw_score = proximity_score + trend_score + volume_score   # Max 12 pts
```

### Exit Conditions
1. **Target**: Price >= entry + 3.0 × (entry - stop)
2. **Stop Loss**: Price <= entry - 1.5 × ATR
3. **Trailing Stop**: If profit >= 1.5R, trail at 1.0R
4. **Max Days**: 30 days

### Current Performance
- **503 trades (largest volume), 30.2% WR**
- Expectancy: 0.38R (positive but underperforming)
- Issue: High volume of trades, but low win rate suggests entries could be tighter

---

## Strategy 3: Mean Reversion (RSI-2)

### Concept
Buy oversold stocks (RSI-2 < 10) in uptrends, expecting mean reversion bounce.

### Entry Conditions

```python
# Calculate indicators
rsi2 = compute_rsi(df['Close'], period=2)
rsi14 = compute_rsi(df['Close'], period=14)
ema20 = df['Close'].ewm(span=20, adjust=False).mean()
adx = compute_adx(df, period=14)

# Entry rules
oversold = rsi2.iloc[-1] < 10          # Extreme oversold on RSI(2)
uptrend = df['Close'].iloc[-1] > ema20.iloc[-1]  # Above EMA20
rsi14_ok = rsi14.iloc[-1] < 60         # RSI(14) not overbought

# Filters (MODERATE - loosened from strict)
vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
volume_adequate = vol_ratio >= 1.0     # 🔧 Was 0.8 (tightened to moderate)
trend_exists = adx.iloc[-1] >= 18      # 🔧 Was 15 (tightened to moderate)

signal_valid = oversold and uptrend and rsi14_ok and volume_adequate and trend_exists
```

### Scoring Algorithm

```python
if signal_valid:
    # Lower RSI(2) = better score
    rsi2_score = max(0, (10 - rsi2_value) * 5)    # Max 50 pts (RSI2 at 0)

    # Price position above EMA20
    ema_distance = (current_price - ema20_value) / ema20_value
    ema_score = min(ema_distance * 100, 1.0) * 20  # Max 20 pts

    # Volume confirmation
    volume_score = min(vol_ratio / 2.0, 1.0) * 15  # Max 15 pts

    # Trend strength
    trend_score = min(adx_value / 30, 1.0) * 15    # Max 15 pts

    raw_score = rsi2_score + ema_score + volume_score + trend_score  # Max 100 pts
```

### Exit Conditions

**Primary Exit**: RSI(2) > 70 (overbought)
```python
if rsi2.iloc[-1] > 70:
    exit_reason = "RSI2_Overbought"
```

**Secondary Exits**:
1. **Target**: Price >= entry + 3.0 × (entry - stop)
2. **Stop Loss**: Price <= entry - 2.0 × ATR (wider for mean reversion)
3. **Trailing Stop**: If profit >= 1.5R, trail at 1.0R
4. **Max Days**: 30 days

### Current Performance
- **60 trades, 75% WR ✅ BEST PERFORMER**
- Expectancy: 0.52R
- Exit breakdown: 7.1% RSI2_Overbought exits (working as designed)
- **This strategy is working perfectly!**

---

## Strategy 4: Consolidation Breakout

### Concept
Detect stocks consolidating in tight ranges (3+ days), then breaking out with volume.

### Entry Conditions

```python
# Calculate 5-day price range
high_5d = df['High'].rolling(5).max()
low_5d = df['Low'].rolling(5).min()
price_range = (high_5d - low_5d) / low_5d

# Consolidation detection (range < 5% for 5 days)
in_consolidation = price_range.iloc[-1] < 0.05

# Breakout detection (current close > 5-day high)
breakout = df['Close'].iloc[-1] > high_5d.iloc[-2]

# Volume confirmation
vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
volume_surge = vol_ratio >= 1.5

# ADX filter
adx = compute_adx(df, period=14)
trend_forming = adx.iloc[-1] >= 20

signal_valid = in_consolidation and breakout and volume_surge and trend_forming
```

### Scoring Algorithm

```python
if signal_valid:
    # Tighter consolidation = better setup
    consolidation_score = (0.05 - price_range.iloc[-1]) * 40  # Max ~2 pts

    # Stronger breakout = higher score
    breakout_strength = (df['Close'].iloc[-1] - high_5d.iloc[-2]) / high_5d.iloc[-2]
    breakout_score = min(breakout_strength * 100, 1.0) * 3    # Max 3 pts

    # Volume surge
    volume_score = min(vol_ratio / 3.0, 1.0) * 3              # Max 3 pts

    # Trend strength
    trend_score = min(adx_value / 40, 1.0) * 2                # Max 2 pts

    raw_score = consolidation_score + breakout_score + volume_score + trend_score  # Max ~10 pts
```

### Exit Conditions
1. **Target**: Price >= entry + 3.0 × (entry - stop)
2. **Stop Loss**: Price <= entry - 1.5 × ATR
3. **Trailing Stop**: If profit >= 1.5R, trail at 1.0R
4. **Max Days**: 30 days

### Current Performance
- **49 trades, 22.4% WR**
- Expectancy: 0.20R (barely positive)
- Issue: Too rare (only 49 trades in 4 years) and poor win rate

---

## Strategy 5: %B Mean Reversion

### Concept
Use Bollinger Band %B indicator to identify oversold conditions. Buy when %B < 0.2 (near lower band) in uptrends.

### Entry Conditions

```python
# Calculate Bollinger Bands (20-day, 2 std dev)
bb_middle = df['Close'].rolling(20).mean()
bb_std = df['Close'].rolling(20).std()
bb_upper = bb_middle + 2 * bb_std
bb_lower = bb_middle - 2 * bb_std

# Calculate %B
percent_b = (df['Close'] - bb_lower) / (bb_upper - bb_lower)

# %B < 0 means price is BELOW lower band (extreme oversold)
# %B = 0 means price is AT lower band
# %B = 0.5 means price is at middle band
# %B = 1 means price is at upper band

# Entry conditions (🔧 LOOSENED from %B < 0 to %B < 0.2)
extreme_oversold = percent_b.iloc[-1] < 0.2  # 🔧 Was < 0 (too rare)

# Uptrend filter (200-day MA)
ma200 = df['Close'].rolling(200).mean()
in_uptrend = df['Close'].iloc[-1] > ma200.iloc[-1]

# Additional filters
rsi14 = compute_rsi(df['Close'], period=14)
adx = compute_adx(df, period=14)
vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]

rsi_oversold = rsi14.iloc[-1] < 40
volume_adequate = vol_ratio >= 1.0
trend_exists = adx.iloc[-1] >= 18

signal_valid = (
    in_uptrend and
    extreme_oversold and
    rsi_oversold and
    volume_adequate and
    trend_exists
)
```

### Scoring Algorithm

```python
if signal_valid:
    # More negative %B = better score
    pb_score = max(0, (0.2 - percent_b_value) * 200)  # Max 40 pts (%B at 0)

    # RSI oversold confirmation
    rsi_score = max(0, (40 - rsi_value) * 1.5)        # Max 60 pts

    # Volume
    volume_score = min(vol_ratio / 2.0, 1.0) * 15     # Max 15 pts

    # Trend
    trend_score = min(adx_value / 30, 1.0) * 15       # Max 15 pts

    raw_score = pb_score + rsi_score + volume_score + trend_score  # Max ~130 pts (capped to 100)
```

### Exit Conditions

**Primary Exit**: %B > 0.5 (price returns to middle band)
```python
if percent_b.iloc[-1] > 0.5:
    exit_reason = "BB_MeanRevert"
```

**Secondary Exits**:
1. **Target**: Price >= entry + 3.0 × (entry - stop)
2. **Stop Loss**: Price <= entry - 2.0 × ATR
3. **Trailing Stop**: If profit >= 1.5R, trail at 1.0R
4. **Max Days**: 30 days

### Current Performance
- **0 trades in previous backtest** (before loosening threshold)
- 🔧 **Recently fixed**: Changed %B < 0 → %B < 0.2
- Expected: 20-40 trades/year with 70-80% WR (similar to RSI-2 mean reversion)

---

## Strategy 6: BB+RSI Combo

### Concept
Double confirmation: Both Bollinger Bands AND RSI must show oversold conditions.

### Entry Conditions

```python
# Bollinger Bands (20-day, 2 std dev)
bb_middle = df['Close'].rolling(20).mean()
bb_std = df['Close'].rolling(20).std()
bb_upper = bb_middle + 2 * bb_std
bb_lower = bb_middle - 2 * bb_std
percent_b = (df['Close'] - bb_lower) / (bb_upper - bb_lower)

# RSI(14)
rsi14 = compute_rsi(df['Close'], period=14)

# Entry conditions (🔧 LOOSENED thresholds)
bb_oversold = percent_b.iloc[-1] < 0.3   # 🔧 Was < 0.2 (loosened)
rsi_oversold = rsi14.iloc[-1] < 35       # 🔧 Was < 30 (loosened)

# Uptrend filter (optional but recommended)
ma200 = df['Close'].rolling(200).mean()
if len(df) >= 200:
    in_uptrend = df['Close'].iloc[-1] > ma200.iloc[-1]
else:
    in_uptrend = True

# Additional filters
adx = compute_adx(df, period=14)
vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]

volume_adequate = vol_ratio >= 1.0
trend_exists = adx.iloc[-1] >= 18

signal_valid = (
    bb_oversold and
    rsi_oversold and
    in_uptrend and
    volume_adequate and
    trend_exists
)
```

### Scoring Algorithm

```python
if signal_valid:
    # BB oversold score
    bb_score = (0.3 - percent_b_value) * 100          # Max ~30 pts

    # RSI oversold score
    rsi_score = (35 - rsi_value) * 1.5                # Max ~52 pts

    # Volume
    volume_score = min(vol_ratio / 2.0, 1.0) * 15     # Max 15 pts

    # Trend
    trend_score = min(adx_value / 20, 1.0) * 20       # Max 20 pts

    raw_score = bb_score + rsi_score + volume_score + trend_score  # Max ~100 pts
```

### Exit Conditions

**Primary Exits**:
1. **%B > 0.8** (price near upper band)
2. **RSI(14) > 70** (overbought)

**Secondary Exits**:
1. **Target**: Price >= entry + 3.0 × (entry - stop)
2. **Stop Loss**: Price <= entry - 1.5 × ATR
3. **Trailing Stop**: If profit >= 1.5R, trail at 1.0R
4. **Max Days**: 30 days

### Current Performance
- **0 trades in previous backtest** (before loosening thresholds)
- 🔧 **Recently fixed**: Changed %B < 0.2 → 0.3, RSI < 30 → 35
- Expected: 15-30 trades/year with 60-70% WR (double confirmation should improve quality)

---

## Strategy 7: BB Squeeze

### Concept
Detect Bollinger Band squeeze (low volatility) followed by breakout (high volatility expansion).

### Entry Conditions

```python
# Bollinger Bands (20-day, 2 std dev)
bb_middle = df['Close'].rolling(20).mean()
bb_std = df['Close'].rolling(20).std()
bb_upper = bb_middle + 2 * bb_std
bb_lower = bb_middle - 2 * bb_std

# Band width (normalized)
band_width = (bb_upper - bb_lower) / bb_middle

# Squeeze detection: Current bandwidth at 6-month low
band_width_min_6m = band_width.rolling(126).min()
is_squeeze = band_width.iloc[-1] <= band_width_min_6m.iloc[-1] * 1.05

# Breakout detection: Price breaks above upper band
breakout_above = df['Close'].iloc[-1] > bb_upper.iloc[-1]

# Volume confirmation
vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
volume_surge = vol_ratio >= 2.0  # 2x volume required for breakout

# ❌ CURRENTLY DISABLED (only 1 trade with 0% WR in backtest)
signal_valid = False  # Disabled
```

### Scoring Algorithm

```python
if signal_valid:
    # Tighter squeeze = better setup
    squeeze_score = max(0, 1.0 - (band_width.iloc[-1] / band_width.rolling(252).mean().iloc[-1])) * 50

    # Breakout strength
    breakout_score = ((df['Close'].iloc[-1] - bb_upper.iloc[-1]) / bb_upper.iloc[-1]) * 100 * 25

    # Volume surge
    volume_score = min(vol_ratio / 3.0, 1.0) * 25

    raw_score = squeeze_score + breakout_score + volume_score  # Max 100 pts
```

### Exit Conditions
1. **Target**: Price >= entry + 3.0 × (entry - stop)
2. **Stop Loss**: Price <= entry - 1.5 × ATR
3. **Trailing Stop**: If profit >= 1.5R, trail at 1.0R
4. **Max Days**: 30 days

### Current Performance
- **1 trade, 0% WR** (lost -1.0R)
- **Status**: ❌ DISABLED (entry conditions too rare)

---

## Exit Logic (Global)

All strategies share the same exit logic, evaluated daily in this order:

### 1. Catastrophic Loss Protection
```python
if current_price <= entry * 0.80:
    exit_reason = "CatastrophicLoss"
    exit_now = True
```

### 2. Strategy-Specific Primary Exits

**Mean Reversion (RSI-2)**:
```python
if rsi2.iloc[-1] > 70:
    exit_reason = "RSI2_Overbought"
    exit_now = True
```

**%B Mean Reversion**:
```python
if percent_b.iloc[-1] > 0.5:
    exit_reason = "BB_MeanRevert"
    exit_now = True
```

**BB+RSI Combo**:
```python
if percent_b.iloc[-1] > 0.8 or rsi14.iloc[-1] > 70:
    exit_reason = "BB_RSI_Exit"
    exit_now = True
```

### 3. Stop Loss Check
```python
if current_price <= stop_loss:
    exit_reason = "StopLoss"
    exit_now = True
```

### 4. Target Hit
```python
if current_price >= target:
    exit_reason = "Target"
    exit_now = True
```

### 5. Trailing Stop
```python
# Update trailing stop if profit >= 1.5R
r_multiple = (current_price - entry) / (entry - stop_loss)
if r_multiple >= 1.5:
    trailing_stop = entry + 1.0 * (entry - stop_loss)
    if current_price <= trailing_stop:
        exit_reason = "TrailingStop"
        exit_now = True
```

### 6. Max Holding Period
```python
if holding_days >= 30:
    exit_reason = "MaxDays"
    exit_now = True
```

### 7. Mean Reversion MA5 Exit (RSI-2 only)
```python
# For Mean Reversion: Exit if closes above MA5 for 2 consecutive days
if strategy == "Mean Reversion":
    ma5 = df['Close'].rolling(5).mean()
    if current_price > ma5.iloc[-1] and df['Close'].iloc[-2] > ma5.iloc[-2]:
        exit_reason = "Above_MA5"
        exit_now = True
```

---

## Risk Management

### Position Sizing
```python
account_size = 100000  # $100K
risk_per_trade = 0.01  # 1% risk per trade
max_risk_dollars = account_size * risk_per_trade  # $1,000

# Calculate shares based on risk
risk_per_share = entry - stop_loss
shares = max_risk_dollars / risk_per_share

# Round to whole shares
shares = int(shares)
```

### Portfolio Rules
- Maximum 10 concurrent positions
- Maximum 1% risk per trade
- No more than 3 positions in same sector (not yet implemented)

### Filters Applied to All Strategies
1. **Minimum liquidity**: $10M average daily dollar volume
2. **Market regime** (not currently used): Disable momentum strategies in bearish markets
3. **Deduplicate signals**: Only one strategy per ticker (highest priority wins)

---

## Cascading Issue Analysis

### Expected vs Actual Performance

| Metric | Expected | Actual (Before Fix) | Actual (After Fix) |
|--------|----------|---------------------|-------------------|
| Win Rate | 65% | 14.6% | 18.8% |
| Trades | 50-100/year | 48 (4 years) | 16 (4 years) |
| Avg R-Multiple | 1.5R | 0.29R | 0.12R |
| Stop Loss Rate | 20-30% | 66.7% | ~50% |

### Root Cause Hypotheses

#### 1. **Detection Logic Issue**
**Problem**: May be detecting false cascading patterns or entering too late after crossover.

**Evidence**:
- Only 16 trades in new backtest vs 48 before (filters are working, but maybe TOO restrictive)
- Win rate barely improved (14.6% → 18.8%)

**Test**: Check if detected cascading patterns actually look like valid setups:
```python
# When cascading detected, verify:
# 1. Did EMA5 actually cross EMA10 recently? (within 5 days)
# 2. Are ALL EMAs in order? (5 > 10 > 20 > 50)
# 3. Is price trending up, not just whipsawing?
```

#### 2. **Entry Timing Problem**
**Problem**: Entering AFTER crossover means EMAs are close together, any pullback triggers stop.

**Current logic**:
```python
# Detects crossover in last 5 days
for i in range(1, 6):
    if ema5.iloc[-i] <= ema10.iloc[-i] and ema5.iloc[-i+1] > ema10.iloc[-i+1]:
        cross_detected = True
```

**Issue**: If crossover was 4-5 days ago, EMAs might have already separated then come back together, creating false signal.

**Proposed fix**: Only enter on DAY OF CROSSOVER or 1 day after:
```python
# Tighter window: Only last 2 days
for i in range(1, 3):
    if ema5.iloc[-i] <= ema10.iloc[-i] and ema5.iloc[-i+1] > ema10.iloc[-i+1]:
        cross_detected = True
```

#### 3. **Market Regime Mismatch**
**Problem**: User's 65% WR observation might be from different market conditions (2010-2020 bull market).

**Evidence**:
- 2022-2026 includes: 2022 bear market, 2023 recovery, 2024-2025 choppy markets
- Crossover strategies struggle in choppy/ranging markets (whipsaws)
- User's 65% WR likely from strong trending 2010s

**Reality**: Crossover strategies may only have 30-40% WR in modern markets.

#### 4. **Stop Loss Still Too Tight**
**Problem**: Even at 1.5 ATR, stop might be too close after crossover.

**Current**: Stop at entry - 1.5 × ATR
**Proposed**: Try 2.0 × ATR or use EMA20 as stop level:
```python
# Option A: Wider ATR stop
stop = entry - 2.0 * atr

# Option B: EMA20 as stop (dynamic support)
stop = min(entry - 2.0 * atr, ema20.iloc[-1] * 0.98)
```

#### 5. **Filters Still Too Strict**
**Current filters** (after loosening):
- ADX >= 20 (trend strength)
- RSI 45-70 (momentum health)
- Volume >= 1.2x (confirmation)
- Price > EMA20

**Issue**: Maybe ADX 20 is still too high? Or RSI range too narrow?

**Proposed**: Try even looser:
```python
trend_strong = adx.iloc[-1] >= 15      # Even looser
rsi_healthy = 40 <= rsi.iloc[-1] <= 75  # Wider range
volume_confirmed = vol_ratio >= 1.0     # Any above-average volume
```

#### 6. **Scoring Problem**
**Current**: Cascading gets priority 7 (highest), but has terrible expectancy (0.29R vs Mean Reversion 0.52R).

**Issue**: Van Tharp scoring should naturally de-prioritize it, but it still gets highest priority in deduplication.

**Solution**: Lower priority or disable entirely:
```python
priority = {
    "Mean Reversion": 7,        # Move to highest (it works!)
    "BB+RSI Combo": 6,
    "%B Mean Reversion": 5,
    "52-Week High": 4,
    "EMA Crossover": 3,         # Lower priority (broken)
    "Consolidation Breakout": 2,
    "BB Squeeze": 1,
}
```

### Recommended Actions (In Order)

1. **DISABLE CASCADING COMPLETELY**
   - 18.8% WR is still unacceptable
   - Dragging down overall portfolio performance
   - Focus on strategies that work (Mean Reversion: 75% WR)

2. **If you want to fix it, try this sequence:**

   **Test A**: Tighter crossover detection window (1-2 days instead of 5)
   ```python
   for i in range(1, 3):  # Only last 2 days
   ```

   **Test B**: Wider stop loss (2.0 ATR or EMA20-based)
   ```python
   stop = entry - 2.0 * atr
   ```

   **Test C**: Even looser filters
   ```python
   trend_strong = adx.iloc[-1] >= 15
   rsi_healthy = 40 <= rsi.iloc[-1] <= 75
   volume_confirmed = vol_ratio >= 1.0
   ```

   **Test D**: Change entry from "crossover + filters" to "pullback after crossover"
   ```python
   # Enter when price pulls back to EMA10 AFTER cascading pattern confirmed
   pullback_to_ema10 = abs(df['Close'].iloc[-1] - ema10.iloc[-1]) < 0.5 * atr
   ```

3. **Accept Reality**: 65% WR might not be achievable in current markets
   - If best case is 30-40% WR with 2R wins → Expectancy = (0.35 × 2.0) - (0.65 × 0.3) = 0.50R
   - That's acceptable, but current 18.8% WR with 0.12R expectancy is NOT

---

## Summary of Current System State

### Working Strategies ✅
1. **Mean Reversion (RSI-2)**: 75% WR, 0.52R expectancy - **PERFECT**

### Underperforming but Positive ⚠️
2. **52-Week High**: 30.2% WR, 0.38R expectancy - Generates most trades (503)

### Barely Positive ⚠️
3. **Consolidation Breakout**: 22.4% WR, 0.20R expectancy - Too rare (49 trades)

### Broken ❌
4. **Cascading (EMA Crossover)**: 18.8% WR, 0.12R expectancy - **NEEDS DISABLE OR MAJOR FIX**

### Unknown (Recently Fixed) 🔧
5. **%B Mean Reversion**: 0 trades before → loosened to %B < 0.2
6. **BB+RSI Combo**: 0 trades before → loosened to %B < 0.3, RSI < 35

### Disabled ❌
7. **BB Squeeze**: 1 trade, 0% WR, -1.00R

### Overall Portfolio
- **543 trades, 37.75% WR, 0.40R avg**
- **51.6% hit stop loss** (still too high, target < 45%)
- **Expectancy positive** but could be much better

### Key Issues
1. Cascading broken (18.8% WR vs expected 65%)
2. Stop loss rate too high (51.6%)
3. 52-Week High generates too many mediocre signals (30% WR)

### Recommendations
1. **DISABLE Cascading** (until proven fixable)
2. **Tighten 52-Week High** filters to improve quality over quantity
3. **Monitor new fixes**: %B and BB+RSI should generate 35-70 trades combined
4. **Focus on what works**: Mean Reversion is carrying the portfolio

---

## Questions for Other LLMs

1. Why would a cascading EMA crossover strategy have 18.8% WR instead of expected 65%?
2. Is the detection logic correct for "cascading" pattern?
3. Should entry be on day of crossover vs 1-5 days after?
4. Is 1.5 ATR stop still too tight after crossover when EMAs are close together?
5. Would EMA20-based stop be better than ATR-based for this strategy?
6. Is 65% WR realistic for crossover strategies in 2022-2026 markets, or was that from different era?
7. Should we use pullback-to-EMA10 entry instead of immediate crossover entry?
8. Any other detection/entry/exit logic problems you can spot?

---

**End of Specification**
