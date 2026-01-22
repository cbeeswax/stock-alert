# Position Storage Locations

## 📍 Storage Summary

Position tracking uses **different storage** depending on the mode:

| Mode | Storage Type | Location | Persistence |
|------|-------------|----------|-------------|
| **Backtesting** | In-Memory | Python dictionary | ❌ Cleared after run |
| **Live Trading** | JSON File | `data/open_positions.json` | ✅ Persists across runs |

---

## 🗂️ File Structure

```
stock-alert/
├── data/
│   ├── open_positions.json          ← 🎯 LIVE TRADING POSITIONS STORED HERE
│   ├── historical/
│   │   ├── .last_update             ← Download session tracking
│   │   ├── AAPL.csv                 ← Historical price data
│   │   ├── MSFT.csv
│   │   └── ...
│   └── sp500_constituents.csv
├── utils/
│   └── position_tracker.py           ← Position tracking module
├── manage_positions.py               ← CLI tool to manage positions
├── main.py                           ← Live trading (uses open_positions.json)
└── backtester_walkforward.py         ← Backtesting (in-memory only)
```

---

## 💾 Detailed Explanation

### 1. **Backtesting Mode** (In-Memory Storage)

**Where**: Python dictionary in RAM

**Code** (`backtester_walkforward.py`):
```python
self.position_tracker = PositionTracker(mode="backtest")
# mode="backtest" → stores in memory only
# Data structure: self.positions = {}
```

**Storage Lifetime**:
```
Run 1: Start backtest → positions = {}
       Add AAPL → positions = {"AAPL": {...}}
       Add MSFT → positions = {"AAPL": {...}, "MSFT": {...}}
       Complete backtest → positions = {} (cleared)

Run 2: Start backtest → positions = {} (fresh start)
```

**Why In-Memory?**
- ✅ Fast (no file I/O)
- ✅ Clean slate each run
- ✅ Simulates realistic portfolio
- ✅ No need to persist (backtest is self-contained)

---

### 2. **Live Trading Mode** (JSON File Storage)

**Where**: `data/open_positions.json`

**Code** (`main.py`):
```python
position_tracker = PositionTracker(mode="live", file="data/open_positions.json")
# mode="live" → saves to JSON file
# file="data/open_positions.json" → location
```

**Storage Lifetime**:
```
Day 1: Add AAPL → File created
       Add MSFT → File updated
       File persists overnight

Day 2: Run main.py → Loads from file
       AAPL, MSFT still there ✅
       Add GOOGL → File updated

Day 3: Remove AAPL → File updated
       AAPL gone, MSFT/GOOGL remain
```

**Why JSON File?**
- ✅ Persists across runs
- ✅ Human-readable (can edit manually if needed)
- ✅ Easy backup (copy file)
- ✅ Cross-platform compatible
- ✅ No database needed

---

## 📄 JSON File Format

**Location**: `data/open_positions.json`

**Format**:
```json
{
  "AAPL": {
    "entry_date": "2026-01-20 09:30:15",
    "entry_price": 150.25,
    "strategy": "EMA Crossover",
    "stop_loss": 147.50,
    "target": 155.50
  },
  "MSFT": {
    "entry_date": "2026-01-20 09:35:22",
    "entry_price": 310.80,
    "strategy": "Golden Cross",
    "stop_loss": 305.00,
    "target": 321.60
  },
  "GOOGL": {
    "entry_date": "2026-01-20 10:15:45",
    "entry_price": 140.50,
    "strategy": "Tight Pullback",
    "stop_loss": 137.00,
    "target": 146.00
  }
}
```

**File Size**: Very small (~1-2 KB for 10 positions)

---

## 🔍 How to Check Storage

### Check if File Exists:
```bash
ls -lh data/open_positions.json
```

**If file doesn't exist**:
- ✅ Normal! File is created when you add first position
- Run: `python manage_positions.py add TEST 100.00`
- File will be created automatically

**If file exists**:
```bash
# View contents
cat data/open_positions.json

# Pretty print
python -m json.tool data/open_positions.json
```

---

## 📊 Data Flow

### Live Trading Flow:

```
1. You run: python manage_positions.py add AAPL 150.00
   ↓
2. PositionTracker adds to self.positions dict
   ↓
3. Calls _save_positions()
   ↓
4. Writes to data/open_positions.json
   ↓
5. File persists on disk

Next Day:
1. You run: python main.py
   ↓
2. PositionTracker loads from data/open_positions.json
   ↓
3. self.positions dict populated from file
   ↓
4. Filters out AAPL from new signals
   ↓
5. Email shows AAPL in "Current Positions"
```

### Backtesting Flow:

```
1. Backtest starts
   ↓
2. PositionTracker initialized with mode="backtest"
   ↓
3. self.positions = {} (empty dict in memory)
   ↓
4. Add positions during simulation
   ↓
5. self.positions = {"AAPL": {...}, "MSFT": {...}}
   ↓
6. Backtest ends
   ↓
7. Python process ends → memory cleared
   ↓
8. No file saved (intentional)
```

---

## 🔧 Code References

### Where Storage is Defined:

**In `utils/position_tracker.py`**:

```python
class PositionTracker:
    def __init__(self, mode="backtest", file="data/open_positions.json"):
        self.mode = mode
        self.file = Path(file)  # ← File location
        self.positions = {}     # ← In-memory dict

        # Load from file if live mode
        if mode == "live" and self.file.exists():
            self._load_positions()  # ← Loads from JSON

    def _save_positions(self):
        """Save positions to JSON file (live mode only)."""
        if self.mode != "live":
            return  # ← Backtesting doesn't save

        # Write to file
        with open(self.file, 'w') as f:
            json.dump(data, f, indent=2)  # ← Writes JSON
```

### Where Storage is Used:

**Backtesting** (`backtester_walkforward.py`):
```python
# Line 40
self.position_tracker = PositionTracker(mode="backtest")
# ↑ In-memory only, no file
```

**Live Trading** (`main.py`):
```python
# Line 11
position_tracker = PositionTracker(mode="live", file="data/open_positions.json")
# ↑ Saves to JSON file
```

---

## 💡 Key Points

### Backtesting:
- ✅ **Storage**: In-memory (Python dictionary)
- ✅ **Location**: RAM (not saved to disk)
- ✅ **Lifetime**: Duration of backtest run only
- ✅ **File Created**: No
- ✅ **Why**: Fast, clean slate each run

### Live Trading:
- ✅ **Storage**: JSON file
- ✅ **Location**: `data/open_positions.json`
- ✅ **Lifetime**: Persists until manually deleted
- ✅ **File Created**: Yes (on first add)
- ✅ **Why**: Needs to persist across days

---

## 📂 File Operations

### When File is Created:
```bash
# First position added
python manage_positions.py add AAPL 150.00
# → Creates data/open_positions.json
```

### When File is Updated:
```bash
# Add position
python manage_positions.py add MSFT 310.00
# → Updates data/open_positions.json

# Remove position
python manage_positions.py remove AAPL
# → Updates data/open_positions.json
```

### When File is Read:
```bash
# Run main.py
python main.py
# → Reads data/open_positions.json at startup
```

### When File is Deleted:
```bash
# Clear all positions
python manage_positions.py clear
# → Writes {} to data/open_positions.json (or deletes file)

# Or manually delete
rm data/open_positions.json
# → Next run will create fresh file
```

---

## 🔒 File Permissions

**File is created with standard permissions**:
```bash
-rw-r--r--  1 user  staff  458 Jan 20 14:00 data/open_positions.json
```

**Readable by**: Owner
**Writable by**: Owner
**Executable**: No

---

## 💾 Backup Recommendations

### Daily Backup (Automated):
```bash
# Add to your cron job or startup script
cp data/open_positions.json data/positions_backup_$(date +%Y%m%d).json
```

### Manual Backup:
```bash
# Before making changes
cp data/open_positions.json data/positions_backup.json

# Restore if needed
cp data/positions_backup.json data/open_positions.json
```

### Git Tracking:
```bash
# Add to .gitignore (recommended for production)
echo "data/open_positions.json" >> .gitignore

# Or commit (if you want version history)
git add data/open_positions.json
git commit -m "Updated positions"
```

---

## 🧪 Testing Storage

### Test 1: Verify File Creation
```bash
# Check if file exists
ls -lh data/open_positions.json
# Should NOT exist yet (if fresh install)

# Add position
python manage_positions.py add TEST 100.00

# Check again
ls -lh data/open_positions.json
# Should exist now!

# View contents
cat data/open_positions.json
```

### Test 2: Verify Persistence
```bash
# Add position
python manage_positions.py add AAPL 150.00

# Close terminal, reboot computer, etc.

# Open terminal again
python manage_positions.py list
# Should still show AAPL ✅
```

### Test 3: Verify In-Memory (Backtest)
```bash
# Run backtest
python backtester_walkforward.py --scan-frequency B

# Check for file
ls -lh data/open_positions.json
# Should NOT exist (backtest doesn't create it)
```

---

## 🎯 Summary Table

| Aspect | Backtesting | Live Trading |
|--------|-------------|--------------|
| **Storage Type** | In-Memory | JSON File |
| **Location** | Python RAM | `data/open_positions.json` |
| **Created When** | N/A | First `add` command |
| **Updated When** | N/A | Every `add`/`remove` |
| **Persists** | ❌ No | ✅ Yes |
| **Size** | Dynamic | ~1-2 KB |
| **Human Readable** | ❌ No | ✅ Yes (JSON) |
| **Backup Needed** | ❌ No | ✅ Yes (recommended) |
| **File Path** | N/A | `data/open_positions.json` |

---

## 📞 Quick Reference

### Check Storage Location:
```bash
# File location (live trading)
echo "data/open_positions.json"

# Check if exists
test -f data/open_positions.json && echo "File exists" || echo "File doesn't exist"

# View contents
cat data/open_positions.json
```

### View Storage:
```bash
# Pretty print JSON
python -m json.tool data/open_positions.json

# Or use CLI tool
python manage_positions.py list
```

### Backup Storage:
```bash
# Manual backup
cp data/open_positions.json backup/positions_$(date +%Y%m%d).json
```

---

**Storage Location**: `data/open_positions.json` (live trading only)

**Backtesting**: In-memory (no file created)

**Size**: Tiny (~1-2 KB)

**Format**: Human-readable JSON
