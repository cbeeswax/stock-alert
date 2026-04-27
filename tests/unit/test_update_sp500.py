import pandas as pd

from scripts.update_sp500 import build_historical_union


def test_build_historical_union_preserves_former_members():
    existing_historical = pd.DataFrame(
        [
            {"Symbol": "AAA", "Security": "Old Co"},
            {"Symbol": "BBB", "Security": "Former Co"},
        ]
    )
    current = pd.DataFrame(
        [
            {"Symbol": "AAA", "Security": "Old Co Renamed"},
            {"Symbol": "CCC", "Security": "New Co"},
        ]
    )

    merged = build_historical_union(existing_historical, current)

    assert merged["Symbol"].tolist() == ["AAA", "BBB", "CCC"]
    assert merged.loc[merged["Symbol"] == "AAA", "Security"].iloc[0] == "Old Co Renamed"
    assert merged.loc[merged["Symbol"] == "AAA", "IsCurrent"].iloc[0]
    assert not merged.loc[merged["Symbol"] == "BBB", "IsCurrent"].iloc[0]
    assert merged.loc[merged["Symbol"] == "CCC", "IsCurrent"].iloc[0]
