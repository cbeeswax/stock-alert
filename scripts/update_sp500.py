#!/usr/bin/env python
"""
Update S&P 500 Constituents List
=================================
Fetches the current S&P 500 member list from Wikipedia and updates
the local + GCS copy of sp500_constituents.csv.

Run weekly (via GitHub Actions) to catch:
  - Newly added companies (e.g. post-IPO inclusions, index rebalancing)
  - Removed/delisted companies

Usage:
    python scripts/update_sp500.py           # fetch + save + upload to GCS
    python scripts/update_sp500.py --dry-run # print changes only, no writes
"""

import sys
import argparse
from pathlib import Path

import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SP500_LOCAL = project_root / "data" / "sp500_constituents.csv"
SP500_GCS_KEY = "config/sp500_constituents.csv"

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
    tables = pd.read_html(WIKIPEDIA_URL, attrs={"id": "constituents"})
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


def load_existing() -> pd.DataFrame:
    """Load existing local CSV, or pull from GCS if missing."""
    if not SP500_LOCAL.exists():
        print("📂 Local CSV not found — trying GCS...")
        try:
            from src.storage.gcs import download_file
            download_file(SP500_GCS_KEY, SP500_LOCAL)
            print("   ✅ Downloaded from GCS")
        except Exception as exc:
            print(f"   ⚠️  Could not pull from GCS: {exc}")
            return pd.DataFrame(columns=["Symbol"])

    try:
        df = pd.read_csv(SP500_LOCAL)
        print(f"📂 Loaded existing list: {len(df)} companies")
        return df
    except Exception as exc:
        print(f"⚠️  Could not read existing CSV: {exc}")
        return pd.DataFrame(columns=["Symbol"])


def compare(existing: pd.DataFrame, updated: pd.DataFrame) -> tuple[set, set]:
    """Return (added, removed) symbol sets."""
    old_symbols = set(existing["Symbol"].tolist()) if not existing.empty else set()
    new_symbols = set(updated["Symbol"].tolist())
    added = new_symbols - old_symbols
    removed = old_symbols - new_symbols
    return added, removed


def save_and_upload(df: pd.DataFrame, dry_run: bool):
    """Save CSV locally and upload to GCS."""
    if dry_run:
        print("\n🔍 Dry-run mode — no files written")
        return

    SP500_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SP500_LOCAL, index=False)
    print(f"\n💾 Saved locally → {SP500_LOCAL}")

    try:
        from src.storage.gcs import upload_file
        upload_file(SP500_LOCAL, SP500_GCS_KEY)
        print(f"☁️  Uploaded to GCS → {SP500_GCS_KEY}")
    except Exception as exc:
        print(f"⚠️  GCS upload failed (local copy is current): {exc}")


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

    # 2. Load existing list
    existing = load_existing()

    # 3. Compare
    added, removed = compare(existing, updated)

    print(f"\n📋 Changes detected:")
    if added:
        print(f"   ✅ Added   ({len(added)}): {', '.join(sorted(added))}")
    else:
        print(f"   ✅ Added   (0): none")

    if removed:
        print(f"   ❌ Removed ({len(removed)}): {', '.join(sorted(removed))}")
    else:
        print(f"   ❌ Removed (0): none")

    if not added and not removed:
        print("\n✅ List is already up to date — no changes needed")
        if not args.dry_run:
            # Still save/upload to keep GCS in sync even if no symbol changes
            save_and_upload(updated, dry_run=False)
        return 0

    # 4. Save and upload
    save_and_upload(updated, dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print(f"✅ Done — {len(updated)} companies in updated list")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
