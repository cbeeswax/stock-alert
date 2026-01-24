# Backtest Improvements - January 2026

## Summary of Changes

Two key improvements were made based on backtest analysis:

### 1. Improved Mean Reversion Partial Exit Thresholds

**Problem:** The `Partial_RSI2_>60` trigger was firing too frequently (76 occurrences) but only achieving 0.37R average. This was cutting profits too early on the strongest bounces.

**Solution:** Raised thresholds to let strong mean reversion bounces run more before taking partial profits.

#### Mean Reversion Strategy
**Before:**
- Partial at 1.0R OR RSI2 > 60

**After:**
- Partial at **1.2R** OR RSI2 > **70**

#### %B Mean Reversion Strategy
**Before:**
- Partial at %B ≥ 0.4 OR 1.0R

**After:**
- Partial at %B ≥ **0.5** OR **1.2R**

#### BB+RSI Combo Strategy
**Before:**
- Partial at %B ≥ 0.6 OR RSI14 > 55

**After:**
- Partial at %B ≥ **0.65** OR RSI14 > **60**

**Expected Impact:**
- Fewer premature partial exits on strong bounces
- Higher average R-multiple for partial exits (target 0.6-0.8R instead of 0.37R)
- Better asymmetric profit capture on mean reversion trades
- May slightly reduce win rate but should significantly improve profitability

---

### 2. Strategy-Wise Performance Analysis

**Problem:** The backtest summary showed crossover type breakdown, but users want to see performance by strategy instead.

**Changes:**

#### Removed:
- ❌ Crossover Type Analysis section (was showing Cascading, Golden Cross, Early Stage, etc.)

#### Added:
- ✅ **Strategy-Wise Performance Analysis**
  - Shows PnL, win rate, avg R-multiple, and holding days for each strategy
  - Sorted by Total PnL (descending) to see best performers first
  - Makes it easy to identify which strategies are profitable

**New Output Format:**
```
📊 Performance by Strategy:
   ------------------------------------------------------------------------------------------
   Strategy                       Trades   WinRate    AvgR     TotalPnL         AvgDays
   ------------------------------------------------------------------------------------------
   EMA Crossover                  150      45.3%      1.25     $15,234.50       18.4
   Mean Reversion                 200      78.5%      0.85     $12,500.00       5.2
   52-Week High                   80       38.8%      2.15     $8,750.25        25.6
   TechMomentum_Swing_30_60       45       42.2%      1.80     $6,100.00        38.2
   ...
```

---

## Files Modified

### `backtester_walkforward.py`

**Lines 328-357:** Updated partial exit thresholds for mean reversion strategies
- Mean Reversion: 1.0R → 1.2R, RSI2 60 → 70
- %B Mean Reversion: 0.4 → 0.5, 1.0R → 1.2R
- BB+RSI Combo: %B 0.6 → 0.65, RSI14 55 → 60

**Lines 814-838:** Replaced CrossoverAnalysis with StrategyAnalysis
- Groups by "Strategy" instead of "CrossoverType"
- Shows same metrics: Trades, WinRate%, AvgRMultiple, TotalPnL, AvgHoldingDays

**Lines 954-964:** Updated output formatting
- Changed section title from "Performance by Crossover Type" to "Performance by Strategy"
- Increased column width for strategy names (30 chars)
- Adjusted table width (90 chars)

---

## Testing

```bash
# Compile check
source venv/bin/activate
python3 -m py_compile backtester_walkforward.py
# ✅ Success

# Run backtest
python backtester_walkforward.py --scan-frequency B
```

---

## Configuration Reference

The new thresholds are hardcoded in the backtester logic. If you want to make them configurable, you can add these to `config/trading_config.py`:

```python
# Mean Reversion Partial Exit Thresholds
MEAN_REVERSION_PARTIAL_R_TRIGGER = 1.2  # Was 1.0
MEAN_REVERSION_PARTIAL_RSI2_TRIGGER = 70  # Was 60

PERCENT_B_MR_PARTIAL_B_TRIGGER = 0.5  # Was 0.4
PERCENT_B_MR_PARTIAL_R_TRIGGER = 1.2  # Was 1.0

BB_RSI_COMBO_PARTIAL_B_TRIGGER = 0.65  # Was 0.6
BB_RSI_COMBO_PARTIAL_RSI14_TRIGGER = 60  # Was 55
```

---

## Expected Results

After these changes, expect to see:

### Better Partial Exits
- **Partial_RSI2_>70** (new) - fewer occurrences but higher R (target 0.6-0.8R)
- **Partial_1.2R_Profit** (new) - replaces 1R exits, higher profit capture
- **Partial_PercentB_0.5** - more selective, better entries
- **Partial_PercentB_0.65** - more selective, better entries
- **Partial_RSI14_>60** - less premature exits

### Strategy Analysis Clarity
- Easy to see which strategies are profitable
- Compare win rates across strategies
- Identify which strategies need tuning
- Understand holding period differences

---

**Implementation Date:** 2026-01-21
**Status:** ✅ Complete - Ready for Backtesting
