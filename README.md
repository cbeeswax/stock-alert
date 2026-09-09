# Stock Alert

A Python position-trading scanner and walk-forward backtester for exactly three supported strategies:

- **RallyPattern_Position** — cross-sectional rally-pattern leader setups.
- **RelativeStrength_Ranker_Position** — liquid technology and communication leaders with strong relative strength.
- **Streak_Position** — one next-session option alert selected from a fixed liquid universe.

## Running a scan

```powershell
python main.py --label "Evening Scan"
```

The scanner loads cached market data, runs enabled registry strategies, validates and deduplicates signals, monitors existing positions, and sends notifications. Strategy activation and capacity are controlled solely by `POSITION_MAX_PER_STRATEGY` in `src/config/settings.py` (with optional `config/settings.json` overrides).

## Backtesting

```powershell
python scripts/backtest_strategies.py --strategy rally
python scripts/backtest_strategies.py --strategy rs
python scripts/backtest_strategies.py --strategy streak
python scripts/backtest_strategies.py --strategy all
```

`Streak_Position` is entered at the following session's open and exits at that session's close. The other two strategies use the shared walk-forward position management flow.

## Setup and testing

```powershell
pip install -r requirements.txt
pytest tests/strategies/test_rally_pattern_position.py tests/strategies/test_streak.py -v
pytest tests/unit/test_scanner_registry_dispatch.py tests/unit/test_backtesting_rally_stage_caps.py -v
```

## Architecture

- `src/strategies/registry.py` registers only the three supported strategy classes.
- `src/scanning/scanner.py` dispatches enabled registered strategies.
- `src/scanning/validator.py` normalizes valid signals and preserves Rally retry invalidation and Streak option-alert handling.
- `src/backtesting/engine.py` reuses the scanner and validator in walk-forward simulations.
- `src/position_management/monitor.py` applies live stops, time stops, Rally exits, RS management, and Streak next-session exits.

Market data is file-backed through `src.data.market`; GCS sync is optional for local development.
