"""Quick debug script to trace WDC signal generation."""
import pandas as pd
import sys
sys.path.insert(0, '.')

from src.scanning.scanner import run_scan_as_of
from src.scanning.validator import pre_buy_check
from src.data.market import get_historical_data
from src.scanning.rs_bought_tracker import RSBoughtTracker
from src.config.settings import BACKTEST_START_DATE

# Test a few dates when WDC was historically active
test_dates = [
    pd.Timestamp('2023-11-06'),
    pd.Timestamp('2024-04-23'),
    pd.Timestamp('2026-03-10'),
]

rs_tracker = RSBoughtTracker()

for date in test_dates:
    print(f"\n{'='*80}")
    print(f"🔍 Scanning {date.date()} for WDC")
    print(f"{'='*80}")
    
    # Run scan
    try:
        signals_list = run_scan_as_of(date, tickers=['WDC'], rs_bought_tracker=rs_tracker)
        print(f"\n📊 Signals generated: {len(signals_list)} total")
        if signals_list:
            for signal in signals_list:
                print(f"   • {signal.get('Ticker', 'N/A')} {signal.get('Strategy', 'N/A')}: entry=${signal.get('Entry', 0):.2f}, stop=${signal.get('StopLoss', 0):.2f}")
    except Exception as e:
        print(f"❌ Error running scan: {e}")
        import traceback
        traceback.print_exc()
        continue
    
    # Check pre_buy_check
    if signals_list:
        print(f"\n✓ Running pre_buy_check...")
        # Convert list to DataFrame for pre_buy_check
        signals = pd.DataFrame(signals_list)
        try:
            validated = pre_buy_check(signals, benchmark="QQQ", as_of_date=date)
            print(f"   Passed: {len(validated)} signals")
            if not validated.empty:
                for idx, sig in validated.iterrows():
                    print(f"     • {sig['Ticker']} {sig['Strategy']}: entry=${sig['Entry']:.2f}")
        except Exception as e:
            print(f"❌ Error in pre_buy_check: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"⚠️  No signals generated for WDC on {date.date()}")
    
    # Check historical data
    print(f"\n📈 WDC Data on {date.date()}:")
    try:
        df = get_historical_data('WDC')
        if not df.empty:
            # Find closest date
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, errors='coerce')
            
            mask = df.index <= date
            if mask.any():
                closest_row = df[mask].iloc[-1]
                print(f"   Close: ${closest_row['Close']:.2f}")
                print(f"   Volume: {closest_row['Volume']:,.0f}")
                if 'RS' in df.columns:
                    print(f"   RS vs QQQ: {closest_row['RS']:.2%}")
                if 'ADX' in df.columns:
                    print(f"   ADX: {closest_row['ADX']:.1f}")
            else:
                print(f"   No data available before {date.date()}")
        else:
            print(f"   No historical data for WDC")
    except Exception as e:
        print(f"❌ Error getting data: {e}")

print(f"\n{'='*80}")
print("✓ Debug complete")
