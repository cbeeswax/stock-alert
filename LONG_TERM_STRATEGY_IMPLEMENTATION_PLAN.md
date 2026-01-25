# Long-Term Strategy Suite Implementation Plan

## Overview
Complete replacement of short-term strategies (3-60 days) with 8 long-term position strategies (60-120 days).

**Target:** 8-20 trades/year total across all strategies, each aiming for 2-10R potential.

---

## Current State (TO BE REPLACED)
1. EMA Crossover (short-term)
2. Mean Reversion (3-5 days)
3. %B Mean Reversion (3-5 days)
4. 52-Week High (20-40 days)
5. Consolidation Breakout (20-40 days)
6. BB Squeeze (20-40 days)
7. BB+RSI Combo (10-15 days)
8. TechMomentum_Swing_30_60 (30-60 days)

---

## New State (8 LONG-TERM STRATEGIES)

### 1. **EMA_Crossover_Position** (60-120 days)
- Strong trend entry with index confirmation
- Entry: EMA20 crosses EMA50 + new 50-day high
- Stop: 3× ATR or weekly swing low
- Exit: 40% at 2R, runner trails EMA50

### 2. **MeanReversion_Position** (60-90 days)
- Long-term uptrend with oversold bounce
- Entry: RSI14 < 38 near EMA50, then close above prior high
- Stop: Weekly swing low - 1.5× weekly ATR
- Exit: 40% when RSI14 > 65, runner trails EMA50

### 3. **%B_MeanReversion_Position** (60-90 days)
- Bollinger Band oversold in strong uptrend
- Entry: %B < 0.12, RSI14 < 38, then close above lower BB
- Stop: 3× ATR
- Exit: 40% when %B > 0.65, runner when %B > 0.92

### 4. **High52_Position** (60-120 days)
- Top 20% relative strength breakouts
- Entry: New 52-week high with 2× volume
- Stop: 3× ATR(20)
- Exit: 50% at 2.5R, runner trails 50-day MA

### 5. **BigBase_Breakout_Position** (60-120 days) ⭐ NEW
- 20+ week consolidation breakouts (rarest, highest priority)
- Entry: 6-month high after tight 20-week range (≤25%)
- Stop: Below base low - 1.5× weekly ATR
- Exit: 40% at 2.5R, runner trails 50-day MA

### 6. **TrendContinuation_Position** (60-90 days) ⭐ NEW
- Pullback entries in strong trends
- Entry: 150-day MA rising, pullback to 21-day EMA, then close > prior high
- Stop: 3× ATR or swing low
- Exit: 30% at 2R, runner trails 34-day EMA

### 7. **RelativeStrength_Ranker_Position** (60-120 days) ⭐ NEW
- Daily ranking of top RS performers
- Entry: Top 10 tech stocks with RS > +30% vs QQQ
- Trigger: New 3-month high or pullback then breakout
- Stop: 3× ATR(20)
- Exit: 50% at 3R, runner trails 50-day MA

### 8. **TechMomentum_Position_90_180_Short** (60-90 days) ⭐ NEW - BEAR MARKET
- Short strategy for bear regime only
- Entry: QQQ < 200-MA (falling), stock in downtrend, rally to EMA20
- Stop: Entry + 3× ATR
- Exit: 40% at 2R short profit, runner closes on EMA50 break

---

## Global Configuration Changes

### Risk & Position Sizing
```python
POSITION_RISK_PER_TRADE_PCT = 1.5  # Was 1.0%
POSITION_MAX_PER_STRATEGY = 5  # Max 5 per strategy
POSITION_MAX_TOTAL = 25  # Max 25 total positions
```

### Time Horizons
```python
POSITION_MAX_DAYS_SHORT = 90  # Mean reversion styles
POSITION_MAX_DAYS_LONG = 120  # Momentum/breakout styles
```

### Partial Profits
```python
POSITION_PARTIAL_SIZE = 0.4  # 40% (30-50% range)
POSITION_PARTIAL_R_TRIGGER_LOW = 2.0  # Most strategies
POSITION_PARTIAL_R_TRIGGER_HIGH = 2.5  # High52, BigBase
POSITION_PARTIAL_R_TRIGGER_HIGHEST = 3.0  # RS_Ranker
```

### Pyramiding
```python
POSITION_PYRAMID_ENABLED = True
POSITION_PYRAMID_R_TRIGGER = 2.0  # Add after +2R
POSITION_PYRAMID_SIZE = 0.5  # 50% of original size
POSITION_PYRAMID_MAX_ADDS = 2  # Maximum 2 add-ons
POSITION_PYRAMID_PULLBACK_EMA = 21  # Must pull back to 21-day EMA
```

### Priority/Deduplication
```python
STRATEGY_PRIORITY = {
    "BigBase_Breakout_Position": 1,
    "RelativeStrength_Ranker_Position": 2,
    "TrendContinuation_Position": 3,
    "EMA_Crossover_Position": 4,
    "High52_Position": 5,
    "MeanReversion_Position": 6,
    "%B_MeanReversion_Position": 7,
    "TechMomentum_Position_90_180_Short": 8,
}
```

---

## Implementation Steps

### Phase 1: Configuration (config/trading_config.py)
- [ ] Add long-term strategy config section
- [ ] Set 1.5% risk per trade
- [ ] Add pyramiding parameters
- [ ] Add strategy priority mapping
- [ ] Remove old short-term config

### Phase 2: Scanner Rewrite (scanners/scanner_walkforward.py)
- [ ] Remove all 8 old strategies
- [ ] Implement EMA_Crossover_Position scanner
- [ ] Implement MeanReversion_Position scanner
- [ ] Implement %B_MeanReversion_Position scanner
- [ ] Implement High52_Position scanner
- [ ] Implement BigBase_Breakout_Position scanner (NEW)
- [ ] Implement TrendContinuation_Position scanner (NEW)
- [ ] Implement RelativeStrength_Ranker_Position scanner (NEW)
- [ ] Implement TechMomentum_Position_90_180_Short scanner (NEW)

### Phase 3: Backtester Updates (backtester_walkforward.py)
- [ ] Update position sizing to 1.5% risk
- [ ] Implement strategy-specific max holding days
- [ ] Implement partial profit logic for each strategy
- [ ] Implement runner exit logic for each strategy
- [ ] Add pyramiding logic (track adds, 21-EMA pullback detection)
- [ ] Add priority/deduplication system
- [ ] Update stop loss calculations (weekly swing low, ATR-based)

### Phase 4: Position Tracker Updates (utils/position_tracker.py)
- [ ] Track pyramid adds per position
- [ ] Track which strategy generated each position
- [ ] Implement per-strategy position limits (max 5)
- [ ] Implement global position limit (max 25)
- [ ] Add deduplication by ticker across strategies

### Phase 5: Testing & Validation
- [ ] Compile all files
- [ ] Test each scanner individually
- [ ] Test backtester with small date range
- [ ] Verify pyramiding logic works
- [ ] Verify priority/deduplication works
- [ ] Run full backtest 2022-2026

---

## Expected Outcomes

### Trade Frequency
- **Before:** 50-200+ trades/year (short-term)
- **After:** 8-20 trades/year total (position trading)

### Holding Period
- **Before:** 3-60 days average
- **After:** 60-120 days average

### R-Multiple Target
- **Before:** 0.5-2R average
- **After:** 2-10R average per trade

### Win Rate
- **Before:** 40-80% (strategy dependent)
- **After:** 35-50% (fewer trades, bigger winners)

### Portfolio Management
- **Before:** 10 max positions, $20K per trade
- **After:** 25 max positions (5 per strategy), 1.5% risk per trade

---

## Risk Considerations

1. **Concentration Risk:** Max 5 per strategy prevents over-concentration
2. **Correlation Risk:** 8 different strategy types for diversification
3. **Pyramiding Risk:** Limited to 2 adds max, only after +2R profit
4. **Bear Market Protection:** Short strategy activates when QQQ < 200-MA
5. **Time Stop:** All positions forced exit at 90-120 days

---

## Files to Modify

1. **config/trading_config.py** - Major config changes
2. **scanners/scanner_walkforward.py** - Complete rewrite
3. **backtester_walkforward.py** - Significant updates
4. **utils/position_tracker.py** - Add pyramid tracking
5. **docs/** - New strategy documentation

---

## Estimated Implementation Time

- **Phase 1 (Config):** 15 minutes
- **Phase 2 (Scanner):** 2-3 hours (8 strategies)
- **Phase 3 (Backtester):** 2-3 hours (exit logic + pyramiding)
- **Phase 4 (Position Tracker):** 30 minutes
- **Phase 5 (Testing):** 1 hour

**Total:** ~6-8 hours of implementation

---

## Confirmation Needed

⚠️ **This is a complete replacement of the existing system.**

**Before proceeding, confirm:**
1. ✅ Remove all 8 existing short-term strategies?
2. ✅ Implement all 8 new long-term strategies?
3. ✅ Add pyramiding logic (max 2 adds per position)?
4. ✅ Implement priority/deduplication system?
5. ✅ Change to 1.5% risk per trade?
6. ✅ Change to 60-120 day holds?

**Type "PROCEED" to begin implementation.**

---

**Date:** 2026-01-21
**Status:** 🟡 Awaiting Confirmation
