# TechMomentum_Swing_30_60 Strategy

## Overview
Medium-term momentum swing strategy designed for tech stocks (20-60 trading days).
Targets trend legs similar to PLTR/GOOG momentum moves.

## Strategy Details

### Universe
- **Sectors**: Information Technology, Communication Services
- **Liquidity**: Minimum $20M average 20-day dollar volume
- **Count**: ~92 stocks from S&P 500

### Market Regime Filter (Index Level)
Uses QQQ (NASDAQ-100) as benchmark:
- QQQ close > SMA(200)
- SMA(200) today > SMA(200) 20 days ago
- **No new positions if regime filter fails**

### Stock-Level Filters

#### Trend Conditions (all must be true)
1. Close > SMA(100)
2. SMA(50) > SMA(100)
3. SMA(100) today > SMA(100) 20 days ago

#### Relative Strength
- Stock 60-day return ≥ Index 60-day return + 5%
- Ensures stock is outperforming the index

### Entry Logic: Pullback to Trend

#### Pullback Detection (Day T-1)
**Condition A - Proximity:**
- Price within 1 × ATR(14) of EMA(20), OR
- Low ≤ EMA(20) + 1 × ATR

**Condition B - Momentum Check:**
- RSI(14) ≥ 40 (no deep momentum break)

#### Entry Trigger (Day T)
Enter long at close if:
- Yesterday satisfied pullback conditions A and B
- Today's close > yesterday's high (bullish resumption)
- Close still > EMA(20)
- Meets liquidity threshold ($20M+ avg dollar volume)

### Position Sizing & Risk
- **Risk per trade**: 1% of account equity
- **Initial stop**: Entry - 2.5 × ATR(14)
- **Swing low adjustment**: If recent 10-bar swing low creates a tighter stop, use that instead (with 0.5 × ATR buffer)
- **Position size**: risk_dollars / (entry_price - stop_price)

### Trade Management

#### Partial Profit (40% at 2R)
When position reaches 2R profit:
- Sell 40% of shares
- Lock remaining position at breakeven + 1R
- Let 60% runner continue with trailing stop

#### Runner Trailing Stop
- Trail by 2.5 × ATR(14) from highest close since entry
- Updates daily as new highs are made
- Exit when close < trailing stop

#### Time Stop
- Maximum holding period: 60 trading days
- Exit at market close on day 60 if still open

### Risk Controls
- Max concurrent positions: 8
- No new entries when QQQ regime filter is off
- Global 1% risk per trade cap

## Configuration

All parameters are in `config/trading_config.py`:

```python
# Universe
TECHMOMENTUM_SECTORS = ["Information Technology", "Communication Services"]
TECHMOMENTUM_MIN_LIQUIDITY = 20_000_000  # $20M

# Entry
TECHMOMENTUM_PULLBACK_ATR_MULTIPLE = 1.0
TECHMOMENTUM_RSI_MIN = 40
TECHMOMENTUM_RELATIVE_STRENGTH_THRESHOLD = 0.05  # 5%

# Stop Loss
TECHMOMENTUM_STOP_ATR_MULTIPLE = 2.5
TECHMOMENTUM_SWING_LOW_BUFFER = 0.5

# Partial Profit
TECHMOMENTUM_PARTIAL_R_TRIGGER = 2.0
TECHMOMENTUM_PARTIAL_SIZE = 0.4  # 40%
TECHMOMENTUM_BREAKEVEN_LOCK = 1.0  # +1R

# Trailing & Time
TECHMOMENTUM_TRAIL_ATR_MULTIPLE = 2.5
TECHMOMENTUM_MAX_HOLDING_DAYS = 60

# Risk
TECHMOMENTUM_MAX_POSITIONS = 8
```

## Running Backtests

### Full Backtest (All Strategies)
```bash
source venv/bin/activate
python backtester_walkforward.py --scan-frequency B
```

This will scan all stocks for all strategies including TechMomentum.

### Quick Test
```bash
source venv/bin/activate
python test_techmomentum.py
```

### Filter Results by Strategy
After running backtest, filter the results CSV:
```python
import pandas as pd

results = pd.read_csv("backtest_results.csv")
techmomentum = results[results["Strategy"] == "TechMomentum_Swing_30_60"]

print(f"TechMomentum trades: {len(techmomentum)}")
print(f"Win rate: {(techmomentum['Outcome'] == 'Win').mean() * 100:.1f}%")
print(f"Avg R-multiple: {techmomentum['RMultiple'].mean():.2f}")
print(f"Total PnL: ${techmomentum['PnL_$'].sum():,.2f}")
```

## Expected Performance Characteristics

- **Holding period**: 20-60 days (medium-term)
- **Win rate**: Target 40-50% (momentum strategies typically lower WR)
- **R-multiple**: Target 1.5-2.5R average (asymmetric wins)
- **Trade frequency**: Selective (requires regime + trend + RS + pullback + entry trigger)
- **Max drawdown**: Controlled by 1% risk per trade + max 8 positions = 8% max portfolio risk

## Integration Notes

### Scanner (scanners/scanner_walkforward.py)
- Checks QQQ regime filter (SMA200)
- Filters by sector (tech/comm only)
- Validates trend, relative strength, pullback conditions
- Generates signals with ATR(14) included

### Backtester (backtester_walkforward.py)
- Immediate entry (no confirmation bar)
- ATR-based stop calculation with swing low adjustment
- Partial exit at 2R with breakeven lock
- ATR trailing stop for runner
- Time stop at 60 days

### Position Tracker
- Respects 8-position concurrent limit
- Prevents duplicate positions
- Tracks entry/exit dates for reporting

## Tuning Guidelines

### More Trades (Relaxed Filters)
- Reduce `TECHMOMENTUM_RSI_MIN` to 35
- Reduce `TECHMOMENTUM_RELATIVE_STRENGTH_THRESHOLD` to 0.03 (3%)
- Increase `TECHMOMENTUM_MAX_POSITIONS` to 10-12

### Higher Quality (Tighter Filters)
- Increase `TECHMOMENTUM_RSI_MIN` to 45
- Increase `TECHMOMENTUM_RELATIVE_STRENGTH_THRESHOLD` to 0.07 (7%)
- Reduce `TECHMOMENTUM_MAX_POSITIONS` to 5-6

### Risk Adjustment
- Lower risk: Increase `TECHMOMENTUM_STOP_ATR_MULTIPLE` to 3.0
- Higher risk: Decrease to 2.0
- Adjust `TECHMOMENTUM_RISK_PER_TRADE_PCT` between 0.5% - 2.0%

## References
- Strategy designed for tech sector momentum (PLTR, GOOG, NVDA style moves)
- Combines trend-following with mean-reversion entry (pullback)
- ATR-based stops adapt to volatility
- Partial exits lock in profits while letting winners run
