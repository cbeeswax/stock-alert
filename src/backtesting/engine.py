"""
Long-Term Position Trading Backtester - Engine
===============================================
Walk-forward backtester for 8 position strategies (60-120 day holds).
Features: Strategy-specific exits, pyramiding, per-strategy position limits.
"""
import logging
import pandas as pd
from src.scanning.scanner import run_scan_as_of
from src.scanning.validator import pre_buy_check
from src.scanning.rs_bought_tracker import RSBoughtTracker
from src.data.market import get_historical_data
from src.position_management.tracker import PositionTracker, filter_trades_by_position
from src.data.indicators import compute_rsi, compute_bollinger_bands, compute_percent_b
from src.analysis.regime import get_regime_config
from src.analysis.market_regime import get_position_regime, PositionRegime, get_regime_params
from src.config.settings import (
    # Position trading settings
    POSITION_RISK_PER_TRADE_PCT,
    POSITION_MAX_PER_STRATEGY,
    POSITION_MAX_TOTAL,
    POSITION_PARTIAL_ENABLED,
    POSITION_PARTIAL_SIZE,
    POSITION_PARTIAL_R_TRIGGER_LOW,
    POSITION_PARTIAL_R_TRIGGER_MID,
    POSITION_PARTIAL_R_TRIGGER_HIGH,
    POSITION_MAX_DAYS_SHORT,
    POSITION_MAX_DAYS_LONG,
    SHORT_RISK_PER_TRADE_PCT,

    # Pyramiding
    POSITION_PYRAMID_ENABLED,
    POSITION_PYRAMID_R_TRIGGER,
    POSITION_PYRAMID_SIZE,
    POSITION_PYRAMID_MAX_ADDS,
    POSITION_PYRAMID_PULLBACK_EMA,
    POSITION_PYRAMID_PULLBACK_ATR,

    # Strategy-specific configs
    EMA_CROSS_POS_PARTIAL_R,
    EMA_CROSS_POS_PARTIAL_SIZE,
    EMA_CROSS_POS_TRAIL_MA,
    EMA_CROSS_POS_TRAIL_DAYS,

    MR_POS_PARTIAL_R,
    MR_POS_TRAIL_MA,
    MR_POS_TRAIL_DAYS,

    PERCENT_B_POS_PARTIAL_R,
    PERCENT_B_POS_TRAIL_MA,
    PERCENT_B_POS_TRAIL_DAYS,

    HIGH52_POS_PARTIAL_R,
    HIGH52_POS_PARTIAL_SIZE,
    HIGH52_POS_TRAIL_MA,
    HIGH52_POS_TRAIL_DAYS,

    BIGBASE_PARTIAL_R,
    BIGBASE_PARTIAL_SIZE,
    BIGBASE_TRAIL_MA,
    BIGBASE_TRAIL_DAYS,

    TREND_CONT_PARTIAL_R,
    TREND_CONT_PARTIAL_SIZE,
    TREND_CONT_TRAIL_MA,
    TREND_CONT_TRAIL_DAYS,

    RS_RANKER_PARTIAL_R,
    RS_RANKER_PARTIAL_SIZE,
    RS_RANKER_TRAIL_MA,
    RS_RANKER_TRAIL_DAYS,

    # Short strategies (regime-based)
    SHORT_ENABLED,
    SHORT_CFG_BULL,
    SHORT_CFG_SIDEWAYS,
    SHORT_CFG_BEAR,
    LEADER_SHORT_CFG_BULL,
    MEGACAP_WEEKLY_SLIDE_CFG,

    # Backtest settings
    BACKTEST_START_DATE,
    BACKTEST_SCAN_FREQUENCY,

    # Legacy (for compatibility)
    CAPITAL_PER_TRADE,
)


class WalkForwardBacktester:
    """
    Position trading backtester with pyramiding and per-strategy limits.
    """

    def __init__(self, tickers, start_date=None, scan_frequency=None, initial_capital=100000):
        """
        Args:
            tickers: List of ticker symbols
            start_date: Backtest start date (default from config)
            scan_frequency: Scan frequency (default from config: W-MON)
            initial_capital: Starting capital for risk calculation
        """
        self.log = logging.getLogger("backtest_gap_reversal")
        self.tickers = tickers
        self.start_date = pd.to_datetime(start_date or BACKTEST_START_DATE)
        self.scan_frequency = scan_frequency or BACKTEST_SCAN_FREQUENCY
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # Position tracker
        self.position_tracker = PositionTracker(mode="backtest")
        
        # RS Ranker bought tracker - Backtest uses separate file to avoid mixing with production
        backtest_tracker_file = "data/backtest/rs_ranker_bought.json"
        self._delete_backtest_tracker_files(backtest_tracker_file)
        self.rs_bought_tracker = RSBoughtTracker(file_path=backtest_tracker_file, load_from_file=False)  # Start fresh

        # Per-strategy position counters
        self.strategy_positions = {}

        # Open positions for day-by-day simulation
        self.open_positions = []  # List of position dicts

        # All completed trades
        self.completed_trades = []

        # Cooldown tracker for strategies that need symbol-level cooldowns
        # Structure: {strategy: {ticker: exit_date}}
        self.cooldown_tracker = {}
        
        # Current market regime (RiskOn/Neutral/RiskOff)
        self.current_position_regime = PositionRegime.NEUTRAL  # Default to neutral
        self.regime_params = get_regime_params(PositionRegime.NEUTRAL)

    def _delete_backtest_tracker_files(self, tracker_file):
        """Delete backtest tracker files at start for clean slate.
        
        Args:
            tracker_file: Path to tracker file to delete
        """
        import os
        try:
            if os.path.exists(tracker_file):
                os.remove(tracker_file)
                print(f"✓ Deleted stale backtest tracker: {tracker_file}")
        except Exception as e:
            print(f"⚠️  Could not delete tracker file {tracker_file}: {e}")

    def _update_market_regime(self, as_of_date):
        """
        Update market regime based on QQQ price and moving averages.
        
        Args:
            as_of_date: Date to classify regime for
        """
        try:
            self.current_position_regime = get_position_regime(as_of_date=as_of_date, index_symbol="QQQ")
            self.regime_params = get_regime_params(self.current_position_regime)
        except Exception as e:
            # If regime detection fails, stay with previous regime
            print(f"⚠️  Failed to update regime on {as_of_date}: {e}")

    def _calculate_atr(self, df, period=14):
        """Calculate ATR"""
        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)

        return tr.rolling(period).mean()

    def _calculate_position_size(self, entry_price, stop_price, risk_pct=None):
        """
        Calculate position size based on risk percentage.

        Args:
            entry_price: Entry price
            stop_price: Stop loss price
            risk_pct: Risk as % of capital (default 1.5%)

        Returns:
            Number of shares
        """
        if risk_pct is None:
            risk_pct = POSITION_RISK_PER_TRADE_PCT

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            return 0

        # Enforce a minimum stop distance (1% of entry) to prevent position-size explosions
        # when the gap fill level is very close to the entry price (e.g. tiny 0.1% gap).
        min_risk_per_share = entry_price * 0.01
        if risk_per_share < min_risk_per_share:
            risk_per_share = min_risk_per_share

        # Use FIXED initial capital for position sizing (prevents exponential growth)
        risk_dollars = self.initial_capital * (risk_pct / 100)
        shares = int(risk_dollars / risk_per_share)

        return max(shares, 1)  # At least 1 share

    def _enter_position(self, entry_day, trade):
        """
        Enter a new position and add to open positions list.
        Returns True if position entered successfully.
        """
        ticker = trade["Ticker"]
        strategy = trade["Strategy"]
        entry_price = trade["Entry"]
        stop_price = trade["StopLoss"]
        direction = trade.get("Direction", "LONG")
        max_days = trade.get("MaxDays", POSITION_MAX_DAYS_LONG)
        regime = trade.get("Regime", None)  # Track regime for SHORT positions

        # Position sizing (use strategy-specific or regime-based risk %)
        risk_pct = None  # Default: use POSITION_RISK_PER_TRADE_PCT (2.0%)

        # RS_Ranker uses regime-based risk
        if strategy == "RelativeStrength_Ranker_Position":
            risk_pct = self.regime_params.get('risk_per_trade_pct', POSITION_RISK_PER_TRADE_PCT)
        
        # Weak-RS shorts use 1.5% risk
        elif strategy == "ShortWeakRS_Retrace_Position":
            risk_pct = SHORT_RISK_PER_TRADE_PCT  # 1.5%

        # Leader Pullback Shorts use smaller size (0.5% risk)
        elif strategy == "LeaderPullback_Short_Position":
            risk_pct = LEADER_SHORT_CFG_BULL["RISK_PER_TRADE_PCT"]  # 0.5%

        shares = self._calculate_position_size(entry_price, stop_price, risk_pct=risk_pct)
        if shares == 0:
            return False

        risk_amount = abs(entry_price - stop_price)

        # Create position state
        position = {
            'ticker': ticker,
            'strategy': strategy,
            'direction': direction,
            'entry_date': entry_day,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'initial_shares': shares,
            'current_shares': shares,
            'risk_amount': risk_amount,
            'max_days': max_days,
            'days_held': 0,
            'highest_price': entry_price,
            'partial_exited': False,
            'partial_result': None,
            'pyramid_adds': [],
            'closes_below_trail': 0,
            'regime': regime,  # Track market regime for regime-based strategies
            'rs_partial_stage': 0,  # Track dual-stage partial exit progress for RS_Ranker
        }

        self.open_positions.append(position)
        return True

    def _check_open_positions(self, current_date):
        """
        Check all open positions for exits on current date.
        Returns list of closed positions (includes partials and full exits).
        """
        closed_positions = []
        remaining_positions = []

        for position in self.open_positions:
            # Increment days held
            position['days_held'] += 1

            # Get current market data
            df = get_historical_data(position['ticker'])
            if df.empty:
                remaining_positions.append(position)
                continue

            # Normalize index timezone to match backtest dates (prevents ghost positions
            # where current_date is never found due to tz-aware vs tz-naive mismatch)
            if hasattr(df.index, 'tz') and df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            # Get today's bar
            if current_date not in df.index:
                # Still enforce MaxDays even when today's bar is missing
                if position['strategy'] == "GapReversal_Position" and position['days_held'] >= position['max_days']:
                    last_price = float(df['Close'].iloc[-1])
                    entry = position['entry_price']
                    risk = max(position['risk_amount'], 0.01)
                    r = (entry - last_price) / risk if position['direction'] == "SHORT" else (last_price - entry) / risk
                    closed_positions.append(
                        self._close_position(position, current_date, last_price, f"TimeStop_{position['max_days']}d", r)
                    )
                else:
                    remaining_positions.append(position)
                continue

            today_data = df.loc[current_date]
            current_close = today_data['Close']
            current_high = today_data['High']
            current_low = today_data['Low']

            # Update highest price
            if current_high > position['highest_price']:
                position['highest_price'] = current_high

            # Calculate current R-multiple
            current_r = (current_close - position['entry_price']) / max(position['risk_amount'], 0.01)
            if position['direction'] == "SHORT":
                current_r = (position['entry_price'] - current_close) / max(position['risk_amount'], 0.01)

            # =================================================================
            # PYRAMIDING LOGIC (add to winners on pullback)
            # =================================================================
            if (POSITION_PYRAMID_ENABLED and
                current_r >= POSITION_PYRAMID_R_TRIGGER and
                len(position['pyramid_adds']) < POSITION_PYRAMID_MAX_ADDS and
                not position['partial_exited']):

                # Calculate indicators for pyramiding
                recent_df = df[df.index <= current_date].tail(50).copy()
                if len(recent_df) >= POSITION_PYRAMID_PULLBACK_EMA:
                    recent_df["EMA21"] = recent_df["Close"].ewm(span=POSITION_PYRAMID_PULLBACK_EMA).mean()
                    recent_df["ATR"] = self._calculate_atr(recent_df, 14)

                    ema21 = recent_df["EMA21"].iloc[-1]
                    atr = recent_df["ATR"].iloc[-1] if not pd.isna(recent_df["ATR"].iloc[-1]) else (position['entry_price'] * 0.02)

                    # Check if price is near EMA21 (within 1 ATR)
                    pullback_distance = abs(current_close - ema21)
                    is_near_ema21 = pullback_distance <= (POSITION_PYRAMID_PULLBACK_ATR * atr)

                    if is_near_ema21:
                        # Add to position
                        add_shares = int(position['initial_shares'] * POSITION_PYRAMID_SIZE)
                        position['pyramid_adds'].append({
                            'date': current_date,
                            'price': current_close,
                            'shares': add_shares,
                            'r_at_add': current_r
                        })
                        position['current_shares'] += add_shares

                        # Record pyramid add to RS Ranker tracker (if applicable)
                        if position['strategy'] == "RelativeStrength_Ranker_Position":
                            self.rs_bought_tracker.add_pyramid(
                                ticker=position['ticker'],
                                date=current_date.strftime('%Y-%m-%d'),
                                price=current_close,
                                size_pct=POSITION_PYRAMID_SIZE
                            )

                        # Display pyramid add
                        print(f"   ➕ {current_date.date()} | PYRAMID {position['ticker']} @ ${current_close:.2f} (+{int(POSITION_PYRAMID_SIZE*100)}%) at {current_r:+.2f}R")

            # =================================================================
            # PARTIAL EXIT LOGIC (take profits at strategy-specific R targets)
            # =================================================================
            if POSITION_PARTIAL_ENABLED and not position['partial_exited']:
                should_partial = False
                partial_trigger = ""
                partial_size = POSITION_PARTIAL_SIZE
                strategy = position['strategy']

                # Check strategy-specific partial exit triggers
                if strategy == "EMA_Crossover_Position":
                    if current_r >= EMA_CROSS_POS_PARTIAL_R:
                        should_partial = True
                        partial_trigger = f"{EMA_CROSS_POS_PARTIAL_R}R"
                        partial_size = EMA_CROSS_POS_PARTIAL_SIZE

                elif strategy == "MeanReversion_Position":
                    if current_r >= MR_POS_PARTIAL_R:
                        should_partial = True
                        partial_trigger = f"{MR_POS_PARTIAL_R}R"

                elif strategy == "%B_MeanReversion_Position":
                    if current_r >= PERCENT_B_POS_PARTIAL_R:
                        should_partial = True
                        partial_trigger = f"{PERCENT_B_POS_PARTIAL_R}R"

                elif strategy in ["High52_Position", "BigBase_Breakout_Position"]:
                    target_r = HIGH52_POS_PARTIAL_R if strategy == "High52_Position" else BIGBASE_PARTIAL_R
                    if current_r >= target_r:
                        should_partial = True
                        partial_trigger = f"{target_r}R"
                        partial_size = HIGH52_POS_PARTIAL_SIZE if strategy == "High52_Position" else BIGBASE_PARTIAL_SIZE

                elif strategy == "TrendContinuation_Position":
                    if current_r >= TREND_CONT_PARTIAL_R:
                        should_partial = True
                        partial_trigger = f"{TREND_CONT_PARTIAL_R}R"
                        partial_size = TREND_CONT_PARTIAL_SIZE

                elif strategy == "RelativeStrength_Ranker_Position":
                    # DUAL-STAGE PARTIALS: Exit 40% @ 2.5R, then 30% @ 4.0R
                    if not position.get('partial_exited'):
                        # First partial: Exit 40% @ 2.5R
                        if current_r >= 2.5:
                            should_partial = True
                            partial_trigger = "2.5R_Stage1"
                            partial_size = 0.40  # Exit 40%
                            position['rs_partial_stage'] = 1
                    elif position.get('rs_partial_stage') == 1:
                        # Second partial: Exit 30% @ 4.0R (from remaining 60%)
                        if current_r >= 4.0:
                            should_partial = True
                            partial_trigger = "4.0R_Stage2"
                            partial_size = 0.30 / 0.60  # 30% of original = 50% of remaining
                            position['rs_partial_stage'] = 2

                elif strategy == "ShortWeakRS_Retrace_Position":
                    # Use regime-specific config for partial exits
                    regime = position.get('regime', 'sideways')
                    cfg = get_regime_config(regime)
                    if current_r >= cfg["PARTIAL_R"]:
                        should_partial = True
                        partial_trigger = f"{cfg['PARTIAL_R']}R"
                        partial_size = cfg["PARTIAL_SIZE"]

                elif strategy == "LeaderPullback_Short_Position":
                    # Use leader short config for partial exits
                    cfg = LEADER_SHORT_CFG_BULL
                    if current_r >= cfg["PARTIAL_R"]:
                        should_partial = True
                        partial_trigger = f"{cfg['PARTIAL_R']}R"
                        partial_size = cfg["PARTIAL_SIZE"]

                elif strategy == "MegaCap_WeeklySlide_Short":
                    # Use signal-specific partial exit parameters
                    partial_r = position.get('PartialR', 2.0)
                    if current_r >= partial_r:
                        should_partial = True
                        partial_trigger = f"{partial_r}R"
                        partial_size = position.get('PartialSize', 0.5)

                if should_partial:
                    position['partial_exited'] = True
                    partial_shares = int(position['current_shares'] * partial_size)

                    # Calculate partial exit P&L - CORRECTED for pyramiding
                    # Partial exits are always taken from most recent shares (LIFO)
                    # This is conservative and simpler to implement
                    if position['direction'] == "LONG":
                        # Calculate weighted average entry price for partial exit shares
                        total_shares = position['current_shares']
                        cost_basis = position['initial_shares'] * position['entry_price']

                        # Add cost basis from pyramid adds
                        for add in position['pyramid_adds']:
                            cost_basis += add['shares'] * add['price']

                        avg_entry_price = cost_basis / total_shares
                        partial_pnl = partial_shares * (current_close - avg_entry_price)
                    else:
                        # Calculate weighted average entry price for partial exit shares
                        total_shares = position['current_shares']
                        cost_basis = position['initial_shares'] * position['entry_price']

                        # Add cost basis from pyramid adds
                        for add in position['pyramid_adds']:
                            cost_basis += add['shares'] * add['price']

                        avg_entry_price = cost_basis / total_shares
                        partial_pnl = partial_shares * (avg_entry_price - current_close)

                    # Create partial exit record
                    partial_result = {
                        "Date": position['entry_date'],
                        "ExitDate": current_date,
                        "Year": position['entry_date'].year,
                        "Ticker": position['ticker'],
                        "Strategy": strategy,
                        "Direction": position['direction'],
                        "PositionType": "Partial",
                        "Entry": round(position['entry_price'], 2),
                        "Exit": round(current_close, 2),
                        "Outcome": "Win",
                        "ExitReason": f"Partial_{partial_trigger}",
                        "RMultiple": round(current_r, 2),
                        "Shares": partial_shares,
                        "PnL_$": round(partial_pnl, 2),
                        "HoldingDays": position['days_held'],
                        "PyramidAdds": 0,
                    }

                    # Store partial result in position for later
                    position['partial_result'] = partial_result
                    closed_positions.append(partial_result)

                    # Display partial exit
                    pnl_display = f"${partial_pnl:+,.2f}"
                    print(f"   💵 {current_date.date()} | PARTIAL {position['ticker']} {current_r:+.2f}R ({pnl_display}) {int(partial_size*100)}% | {partial_trigger}")

                    # Update position
                    position['current_shares'] -= partial_shares

                    # Move stop to breakeven (if enabled for this position)
                    breakeven_enabled = position.get('BreakevenAfterPartial', True)  # Default True for backwards compatibility
                    if breakeven_enabled:
                        position['stop_price'] = position['entry_price']  # Move stop to breakeven

            # =================================================================
            # CHECK FOR FULL EXIT
            # =================================================================
            exit_result = self._evaluate_exit_conditions(position, current_date, today_data, current_close, current_r, df)

            if exit_result:
                # If we had a partial exit, mark runner as "Runner", else "Full"
                if position['partial_exited']:
                    exit_result['PositionType'] = "Runner"
                closed_positions.append(exit_result)
            else:
                remaining_positions.append(position)

        # Update open positions list
        self.open_positions = remaining_positions
        return closed_positions

    def _evaluate_exit_conditions(self, position, current_date, today_data, current_close, current_r, full_df):
        """
        Evaluate if position should exit based on strategy-specific conditions.
        Returns trade result dict if exiting, None if holding.
        """
        ticker = position['ticker']
        strategy = position['strategy']
        direction = position['direction']
        entry = position['entry_price']
        stop = position['stop_price']
        days_held = position['days_held']
        max_days = position['max_days']

        # Check stop loss first — guard against NaN in OHLC data (prevents stop from silently not firing)
        low_price = today_data.get('Low', float('nan')) if hasattr(today_data, 'get') else today_data['Low']
        high_price = today_data.get('High', float('nan')) if hasattr(today_data, 'get') else today_data['High']
        import math
        if direction == "LONG" and not math.isnan(float(low_price)) and float(low_price) <= stop:
            return self._close_position(position, current_date, stop, "StopLoss", -1.0)
        elif direction == "SHORT" and not math.isnan(float(high_price)) and float(high_price) >= stop:
            return self._close_position(position, current_date, stop, "StopLoss", -1.0)

        # Calculate indicators (need historical context)
        recent_df = full_df[full_df.index <= current_date].tail(250).copy()
        if len(recent_df) < 50:
            return None  # Not enough data

        recent_df["EMA21"] = recent_df["Close"].ewm(span=21).mean()
        recent_df["EMA50"] = recent_df["Close"].ewm(span=50).mean()
        recent_df["MA50"] = recent_df["Close"].rolling(50).mean()
        recent_df["MA100"] = recent_df["Close"].rolling(100).mean()
        recent_df["MA200"] = recent_df["Close"].rolling(200).mean()
        recent_df["RSI14"] = compute_rsi(recent_df["Close"], 14)

        # Get current indicator values
        ema21 = recent_df["EMA21"].iloc[-1] if len(recent_df) >= 21 else None
        ema50 = recent_df["EMA50"].iloc[-1] if len(recent_df) >= 50 else None
        ma50 = recent_df["MA50"].iloc[-1] if len(recent_df) >= 50 else None
        ma100 = recent_df["MA100"].iloc[-1] if len(recent_df) >= 100 else None
        ma200 = recent_df["MA200"].iloc[-1] if len(recent_df) >= 200 else None
        rsi14 = recent_df["RSI14"].iloc[-1]

        # Strategy-specific exits
        if strategy == "EMA_Crossover_Position":
            if ma100 and pd.notna(ma100):
                if current_close < ma100:
                    position['closes_below_trail'] += 1
                    if position['closes_below_trail'] >= EMA_CROSS_POS_TRAIL_DAYS:
                        return self._close_position(position, current_date, current_close, "MA100_Trail", current_r)
                else:
                    position['closes_below_trail'] = 0

        elif strategy == "MeanReversion_Position":
            if ma50 and pd.notna(ma50):
                if current_close < ma50:
                    position['closes_below_trail'] += 1
                    if position['closes_below_trail'] >= MR_POS_TRAIL_DAYS:
                        return self._close_position(position, current_date, current_close, "MA50_Trail", current_r)
                else:
                    position['closes_below_trail'] = 0

        elif strategy == "%B_MeanReversion_Position":
            if ma50 and pd.notna(ma50):
                if current_close < ma50:
                    position['closes_below_trail'] += 1
                    if position['closes_below_trail'] >= PERCENT_B_POS_TRAIL_DAYS:
                        return self._close_position(position, current_date, current_close, "MA50_Trail", current_r)
                else:
                    position['closes_below_trail'] = 0

        elif strategy == "High52_Position":
            # High52: HYBRID TRAIL - EMA21 early (protect), MA100 late (let run)
            if days_held <= 60:
                # First 60 days: Tight EMA21 trail (cut losers fast)
                if ema21 and pd.notna(ema21):
                    if current_close < ema21:
                        position['closes_below_trail'] += 1
                        if position['closes_below_trail'] >= 5:
                            return self._close_position(position, current_date, current_close, "EMA21_Trail_Early", current_r)
                    else:
                        position['closes_below_trail'] = 0
            else:
                # After 60 days: Loose MA100 trail (let winners run to time stop)
                if ma100 and pd.notna(ma100):
                    if current_close < ma100:
                        position['closes_below_trail'] += 1
                        if position['closes_below_trail'] >= 8:
                            return self._close_position(position, current_date, current_close, "MA100_Trail_Late", current_r)
                    else:
                        position['closes_below_trail'] = 0

        elif strategy == "BigBase_Breakout_Position":
            # BigBase: HYBRID TRAIL - EMA21 early (cut failed breakouts), MA200 late (home runs)
            if days_held <= 45:
                # First 45 days: Tight EMA21 trail (cut failed breakouts fast)
                if ema21 and pd.notna(ema21):
                    if current_close < ema21:
                        position['closes_below_trail'] += 1
                        if position['closes_below_trail'] >= 5:
                            return self._close_position(position, current_date, current_close, "EMA21_Trail_Early", current_r)
                    else:
                        position['closes_below_trail'] = 0
            else:
                # After 45 days: Loose MA200 trail (let home runs develop)
                if ma200 and pd.notna(ma200):
                    if current_close < ma200:
                        position['closes_below_trail'] += 1
                        if position['closes_below_trail'] >= 10:
                            return self._close_position(position, current_date, current_close, "MA200_Trail_Late", current_r)
                    else:
                        position['closes_below_trail'] = 0

        elif strategy == "TrendContinuation_Position":
            if ma50 and pd.notna(ma50):
                if current_close < ma50:
                    position['closes_below_trail'] += 1
                    if position['closes_below_trail'] >= TREND_CONT_TRAIL_DAYS:
                        return self._close_position(position, current_date, current_close, "MA50_Trail", current_r)
                else:
                    position['closes_below_trail'] = 0

        elif strategy == "RelativeStrength_Ranker_Position":
            # RS_Ranker: HYBRID TRAIL - EMA21 early (protect), MA100 late (let run)
            # PROFIT-GATED: Skip EMA21 trail until +0.75R profit reached
            profit_gate_threshold = 0.75  # Don't use EMA21 until +0.75R
            
            if days_held <= 60:
                # First 60 days: Tight EMA21 trail (cut losers fast) - BUT ONLY AFTER +0.75R
                if ema21 and pd.notna(ema21):
                    # Check if we should apply EMA21 exit
                    if current_r >= profit_gate_threshold:
                        # Profit-gated: Use EMA21 trail
                        if current_close < ema21:
                            position['closes_below_trail'] += 1
                            if position['closes_below_trail'] >= 5:
                                return self._close_position(position, current_date, current_close, "EMA21_Trail_Early", current_r)
                        else:
                            position['closes_below_trail'] = 0
                    else:
                        # Before +0.75R: Ignore EMA21, only stop loss applies
                        position['closes_below_trail'] = 0
            else:
                # After 60 days: Loose MA100 trail (let winners run to time stop)
                if ma100 and pd.notna(ma100):
                    if current_close < ma100:
                        position['closes_below_trail'] += 1
                        if position['closes_below_trail'] >= 8:
                            return self._close_position(position, current_date, current_close, "MA100_Trail_Late", current_r)
                    else:
                        position['closes_below_trail'] = 0

        # All sector-based ranker strategies use same exit logic as RS_Ranker
        elif strategy in ["Industrials_Ranker_Position", "Healthcare_Ranker_Position", 
                          "Energy_Ranker_Position", "Materials_Ranker_Position", "ConsumerDisc_Ranker_Position"]:
            # SECTOR RANKERS: HYBRID TRAIL - EMA21 early (protect), MA100 late (let run)
            # PROFIT-GATED: Skip EMA21 trail until +0.75R profit reached
            profit_gate_threshold = 0.75
            
            if days_held <= 60:
                # First 60 days: Tight EMA21 trail (cut losers fast) - BUT ONLY AFTER +0.75R
                if ema21 and pd.notna(ema21):
                    if current_r >= profit_gate_threshold:
                        # Profit-gated: Use EMA21 trail
                        if current_close < ema21:
                            position['closes_below_trail'] += 1
                            if position['closes_below_trail'] >= 5:
                                return self._close_position(position, current_date, current_close, "EMA21_Trail_Early", current_r)
                        else:
                            position['closes_below_trail'] = 0
                    else:
                        # Before +0.75R: Ignore EMA21, only stop loss applies
                        position['closes_below_trail'] = 0
            else:
                # After 60 days: Loose MA100 trail (let winners run to time stop)
                if ma100 and pd.notna(ma100):
                    if current_close < ma100:
                        position['closes_below_trail'] += 1
                        if position['closes_below_trail'] >= 8:
                            return self._close_position(position, current_date, current_close, "MA100_Trail_Late", current_r)
                    else:
                        position['closes_below_trail'] = 0

        elif strategy == "ShortWeakRS_Retrace_Position":
            # REGIME-BASED: SHORT strategy with regime-specific exit parameters
            # For shorts, we exit if price closes ABOVE trail (opposite of longs)
            regime = position.get('regime', 'sideways')
            cfg = get_regime_config(regime)

            # Trailing stop (regime-specific)
            trail_ema = cfg.get("TRAIL_EMA")
            trail_days = cfg.get("TRAIL_DAYS")
            trail_only_after_partial = cfg.get("TRAIL_ONLY_AFTER_PARTIAL", True)

            if trail_ema is not None and trail_days is not None:
                # Only trail if partial was taken (protect winners only)
                should_trail = True
                if trail_only_after_partial:
                    should_trail = position.get('partial_exited', False)

                if should_trail:
                    # Use regime-specific EMA for trailing
                    ema_trail = recent_df['Close'].ewm(span=trail_ema, adjust=False).mean().iloc[-1] if len(recent_df) >= trail_ema else None

                    if ema_trail and pd.notna(ema_trail):
                        if current_close > ema_trail:  # Price rising above trail = exit short
                            position['closes_below_trail'] += 1
                            if position['closes_below_trail'] >= trail_days:
                                return self._close_position(position, current_date, current_close, f"EMA{trail_ema}_Trail_Short", current_r)
                        else:
                            position['closes_below_trail'] = 0

            # Early time stop (regime-specific)
            early_exit_days = cfg.get("EARLY_EXIT_DAYS")
            early_exit_r_threshold = cfg.get("EARLY_EXIT_R_THRESHOLD")

            if early_exit_days is not None and early_exit_r_threshold is not None:
                if days_held >= early_exit_days:
                    if current_r < early_exit_r_threshold:
                        return self._close_position(position, current_date, current_close, f"TimeStop_Early_{early_exit_days}d", current_r)

        elif strategy == "LeaderPullback_Short_Position":
            # LEADER PULLBACK SHORT: Fast tactical exits
            # For shorts, we exit if price closes ABOVE trail (opposite of longs)
            cfg = LEADER_SHORT_CFG_BULL

            # Trailing stop (leader-specific)
            trail_ema = cfg.get("TRAIL_EMA")
            trail_days = cfg.get("TRAIL_DAYS")
            trail_only_after_partial = cfg.get("TRAIL_ONLY_AFTER_PARTIAL", True)

            if trail_ema is not None and trail_days is not None:
                # Only trail if partial was taken (protect winners only)
                should_trail = True
                if trail_only_after_partial:
                    should_trail = position.get('partial_exited', False)

                if should_trail:
                    # Use leader-specific EMA for trailing
                    ema_trail = recent_df['Close'].ewm(span=trail_ema, adjust=False).mean().iloc[-1] if len(recent_df) >= trail_ema else None

                    if ema_trail and pd.notna(ema_trail):
                        if current_close > ema_trail:  # Price rising above trail = exit short
                            position['closes_below_trail'] += 1
                            if position['closes_below_trail'] >= trail_days:
                                return self._close_position(position, current_date, current_close, f"EMA{trail_ema}_Trail_Leader", current_r)
                        else:
                            position['closes_below_trail'] = 0

            # Early time stop (leader-specific - faster than trend shorts)
            # Only exit if R <= 0 AND price hasn't moved much (avoiding premature exit on working trades)
            early_exit_days = cfg.get("EARLY_EXIT_DAYS")
            early_exit_r_threshold = cfg.get("EARLY_EXIT_R_THRESHOLD")

            if early_exit_days is not None and early_exit_r_threshold is not None:
                if days_held >= early_exit_days:
                    # For SHORT: exit if R <= 0 AND close hasn't dropped much (close >= entry * 0.99)
                    # This avoids cutting trades that are working but haven't reached 0R yet due to wide stops
                    if direction == "SHORT":
                        if current_r <= early_exit_r_threshold and current_close >= position['entry_price'] * 0.99:
                            return self._close_position(position, current_date, current_close, f"TimeStop_Early_{early_exit_days}d_Leader", current_r)
                    else:
                        # For LONG: keep original logic
                        if current_r < early_exit_r_threshold:
                            return self._close_position(position, current_date, current_close, f"TimeStop_Early_{early_exit_days}d_Leader", current_r)

        elif strategy == "GapReversal_Position":
            # GAP REVERSAL: Gap-fill stop + EMA21 trailing exit
            gap_fill_lvl = position.get('stop_price')  # stored as stop_price at entry
            current_low = today_data.get('Low', current_close)
            ticker = position.get('ticker', '?')

            # 1. Gap-fill stop (LONG only): if Low of current bar touches/passes prior close (fills the gap)
            if direction == "LONG" and gap_fill_lvl is not None and current_low <= float(gap_fill_lvl):
                self.log.debug(
                    f"GapReversal EXIT gap_fill | {ticker} LONG | "
                    f"date={current_date} low={current_low:.2f} fill_lvl={float(gap_fill_lvl):.2f} R={current_r:.2f}"
                )
                return self._close_position(position, current_date, float(gap_fill_lvl), "GapFillStop", current_r)

            # For SHORT: gap fill means price RALLIED back to prior close (high >= fill level, not low)
            if direction == "SHORT" and gap_fill_lvl is not None and float(high_price) >= float(gap_fill_lvl):
                self.log.debug(
                    f"GapReversal EXIT gap_fill_short | {ticker} SHORT | "
                    f"date={current_date} high={float(high_price):.2f} fill_lvl={float(gap_fill_lvl):.2f} R={current_r:.2f}"
                )
                return self._close_position(position, current_date, float(gap_fill_lvl), "GapFillStop_Short", current_r)

            # 2. EMA21 trailing exit
            if len(recent_df) >= 21:
                ema21 = recent_df['Close'].ewm(span=21, adjust=False).mean().iloc[-1]
                if pd.notna(ema21):
                    if direction == "LONG" and current_close < ema21:
                        self.log.debug(
                            f"GapReversal EXIT ema21_trail | {ticker} LONG | "
                            f"date={current_date} close={current_close:.2f} ema21={ema21:.2f} R={current_r:.2f}"
                        )
                        return self._close_position(position, current_date, current_close, "EMA21_TrailingExit", current_r)
                    if direction == "SHORT" and current_close > ema21:
                        self.log.debug(
                            f"GapReversal EXIT ema21_trail_short | {ticker} SHORT | "
                            f"date={current_date} close={current_close:.2f} ema21={ema21:.2f} R={current_r:.2f}"
                        )
                        return self._close_position(position, current_date, current_close, "EMA21_TrailingExit_Short", current_r)


        has_pyramids = len(position['pyramid_adds']) > 0

        # GapReversal: always enforce MaxDays hard cap — never pyramid, and open-ended
        # holds are what caused the -245R PLTR trade (1134 days with no exit).
        if strategy == "GapReversal_Position" and days_held >= max_days:
            self.log.info(
                f"GapReversal EXIT max_days | {position.get('ticker','?')} {direction} | "
                f"date={current_date} days={days_held} R={current_r:.2f}"
            )
            return self._close_position(position, current_date, current_close, f"TimeStop_{max_days}d", current_r)

        if not has_pyramids and days_held >= max_days:
            # Only apply time stop to non-pyramided positions
            return self._close_position(position, current_date, current_close, f"TimeStop_{max_days}d", current_r)

        # Pyramided positions: No time limit, managed by trail stops only

        return None  # Continue holding

    def _close_position(self, position, exit_date, exit_price, exit_reason, r_multiple):
        """
        Close a position and return trade result.
        """
        ticker = position['ticker']
        strategy = position['strategy']
        direction = position['direction']
        entry = position['entry_price']
        shares = position['current_shares']
        days_held = position['days_held']

        # Calculate P&L - Use weighted average entry price for current shares
        # This correctly handles partial exits and pyramiding

        # Calculate weighted average entry price across all entries (initial + pyramids)
        cost_basis = position['initial_shares'] * position['entry_price']
        total_shares_entered = position['initial_shares']

        for add in position['pyramid_adds']:
            cost_basis += add['shares'] * add['price']
            total_shares_entered += add['shares']

        avg_entry_price = cost_basis / total_shares_entered if total_shares_entered > 0 else entry

        # Calculate P&L for CURRENT shares (accounts for partial exits)
        if direction == "LONG":
            pnl = shares * (exit_price - avg_entry_price)
        else:
            pnl = shares * (avg_entry_price - exit_price)

        outcome = "Win" if pnl > 0 else "Loss"

        # Calculate ACTUAL R-multiple from real P&L (don't use passed r_multiple which may be hardcoded)
        # R = (P&L per share) / (initial risk per share)
        risk_per_share = position['risk_amount']
        pnl_per_share = pnl / shares if shares > 0 else 0
        actual_r_multiple = pnl_per_share / risk_per_share if risk_per_share > 0 else 0

        # Display exit
        pnl_display = f"${pnl:+,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
        outcome_icon = "💰" if pnl > 0 else "📉"
        print(f"   {outcome_icon} {exit_date.date()} | EXIT {ticker} {actual_r_multiple:+.2f}R ({pnl_display}) in {days_held}d | {exit_reason}")

        # Create trade result
        result = {
            "Date": position['entry_date'],
            "ExitDate": exit_date,
            "Year": position['entry_date'].year,
            "Ticker": ticker,
            "Strategy": strategy,
            "Direction": direction,
            "PositionType": "Full",
            "Entry": round(entry, 2),
            "Exit": round(exit_price, 2),
            "Outcome": outcome,
            "ExitReason": exit_reason,
            "RMultiple": round(actual_r_multiple, 2),  # Use ACTUAL R-multiple from P&L, not passed parameter
            "Shares": shares,
            "PnL_$": round(pnl, 2),
            "HoldingDays": days_held,
            "PyramidAdds": len(position['pyramid_adds']),
        }

        # Track cooldown for strategies that need it
        if strategy == "MegaCap_WeeklySlide_Short":
            if strategy not in self.cooldown_tracker:
                self.cooldown_tracker[strategy] = {}
            self.cooldown_tracker[strategy][ticker] = exit_date

        # Record exit to RS Ranker tracker (if applicable)
        if strategy == "RelativeStrength_Ranker_Position":
            # Calculate days held
            position_entry = pd.Timestamp(position['entry_date'])
            days_held = (exit_date - position_entry).days
            
            self.rs_bought_tracker.close_position(
                ticker=ticker,
                exit_date=exit_date.strftime('%Y-%m-%d'),
                exit_price=exit_price,
                exit_reason=exit_reason,
                profit_loss=pnl,
                r_multiple=r_multiple,
                days_held=days_held
            )

        return result

    def run(self):
        """Run walk-forward backtest"""
        # Ensure fresh tracker for this backtest run
        self.rs_bought_tracker.clear_all()
        
        end_date = pd.Timestamp.today()
        print(f"🚀 Position Trading Backtest: {self.start_date.date()} to {end_date.date()}")
        print(f"📅 Scan frequency: {self.scan_frequency}")
        print(f"💰 Initial capital: ${self.initial_capital:,}")
        print(f"⚠️  Risk per trade: {POSITION_RISK_PER_TRADE_PCT}%")
        if isinstance(POSITION_MAX_PER_STRATEGY, dict):
            print(f"📊 Max positions: {POSITION_MAX_TOTAL} total, per-strategy limits (3-8)")
        else:
            print(f"📊 Max positions: {POSITION_MAX_TOTAL} total, {POSITION_MAX_PER_STRATEGY} per strategy")

        all_trades = []
        scan_dates = pd.date_range(self.start_date, end_date, freq=self.scan_frequency)

        print(f"\n🔍 Total scan dates: {len(scan_dates)}\n")

        for idx, day in enumerate(scan_dates, 1):
            # Update market regime at each scan date
            self._update_market_regime(day)
            regime_emoji = "🟢" if self.current_position_regime == PositionRegime.RISK_ON else "🟡" if self.current_position_regime == PositionRegime.NEUTRAL else "🔴"
            
            # Log regime change
            regime_str = "RISK_ON" if self.current_position_regime == PositionRegime.RISK_ON else "NEUTRAL" if self.current_position_regime == PositionRegime.NEUTRAL else "RISK_OFF"
            risk_pct = self.regime_params.get('risk_per_trade_pct', 2.0)
            adx_thresh = self.regime_params.get('adx_threshold', 25)
            max_pos = self.regime_params.get('max_positions', 10)
            
            # Progress indicator
            if idx % 10 == 0:
                open_tickers = self.position_tracker.get_open_tickers()
                tickers_display = ", ".join(open_tickers[:5]) if open_tickers else "None"
                if len(open_tickers) > 5:
                    tickers_display += f" +{len(open_tickers)-5} more"
                print(f"📅 {day.date()} {regime_emoji} | Progress: {idx}/{len(scan_dates)} | Open: {len(open_tickers)} [{tickers_display}]")

            # Check open positions for exits EVERY day
            closed_today = self._check_open_positions(day)
            for closed_trade in closed_today:
                all_trades.append(closed_trade)

                # Update tracker - ONLY remove on full exit (not partial)
                # Partial exits keep position open with reduced shares
                position_type = closed_trade.get("PositionType", "Full")
                if position_type in ["Full", "Runner"]:  # Full exit or runner exit (after partial)
                    ticker = closed_trade["Ticker"]
                    strategy = closed_trade["Strategy"]
                    if ticker in self.position_tracker.positions:
                        self.position_tracker.remove_position(ticker)
                        self.strategy_positions[strategy] = max(0, self.strategy_positions.get(strategy, 0) - 1)

            # Run scanner for new entries (pass persistent tracker for backtest)
            signals = run_scan_as_of(day, self.tickers, rs_bought_tracker=self.rs_bought_tracker)

            if signals:
                # Log detailed signal information
                signal_count = len(signals)
                by_strategy = {}
                for s in signals:
                    strat = s.get("Strategy", "Unknown")
                    by_strategy[strat] = by_strategy.get(strat, 0) + 1
                
                if idx % 5 == 0 or signal_count > 5:  # Log detailed every 5 scans or on large signal days
                    print(f"   📊 {day.date()} {regime_emoji} [{regime_str}] | {signal_count} signals generated | Regime: Risk={risk_pct}% ADX={adx_thresh} MaxPos={max_pos}")
                    for strat, count in sorted(by_strategy.items()):
                        print(f"      - {strat}: {count} signal(s)")
                
                # Pre-buy check (deduplication, formatting)
                validated = pre_buy_check(signals, benchmark="QQQ", as_of_date=day)
                
                # Log filtering results
                filtered_out = signal_count - len(validated)
                if filtered_out > 0 and (idx % 5 == 0 or signal_count > 5):
                    print(f"      Filtered by pre_buy_check: -{filtered_out} ({100*filtered_out/signal_count:.0f}%)")
                
                if not validated.empty:
                    # Filter out positions we already hold
                    before_filter = len(validated)
                    validated = filter_trades_by_position(validated, self.position_tracker, as_of_date=day)
                    held_filter = before_filter - len(validated)
                    
                    if held_filter > 0 and (idx % 5 == 0 or before_filter > 5):
                        print(f"      Already holding: -{held_filter}")

                    if not validated.empty:
                        # Check if new entries are allowed in current regime
                        allow_new_entries = self.regime_params.get('allow_new_entries', True)
                        if not allow_new_entries:
                            if idx % 10 == 0:
                                print(f"   🔴 {day.date()} | RISK_OFF regime: No new entries allowed")
                        
                        # Take trades respecting limits
                        entered_count = 0
                        skipped_count = 0
                        
                        for _, trade in validated.iterrows():
                            strategy = trade["Strategy"]

                            # Check if new entries allowed in current regime
                            if not allow_new_entries:
                                skipped_count += 1
                                continue  # Skip all new entries in RISK_OFF

                            # Check global position limit
                            if len(self.position_tracker.positions) >= POSITION_MAX_TOTAL:
                                skipped_count += 1
                                break

                            # Check per-strategy limit
                            strategy_count = self.strategy_positions.get(strategy, 0)
                            # Handle both dict and int for compatibility
                            if isinstance(POSITION_MAX_PER_STRATEGY, dict):
                                max_for_strategy = POSITION_MAX_PER_STRATEGY.get(strategy, 5)
                            else:
                                max_for_strategy = POSITION_MAX_PER_STRATEGY

                            if strategy_count >= max_for_strategy:
                                skipped_count += 1
                                continue

                            # Check cooldown for strategies that need it
                            if strategy == "MegaCap_WeeklySlide_Short":
                                ticker = trade["Ticker"]
                                if strategy in self.cooldown_tracker and ticker in self.cooldown_tracker[strategy]:
                                    exit_date = self.cooldown_tracker[strategy][ticker]
                                    days_since_exit = (day - exit_date).days
                                    cooldown_days = MEGACAP_WEEKLY_SLIDE_CFG.get("COOLDOWN_DAYS", 10)
                                    if days_since_exit < cooldown_days:
                                        skipped_count += 1
                                        continue  # Still in cooldown period

                            # Enter position
                            success = self._enter_position(day, trade.to_dict())

                            if success:
                                # Show trade entry
                                print(f"   ✅ {day.date()} | ENTER {trade['Ticker']} @ ${trade['Entry']:.2f} | {strategy[:20]}")
                                if strategy == "GapReversal_Position":
                                    self.log.info(
                                        f"GapReversal ENTER | {trade['Ticker']} {trade.get('Direction','?')} | "
                                        f"date={day.date()} entry={trade['Entry']:.2f} stop={trade.get('StopLoss', trade.get('StopPrice','?'))} "
                                        f"gap={trade.get('GapPct','?')}% rsi={trade.get('SmoothedRSI','?')}"
                                    )
                                entered_count += 1

                                # Update position counts
                                self.position_tracker.add_position(
                                    ticker=trade["Ticker"],
                                    entry_date=day,
                                    entry_price=trade["Entry"],
                                    strategy=trade["Strategy"],
                                    as_of_date=day
                                )
                                self.strategy_positions[strategy] = strategy_count + 1
                        
                        # Log summary for day
                        if entered_count > 0 or skipped_count > 0:
                            print(f"      Summary: Entered={entered_count}, Skipped={skipped_count}, Total Open={len(self.position_tracker.positions)}/{POSITION_MAX_TOTAL}")

        # =================================================================
        # Close any remaining open positions at end of backtest
        # =================================================================
        if self.open_positions:
            print(f"\n⚠️  Closing {len(self.open_positions)} open position(s) at end of backtest (using last available price)...")

            for position in self.open_positions:
                ticker = position['ticker']

                # Get final price - use last available data
                df = get_historical_data(ticker)
                if df.empty:
                    print(f"   ⚠️  Cannot close {ticker} - no price data")
                    continue

                # Ensure index is DatetimeIndex
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index, errors='coerce')
                    df = df[df.index.notna()]
                    if df.empty:
                        print(f"   ⚠️  Cannot close {ticker} - invalid date index")
                        continue

                # Use the last available date (not necessarily end_date)
                final_date = df.index[-1]
                final_price = df['Close'].iloc[-1]

                # Update position's days_held to final date
                entry_date = position['entry_date']
                if not isinstance(entry_date, pd.Timestamp):
                    entry_date = pd.Timestamp(entry_date)
                days_from_entry = (final_date - entry_date).days
                position['days_held'] = days_from_entry

                # Calculate final R-multiple
                risk_amount = position['risk_amount']
                entry_price = position['entry_price']
                direction = position['direction']

                if direction == "LONG":
                    final_r = (final_price - entry_price) / max(risk_amount, 0.01)
                else:
                    final_r = (entry_price - final_price) / max(risk_amount, 0.01)

                # Close position
                exit_result = self._close_position(
                    position,
                    final_date,
                    final_price,
                    "EndOfBacktest",
                    final_r
                )

                # Mark as Full or Runner depending on partial exit status
                if position['partial_exited']:
                    exit_result['PositionType'] = "Runner"

                all_trades.append(exit_result)

        # Convert to DataFrame
        if all_trades:
            df = pd.DataFrame(all_trades)
            print(f"\n✅ Backtest complete! Total trades: {len(df)}")
            return df
        else:
            print("\n⚠️  No trades executed")
            return pd.DataFrame()


    def evaluate(self, df):
        """Generate performance statistics"""
        if df.empty:
            return "No trades executed"

        wins = (df["Outcome"] == "Win").sum()

        summary = {
            "TotalTrades": len(df),
            "Wins": int(wins),
            "Losses": int(len(df) - wins),
            "WinRate%": round(wins / len(df) * 100, 2),
            "TotalPnL_$": round(df["PnL_$"].sum(), 2),
            "AvgHoldingDays": round(df["HoldingDays"].mean(), 2),
            "AvgRMultiple": round(df["RMultiple"].mean(), 2),
        }

        # Yearly breakdown
        yearly = (
            df.groupby("Year")
            .agg({
                "Ticker": "count",
                "Outcome": lambda x: (x == "Win").sum(),
                "PnL_$": "sum",
                "HoldingDays": "mean",
            })
            .round(2)
        )

        yearly.columns = ["Trades", "Wins", "TotalPnL_$", "AvgHoldingDays"]
        summary["YearlySummary"] = yearly.to_dict("index")

        # Strategy-wise analysis
        if "Strategy" in df.columns:
            strategy_analysis = (
                df.groupby("Strategy")
                .agg({
                    "Ticker": "count",
                    "Outcome": lambda x: (x == "Win").sum() / len(x) * 100,
                    "RMultiple": "mean",
                    "PnL_$": "sum",
                    "HoldingDays": "mean",
                })
                .round(2)
            )

            strategy_analysis.columns = [
                "Trades",
                "WinRate%",
                "AvgRMultiple",
                "TotalPnL_$",
                "AvgHoldingDays",
            ]

            strategy_analysis = strategy_analysis.sort_values("TotalPnL_$", ascending=False)
            summary["StrategyAnalysis"] = strategy_analysis.to_dict("index")

        # Exit reason analysis
        if "ExitReason" in df.columns:
            exit_analysis = (
                df.groupby("ExitReason")
                .agg({
                    "Ticker": "count",
                    "PnL_$": "sum",
                    "RMultiple": "mean",
                })
                .round(2)
            )

            exit_analysis.columns = ["Count", "TotalPnL_$", "AvgRMultiple"]
            exit_analysis = exit_analysis.sort_values("Count", ascending=False)
            summary["ExitReasonAnalysis"] = exit_analysis.to_dict("index")

        return summary

