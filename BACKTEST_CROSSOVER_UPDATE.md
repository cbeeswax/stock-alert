# Backtester Crossover Integration

## ✅ Changes Made

The backtester has been updated to fully support the new 4-type crossover system and provide detailed analysis of performance by crossover type.

---

## 🔧 What Was Updated

### 1. **`backtester_walkforward.py`** - Capture Crossover Data

#### Added to `_simulate_trade()` (lines 100-103):
```python
# Capture crossover information for analysis
crossover_type = trade.get("CrossoverType", "Unknown")
crossover_bonus = trade.get("CrossoverBonus", 0)
score = trade.get("Score", 0)
```

#### Updated trade results dict (lines 180-192):
```python
return {
    "Date": entry_day,
    "Year": entry_day.year,
    "Ticker": ticker,
    "Strategy": strategy,
    "CrossoverType": crossover_type,      # 🆕 NEW
    "CrossoverBonus": crossover_bonus,    # 🆕 NEW
    "Score": score,                       # 🆕 NEW
    "Entry": entry,
    "Exit": exit_price,
    "Outcome": outcome,
    "ExitReason": exit_reason,
    "RMultiple": r_multiple,
    "PnL_$": pnl,
    "HoldingDays": holding_days
}
```

---

### 2. **`backtester_walkforward.py`** - Crossover Performance Analysis

#### Added to `evaluate()` method (lines 238-262):

```python
# Crossover Type Analysis
if "CrossoverType" in df.columns:
    crossover_analysis = (
        df.groupby("CrossoverType")
        .agg({
            "Ticker": "count",              # Number of trades
            "Outcome": lambda x: (x == "Win").sum() / len(x) * 100,  # Win rate %
            "RMultiple": "mean",            # Avg R-multiple
            "PnL_$": "sum",                 # Total PnL
            "HoldingDays": "mean",          # Avg holding days
        })
        .round(2)
    )

    # Sort by total PnL to see best performing type
    crossover_analysis = crossover_analysis.sort_values("TotalPnL_$", ascending=False)
    summary["CrossoverAnalysis"] = crossover_analysis.to_dict("index")
```

#### Added to `evaluate()` method (lines 265-278):

```python
# Exit Reason Analysis
if "ExitReason" in df.columns:
    exit_analysis = (
        df.groupby("ExitReason")
        .agg({
            "Ticker": "count",
            "PnL_$": "sum",
            "RMultiple": "mean",
        })
        .round(2)
    )

    exit_analysis = exit_analysis.sort_values("Count", ascending=False)
    summary["ExitReasonAnalysis"] = exit_analysis.to_dict("index")
```

---

### 3. **`backtester_walkforward.py`** - Enhanced Output Display

#### Replaced simple print loop with formatted output (lines 336-379):

```python
# Overall Performance
print(f"\n📈 Overall Performance:")
print(f"   Total Trades: {stats['TotalTrades']}")
print(f"   Wins: {stats['Wins']} | Losses: {stats['Losses']}")
print(f"   Win Rate: {stats['WinRate%']}%")
print(f"   Total PnL: ${stats['TotalPnL_$']:,.2f}")
print(f"   Avg R-Multiple: {stats['AvgRMultiple']}")

# Yearly Breakdown
for year, metrics in stats["YearlySummary"].items():
    print(f"   {year}: {metrics['Trades']} trades, ${metrics['TotalPnL_$']:,.2f} PnL")

# 🆕 Performance by Crossover Type
print(f"\n🎯 Performance by Crossover Type:")
print("   Type              Trades   WinRate   AvgR     TotalPnL         AvgDays")
for crossover_type, metrics in stats["CrossoverAnalysis"].items():
    print(f"   {crossover_type:<18} {metrics['Trades']:<8} "
          f"{metrics['WinRate%']:<9.1f}% {metrics['AvgRMultiple']:<8.2f} "
          f"${metrics['TotalPnL_$']:>12,.2f} {metrics['AvgHoldingDays']:<8.1f}")

# 🆕 Exit Reason Breakdown
print(f"\n🚪 Exit Reason Breakdown:")
for reason, metrics in stats["ExitReasonAnalysis"].items():
    print(f"   {reason:<18} {metrics['Count']:<8} "
          f"${metrics['TotalPnL_$']:>12,.2f} {metrics['AvgRMultiple']:<8.2f}")
```

#### Added CSV export (line 334):
```python
trades.to_csv("backtest_results.csv", index=False)
print(f"\n💾 Results saved to: backtest_results.csv")
```

---

### 4. **`core/pre_buy_check.py`** - Pass Crossover Data Through

#### Updated trades dict (lines 182-192):
```python
trades.append({
    "Ticker": ticker,
    "Strategy": strategy,
    "Entry": round(entry, 2),
    "StopLoss": round(stop, 2),
    "Target": round(target, 2),
    "Score": s.get("Score", 0),
    "NormalizedScore": norm_score,
    "CrossoverType": s.get("CrossoverType", "Unknown"),  # 🆕 NEW
    "CrossoverBonus": s.get("CrossoverBonus", 0),        # 🆕 NEW
})
```

This ensures crossover data flows from scanner → pre_buy_check → backtester → results.

---

## 📊 New Backtest Output Format

### Before (Old):
```
📊 WALK-FORWARD SUMMARY
TotalTrades : 150
Wins : 52
Losses : 98
WinRate% : 34.67
TotalPnL_$ : 92000.0
AvgHoldingDays : 28.5
YearlySummary : {...}
```

### After (New):
```
================================================================================
📊 WALK-FORWARD BACKTEST SUMMARY
================================================================================

📈 Overall Performance:
   Total Trades: 150
   Wins: 52 | Losses: 98
   Win Rate: 34.67%
   Total PnL: $92,000.00
   Avg R-Multiple: 0.21
   Avg Holding Days: 28.5

📅 Yearly Breakdown:
   2022: 35 trades, 12 wins, $18,450.00 PnL
   2023: 42 trades, 15 wins, $25,300.00 PnL
   2024: 38 trades, 14 wins, $22,800.00 PnL
   2025: 35 trades, 11 wins, $25,450.00 PnL

🎯 Performance by Crossover Type:
   ----------------------------------------------------------------------------
   Type               Trades   WinRate    AvgR     TotalPnL         AvgDays
   ----------------------------------------------------------------------------
   Cascading          15       60.0%      1.15     $45,200.00       32.5
   GoldenCross        28       50.0%      0.68     $28,500.00       30.2
   TightPullback      45       42.2%      0.35     $15,800.00       25.8
   EarlyStage         62       29.0%      0.12     $2,500.00        22.3
   ----------------------------------------------------------------------------

🚪 Exit Reason Breakdown:
   ----------------------------------------------------------------------------
   Reason             Count    TotalPnL         AvgR
   ----------------------------------------------------------------------------
   StopLoss           85       -$35,200.00      -0.85
   TrailingStop       25       $42,500.00       1.45
   Target             18       $65,300.00       2.10
   EMABreakdown       15       -$8,200.00       -0.42
   MaxDays            7        $27,600.00       0.95
   ----------------------------------------------------------------------------

================================================================================

💾 Results saved to: backtest_results.csv
```

---

## 📈 What You Can Now Analyze

### 1. **Crossover Type Performance**
Compare which crossover type performs best:
- **Cascading**: Should have highest win rate (55-60%) but lowest frequency
- **Golden Cross**: Should have good win rate (50-55%) and moderate frequency
- **Tight Pullback**: Moderate win rate (45-50%), higher frequency
- **Early Stage**: Lower win rate (40-45%), highest frequency

**If weightage is correct**: Cascading should have highest total PnL despite fewer trades.

**If weightage needs adjustment**: If Early Stage outperforms Cascading, increase Early Stage bonus or reduce Cascading bonus.

---

### 2. **Exit Reason Analysis**
See how trades exit:
- **Target**: Best outcome (2:1 R/R achieved)
- **TrailingStop**: Good outcome (locked in profits)
- **StopLoss**: Loss (initial stop hit)
- **EMABreakdown**: Early exit (trend broke)
- **MaxDays**: Time-based exit (held too long)

**Expected Distribution**:
- Target: 15-20% of trades
- TrailingStop: 10-15% of trades
- StopLoss: 50-60% of trades
- EMABreakdown: 5-10% of trades
- MaxDays: 5-10% of trades

---

### 3. **CSV Export for Deep Analysis**

File: `backtest_results.csv`

Contains all trade details:
```csv
Date,Year,Ticker,Strategy,CrossoverType,CrossoverBonus,Score,Entry,Exit,Outcome,ExitReason,RMultiple,PnL_$,HoldingDays
2022-01-05,2022,AAPL,EMA Crossover,Cascading,25,92.5,150.00,165.00,Win,Target,2.0,2000.00,18
2022-01-12,2022,MSFT,EMA Crossover,GoldenCross,18,85.2,310.00,305.00,Loss,StopLoss,-1.0,-500.00,8
...
```

**Analysis you can do**:
1. Group by CrossoverType to validate weightage
2. Filter by CrossoverType = "Cascading" to see best setups
3. Analyze which exit reasons are most profitable
4. Check if high Score correlates with wins
5. Find optimal holding period by crossover type

---

## 🧪 How to Use

### Run Full Backtest:
```bash
python3 backtester_walkforward.py --scan-frequency B
```

### Expected Output:
1. Overall metrics (win rate, PnL, R-multiple)
2. Yearly breakdown
3. **🆕 Performance by crossover type** (key for validating weightage)
4. **🆕 Exit reason distribution** (key for understanding what's working)
5. **🆕 CSV file** for detailed analysis

---

## ✅ Validation Checklist

After running backtest, check:

- [ ] **Cascading has highest win rate** (55-60%)
  - If NO: Tighten windows or increase bonus

- [ ] **Cascading has highest total PnL** (despite fewer trades)
  - If NO: Investigate if weightage is correct

- [ ] **Early Stage has lowest win rate** (40-45%)
  - If NO: Tighten filters or reduce bonus

- [ ] **TrailingStop exits are profitable** (positive R-multiple)
  - If NO: Adjust trailing stop logic

- [ ] **EMABreakdown exits limit losses** (negative but small R-multiple)
  - If NO: Review EMA breakdown threshold

- [ ] **Target hits are 15-20% of trades** (not too many, not too few)
  - If too low: Consider tighter targets (2:1 → 1.5:1)
  - If too high: Markets are trending strongly

---

## 🎯 Example Analysis Workflow

### Step 1: Run Backtest
```bash
python3 backtester_walkforward.py --scan-frequency B
```

### Step 2: Review Crossover Performance
Look at the "Performance by Crossover Type" section.

**Good result**:
```
Cascading: 60% win rate, $50K PnL (15 trades)
GoldenCross: 52% win rate, $35K PnL (28 trades)
TightPullback: 45% win rate, $20K PnL (45 trades)
EarlyStage: 38% win rate, $5K PnL (62 trades)
```
✅ Weightage is working correctly!

**Bad result**:
```
EarlyStage: 55% win rate, $60K PnL (62 trades)
Cascading: 40% win rate, $10K PnL (15 trades)
```
❌ Weightage is wrong! Early Stage outperforms Cascading.

**Fix**: Increase Early Stage bonus from 10 → 15 points, or investigate why Cascading is underperforming.

### Step 3: Analyze CSV
```python
import pandas as pd

df = pd.read_csv("backtest_results.csv")

# Best crossover type
print(df.groupby("CrossoverType")["PnL_$"].sum().sort_values(ascending=False))

# Best exit reason
print(df.groupby("ExitReason")["PnL_$"].sum())

# High score = high win rate?
print(df.groupby(df["Score"] > 80)["Outcome"].value_counts())
```

---

## 📝 Summary

### Files Modified:
1. ✅ `backtester_walkforward.py` - Capture and analyze crossover data
2. ✅ `core/pre_buy_check.py` - Pass crossover data through

### New Features:
1. ✅ Crossover type tracked in every trade
2. ✅ Performance analysis by crossover type
3. ✅ Exit reason analysis
4. ✅ CSV export for deep analysis
5. ✅ Enhanced formatted output

### Expected Benefits:
1. ✅ Validate if weightage system works correctly
2. ✅ Identify best/worst crossover types
3. ✅ Optimize exit strategy based on data
4. ✅ Fine-tune bonuses based on actual performance

---

**Your crossover weightage system is now fully integrated with backtesting!** 🎉

Run the backtest to see which crossover type performs best and validate the weightage logic.
