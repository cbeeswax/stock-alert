# Position Management Quick Reference

## 🚀 Daily Commands

```bash
# Check current positions
python manage_positions.py list

# Run daily scan (filters out existing positions)
python main.py

# After entering trade in broker
python manage_positions.py add TICKER PRICE

# After exiting trade
python manage_positions.py remove TICKER
```

---

## 📋 All Commands

| Command | Usage | Example |
|---------|-------|---------|
| **list** | Show all positions | `python manage_positions.py list` |
| **count** | Count positions | `python manage_positions.py count` |
| **add** | Add position | `python manage_positions.py add AAPL 150.00` |
| **add (full)** | Add with stop/target | `python manage_positions.py add AAPL 150.00 "EMA Cross" 147.50 155.50` |
| **remove** | Remove position | `python manage_positions.py remove AAPL` |
| **clear** | Clear all (⚠️) | `python manage_positions.py clear` |
| **help** | Show help | `python manage_positions.py help` |

---

## 🔄 Daily Workflow

### Morning (Before Market)
```bash
python manage_positions.py list    # What am I holding?
python main.py                     # Get new signals (skips existing)
```

### After Entering Trades
```bash
# Bought AAPL at $150.00
python manage_positions.py add AAPL 150.00

# Bought MSFT at $310.50 with stop/target
python manage_positions.py add MSFT 310.50 "Golden Cross" 305.00 321.60
```

### After Exiting Trades
```bash
# Sold AAPL (hit target or stop)
python manage_positions.py remove AAPL
```

---

## 📧 What You'll See in Email

### Current Positions (Top of Email)
```
CURRENT OPEN POSITIONS (3 stocks)
Ticker | Entry $ | Entry Date | Strategy      | Stop $  | Target $
AAPL   | $150.25 | 2026-01-19 | EMA Crossover | $147.50 | $155.50
MSFT   | $310.80 | 2026-01-19 | Golden Cross  | $305.00 | $321.60
GOOGL  | $140.50 | 2026-01-20 | Tight Pull    | $137.00 | $146.00
```

### Actionable Trades (New Signals Only)
```
ACTIONABLE TRADES (3 stocks)
Ticker | Strategy   | Entry | Stop | Target | Score
TSLA   | Cascading  | 245   | 240  | 255    | 9.1
META   | EMA Cross  | 385   | 378  | 398    | 8.3
NVDA   | Golden     | 495   | 485  | 515    | 8.1

Note: AAPL, MSFT, GOOGL skipped (already in position)
```

---

## 💾 Position File Location

`data/open_positions.json`

**Format**:
```json
{
  "AAPL": {
    "entry_date": "2026-01-20 09:30:15",
    "entry_price": 150.25,
    "strategy": "EMA Crossover",
    "stop_loss": 147.50,
    "target": 155.50
  }
}
```

**Backup**:
```bash
cp data/open_positions.json data/positions_backup.json
```

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Getting duplicate signals | Check: `python manage_positions.py list`<br>Add missing: `python manage_positions.py add TICKER PRICE` |
| Forgot to remove position | `python manage_positions.py remove TICKER` |
| Want to start fresh | `python manage_positions.py clear` |
| Lost position file | Add positions again: `python manage_positions.py add ...` |

---

## ✅ Checklist

**Before Market Open**:
- [ ] Check positions: `python manage_positions.py list`
- [ ] Run scan: `python main.py`
- [ ] Check email for new signals

**After Entering Trades**:
- [ ] Add each position: `python manage_positions.py add TICKER PRICE`

**After Exiting Trades**:
- [ ] Remove each position: `python manage_positions.py remove TICKER`

**Weekend Review**:
- [ ] List all positions: `python manage_positions.py list`
- [ ] Remove closed positions
- [ ] Backup file: `cp data/open_positions.json backup.json`

---

## 🎯 Key Points

1. **Always add positions** after entering trades (system can't track automatically)
2. **Always remove positions** after exiting trades (frees up ticker for new signals)
3. **Check positions daily** before running scan
4. **Email shows current positions** at the top
5. **System filters out** tickers already in position

---

## 📞 Need Help?

Read full docs:
- `LIVE_TRADING_GUIDE.md` - Complete guide
- `POSITION_TRACKING_SYSTEM.md` - Technical details
- `python manage_positions.py help` - CLI help

---

**Remember**: The system can only prevent duplicates if you manually track your positions!
