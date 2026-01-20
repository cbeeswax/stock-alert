"""
Trading Strategy Configuration
================================
Centralized configuration for BOTH live trading and backtesting.
Modify these values to tune your strategy - changes apply everywhere.
"""

# =============================================================================
# POSITION SIZING & RISK MANAGEMENT
# =============================================================================

CAPITAL_PER_TRADE = 10_000  # Capital allocated per trade in USD
RISK_REWARD_RATIO = 2       # Target profit is X times the risk (OPTION 3: Easier target)
                            # 2 = 2:1 (conservative)
                            # 3 = 3:1 (balanced)
                            # 4 = 4:1 (aggressive)

MAX_HOLDING_DAYS = 45       # Maximum days to hold a trade


# =============================================================================
# TRADE SELECTION
# =============================================================================

MAX_TRADES_PER_SCAN = 3     # Maximum trades to take per scan
                            # Live mode: top 3 trades in email
                            # Backtest: top 3 trades per simulation date
                            # 1 = most selective
                            # 3 = balanced
                            # 5-10 = more opportunities


# =============================================================================
# TECHNICAL FILTER PARAMETERS
# =============================================================================

# Trend strength (ADX)
ADX_THRESHOLD = 24          # Minimum ADX for valid trend (OPTION 3: Stricter)
                            # 20 = weak trend OK
                            # 22 = medium trend (balanced)
                            # 24 = good trend (Option 3)
                            # 25 = strong trend required
                            # 30 = very strong trend

# Momentum (RSI)
RSI_MIN = 50                # Minimum RSI value (OPTION 3: Tighter range)
RSI_MAX = 66                # Maximum RSI value (OPTION 3: Tighter range)
                            # Tight: 50-65 (selective)
                            # Medium: 48-68 (balanced)
                            # Option 3: 50-66 (balanced quality)
                            # Wide: 45-70 (more trades)

# Volume confirmation
VOLUME_MULTIPLIER = 1.4     # Current volume vs 20-day average (OPTION 3: Moderate)
                            # 1.0 = no filter
                            # 1.3 = 30% above average (relaxed)
                            # 1.4 = 40% above average (Option 3)
                            # 1.5 = 50% above average (moderate)
                            # 2.0 = 100% above average (strict)

# Liquidity requirement
MIN_LIQUIDITY_USD = 30_000_000  # Minimum 20-day avg dollar volume
                                # $20M = smaller stocks OK
                                # $30M = balanced (current)
                                # $50M = large cap only
                                # $100M = mega cap only

# Price action (distance from EMA20)
PRICE_ABOVE_EMA20_MIN = 0.01    # Min 1% above EMA20
PRICE_ABOVE_EMA20_MAX = 0.05    # Max 5% above EMA20
                                # Prevents buying at resistance


# =============================================================================
# BACKTEST-SPECIFIC SETTINGS
# =============================================================================

BACKTEST_START_DATE = "2022-01-01"  # Historical backtest start date
SCAN_FREQUENCY = "W-MON"            # Backtest scan frequency
                                    # "B" = daily
                                    # "W-MON" = weekly Monday
                                    # "W-FRI" = weekly Friday


# =============================================================================
# NOTES & GUIDELINES
# =============================================================================

"""
TUNING FOR HIGHER WIN RATE (fewer trades):
-------------------------------------------
✓ Increase ADX_THRESHOLD to 25+
✓ Tighten RSI to 50-65
✓ Increase VOLUME_MULTIPLIER to 1.5+
✓ Increase MIN_LIQUIDITY_USD to $50M+
✓ Reduce MAX_TRADES_PER_SCAN to 1-2
✓ Use RISK_REWARD_RATIO of 2:1

Expected: 40-45% win rate, lower total profit


TUNING FOR HIGHER PROFIT (more trades):
----------------------------------------
✓ Decrease ADX_THRESHOLD to 20
✓ Widen RSI to 45-70
✓ Decrease VOLUME_MULTIPLIER to 1.2
✓ Decrease MIN_LIQUIDITY_USD to $20M
✓ Increase MAX_TRADES_PER_SCAN to 5-10
✓ Use RISK_REWARD_RATIO of 3:1

Expected: 30-35% win rate, higher total profit


CURRENT SETTINGS (Balanced):
-----------------------------
ADX: 22, RSI: 48-68, Volume: 1.3x, Liquidity: $30M
Max Trades: 3, R/R: 3:1
Expected: ~35-40% win rate, balanced profit


RISK/REWARD IMPACT:
-------------------
2:1 → Higher win rate (~40%), smaller wins, steady growth
3:1 → Medium win rate (~30%), bigger wins, good balance
4:1 → Lower win rate (~25%), large wins, high volatility
"""
