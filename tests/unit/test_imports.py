#!/usr/bin/env python3
"""Test all key imports to verify migration to src/ structure"""

print("Testing all key imports...")
print("=" * 80)

tests = [
    ("src.config.settings", "POSITION_MAX_TOTAL, ADX_THRESHOLD", "from src.config.settings import POSITION_MAX_TOTAL, ADX_THRESHOLD"),
    ("src.data.market", "get_historical_data", "from src.data.market import get_historical_data"),
    ("src.data.indicators", "compute_rsi, compute_ema_incremental", "from src.data.indicators import compute_rsi, compute_ema_incremental"),
    ("src.position_management.tracker", "PositionTracker", "from src.position_management.tracker import PositionTracker"),
    ("src.position_management.monitor", "monitor_positions", "from src.position_management.monitor import monitor_positions"),
    ("src.scanning.validator", "pre_buy_check", "from src.scanning.validator import pre_buy_check"),
    ("src.scanning.scanner", "run_scan_as_of", "from src.scanning.scanner import run_scan_as_of"),
    ("src.notifications.email", "send_email_alert", "from src.notifications.email import send_email_alert"),
    ("strategies.relative_strength", "check_relative_strength", "from strategies.relative_strength import check_relative_strength"),
    ("main", "main module", "import main"),
    ("core.pre_buy_check", "pre_buy_check module", "import core.pre_buy_check"),
]

passed = 0
failed = 0

for i, (module, items, import_stmt) in enumerate(tests, 1):
    try:
        exec(import_stmt)
        print(f"{i}. ✅ {module}")
        passed += 1
    except Exception as e:
        print(f"{i}. ❌ {module}: {str(e)[:60]}")
        failed += 1

print("=" * 80)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("✨ All imports successful!")
else:
    print(f"⚠️  {failed} import(s) failed")
    exit(1)
