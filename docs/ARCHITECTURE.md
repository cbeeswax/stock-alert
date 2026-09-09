# Architecture

`main.py` coordinates daily scans, validation, position tracking, monitoring, and notifications. `src.scanning.scanner.run_scan_as_of()` dispatches the enabled strategies registered in `src.strategies.registry`: `RallyPattern_Position`, `RelativeStrength_Ranker_Position`, and `Streak_Position`.

The walk-forward engine in `src.backtesting.engine` uses the same scan and validation path. Open equity positions are persisted through `PositionTracker`; Streak output remains a manual next-session option alert. Historical OHLCV access is provided by `src.data.market`, with optional GCS synchronization.
