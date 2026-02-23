# Quick Reference: Import Updates

## When Writing New Code

Use these imports for the new `src/` structure:

### Configuration
```python
from src.config.settings import POSITION_MAX_TOTAL, POSITION_RISK_PER_TRADE_PCT
```

### Data Layer
```python
from src.data.market import get_historical_data, get_market_cap
from src.data.indicators import compute_rsi, compute_ema_incremental, compute_bollinger_bands
```

### Position Management
```python
from src.position_management.tracker import PositionTracker, filter_trades_by_position
from src.position_management.monitor import monitor_positions
```

### Scanning & Validation
```python
from src.scanning.scanner import run_scan_as_of
from src.scanning.validator import pre_buy_check, normalize_score
```

### Notifications
```python
from src.notifications.email import send_email_alert
from src.notifications.ledger import update_highs_ledger
```

### Analysis & Utilities
```python
from src.analysis.sectors import get_ticker_sector
from src.analysis.regime import get_regime_label
```

## Old vs New Comparison

### Market Data
```python
# ❌ Old
from utils.market_data import get_historical_data

# ✅ New
from src.data.market import get_historical_data
```

### Technical Indicators
```python
# ❌ Old
from utils.ema_utils import compute_rsi, compute_ema_incremental

# ✅ New
from src.data.indicators import compute_rsi, compute_ema_incremental
```

### Position Tracking
```python
# ❌ Old
from utils.position_tracker import PositionTracker

# ✅ New
from src.position_management.tracker import PositionTracker
```

### Position Monitoring
```python
# ❌ Old
from utils.position_monitor import monitor_positions

# ✅ New
from src.position_management.monitor import monitor_positions
```

### Email Alerts
```python
# ❌ Old
from utils.email_utils import send_email_alert

# ✅ New
from src.notifications.email import send_email_alert
```

### Scanner
```python
# ❌ Old
from scanners.scanner_walkforward import run_scan_as_of

# ✅ New
from src.scanning.scanner import run_scan_as_of
```

### Pre-Buy Check / Validation
```python
# ❌ Old
from core.pre_buy_check import pre_buy_check

# ✅ New
from src.scanning.validator import pre_buy_check
```

### Configuration
```python
# ❌ Old
from config.trading_config import POSITION_MAX_TOTAL

# ✅ New
from src.config.settings import POSITION_MAX_TOTAL
# Or (for complete backward compatibility)
from config.trading_config import POSITION_MAX_TOTAL
```

## File Organization

### Old Structure
```
stock-alert/
├── utils/
│   ├── market_data.py
│   ├── ema_utils.py
│   ├── position_tracker.py
│   ├── position_monitor.py
│   ├── email_utils.py
│   └── ...
├── config/
│   └── trading_config.py
├── scanners/
│   └── scanner_walkforward.py
├── core/
│   └── pre_buy_check.py
└── strategies/
    ├── relative_strength.py
    └── ...
```

### New Structure
```
stock-alert/
├── src/
│   ├── config/
│   │   ├── settings.py          (configs)
│   │   └── config.py            (shim)
│   ├── data/
│   │   ├── market.py            (market data)
│   │   └── indicators.py        (technical indicators)
│   ├── position_management/
│   │   ├── tracker.py           (position tracking)
│   │   └── monitor.py           (position monitoring)
│   ├── scanning/
│   │   ├── scanner.py           (scanner logic)
│   │   └── validator.py         (pre-buy checks)
│   ├── notifications/
│   │   ├── email.py             (email alerts)
│   │   └── ledger.py            (shim)
│   ├── analysis/
│   │   ├── sectors.py           (shim)
│   │   ├── regime.py            (shim)
│   │   └── backtester.py
│   └── strategies/
│       ├── relative_strength.py
│       └── ...
├── utils/                       (OLD - still available)
├── config/                      (OLD - still available)
├── scanners/                    (OLD - still available)
├── core/                        (OLD - still available)
└── main.py                      (uses new src/ imports)
```

## Migration Checklist

When updating a file to use new imports:

- [ ] Find all `from utils.` imports
- [ ] Replace with corresponding `from src.X.` imports (see table above)
- [ ] Find all `from config.` imports
- [ ] Replace with `from src.config.` imports
- [ ] Find all `from scanners.` imports
- [ ] Replace with `from src.scanning.` imports
- [ ] Find all `from core.` imports
- [ ] Replace with appropriate `from src.` imports
- [ ] Test the file to ensure imports work
- [ ] Commit changes

## Testing Your Changes

```bash
# Test a single file
python -c "import your_file; print('✅ Imports work')"

# Test all imports
python test_imports.py

# Run the application
python main.py
```

## Need Help?

Reference documents:
- `MIGRATION_COMPLETE.md` - Full migration details
- `IMPORT_MIGRATION_SUMMARY.md` - File-by-file changes
- `README_IMPORTS.md` - This guide's full version

All imports have been tested and validated. If you encounter any import errors, the migration summary documents have detailed information about which files were changed and how.
