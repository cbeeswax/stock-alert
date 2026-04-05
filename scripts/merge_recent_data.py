"""Merge recent yfinance data into existing historical CSVs."""
import yfinance as yf
import pandas as pd
import os

data_dir = r"C:\Users\pelac\Git\HistoricalData\historical"
tickers = sorted([f[:-4] for f in os.listdir(data_dir) if f.endswith(".csv")])
if "SPY" not in tickers:
    tickers.append("SPY")

print(f"Downloading Jan 14 – Apr 4, 2026 for {len(tickers)} tickers...")
df_new = yf.download(" ".join(tickers), start="2026-01-14", end="2026-04-05", progress=False)

updated = 0
for ticker in tickers:
    csv_path = os.path.join(data_dir, f"{ticker}.csv")
    try:
        new_rows = pd.DataFrame({
            "Close": df_new["Close"][ticker],
            "High": df_new["High"][ticker],
            "Low": df_new["Low"][ticker],
            "Open": df_new["Open"][ticker],
            "Volume": df_new["Volume"][ticker],
        }).dropna(how="all")
    except (KeyError, Exception):
        continue

    if new_rows.empty:
        continue

    if os.path.exists(csv_path):
        existing = pd.read_csv(csv_path, skiprows=[1], index_col=0)
        existing.index = pd.to_datetime(existing.index, format="%Y-%m-%d", errors="coerce")
        existing = existing[existing.index.notna()]
        combined = pd.concat([existing, new_rows[~new_rows.index.isin(existing.index)]]).sort_index()
    else:
        combined = new_rows

    with open(csv_path, "w") as f:
        f.write("Price,Close,High,Low,Open,Volume\n")
        f.write(f"Ticker,{ticker},{ticker},{ticker},{ticker},{ticker}\n")
        for dt, row in combined.iterrows():
            c = row["Close"]
            h = row["High"]
            l = row["Low"]
            o = row["Open"]
            v = row["Volume"]
            f.write(f"{dt.date()},{c},{h},{l},{o},{v}\n")
    updated += 1

print(f"Updated {updated} ticker files.")

# Verify
test = pd.read_csv(os.path.join(data_dir, "AAPL.csv"), skiprows=[1], index_col=0)
test.index = pd.to_datetime(test.index, format="%Y-%m-%d", errors="coerce")
test = test[test.index.notna()]
print(f"AAPL: {test.index.min().date()} -> {test.index.max().date()} ({len(test)} days)")
