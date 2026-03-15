# RelativeStrength_Ranker_Position - Complete Strategy Details

## Overview
**Relative Strength momentum strategy** focusing on top 10 strongest tech/communication stocks with trend confirmation.

**Active Since**: Refactored to only this strategy (2026)  
**Backtest Results**: $204,479 total PnL (2022-2026)  
**Win Rate**: 52.25%  
**Average R-Multiple**: 1.37R  
**Average Hold**: 57.7 days  
**Total Trades**: 111

---

## Entry Criteria

### Universe Selection
```
- Sector: Information Technology OR Communication Services ONLY
- Liquidity: $30M+ average 20-day dollar volume
- Price: $10 minimum
- Market Cap: No restriction
```

### Relative Strength (RS) Filter
```
- 6-month RS vs QQQ: >= +30% (minimum)
- Definition: Stock 6-mo return vs QQQ 6-mo return
- Example: Stock +50%, QQQ +10% = Stock is +40% relative
```

### Trend Confirmation (Moving Averages)
```
REQUIREMENT: Price > MA50 > MA100 > MA200 (ALL RISING)

- Price: Current close
- MA50: 50-day simple moving average (rising)
- MA100: 100-day simple moving average (rising)
- MA200: 200-day simple moving average (rising)

All 3 MAs must be in stacked order AND trending higher
```

### Momentum Filter (ADX)
```
- ADX(14) >= 30 (strong trend strength)
- Filters out choppy/sideways markets
- Only trades when direction is clear
```

### Market Regime Filter
```
- QQQ > 100-day MA (bullish)
- QQQ 100-MA is rising (trend confirmation)
- If FALSE: Strategy skips all signals (BEARISH MODE)
- Current status (March 2026): BEARISH (skip mode)
```

### Entry Trigger (Choose ONE)

**Option A: New 3-Month High**
```
Close >= 99.5% of highest close in last 63 days
Example: 63-day high = $100, triggers at $99.50+
```

**Option B: Pullback to EMA21 Breakout**
```
1. Price pulls back to within 2% of 21-day EMA
2. Then closes above previous day's high
3. Signals breakout after pullback
```

### Quality Score
```
Score = (RS_6mo / 0.30) * 100, capped at 100
Example:
  RS = 50% → Score = (0.50 / 0.30) * 100 = 167 → capped at 100
  RS = 30% → Score = (0.30 / 0.30) * 100 = 100
  RS = 15% → Score = (0.15 / 0.30) * 100 = 50
```

---

## Entry Mechanics

### Position Sizing
```
Risk Amount = Account Equity * 2.0% (POSITION_RISK_PER_TRADE_PCT)
Example: $100,000 account = $2,000 risk per trade

Stop Loss = Entry Price - (4.5 × ATR(20))
Shares = Risk Amount / (Entry - Stop)
Position Size = Shares × Entry Price

Example:
  Entry: $150
  ATR20: $5
  Stop: $150 - (4.5 × $5) = $127.50
  Risk per share: $22.50
  Risk Amount: $2,000
  Shares: 2000 / 22.50 = 88 shares
  Position Size: 88 × $150 = $13,200
```

### Max Positions
```
- Max 10 concurrent RelativeStrength_Ranker positions
- Once 10 open, skip new signals until one closes
```

---

## Exit System

### 1. Stop Loss (Risk Control)
```
- Trigger: Low <= Entry - (4.5 × ATR20)
- Exit: At stop price (-1.0R loss)
- Count: 12 trades, -$21,920 total, -0.92R avg
- Protect capital on failed setups
```

### 2. Partial Profit Taking (30% at +3.0R)
```
- Trigger: Close >= Entry + (3.0 × Risk Amount / Shares)
- Exit: 30% of position at market
- Remaining: 70% becomes "runner" (no time limit)
- Count: 21 trades, +$38,372 total, +2.81R avg
- Lock in gains on strong moves
```

### 3. MA100 Trailing Stop (Late-Stage Winners)
```
- After 60+ days: Follow MA100 from below
- Trigger: Close < MA100 for 8 consecutive days
- Exit: At market price
- Count: 9 trades, +$83,066 total, +3.61R avg
- LET WINNERS RUN - Best performers use this exit
```

### 4. EMA21 Trailing Stop (Early-Stage Protection)
```
- First 60 days: Tight EMA21 trail
- Trigger: Close < EMA21 for 5 consecutive days
- Exit: At market price
- Count: 57 trades, -$13,385 total, -0.09R avg
- Cut losers fast, protect early failures
```

### 5. Time Stop (150 days max)
```
- Trigger: 150 days since entry
- Exit: At market price (if no other exit hit)
- Count: 4 trades, +$55,186 total, +9.88R avg
- Discipline rule - don't hold forever
```

### 6. End of Backtest (Holding at end)
```
- Trigger: Backtest ends with position open
- Exit: At last close price
- Count: 8 trades, +$63,160 total, +4.65R avg
- Marks winners still running
```

---

## Pyramiding (Add to Winners)

### Trigger
```
- Trigger: Position up +1.5R AND within pullback zone
- Can add max 3 times total
- Disabled if already took partial profit (70% runner)
```

### Pullback Condition
```
- Price must pull back to within 1 ATR of 21-day EMA
- Shows support/consolidation before next leg
- Confirms trend strength
```

### Add Mechanics
```
- Add Size: 50% of original position
- Example: Bought 100 shares, add 50 more
- New Stop: Moved to breakeven on original entry
- Gives room for runner to breathe
```

---

## Backtesting Results by Year

### 2022: Rough Start
```
Trades: 12 | Wins: 1 | PnL: -$11,287
- Market conditions: Bearish tech year
- Losses on wrong entries
- Foundation for learning
```

### 2023: Strong Recovery
```
Trades: 29 | Wins: 17 | PnL: +$67,837
- Market: Tech recovery
- 58.6% win rate
- Momentum trades working well
```

### 2024: Steady Gains
```
Trades: 33 | Wins: 18 | PnL: +$38,945
- Market: Mixed conditions
- 54.5% win rate
- Tighter management
```

### 2025: Best Year
```
Trades: 33 | Wins: 20 | PnL: +$108,133
- Market: Strong tech rally
- 60.6% win rate
- Pyramiding driving winners
```

### 2026: Bearish Period (Only 3 months)
```
Trades: 4 | Wins: 2 | PnL: +$850
- Market: BEARISH (QQQ < 100-MA)
- Strategy in skip mode
- Minimal trade generation
```

---

## Exit Breakdown (What Worked Best)

| Exit Type | Trades | Win% | Avg R | Total PnL | Quality |
|-----------|--------|------|-------|-----------|---------|
| **MA100_Trail_Late** | 9 | 100% | 3.61R | +$83,066 | ⭐⭐⭐⭐⭐ BEST |
| **EndOfBacktest** | 8 | 100% | 4.65R | +$63,160 | ⭐⭐⭐⭐ (Winners) |
| **TimeStop_150d** | 4 | 100% | 9.88R | +$55,186 | ⭐⭐⭐⭐ (Big wins) |
| **Partial_2.5R** | 21 | 100% | 2.81R | +$38,372 | ⭐⭐⭐ (Profit lock) |
| **StopLoss** | 12 | 0% | -0.92R | -$21,920 | ⭐ (Risk control) |
| **EMA21_Trail_Early** | 57 | 2% | -0.09R | -$13,385 | ⭐ (Failed entries) |

**Key Insight**: MA100 trailing stop (let winners run) produces highest average R-multiples. Time stop also exceptional.

---

## Performance Mechanics

### Why Only 1.37R Average?

The strategy has asymmetric payoff:
- **Losers**: -0.92R average (well-controlled)
- **Winners**: +2.81R to +9.88R (but few hit big winners)
- **Mix**: 52% win rate × higher average loss = 1.37R overall

### Composition Analysis
```
Winners: 58 trades × 1.37R average = Need $79.46R total return
Losers:  53 trades × ???

Actual: 58 winners, 53 losers = Net $204,479 on $100k initial
Average winner payout covers losses with 1.37R margin
```

---

## Current Operational Status

### Live Trading (as of March 2026)
```
Status: BEARISH MARKET - Strategy in SKIP MODE
- QQQ < 100-MA (not bullish)
- No new signals being generated
- Waits for market regime shift
```

### Configuration
```
Max Positions: 10 (per strategy limit)
Risk per Trade: 2.0%
Time Horizon: 60-120 days average
Pyramiding: Enabled (up to 3 adds)
Partial Profit: 30% at +3.0R
```

### Historical Data
```
Latest Backtest: 2022-01-01 to 2026-03-15
Profit Stability: 2023-2025 consistent, 2026 suppressed by market
```

---

## Summary

**RelativeStrength_Ranker_Position** is a **selective momentum strategy** that:

✅ **Works**: 52.25% win rate, $204K profit on 4 years  
✅ **Protects**: Tight early exits, good stop loss placement  
✅ **Captures**: Lets winners run with MA100 trail  
✅ **Pyramids**: Adds to confirmed winners for larger gains  
✅ **Waits**: Market regime filter skips bad conditions  

⚠️ **Limitations**: Only works in bullish markets, needs conviction setups, takes 60-120 days per trade

---

*Last Updated: March 15, 2026*
