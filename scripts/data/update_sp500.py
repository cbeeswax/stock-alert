#!/usr/bin/env python
"""
Update S&P 500 Constituents Lists
=================================
Fetches the current S&P 500 member list from Wikipedia and updates:
  - a current-only constituents file for live scans/downloads
  - a historical-union file that preserves former constituents for backtests

Run weekly (via GitHub Actions) to catch:
  - Newly added companies (e.g. post-IPO inclusions, index rebalancing)
  - Removed/delisted companies

Usage:
    python scripts/update_sp500.py           # fetch + save + upload to GCS
    python scripts/update_sp500.py --dry-run # print changes only, no writes
"""

import sys
import argparse
from io import StringIO
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SP500_HISTORICAL_LOCAL = project_root / "data" / "sp500_constituents.csv"
SP500_CURRENT_LOCAL = project_root / "data" / "sp500_current_constituents.csv"
SP500_HISTORICAL_GCS_KEY = "config/sp500_constituents.csv"
SP500_CURRENT_GCS_KEY = "config/sp500_current_constituents.csv"
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; stock-alert-bot/1.0; "
        "+https://github.com/cbeeswax/stock-alert)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Wikipedia column → our CSV column
WIKI_COLUMNS = {
    "Symbol": "Symbol",
    "Security": "Security",
    "GICS Sector": "GICS Sector",
    "GICS Sub-Industry": "GICS Sub-Industry",
    "Headquarters Location": "Headquarters Location",
    "Date added": "Date Added",
    "CIK": "CIK",
    "Founded": "Founded",
}


def normalize_symbol(symbol: str) -> str:
    """Convert Wikipedia-style BRK.B → yfinance-compatible BRK-B."""
    return symbol.strip().replace(".", "-")


def fetch_wikipedia_sp500() -> pd.DataFrame:
    """Fetch current S&P 500 list from Wikipedia. Returns DataFrame with Symbol column."""
    print(f"🌐 Fetching S&P 500 list from Wikipedia...")
    request = Request(WIKIPEDIA_URL, headers=HTTP_HEADERS)
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    tables = pd.read_html(StringIO(html), attrs={"id": "constituents"})
    if not tables:
        raise ValueError("Could not find S&P 500 table on Wikipedia")
    df = tables[0]

    # Rename columns to our standard names
    df = df.rename(columns=WIKI_COLUMNS)

    # Keep only columns we know about
    keep = [c for c in WIKI_COLUMNS.values() if c in df.columns]
    df = df[keep]

    # Normalize symbols: BRK.B → BRK-B
    df["Symbol"] = df["Symbol"].apply(normalize_symbol)

    df = df.drop_duplicates(subset="Symbol").reset_index(drop=True)
    print(f"   ✅ {len(df)} companies found on Wikipedia")
    return df


def load_existing(local_path: Path, gcs_key: str, label: str) -> pd.DataFrame:
    """Load a local CSV, or pull from GCS if missing."""
    if not local_path.exists():
        print(f"📂 Local {label} CSV not found — trying GCS...")
        try:
            from src.storage.gcs import download_file
            if download_file(gcs_key, local_path):
                print(f"   ✅ Downloaded {label} from GCS")
        except Exception as exc:
            print(f"   ⚠️  Could not pull {label} from GCS: {exc}")
            return pd.DataFrame(columns=["Symbol"])

    try:
        df = pd.read_csv(local_path)
        print(f"📂 Loaded existing {label} list: {len(df)} companies")
        return df
    except Exception as exc:
        print(f"⚠️  Could not read existing {label} CSV: {exc}")
        return pd.DataFrame(columns=["Symbol"])


def compare(existing: pd.DataFrame, updated: pd.DataFrame) -> tuple[set, set]:
    """Return (added, removed) symbol sets."""
    old_symbols = set(existing["Symbol"].tolist()) if not existing.empty else set()
    new_symbols = set(updated["Symbol"].tolist())
    added = new_symbols - old_symbols
    removed = old_symbols - new_symbols
    return added, removed


def build_historical_union(existing_historical: pd.DataFrame, current_df: pd.DataFrame) -> pd.DataFrame:
    """Preserve former members for backtests while refreshing current-member metadata."""
    existing = existing_historical.copy() if not existing_historical.empty else pd.DataFrame(columns=["Symbol"])
    current = current_df.copy()

    if "Symbol" not in existing.columns:
        existing["Symbol"] = pd.Series(dtype="object")

    existing["IsCurrent"] = False
    current["IsCurrent"] = True

    combined = pd.concat([current, existing], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(subset="Symbol", keep="first")
    combined = combined.sort_values("Symbol").reset_index(drop=True)
    return combined


def save_and_upload(current_df: pd.DataFrame, historical_df: pd.DataFrame, dry_run: bool):
    """Save both current-only and historical-union CSVs locally and to GCS."""
    if dry_run:
        print("\n🔍 Dry-run mode — no files written")
        return

    SP500_HISTORICAL_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    current_df.to_csv(SP500_CURRENT_LOCAL, index=False)
    historical_df.to_csv(SP500_HISTORICAL_LOCAL, index=False)
    print(f"\n💾 Saved current list → {SP500_CURRENT_LOCAL}")
    print(f"💾 Saved historical-union list → {SP500_HISTORICAL_LOCAL}")

    try:
        from src.storage.gcs import upload_file
        upload_file(SP500_CURRENT_LOCAL, SP500_CURRENT_GCS_KEY)
        upload_file(SP500_HISTORICAL_LOCAL, SP500_HISTORICAL_GCS_KEY)
        print(f"☁️  Uploaded current list → {SP500_CURRENT_GCS_KEY}")
        print(f"☁️  Uploaded historical-union list → {SP500_HISTORICAL_GCS_KEY}")
    except Exception as exc:
        print(f"⚠️  GCS upload failed (local copies are current): {exc}")


def main():
    parser = argparse.ArgumentParser(description="Update S&P 500 constituents list")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print changes without writing any files",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("📊 S&P 500 CONSTITUENTS UPDATE")
    print("=" * 60)

    # 1. Fetch latest list
    try:
        updated = fetch_wikipedia_sp500()
    except Exception as exc:
        print(f"❌ Failed to fetch from Wikipedia: {exc}")
        sys.exit(1)

    # 2. Load existing lists
    existing_current = load_existing(SP500_CURRENT_LOCAL, SP500_CURRENT_GCS_KEY, "current")
    existing_historical = load_existing(SP500_HISTORICAL_LOCAL, SP500_HISTORICAL_GCS_KEY, "historical")
    if existing_current.empty and not existing_historical.empty:
        if "IsCurrent" in existing_historical.columns:
            existing_current = existing_historical[existing_historical["IsCurrent"]].copy()
        else:
            existing_current = existing_historical.copy()

    # 3. Compare
    added, removed = compare(existing_current, updated)
    historical_union = build_historical_union(existing_historical, updated)
    preserved_former = max(len(historical_union) - len(updated), 0)

    print(f"\n📋 Changes detected:")
    if added:
        print(f"   ✅ Added   ({len(added)}): {', '.join(sorted(added))}")
    else:
        print(f"   ✅ Added   (0): none")

    if removed:
        print(f"   ❌ Removed ({len(removed)}): {', '.join(sorted(removed))}")
    else:
        print(f"   ❌ Removed (0): none")
    print(f"   🗃️  Historical-only preserved: {preserved_former}")

    if not added and not removed:
        print("\n✅ List is already up to date — no changes needed")
        if not args.dry_run:
            save_and_upload(updated, historical_union, dry_run=False)
        return 0

    # 4. Save and upload
    save_and_upload(updated, historical_union, dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print(f"✅ Done — {len(updated)} companies in updated list")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
