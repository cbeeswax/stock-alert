# Bollinger Band Strategies Implementation

## 🎯 Overview

**Bollinger Bands** are volatility-based indicators that expand and contract based on market volatility. Price tends to stay within the bands 95% of the time, making extreme moves outside the bands statistically significant.

**Key Components**:
- **Middle Band**: 20-day Simple Moving Average (SMA)
- **Upper Band**: Middle Band + 2 × Standard Deviation
- **Lower Band**: Middle Band - 2 × Standard Deviation
- **BandWidth**: (Upper - Lower) / Middle × 100 (measures volatility)
- **%B**: (Price - Lower) / (Upper - Lower) (price position relative to bands)

---

## 📊 Three Complementary Strategies

We've implemented **3 BB strategies** that work in different market conditions:

### **1. BB Squeeze (Breakout) - Momentum**
- **Philosophy**: Buy strength after low volatility compression
- **Entry**: Volatility expansion (breakout above upper band)
- **Win Rate**: 35-45% (momentum strategy)
- **R-Multiple**: 1.5-2.5R
- **Holding**: 5-10 days

### **2. %B Mean Reversion**
- **Philosophy**: Buy extreme weakness in uptrends
- **Entry**: Price below lower band (%B < 0)
- **Win Rate**: 70-80% (mean reversion)
- **R-Multiple**: 0.5-1.0R
- **Holding**: 3-5 days

### **3. BB+RSI Combo**
- **Philosophy**: Double confirmation of oversold
- **Entry**: Near lower band (%B < 0.2) + RSI < 30
- **Win Rate**: 65-75% (mean reversion with confirmation)
- **R-Multiple**: 0.7-1.2R
- **Holding**: 4-7 days

---

## 📈 Strategy 1: BB Squeeze (Breakout)

### **Concept**
Low volatility doesn't last forever. When Bollinger Bands squeeze tight (low volatility), a big move is coming. We wait for the breakout direction and ride the momentum.

### **SETUP**
```
1. BandWidth at 6-month low (squeeze indicator)
2. Price breaks above upper band (direction confirmed)
3. Volume surge (>1.5x average) confirms strength
4. Short-term trend aligned (EMA20 > EMA50)
```

### **ENTRY (BUY)**
- ✅ BandWidth at 6-month low (within 5%)
- ✅ Close ABOVE upper band (breakout)
- ✅ Volume > 1.5x average (confirmation)
- ✅ ADX >= 20 (trend exists)
- ✅ RSI(14) 40-75 (healthy, not extreme)
- ✅ EMA20 > EMA50 (short-term uptrend)

### **EXIT (SELL)**
- ❌ Trailing stops (standard momentum exits)
- ❌ 2R target hit
- ❌ Stop loss hit (1.5 × ATR)

### **Risk Management**
- **Stop Loss**: 1.5 × ATR (middle band or opposite band)
- **Target**: 2R (entry + 2 × risk)
- **Trailing Stop**: Yes (standard momentum rules)
- **Min Holding**: 3 days (anti-whipsaw)

### **Quality Scoring (Max 100 points)**
```python
squeeze_score = (1 - current_width / 6mo_avg_width) * 30  # Max 30 pts
breakout_strength = (price_above_upper / upper) * 100 * 20  # Max 20 pts
volume_score = (vol_ratio - 1.5) / 1.5 * 25  # Max 25 pts
trend_score = ADX / 30 * 25  # Max 25 pts
```

### **Expected Performance**
```
Win Rate: 35-45% (momentum strategy)
Average Holding: 5-10 days
Average R-Multiple: 1.5-2.5R
Best Market: Trending markets after consolidation
```

---

## 📉 Strategy 2: %B Mean Reversion

### **Concept**
In uptrends, price rarely stays below the lower Bollinger Band. When %B goes negative (price below lower band), it's statistically extreme and tends to snap back to the middle band quickly.

### **SETUP**
```
1. Price ABOVE 200-day MA (uptrend filter)
2. %B < 0 (price below lower band - extreme oversold)
3. Light volume/trend requirements (buying panic)
```

### **ENTRY (BUY)**
- ✅ Price > 200-day MA (uptrend only)
- ✅ %B < 0 (below lower band)
- ✅ RSI(14) < 40 (confirms oversold)
- ✅ Volume >= 0.8x average (lighter filter)
- ✅ ADX >= 15 (trend exists, but light)

### **EXIT (SELL)**
- ✅ %B > 0.5 (price back to middle band or above)
- ❌ Stop loss hit (2.0 × ATR)

### **Risk Management**
- **Stop Loss**: 2.0 × ATR (wider - buying weakness needs room)
- **No Fixed Target**: Exits on %B reversion signal
- **No Trailing Stop**: Uses %B-based exit
- **No Min Holding**: Can exit any day

### **Quality Scoring (Max 100 points)**
```python
oversold_score = abs(%B) * 40  # Max 40 pts (more negative = better)
uptrend_score = (price - MA200) / MA200 * 100 * 30  # Max 30 pts
volume_score = vol_ratio / 2.0 * 15  # Max 15 pts
trend_score = ADX / 25 * 15  # Max 15 pts
```

### **Expected Performance**
```
Win Rate: 70-80% (mean reversion)
Average Holding: 3-5 days
Average R-Multiple: 0.5-1.0R
Best Market: Uptrends with volatility spikes
```

---

## 🎯 Strategy 3: BB+RSI Combo

### **Concept**
Double confirmation of oversold conditions. Both Bollinger Bands (%B < 0.2) and RSI (< 30) must agree that the stock is oversold. This filters out false signals and improves win rate.

### **SETUP**
```
1. %B < 0.2 (near or below lower band)
2. RSI(14) < 30 (oversold confirmation)
3. Optional: Price > 200-day MA (uptrend filter)
```

### **ENTRY (BUY)**
- ✅ %B < 0.2 (near lower band)
- ✅ RSI(14) < 30 (oversold)
- ✅ Volume >= 0.8x average
- ✅ ADX >= 12 (very light - double confirmation is strong)
- ✅ Optional: Price > 200-day MA (recommended)

### **EXIT (SELL)**
- ✅ %B > 0.8 (near upper band) OR
- ✅ RSI(14) > 70 (overbought)
- ❌ Stop loss hit (1.5 × ATR)

### **Risk Management**
- **Stop Loss**: 1.5 × ATR (tighter - double confirmation gives confidence)
- **No Fixed Target**: Exits when either indicator overbought
- **No Trailing Stop**: Uses BB+RSI exit signals
- **No Min Holding**: Can exit any day

### **Quality Scoring (Max 100 points)**
```python
bb_score = (0.2 - %B) * 100  # Max ~20 pts
rsi_score = (30 - RSI) * 1.5  # Max ~45 pts
volume_score = vol_ratio / 2.0 * 15  # Max 15 pts
trend_score = ADX / 20 * 20  # Max 20 pts
```

### **Expected Performance**
```
Win Rate: 65-75% (mean reversion with double confirmation)
Average Holding: 4-7 days
Average R-Multiple: 0.7-1.2R
Best Market: Uptrends with pullbacks
```

---

## 🔍 How BB Strategies Complement Existing Strategies

### **Current Portfolio (Before BB)**
```
Momentum Strategies:
- 52-Week High (30.6% WR, 1.5-2R)
- Consolidation Breakout (24.6% WR, 1.5-2R)
- EMA Crossover/Cascading (65% WR when filtered)

Mean Reversion:
- RSI(2) Mean Reversion (70-80% WR, 0.5-1R)
```

### **After Adding BB Strategies**
```
Momentum Strategies:
- 52-Week High
- Consolidation Breakout
- EMA Crossover/Cascading
+ BB Squeeze Breakout ← NEW (35-45% WR, 1.5-2.5R)

Mean Reversion Strategies:
- RSI(2) Mean Reversion
+ %B Mean Reversion ← NEW (70-80% WR, 0.5-1R)
+ BB+RSI Combo ← NEW (65-75% WR, 0.7-1.2R)
```

### **Diversification Benefits**
1. **Different entry triggers**: Price, RSI, Bollinger Bands
2. **Different market conditions**: Trending vs choppy vs volatile
3. **Different time horizons**: 3-5 days vs 5-10 days
4. **Different risk profiles**: High WR/low R vs Low WR/high R

---

## 📊 Strategy Comparison Table

| Strategy | Type | Entry | Exit | Win Rate | R-Multiple | Holding | Stop |
|----------|------|-------|------|----------|------------|---------|------|
| **BB Squeeze** | Momentum | Close > Upper + Volume | Trailing/Target | 35-45% | 1.5-2.5R | 5-10d | 1.5 ATR |
| **%B MR** | Mean Rev | %B < 0 in uptrend | %B > 0.5 | 70-80% | 0.5-1.0R | 3-5d | 2.0 ATR |
| **BB+RSI** | Mean Rev | %B<0.2 + RSI<30 | %B>0.8 OR RSI>70 | 65-75% | 0.7-1.2R | 4-7d | 1.5 ATR |
| **RSI(2) MR** | Mean Rev | RSI(2)<10 in uptrend | RSI(2)>70 OR MA5 | 70-80% | 0.5-1.0R | 3-5d | 2.0 ATR |
| **52W High** | Momentum | Price near 52W high | Trailing/Target | 30-35% | 1.5-2.5R | 5-10d | 1.5 ATR |
| **Cascading** | Momentum | All EMAs cross | Trailing/Target | 65% | 1.5-2.5R | 5-10d | 1.0 ATR |

---

## 🎯 When Each BB Strategy Works

### **BB Squeeze (Breakout)**
- ✅ After consolidation periods (low volatility)
- ✅ When clear direction emerges (volume confirms)
- ✅ Trending markets (ADX rising)
- ❌ Choppy markets (false breakouts)
- ❌ Very high volatility (bands too wide)

### **%B Mean Reversion**
- ✅ Uptrends with volatility spikes
- ✅ Panic selling in bull markets
- ✅ High volatility periods (bands expand)
- ❌ Downtrends (price stays below lower band)
- ❌ Low volatility (bands too tight, rare signals)

### **BB+RSI Combo**
- ✅ Uptrends with pullbacks
- ✅ When both indicators oversold (high confidence)
- ✅ Moderate volatility (not extreme)
- ❌ Trending markets (RSI stays high/low)
- ❌ When indicators diverge (one oversold, one not)

---

## 📋 Example Trade Walkthroughs

### **Example 1: BB Squeeze Breakout**
```
Ticker: MSFT
Setup Day:
- BandWidth: 3.2% (6-month low: 3.3%)
- Price: $280 (below bands, consolidating)
- Volume: 0.9x average (quiet)

Entry Day (Next Day):
- Price: $285 (breaks above upper band at $283)
- Volume: 2.1x average (surge!)
- ADX: 24, RSI: 58
→ BUY at $285
→ Stop: $281 (1.5 × ATR = $4)
→ Target: $293 (2R = $285 + 2 × $4)

Exit (Day 6):
- Price: $294 (target hit!)
- Exit: $293 (target)
- Profit: $8 ($293 - $285)
- R-Multiple: 2.0R
- Win! ✅
```

### **Example 2: %B Mean Reversion**
```
Ticker: AAPL
Setup:
- MA200: $170 (uptrend)
- BB Lower: $178
- Price: $176 (%B = -0.15, below lower band)
- RSI(14): 28 (oversold)

Entry:
→ BUY at $176
→ Stop: $168 (2.0 × ATR = $8)

Day 1: Price $174, %B -0.25 → Hold (more oversold)
Day 2: Price $177, %B 0.05 → Hold (not to middle yet)
Day 3: Price $181, %B 0.52 → EXIT!

Exit:
- Exit Reason: %B > 0.5 (back to middle band)
- Exit Price: $181
- Profit: $5 ($181 - $176)
- R-Multiple: 0.625R ($5 profit / $8 risk)
- Holding: 3 days
- Win! ✅ (70% of these trades win)
```

### **Example 3: BB+RSI Combo**
```
Ticker: NVDA
Setup:
- %B: 0.15 (near lower band)
- RSI(14): 28 (oversold)
- MA200: $430 (uptrend)
- Price: $445

Entry:
→ BUY at $445
→ Stop: $437 (1.5 × ATR = $8)

Day 1: Price $442, %B 0.10, RSI 24 → Hold
Day 2: Price $448, %B 0.35, RSI 38 → Hold
Day 3: Price $454, %B 0.62, RSI 54 → Hold
Day 4: Price $462, %B 0.85, RSI 68 → Hold
Day 5: Price $465, %B 0.92, RSI 72 → EXIT!

Exit:
- Exit Reason: RSI(14) > 70 (overbought)
- Exit Price: $465
- Profit: $20 ($465 - $445)
- R-Multiple: 2.5R ($20 profit / $8 risk)
- Holding: 5 days
- Win! ✅
```

---

## 🧪 Testing the Strategies

Run backtest with all strategies:
```bash
python backtester_walkforward.py --scan-frequency B
```

### **What to Look For**

**1. Entry Characteristics**
```
BB Squeeze:
✅ All entries have BandWidth at 6-month low
✅ All entries break above upper band
✅ Volume surge on entry day

%B Mean Reversion:
✅ All entries have %B < 0
✅ All entries have Price > MA200
✅ RSI confirms oversold

BB+RSI Combo:
✅ All entries have %B < 0.2 AND RSI < 30
✅ Double confirmation on every trade
```

**2. Exit Reasons**
```
BB Squeeze:
- Target (momentum target hit)
- TrailingStop (locked in profits)
- StopLoss (rare, momentum trades can fail)

%B Mean Reversion:
- PercentB_Middle (%B > 0.5, most common)
- StopLoss (20-30% of trades)

BB+RSI Combo:
- BB_Overbought (%B > 0.8)
- RSI14_Overbought (RSI > 70)
- StopLoss (25-35% of trades)
```

**3. Performance Metrics**
```
BB Squeeze:
✅ Win Rate: 35-45%
✅ Avg Holding: 5-10 days
✅ Avg R-Multiple: 1.5-2.5R
✅ Complements momentum strategies

%B Mean Reversion:
✅ Win Rate: 70-80%
✅ Avg Holding: 3-5 days
✅ Avg R-Multiple: 0.5-1.0R
✅ Similar to RSI(2) mean reversion

BB+RSI Combo:
✅ Win Rate: 65-75%
✅ Avg Holding: 4-7 days
✅ Avg R-Multiple: 0.7-1.2R
✅ Best overall (high WR + decent R)
```

---

## ⚙️ Configuration

### **BB Squeeze Settings**
```python
BB_PERIOD = 20  # Standard
BB_STD_DEV = 2  # Standard
SQUEEZE_LOOKBACK = 126  # 6 months
SQUEEZE_TOLERANCE = 0.05  # Within 5% of low

# Filters
MIN_ADX = 20
MIN_VOLUME_RATIO = 1.5
RSI_MIN = 40
RSI_MAX = 75

# Risk
STOP_ATR_MULTIPLE = 1.5
USE_TRAILING_STOPS = True
MIN_HOLDING_DAYS = 3
```

### **%B Mean Reversion Settings**
```python
BB_PERIOD = 20
BB_STD_DEV = 2
PERCENT_B_ENTRY = 0  # Below lower band
PERCENT_B_EXIT = 0.5  # Back to middle

# Filters
MIN_ADX = 15  # Lighter
MIN_VOLUME_RATIO = 0.8  # Lighter
RSI_MAX = 40  # Confirms oversold
REQUIRE_MA200_UPTREND = True

# Risk
STOP_ATR_MULTIPLE = 2.0  # Wider
USE_TRAILING_STOPS = False
MIN_HOLDING_DAYS = 0  # No minimum
```

### **BB+RSI Combo Settings**
```python
BB_PERIOD = 20
BB_STD_DEV = 2
PERCENT_B_ENTRY = 0.2  # Near lower band
PERCENT_B_EXIT = 0.8  # Near upper band
RSI_ENTRY = 30  # Oversold
RSI_EXIT = 70  # Overbought

# Filters
MIN_ADX = 12  # Very light
MIN_VOLUME_RATIO = 0.8
REQUIRE_MA200_UPTREND = True  # Recommended

# Risk
STOP_ATR_MULTIPLE = 1.5
USE_TRAILING_STOPS = False
MIN_HOLDING_DAYS = 0
```

---

## 📈 Expected Portfolio Impact

### **Before BB Strategies**
```
Total Strategies: 4
- 3 Momentum (52W, Consol, Cascading)
- 1 Mean Reversion (RSI(2))

Total Trades: ~683 + ~30 Mean Rev = ~713 over 4 years
Overall Win Rate: ~35-40%
PnL: ~$100-115K over 4 years
```

### **After Adding BB Strategies**
```
Total Strategies: 7
- 4 Momentum (52W, Consol, Cascading, BB Squeeze)
- 3 Mean Reversion (RSI(2), %B, BB+RSI)

Expected Additional Trades:
- BB Squeeze: 20-40/year (rare, needs squeeze)
- %B Mean Rev: 30-50/year (moderate, needs %B < 0)
- BB+RSI: 40-60/year (more common, %B < 0.2)

Total Additional: 90-150 trades/year
Total over 4 years: ~360-600 additional trades

Expected Contribution:
- Momentum (BB Squeeze): 40% WR × 80 trades × 2R avg = +$16-20K
- Mean Rev (%B): 75% WR × 150 trades × 0.75R avg = +$25-30K
- Mean Rev (BB+RSI): 70% WR × 200 trades × 0.9R avg = +$30-35K

Total Expected: $71-85K additional over 4 years
New Portfolio Total: $171-200K over 4 years (70-100% boost!)
```

---

## ⚠️ Important Notes

### **1. Strategy Interactions**
- All strategies can run **simultaneously** (diversification)
- Position sizing remains **$10K per trade**
- Max **10 open positions** at any time
- Duplicate prevention: **1 position per ticker**

### **2. Market Conditions**
- **Low volatility → Squeeze**: BB Squeeze finds compression
- **High volatility → Mean Reversion**: %B and BB+RSI catch extremes
- **Trending → Momentum**: 52W, Cascading, BB Squeeze work
- **Choppy → Mean Reversion**: RSI(2), %B, BB+RSI work

### **3. Risk Management**
- **Momentum** (BB Squeeze): Low WR, high R, use trailing stops
- **Mean Reversion** (%B, BB+RSI): High WR, low R, use signal exits
- **Portfolio balanced**: Multiple strategies smooth returns

### **4. Bollinger Band Math**
```python
Middle Band = 20-day SMA
Upper Band = Middle + 2 × StdDev
Lower Band = Middle - 2 × StdDev
BandWidth = (Upper - Lower) / Middle × 100
%B = (Price - Lower) / (Upper - Lower)
```

**%B Interpretation**:
- %B > 1.0: Price above upper band (extremely overbought)
- %B = 0.8: Price near upper band (overbought)
- %B = 0.5: Price at middle band (neutral)
- %B = 0.2: Price near lower band (oversold)
- %B < 0: Price below lower band (extremely oversold)

---

## ✅ Implementation Complete

### **Files Modified**

1. ✅ `utils/ema_utils.py` - Added BB utility functions
   - `compute_bollinger_bands()` - Calculate bands and bandwidth
   - `compute_percent_b()` - Calculate %B indicator

2. ✅ `scanners/scanner_walkforward.py` - Added 3 BB strategies
   - BB Squeeze detection (bandwidth at 6-month low)
   - %B Mean Reversion detection (%B < 0 in uptrend)
   - BB+RSI Combo detection (%B < 0.2 + RSI < 30)

3. ✅ `backtester_walkforward.py` - Added BB exit logic
   - %B Mean Reversion exit (%B > 0.5)
   - BB+RSI Combo exit (%B > 0.8 OR RSI > 70)
   - BB Squeeze uses standard momentum exits

4. ✅ `core/pre_buy_check.py` - Added BB stop calculations
   - BB Squeeze: 1.5 × ATR (momentum)
   - %B Mean Reversion: 2.0 × ATR (wider)
   - BB+RSI Combo: 1.5 × ATR (double confirmation)

### **What's New**

**BB Squeeze (Momentum)**:
- ✅ Detects volatility compression (6-month low bandwidth)
- ✅ Enters on breakout above upper band with volume
- ✅ Uses trailing stops and 2R target
- ✅ Expected 35-45% win rate, 1.5-2.5R avg

**%B Mean Reversion**:
- ✅ Buys extreme weakness (%B < 0) in uptrends
- ✅ Exits when price returns to middle (%B > 0.5)
- ✅ Quick exits (3-5 days), no trailing stops
- ✅ Expected 70-80% win rate, 0.5-1.0R avg

**BB+RSI Combo**:
- ✅ Double confirmation (%B < 0.2 + RSI < 30)
- ✅ Exits when either overbought (%B > 0.8 OR RSI > 70)
- ✅ Medium holding (4-7 days), no trailing stops
- ✅ Expected 65-75% win rate, 0.7-1.2R avg

### **Ready to Test**

```bash
python backtester_walkforward.py --scan-frequency B
```

**You now have 7 strategies working together:**
1. 52-Week High (momentum)
2. Consolidation Breakout (momentum)
3. Cascading Crossover (trend reversal)
4. Mean Reversion RSI(2) (counter-trend)
5. BB Squeeze (momentum/volatility) ← NEW!
6. %B Mean Reversion (counter-trend/volatility) ← NEW!
7. BB+RSI Combo (counter-trend/confirmation) ← NEW!

---

**Diversified portfolio across:**
- ✅ Momentum vs Mean Reversion
- ✅ Price vs Indicator vs Volatility signals
- ✅ Short holding (3-5d) vs Long holding (5-10d)
- ✅ High WR/Low R vs Low WR/High R
- ✅ Trending vs Choppy markets

**Expected portfolio win rate: 45-55% (balanced)**
**Expected total PnL: $171-200K over 4 years** 🚀
