# Supported strategy details

## RallyPattern_Position
Cross-sectional daily leader scan driven by the required `config/rally_pattern_config.json` configuration. It persists Rally setup metadata so a failed breakout is not immediately retried without a materially fresh trigger.

## RelativeStrength_Ranker_Position
Selects liquid technology and communication leaders with six-month relative strength, a stacked moving-average trend, sufficient trend strength, and a three-month-high or pullback-breakout trigger. It uses an ATR stop, RS partial-profit management, and trailing exits.

## Streak_Position
Ranks the fixed liquid mega-cap universe using one year of walk-forward-safe historical features. It emits one next-session option alert; it is not included in live equity position tracking and exits at the next session close in backtests and monitoring.
