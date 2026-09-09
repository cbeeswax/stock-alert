# API overview

## Scanner
`src.scanning.scanner.run_scan_as_of(as_of_date, tickers, rs_bought_tracker=None)` returns signals only from enabled supported registry strategies.

## Validator
`src.scanning.validator.pre_buy_check(signals, as_of_date=None, strategy_trackers=None)` deduplicates signals, applies liquidity and trade-shape validation, and returns normalized trade records.

## Backtesting
`src.backtesting.engine.WalkForwardBacktester` uses the shared scan/validate pipeline for Rally Pattern, Relative Strength Ranker, and Streak simulations.

## Position monitoring
`src.position_management.monitor.monitor_positions(position_tracker)` produces stop, time-stop, strategy-exit, partial, and pyramid actions for open positions.
