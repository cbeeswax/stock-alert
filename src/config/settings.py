"""Central configuration for the supported position strategies."""

POSITION_INITIAL_EQUITY = 100000
POSITION_RISK_PER_TRADE_PCT = 2.0
POSITION_MAX_TOTAL = 20
POSITION_MAX_PER_STRATEGY = {
    "RallyPattern_Position": 10,
    "RelativeStrength_Ranker_Position": 10,
    "Streak_Position": 1,
}
POSITION_MAX_PER_STRATEGY_DEFAULT = 5
POSITION_MAX_DAYS_LONG = 120
POSITION_PARTIAL_ENABLED = True
POSITION_PARTIAL_SIZE = 0.3
POSITION_PYRAMID_ENABLED = True
POSITION_PYRAMID_R_TRIGGER = 1.5
POSITION_PYRAMID_SIZE = 0.5
POSITION_PYRAMID_MAX_ADDS = 3
POSITION_PYRAMID_PULLBACK_EMA = 21
POSITION_PYRAMID_PULLBACK_ATR = 1.0

MIN_LIQUIDITY_USD = 30_000_000
MIN_PRICE = 10.0
MAX_PRICE = 999999.0
REGIME_INDEX = "QQQ"
UNIVERSAL_ADX_MIN = 30
UNIVERSAL_RS_MIN = 0.30
UNIVERSAL_VOLUME_MULT = 2.5
UNIVERSAL_ALL_MAS_RISING = True
UNIVERSAL_QQQ_BULL_MA = 100
UNIVERSAL_QQQ_MA_RISING_DAYS = 20
RISK_REWARD_RATIO = 2

STRATEGY_PRIORITY = {
    "RallyPattern_Position": 3,
    "RelativeStrength_Ranker_Position": 2,
    "Streak_Position": 4,
}

RS_RANKER_SECTORS = ["Information Technology", "Communication Services", "Technology"]
RS_RANKER_TOP_N = 10
RS_RANKER_RS_THRESHOLD = 0.30
RS_RANKER_STOP_ATR_MULT = 2.0
RS_RANKER_PARTIAL_R = 2.5
RS_RANKER_PARTIAL_SIZE = 0.3
RS_RANKER_TRAIL_MA = 100
RS_RANKER_TRAIL_DAYS = 10
RS_RANKER_MAX_DAYS = 120

BACKTEST_START_DATE = "2022-01-01"
BACKTEST_SCAN_FREQUENCY = "B"
BACKTEST_COMPOUNDING = True
BACKTEST_BROKERAGE_ENABLED = True
BACKTEST_SEC_FEE_RATE = 0.0000278
BACKTEST_FINRA_TAF_RATE = 0.000119
BACKTEST_FINRA_TAF_MAX = 5.95
BACKTEST_TAX_ENABLED = True
BACKTEST_TAX_SHORT_TERM_RATE = 0.37
BACKTEST_TAX_LONG_TERM_RATE = 0.20

MIN_NORM_SCORE = 7.0
MAX_TRADES_EMAIL = 5


def _apply_gcs_overrides():
    import json
    import os
    import tempfile
    from pathlib import Path

    def _apply(data: dict, source: str):
        known = globals()
        applied = [key for key in data if key in known]
        for key in applied:
            known[key] = data[key]
        if applied:
            print(f"[settings] Loaded {len(applied)} override(s) from {source}")

    local_file = Path(__file__).parent.parent.parent / "config" / "settings.json"
    if local_file.exists():
        try:
            with local_file.open(encoding="utf-8") as handle:
                _apply(json.load(handle), f"local {local_file}")
            return
        except Exception as exc:
            print(f"[settings] Could not load local settings: {exc}")

    try:
        from src.storage.gcs import download_file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
            temp_path = handle.name
        try:
            if download_file("config/settings.json", temp_path):
                with open(temp_path, encoding="utf-8") as handle:
                    _apply(json.load(handle), "GCS config/settings.json")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    except Exception as exc:
        print(f"[settings] Could not load GCS overrides: {exc}")


_apply_gcs_overrides()
POSITION_MAX_PER_STRATEGY.setdefault("Streak_Position", 1)
