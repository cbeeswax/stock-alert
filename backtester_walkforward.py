"""
Long-Term Position Trading Backtester
======================================
Walk-forward backtester for 8 position strategies (60-120 day holds).
Features: Strategy-specific exits, pyramiding, per-strategy position limits.
"""

import pandas as pd
from scanners.scanner_walkforward import run_scan_as_of
from core.pre_buy_check import pre_buy_check
from utils.market_data import get_historical_data
from utils.position_tracker import PositionTracker, filter_trades_by_position
from utils.ema_utils import compute_rsi, compute_bollinger_bands, compute_percent_b
from scripts.download_history import download_ticker, was_update_session_today, mark_update_session
from config.trading_config import (
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
        self.tickers = tickers
        self.start_date = pd.to_datetime(start_date or BACKTEST_START_DATE)
        self.scan_frequency = scan_frequency or BACKTEST_SCAN_FREQUENCY
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # Position tracker
        self.position_tracker = PositionTracker(mode="backtest")

        # Per-strategy position counters
        self.strategy_positions = {}

        # Open positions for day-by-day simulation
        self.open_positions = []  # List of position dicts

        # All completed trades
        self.completed_trades = []

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

        # Position sizing
        shares = self._calculate_position_size(entry_price, stop_price)
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

            # Get today's bar
            if current_date not in df.index:
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
                    if current_r >= RS_RANKER_PARTIAL_R:
                        should_partial = True
                        partial_trigger = f"{RS_RANKER_PARTIAL_R}R"
                        partial_size = RS_RANKER_PARTIAL_SIZE

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

        # Check stop loss first
        if direction == "LONG" and today_data['Low'] <= stop:
            return self._close_position(position, current_date, stop, "StopLoss", -1.0)
        elif direction == "SHORT" and today_data['High'] >= stop:
            return self._close_position(position, current_date, stop, "StopLoss", -1.0)

        # Calculate indicators (need historical context)
        recent_df = full_df[full_df.index <= current_date].tail(250).copy()
        if len(recent_df) < 50:
            return None  # Not enough data

        recent_df["EMA21"] = recent_df["Close"].ewm(span=21).mean()
        recent_df["MA50"] = recent_df["Close"].rolling(50).mean()
        recent_df["MA100"] = recent_df["Close"].rolling(100).mean()
        recent_df["MA200"] = recent_df["Close"].rolling(200).mean()
        recent_df["RSI14"] = compute_rsi(recent_df["Close"], 14)

        # Get current indicator values
        ema21 = recent_df["EMA21"].iloc[-1] if len(recent_df) >= 21 else None
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

        # Time stop (SKIP for pyramided positions - let trail stops manage winners)
        has_pyramids = len(position['pyramid_adds']) > 0

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

        # Display exit
        pnl_display = f"${pnl:+,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
        outcome_icon = "💰" if pnl > 0 else "📉"
        print(f"   {outcome_icon} {exit_date.date()} | EXIT {ticker} {r_multiple:+.2f}R ({pnl_display}) in {days_held}d | {exit_reason}")

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
            "RMultiple": round(r_multiple, 2),
            "Shares": shares,
            "PnL_$": round(pnl, 2),
            "HoldingDays": days_held,
            "PyramidAdds": len(position['pyramid_adds']),
        }

        return result

    def run(self):
        """Run walk-forward backtest"""
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
            # Progress indicator
            if idx % 10 == 0:
                open_tickers = self.position_tracker.get_open_tickers()
                tickers_display = ", ".join(open_tickers[:5]) if open_tickers else "None"
                if len(open_tickers) > 5:
                    tickers_display += f" +{len(open_tickers)-5} more"
                print(f"📅 {day.date()} | Progress: {idx}/{len(scan_dates)} | Open: {len(open_tickers)} [{tickers_display}]")

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

            # Run scanner for new entries
            signals = run_scan_as_of(day, self.tickers)

            if signals:
                # Pre-buy check (deduplication, formatting)
                validated = pre_buy_check(signals, benchmark="QQQ", as_of_date=day)

                if not validated.empty:
                    # Filter out positions we already hold
                    validated = filter_trades_by_position(validated, self.position_tracker, as_of_date=day)

                    if not validated.empty:
                        # Take trades respecting limits
                        for _, trade in validated.iterrows():
                            strategy = trade["Strategy"]

                            # Check global position limit
                            if len(self.position_tracker.positions) >= POSITION_MAX_TOTAL:
                                break

                            # Check per-strategy limit
                            strategy_count = self.strategy_positions.get(strategy, 0)
                            # Handle both dict and int for compatibility
                            if isinstance(POSITION_MAX_PER_STRATEGY, dict):
                                max_for_strategy = POSITION_MAX_PER_STRATEGY.get(strategy, 5)
                            else:
                                max_for_strategy = POSITION_MAX_PER_STRATEGY

                            if strategy_count >= max_for_strategy:
                                continue

                            # Enter position
                            success = self._enter_position(day, trade.to_dict())

                            if success:
                                # Show trade entry
                                print(f"   ✅ {day.date()} | ENTER {trade['Ticker']} @ ${trade['Entry']:.2f} | {strategy[:20]}")

                                # Update position counts
                                self.position_tracker.add_position(
                                    ticker=trade["Ticker"],
                                    entry_date=day,
                                    entry_price=trade["Entry"],
                                    strategy=trade["Strategy"],
                                    as_of_date=day
                                )
                                self.strategy_positions[strategy] = strategy_count + 1

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

                # Use the last available date (not necessarily end_date)
                final_date = df.index[-1]
                final_price = df['Close'].iloc[-1]

                # Update position's days_held to final date
                days_from_entry = (final_date - position['entry_date']).days
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


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Position trading backtest")
    parser.add_argument(
        "--scan-frequency",
        type=str,
        default=BACKTEST_SCAN_FREQUENCY,
        choices=["B", "W-MON", "W-TUE", "W-WED", "W-THU", "W-FRI"],
        help="Scan frequency (default: W-MON for weekly)"
    )
    args = parser.parse_args()

    # Load S&P 500 tickers
    tickers = pd.read_csv("data/sp500_constituents.csv")["Symbol"].tolist()

    # Check if data update needed
    print("="*60)
    print("📥 CHECKING HISTORICAL DATA")
    print("="*60)

    if was_update_session_today():
        print("⚡ Data already updated today - skipping download")
    else:
        print("🔄 Updating historical data for all tickers...")
        for i, ticker in enumerate(tickers, 1):
            if i % 50 == 0:
                print(f"\n[Progress: {i}/{len(tickers)} tickers processed]")
            download_ticker(ticker)

        # Update benchmarks
        print("\n📊 Updating benchmark data...")
        download_ticker("SPY")
        download_ticker("QQQ")

        mark_update_session()
        print("\n✅ Data update complete!")

    print("\n" + "="*60)
    print("🚀 Starting position trading backtest...")
    print("="*60 + "\n")

    # Run backtest
    bt = WalkForwardBacktester(
        tickers=tickers,
        start_date=BACKTEST_START_DATE,
        scan_frequency=args.scan_frequency
    )

    print(f"⚙️  CONFIG:")
    print(f"   Risk per trade: {POSITION_RISK_PER_TRADE_PCT}%")
    if isinstance(POSITION_MAX_PER_STRATEGY, dict):
        print(f"   Max positions: {POSITION_MAX_TOTAL} total")
        print(f"   Per-strategy limits: RS_Ranker/High52=8, BigBase=6, EMA_Cross=4, Others=3")
    else:
        print(f"   Max positions: {POSITION_MAX_TOTAL} total, {POSITION_MAX_PER_STRATEGY} per strategy")
    print(f"   Scan frequency: {args.scan_frequency}")
    print(f"   Pyramiding: {'Enabled' if POSITION_PYRAMID_ENABLED else 'Disabled'}\n")

    trades = bt.run()

    # Save results
    if not trades.empty:
        trades.to_csv("backtest_results.csv", index=False)
        print(f"\n💾 Results saved to: backtest_results.csv")

    stats = bt.evaluate(trades)

    # Print results
    print("\n" + "="*80)
    print("📊 POSITION TRADING BACKTEST SUMMARY")
    print("="*80)

    print(f"\n📈 Overall Performance:")
    print(f"   Total Trades: {stats['TotalTrades']}")
    print(f"   Wins: {stats['Wins']} | Losses: {stats['Losses']}")
    print(f"   Win Rate: {stats['WinRate%']}%")
    print(f"   Total PnL: ${stats['TotalPnL_$']:,.2f}")
    print(f"   Avg R-Multiple: {stats['AvgRMultiple']}")
    print(f"   Avg Holding Days: {stats['AvgHoldingDays']}")

    # Yearly breakdown
    if "YearlySummary" in stats:
        print(f"\n📅 Yearly Breakdown:")
        for year, metrics in stats["YearlySummary"].items():
            print(f"   {year}: {metrics['Trades']} trades, {metrics['Wins']} wins, ${metrics['TotalPnL_$']:,.2f} PnL")

    # Strategy-wise analysis
    if "StrategyAnalysis" in stats:
        print(f"\n📊 Performance by Strategy:")
        print("   " + "-"*90)
        print(f"   {'Strategy':<30} {'Trades':<8} {'WinRate':<10} {'AvgR':<8} {'TotalPnL':<15} {'AvgDays':<8}")
        print("   " + "-"*90)
        for strategy, metrics in stats["StrategyAnalysis"].items():
            print(f"   {strategy:<30} {int(metrics['Trades']):<8} "
                  f"{metrics['WinRate%']:<9.1f}% {metrics['AvgRMultiple']:<8.2f} "
                  f"${metrics['TotalPnL_$']:>12,.2f} {metrics['AvgHoldingDays']:<8.1f}")
        print("   " + "-"*90)

    # Exit reason analysis
    if "ExitReasonAnalysis" in stats:
        print(f"\n🚪 Exit Reason Breakdown:")
        print("   " + "-"*60)
        print(f"   {'Reason':<25} {'Count':<8} {'TotalPnL':<15} {'AvgR':<8}")
        print("   " + "-"*60)
        for reason, metrics in stats["ExitReasonAnalysis"].items():
            print(f"   {reason:<25} {int(metrics['Count']):<8} "
                  f"${metrics['TotalPnL_$']:>12,.2f} {metrics['AvgRMultiple']:<8.2f}")
        print("   " + "-"*60)

    print("\n" + "="*80)
