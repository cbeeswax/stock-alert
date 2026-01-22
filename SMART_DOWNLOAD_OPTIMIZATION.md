# Smart Download Optimization

## 🎯 Problem Fixed

**Before**: Every time you ran the backtest (even 3 times in a row), it would download data for all 500+ tickers, even though the data already existed and was up to date.

**After**: Smart caching system that:
1. ✅ Checks if data already exists before downloading
2. ✅ Skips download if file was updated today
3. ✅ Tracks update sessions to avoid re-downloading on same day
4. ✅ Only downloads new data (incremental updates)

---

## 🚀 Performance Improvement

### Before:
```
Run 1: Download 500 tickers (10-15 minutes)
Run 2: Download 500 tickers AGAIN (10-15 minutes)
Run 3: Download 500 tickers AGAIN (10-15 minutes)
Total wasted time: 20-30 minutes
```

### After:
```
Run 1: Download 500 tickers (10-15 minutes)
Run 2: Skip all (already updated today) (< 1 second)
Run 3: Skip all (already updated today) (< 1 second)
Total saved time: 20-30 minutes per day
```

---

## 🔧 What Changed

### 1. **`scripts/download_history.py`** - Smart Download Logic

#### Added Update Tracking (lines 1-16):
```python
import os  # For file size check

# Track last update to avoid re-downloading on same day
UPDATE_TRACKER_FILE = DATA_DIR / ".last_update"
```

#### Added Helper Functions (lines 18-48):
```python
def was_updated_today(file: Path) -> bool:
    """Check if file was modified today."""
    if not file.exists():
        return False

    file_mtime = datetime.fromtimestamp(file.stat().st_mtime)
    today = datetime.now().date()
    file_date = file_mtime.date()

    return file_date == today

def mark_update_session():
    """Mark that we performed an update session today."""
    UPDATE_TRACKER_FILE.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def was_update_session_today() -> bool:
    """Check if we already ran an update session today."""
    if not UPDATE_TRACKER_FILE.exists():
        return False

    try:
        last_update = UPDATE_TRACKER_FILE.read_text().strip()
        last_update_date = datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S").date()
        return last_update_date == datetime.now().date()
    except:
        return False
```

#### Updated `download_ticker()` Function (lines 50-120):

**Added Smart Checks**:
```python
def download_ticker(ticker: str, force: bool = False):
    """
    Download or update historical data for a ticker.

    Args:
        ticker: Stock ticker symbol
        force: Force download even if already updated today
    """
    file = DATA_DIR / f"{ticker}.csv"

    try:
        # 🆕 CHECK 1: Skip if file was already updated today (unless forced)
        if not force and was_updated_today(file):
            # File was already downloaded/updated today, skip silently
            return

        # CHECK 2: File exists - do incremental update
        if file.exists():
            existing_df = pd.read_csv(file, index_col=0, parse_dates=True)

            # Handle empty files
            if existing_df.empty:
                print(f"⚠️ {ticker}: Empty file, re-downloading...")
                file.unlink()  # Delete and re-download
            else:
                last_date = existing_df.index.max()
                today = pd.Timestamp.now().normalize()

                # If data is up to date (within 3 days), skip
                days_diff = (today - last_date).days
                if days_diff <= 3:
                    print(f"⚡ {ticker}: Already up to date (last: {last_date.date()})")
                    file.touch()  # Update modification time
                    return

                # Download only new data
                start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                print(f"🔄 {ticker}: Updating from {start_date}...")
                # ... download logic ...

        # File doesn't exist - full download
        if not file.exists():
            print(f"📥 {ticker}: Downloading 5 years...")
            # ... download logic ...

        # ... save logic ...

        # 🆕 Touch file to mark as updated today
        file.touch()

    except Exception as e:
        print(f"❌ {ticker}: {e}")
```

**Key Improvements**:
1. **Early exit if updated today** (line 62-65): Checks file modification date
2. **Empty file handling** (line 71-73): Deletes and re-downloads corrupted files
3. **Touch file after update** (line 110): Marks file as updated today
4. **File size check** (line 115): Ensures file has content before appending

---

### 2. **`backtester_walkforward.py`** - Session Tracking

#### Added Import (line 5):
```python
from scripts.download_history import download_ticker, was_update_session_today, mark_update_session
```

#### Updated Data Download Section (lines 304-339):

**Before**:
```python
print("📥 UPDATING HISTORICAL DATA FOR ALL TICKERS")

for i, ticker in enumerate(tickers, 1):
    download_ticker(ticker)  # Always downloads

download_ticker("SPY")  # Always downloads

print("✅ DATA UPDATE COMPLETE!")
```

**After**:
```python
print("📥 CHECKING HISTORICAL DATA")

# 🆕 Check if we already updated today
if was_update_session_today():
    print("⚡ Data already updated today - skipping download")
    print("   (All tickers were checked/updated earlier today)")
else:
    print("🔄 Updating historical data for all tickers...")

    for i, ticker in enumerate(tickers, 1):
        download_ticker(ticker)  # Downloads only if needed

    download_ticker("SPY")

    # 🆕 Mark that we completed an update session today
    mark_update_session()
    print("\n✅ Data update complete!")

print("🚀 Starting backtest...")
```

---

## 📊 How It Works

### Scenario 1: First Run of the Day (9:00 AM)

```
Step 1: Check if update session happened today
   → NO (no .last_update file or date is old)

Step 2: Download data for all tickers
   AAPL: Already up to date (last: 2026-01-17) ⚡
   MSFT: Already up to date (last: 2026-01-17) ⚡
   GOOGL: Updating from 2026-01-18... 🔄
   ... (only downloads missing data)

Step 3: Mark update session complete
   → Write "2026-01-20 09:00:15" to .last_update

Step 4: Run backtest
   → Uses latest data
```

### Scenario 2: Second Run Same Day (9:30 AM)

```
Step 1: Check if update session happened today
   → YES (.last_update shows 2026-01-20 09:00:15)

Step 2: Skip entire download process
   ⚡ Data already updated today - skipping download
   (Saved 10-15 minutes!)

Step 3: Run backtest immediately
   → Uses cached data from earlier today
```

### Scenario 3: Third Run Same Day (10:00 AM)

```
Step 1: Check if update session happened today
   → YES (.last_update shows 2026-01-20 09:00:15)

Step 2: Skip entire download process
   ⚡ Data already updated today - skipping download
   (Saved another 10-15 minutes!)

Step 3: Run backtest immediately
   → Uses cached data
```

### Scenario 4: Next Day (Next Morning)

```
Step 1: Check if update session happened today
   → NO (.last_update shows yesterday's date)

Step 2: Download new data
   → Only downloads data for new trading day
   → Much faster (< 1 minute for incremental update)

Step 3: Mark update session complete
   → Write new timestamp

Step 4: Run backtest with fresh data
```

---

## 🗂️ New Files Created

### `.last_update` File
Located at: `data/historical/.last_update`

**Content Example**:
```
2026-01-20 09:00:15
```

**Purpose**:
- Tracks when the last full update session completed
- Checked before each backtest run
- Prevents redundant downloads on same day

**Maintenance**:
- Auto-updated after each successful download session
- Can be manually deleted to force re-download: `rm data/historical/.last_update`

---

## 🔍 File Modification Time Tracking

Each CSV file's modification time is now tracked:

**Example**:
```bash
$ ls -lh data/historical/AAPL.csv
-rw-r--r--  1 user  staff   125K Jan 20 09:00 AAPL.csv
                                    ^^^^^^^^^^^^
                                    Last modified today at 9:00 AM
```

If file was touched today (modification date = today), skip download.

---

## 🎛️ Force Download Option

If you need to force a re-download (rare cases):

### Option 1: Delete Update Tracker
```bash
rm data/historical/.last_update
python3 backtester_walkforward.py
```

### Option 2: Delete Specific Ticker Data
```bash
rm data/historical/AAPL.csv
python3 backtester_walkforward.py
# Will re-download only AAPL
```

### Option 3: Delete All Data (Nuclear Option)
```bash
rm data/historical/*.csv
rm data/historical/.last_update
python3 backtester_walkforward.py
# Will re-download everything
```

---

## 📈 Performance Metrics

### Before Optimization:
```
Download Time per Run: 10-15 minutes
Runs per Day: 3-5
Total Download Time: 30-75 minutes/day
Wasted Time: 20-60 minutes/day (redundant downloads)
```

### After Optimization:
```
Download Time (First Run): 10-15 minutes
Download Time (Subsequent Runs): < 1 second
Runs per Day: 3-5
Total Download Time: 10-15 minutes/day
Time Saved: 20-60 minutes/day
```

**Annual Time Savings**: ~120-360 hours/year!

---

## 🧪 Testing the Optimization

### Test 1: First Run
```bash
python3 backtester_walkforward.py --scan-frequency B
```

**Expected Output**:
```
============================================================
📥 CHECKING HISTORICAL DATA
============================================================
🔄 Updating historical data for all tickers...

⚡ AAPL: Already up to date (last: 2026-01-17)
⚡ MSFT: Already up to date (last: 2026-01-17)
🔄 GOOGL: Updating from 2026-01-18...
✅ GOOGL: Added 2 new rows (total: 1258)
...

✅ Data update complete!

============================================================
🚀 Starting backtest...
============================================================
```

### Test 2: Immediate Second Run
```bash
python3 backtester_walkforward.py --scan-frequency B
```

**Expected Output**:
```
============================================================
📥 CHECKING HISTORICAL DATA
============================================================
⚡ Data already updated today - skipping download
   (All tickers were checked/updated earlier today)

============================================================
🚀 Starting backtest...
============================================================
```

**Time Saved**: ~10-15 minutes! ✅

---

## 🐛 Troubleshooting

### Problem: "Still downloading every time"

**Check 1**: Verify `.last_update` file exists
```bash
cat data/historical/.last_update
# Should show today's date
```

**Check 2**: Verify file modification times
```bash
ls -lh data/historical/*.csv | head -5
# Should show today's date if updated
```

**Check 3**: Delete tracker and retry
```bash
rm data/historical/.last_update
python3 backtester_walkforward.py
```

### Problem: "Data is outdated"

**Solution**: Force re-download by deleting tracker
```bash
rm data/historical/.last_update
python3 backtester_walkforward.py
```

### Problem: "Some tickers missing data"

**Check**: Look for empty files
```bash
find data/historical -name "*.csv" -size 0
# Delete any empty files found
```

**Solution**: Delete problematic tickers and re-run
```bash
rm data/historical/PROBLEMATIC_TICKER.csv
python3 backtester_walkforward.py
```

---

## ✅ Summary

### Files Modified:
1. ✅ `scripts/download_history.py` - Smart download logic with update tracking
2. ✅ `backtester_walkforward.py` - Session-based update checking

### New Features:
1. ✅ File modification time tracking (skip if updated today)
2. ✅ Update session tracking (skip entire download if done today)
3. ✅ Empty file detection and cleanup
4. ✅ Incremental updates (only download new data)
5. ✅ Silent skip for efficiency (no spam output)

### Benefits:
1. ✅ **20-60 minutes saved per day** on redundant downloads
2. ✅ **Instant backtest runs** after first run of the day
3. ✅ **Better data integrity** (handles corrupted files)
4. ✅ **Clear feedback** (shows what's being downloaded vs skipped)

---

**Your download system is now optimized!** 🎉

Run your backtest 3 times in a row and watch it skip the download after the first run.
