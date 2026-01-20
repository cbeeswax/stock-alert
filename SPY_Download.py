import yfinance as yf
import pandas as pd
from pathlib import Path

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
TICKER = "SPY"
PERIOD = "6y"
INTERVAL = "1d"
DATA_DIR = Path("historical_data")
DATA_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = DATA_DIR / f"{TICKER}.csv"

# -------------------------------------------------
# DOWNLOAD
# -------------------------------------------------
print("📥 Downloading SPY historical data (6 years)...")

df = yf.download(
    TICKER,
    period=PERIOD,
    interval=INTERVAL,
    auto_adjust=False,
    progress=False
)

if df.empty:
    raise RuntimeError("❌ Failed to download SPY data")

# -------------------------------------------------
# CLEANUP (match your pipeline expectations)
# -------------------------------------------------
df = df.rename(columns={
    "Open": "Open",
    "High": "High",
    "Low": "Low",
    "Close": "Close",
    "Adj Close": "AdjClose",
    "Volume": "Volume"
})

df.index.name = "Date"

df.to_csv(OUTPUT_FILE)

print(f"✅ SPY data saved to: {OUTPUT_FILE.resolve()}")
print(f"📊 Rows: {len(df)} | From {df.index.min().date()} to {df.index.max().date()}")
