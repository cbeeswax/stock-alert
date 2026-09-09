# Position management

Use `python main.py --label "Evening Scan"` for the live pipeline and `python scripts/manage_positions.py` for manual position maintenance. Supported strategy names are `RallyPattern_Position`, `RelativeStrength_Ranker_Position`, and `Streak_Position`.

Streak is a next-session option alert and is not added to the live equity position tracker. Equity positions are monitored for stop losses, strategy-specific exits, and time stops.
