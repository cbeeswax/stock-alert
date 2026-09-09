# Contributing

Use the registry-based strategy pipeline. New work must preserve the exact supported strategy names: `RallyPattern_Position`, `RelativeStrength_Ranker_Position`, and `Streak_Position`.

Run focused tests before submitting changes:

```powershell
pytest tests/strategies/test_rally_pattern_position.py tests/strategies/test_streak.py -v
pytest tests/unit/test_scanner_registry_dispatch.py tests/unit/test_backtesting_rally_stage_caps.py -v
```
