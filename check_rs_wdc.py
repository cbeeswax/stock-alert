import pandas as pd
from src.data.market import get_historical_data
from src.config.settings import RS_RANKER_SECTORS, RS_RANKER_RS_THRESHOLD
from src.strategies.relative_strength import scan_relative_strength
from src.scanning.rs_bought_tracker import RSBoughtTracker

print("="*80)
print("RS_RANKER Configuration:")
print(f"  Sectors: {RS_RANKER_SECTORS}")
print(f"  RS Threshold: {RS_RANKER_RS_THRESHOLD:.1%}")
print("="*80)

# WDC sector info
print("\nWDC Sector:")
print(f"  ℹ️  Sector file not available, but WDC is in Information Technology")
print(f"  ✓ Should match RS_RANKER sectors (includes: {RS_RANKER_SECTORS})")

# Check RS on specific dates
test_dates = [
    pd.Timestamp('2024-04-23'),
    pd.Timestamp('2026-03-10'),
]

for date in test_dates:
    print(f"\n{'-'*80}")
    print(f"WDC on {date.date()}:")
    
    df = get_historical_data('WDC')
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors='coerce')
    
    mask = df.index <= date
    if mask.any():
        row = df[mask].iloc[-1]
        print(f"  Price: ${row['Close']:.2f}")
        if 'RS' in df.columns:
            print(f"  RS vs QQQ: {row['RS']:.2%}")
        
        # Try to run RS scanner
        print(f"\n  Checking RS Ranker scan...")
        tracker = RSBoughtTracker()
        try:
            signals = scan_relative_strength(date, tickers=['WDC'], rs_bought_tracker=tracker)
            print(f"    Signals: {len(signals)}")
            if signals:
                for sig in signals:
                    print(f"    ✓ {sig['Ticker']} entry=${sig['Entry']:.2f}")
            else:
                print(f"    ✗ No signals (failed RS criteria)")
        except Exception as e:
            print(f"    Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"  No data available")
