import pandas as pd
from scanners.scanner_walkforward import run_scan_as_of
from core.pre_buy_check import pre_buy_check
from utils.market_data import get_historical_data
from utils.position_tracker import PositionTracker, filter_trades_by_position
from utils.ema_utils import compute_rsi, compute_bollinger_bands, compute_percent_b  # For Mean Reversion and BB exits
from scripts.download_history import download_ticker, was_update_session_today, mark_update_session
from config.trading_config import (
    CAPITAL_PER_TRADE,
    RISK_REWARD_RATIO,
    MAX_HOLDING_DAYS,
    BACKTEST_START_DATE,
    SCAN_FREQUENCY,
    MAX_TRADES_PER_SCAN,
    MAX_OPEN_POSITIONS,
    REQUIRE_CONFIRMATION_BAR,
    CONFIRMATION_MAX_GAP_PCT,
    CONFIRMATION_MIN_VOLUME_RATIO,
    MIN_HOLDING_DAYS,
    CATASTROPHIC_LOSS_THRESHOLD
)


class WalkForwardBacktester:
    """
    True walk-forward backtester:
    - Daily simulation
    - No look-ahead bias
    - Uses scanner_walkforward
    """

    def __init__(self, tickers, start_date="2022-01-01", rr_ratio=2, max_days=45, scan_frequency="W-MON"):
        """
        Args:
            tickers: List of ticker symbols to backtest
            start_date: Start date for backtest
            rr_ratio: Risk/reward ratio (default 2:1)
            max_days: Maximum holding period in days (default 45 for swing trading)
            scan_frequency: How often to scan for signals (default 'W-MON' = weekly on Mondays)
                           Options: 'B' (daily), 'W-MON' (weekly), 'W-FRI' (weekly Friday)
        """
        self.tickers = tickers
        self.start_date = pd.to_datetime(start_date)
        self.rr_ratio = rr_ratio
        self.max_days = max_days
        self.scan_frequency = scan_frequency

        # 🆕 Position tracker to prevent duplicate positions
        self.position_tracker = PositionTracker(mode="backtest")

    # -------------------------------------------------
    # MAIN RUN
    # -------------------------------------------------
    def run(self):
        end_date = pd.Timestamp.today()
        print(f"🚀 Walk-forward backtest from {self.start_date.date()} to {end_date.date()}")
        print(f"📅 Scan frequency: {self.scan_frequency} | Max holding: {self.max_days} days")

        all_trades = []

        # Generate scan dates based on frequency (weekly is much faster than daily)
        scan_dates = pd.date_range(
            self.start_date,
            end_date,
            freq=self.scan_frequency
        )

        print(f"🔍 Total scan dates: {len(scan_dates)}")

        for idx, day in enumerate(scan_dates, 1):
            # Count positions that are still open as of this date
            open_positions = sum(
                1 for ticker in self.position_tracker.get_open_tickers()
                if self.position_tracker.is_in_position(ticker, as_of_date=day)
            )
            print(f"📅 [{idx}/{len(scan_dates)}] Simulating {day.date()} | Open positions: {open_positions}")

            # 🆕 GLOBAL POSITION LIMIT: Skip scanning if at maximum capacity
            if open_positions >= MAX_OPEN_POSITIONS:
                print(f"   🛑 Max positions reached ({MAX_OPEN_POSITIONS}), skipping scan")
                continue

            # Generate signals using only data up to this date (no look-ahead bias)
            signals = run_scan_as_of(day, self.tickers)
            if not signals:
                print(f"   ⚠️  No signals generated")
                continue

            print(f"   ✅ Found {len(signals)} signals")

            # 🔒 CRITICAL: Pass as_of_date to prevent look-ahead bias in pre_buy_check
            trades = pre_buy_check(signals, rr_ratio=self.rr_ratio, as_of_date=day)
            if trades.empty:
                print(f"   ⚠️  No trades passed pre-buy filters")
                continue

            print(f"   💼 {len(trades)} trades passed filters")

            # 🆕 Filter out tickers already in position (as of this scan date)
            trades = filter_trades_by_position(trades, self.position_tracker, as_of_date=day)
            if trades.empty:
                print(f"   ⚠️  All trades filtered out (already in position)")
                continue

            # 🎯 Take top N trades per day based on config, but respect global limit
            if not trades.empty:
                # Calculate remaining slots
                available_slots = MAX_OPEN_POSITIONS - open_positions
                max_new_trades = min(MAX_TRADES_PER_SCAN, available_slots)

                trades = trades.head(max_new_trades)
                tickers_selected = ", ".join([f"{row['Ticker']}({row['FinalScore']:.1f})" for _, row in trades.iterrows()])
                print(f"   🎯 Selected top {len(trades)} trade(s) (slots available: {available_slots}): {tickers_selected}")

            for trade in trades.to_dict("records"):
                result = self._simulate_trade(day, trade)
                if result:
                    all_trades.append(result)

        return pd.DataFrame(all_trades)

    # -------------------------------------------------
    # TRADE SIMULATION (WITH TRAILING STOP & EMA BREAKDOWN)
    # -------------------------------------------------
    def _simulate_trade(self, entry_day, trade):
        ticker = trade["Ticker"]
        signal_entry = trade["Entry"]  # Entry price from signal (close of signal day)
        initial_stop = trade["StopLoss"]
        target = trade["Target"]
        strategy = trade.get("Strategy", "Unknown")

        # 🆕 Capture crossover information for analysis
        crossover_type = trade.get("CrossoverType", "Unknown")
        crossover_bonus = trade.get("CrossoverBonus", 0)
        score = trade.get("Score", 0)

        # 🆕 Check if already in position (safety check with date)
        if self.position_tracker.is_in_position(ticker, as_of_date=entry_day):
            print(f"   ⚠️ {ticker}: Already in position, skipping")
            return None

        df = get_historical_data(ticker)
        if df.empty:
            return None

        # 🔒 Only future candles AFTER entry day
        # Use .copy() to avoid SettingWithCopyWarning
        future_df = df[df.index > entry_day].iloc[: self.max_days].copy()
        if future_df.empty:
            return None

        # ========================================
        # 🆕 CONFIRMATION BAR LOGIC
        # ========================================
        if REQUIRE_CONFIRMATION_BAR:
            # Get signal day data for reference
            signal_df = df[df.index <= entry_day].copy()
            if len(signal_df) < 20:
                return None  # Not enough data

            signal_close = signal_df["Close"].iloc[-1]
            signal_ema20 = signal_df["Close"].ewm(span=20).mean().iloc[-1]
            avg_volume = signal_df["Volume"].rolling(20).mean().iloc[-1]

            # Get confirmation day (next day after signal)
            confirmation_day = future_df.iloc[0]
            conf_open = confirmation_day.Open
            conf_close = confirmation_day.Close
            conf_volume = confirmation_day.Volume

            # Calculate gap from signal close to confirmation open
            gap_pct = abs((conf_open - signal_close) / signal_close * 100)

            # Confirmation checks
            gap_ok = gap_pct < CONFIRMATION_MAX_GAP_PCT
            price_holds = conf_close > signal_ema20  # Still above EMA20
            no_reversal = conf_close >= conf_open * 0.99  # Not bearish bar
            volume_ok = conf_volume > avg_volume * CONFIRMATION_MIN_VOLUME_RATIO

            if not all([gap_ok, price_holds, no_reversal, volume_ok]):
                # Failed confirmation
                return None

            # CONFIRMED: Enter at confirmation day open
            entry = conf_open
            actual_entry_day = future_df.index[0]

            # Adjust stop and target based on actual entry
            risk = signal_entry - initial_stop
            initial_stop = entry - risk  # Keep same risk amount
            target = entry + self.rr_ratio * risk

            # Use remaining candles after confirmation (explicit copy)
            df = future_df.iloc[1:].copy()
        else:
            # No confirmation required - enter at signal close
            entry = signal_entry
            actual_entry_day = entry_day
            df = future_df.copy()

        if df.empty:
            return None

        # Calculate EMAs for breakdown detection
        df["EMA20"] = df["Close"].ewm(span=20).mean()

        # Calculate Mean Reversion indicators (RSI(2) and MA5)
        df["RSI2"] = compute_rsi(df["Close"], 2)
        df["MA5"] = df["Close"].rolling(5).mean()

        # Calculate Bollinger Bands for BB strategies
        middle_band, upper_band, lower_band, bandwidth = compute_bollinger_bands(df["Close"], period=20, std_dev=2)
        df["BB_Middle"] = middle_band
        df["BB_Upper"] = upper_band
        df["BB_Lower"] = lower_band
        df["PercentB"] = compute_percent_b(df["Close"], upper_band, lower_band)

        # Calculate RSI(14) for BB+RSI combo exit
        df["RSI14"] = compute_rsi(df["Close"], 14)

        exit_price = df["Close"].iloc[-1]
        outcome = "TimeExit"
        holding_days = len(df)
        exit_reason = "MaxDays"

        # Trailing stop logic
        stop = initial_stop
        risk_amount = entry - initial_stop
        highest_price = entry

        for i, row in enumerate(df.itertuples()):
            current_close = row.Close
            current_ema20 = df["EMA20"].iloc[i]
            current_holding_days = i + 1

            # Track highest price for trailing stop
            if row.High > highest_price:
                highest_price = row.High

            # Calculate unrealized R-multiple
            unrealized_r = (highest_price - entry) / max(risk_amount, 0.01)

            # 🎯 TRAILING STOP LOGIC (Skip for mean reversion strategies - they use specific exits)
            if strategy not in ["Mean Reversion", "%B Mean Reversion", "BB+RSI Combo"]:
                # Once up 1R, move stop to breakeven
                if unrealized_r >= 1.0 and stop < entry:
                    stop = entry

                # Once up 2R, lock in 1R profit
                if unrealized_r >= 2.0 and stop < entry + risk_amount:
                    stop = entry + risk_amount

                # Once up 3R, lock in 2R profit
                if unrealized_r >= 3.0 and stop < entry + 2 * risk_amount:
                    stop = entry + 2 * risk_amount

            # ========================================
            # 🆕 MINIMUM HOLDING PERIOD (Anti-Whipsaw)
            # ========================================
            # Skip minimum holding for:
            # - Cascading (they don't have EMA20BD exit anymore)
            # - Mean Reversion strategies (designed for quick 3-5 day exits)
            # Before minimum holding days, only exit if catastrophic loss
            if (current_holding_days < MIN_HOLDING_DAYS and
                crossover_type != "Cascading" and
                strategy not in ["Mean Reversion", "%B Mean Reversion", "BB+RSI Combo"]):
                # Calculate current loss in R-multiples
                current_loss_r = (entry - current_close) / max(risk_amount, 0.01)

                # Only allow exit if catastrophic loss (> 1.5R)
                if current_loss_r > CATASTROPHIC_LOSS_THRESHOLD and row.Low <= stop:
                    exit_price = stop
                    outcome = "Loss"
                    holding_days = current_holding_days
                    exit_reason = "CatastrophicLoss"
                    break

                # Otherwise, skip all other exit checks and continue holding
                continue

            # ========================================
            # NORMAL EXIT CONDITIONS (after min holding)
            # ========================================

            # ========================================
            # MEAN REVERSION EXIT (🔧 FASTER EXITS)
            # ========================================
            # Exit when RSI(2) > 65 OR Close > MA5 (1 day)
            # Faster exits to lock in gains quicker
            if strategy == "Mean Reversion":
                current_rsi2 = df["RSI2"].iloc[i]
                # 🔧 Calculate MA5 on the fly since signal data may not have it
                ma5 = df["Close"].iloc[max(0, i-4):i+1].mean() if i >= 4 else df["Close"].iloc[:i+1].mean()

                # 🔧 Exit condition 1: RSI(2) rises above 65 (was 70 - faster exit)
                rsi_overbought = current_rsi2 > 65

                # 🔧 Exit condition 2: Price closes above 5-day MA (1 close, not 2)
                above_ma5 = current_close > ma5

                if rsi_overbought or above_ma5:
                    exit_price = current_close
                    outcome = "Win" if exit_price > entry else "Loss"
                    holding_days = current_holding_days
                    exit_reason = "RSI2_Overbought" if rsi_overbought else "Above_MA5"
                    break

            # ========================================
            # %B MEAN REVERSION EXIT (🔧 FASTER EXIT)
            # ========================================
            # Exit when %B > 0.4 (was 0.5 - faster exit)
            # Lock in gains before full mean reversion
            if strategy == "%B Mean Reversion":
                current_percent_b = df["PercentB"].iloc[i]

                # 🔧 Exit condition: %B rises above 0.4 (was 0.5 - faster exit)
                back_to_middle = current_percent_b > 0.4

                if back_to_middle:
                    exit_price = current_close
                    outcome = "Win" if exit_price > entry else "Loss"
                    holding_days = current_holding_days
                    exit_reason = "PercentB_Middle"
                    break

            # ========================================
            # BOLLINGER + RSI COMBO EXIT (🔧 FASTER EXITS)
            # ========================================
            # Exit when %B > 0.6 OR RSI(14) > 60 (was %B > 0.8 OR RSI14 > 70)
            # Faster exits to lock in gains
            if strategy == "BB+RSI Combo":
                current_percent_b = df["PercentB"].iloc[i]
                current_rsi14 = df["RSI14"].iloc[i]

                # 🔧 Exit condition 1: %B rises above 0.6 (was 0.8 - faster exit)
                bb_overbought = current_percent_b > 0.6

                # 🔧 Exit condition 2: RSI(14) rises above 60 (was 70 - faster exit)
                rsi_overbought = current_rsi14 > 60

                if bb_overbought or rsi_overbought:
                    exit_price = current_close
                    outcome = "Win" if exit_price > entry else "Loss"
                    holding_days = current_holding_days
                    exit_reason = "BB_Overbought" if bb_overbought else "RSI14_Overbought"
                    break

            # ❌ EMA20 BREAKDOWN EXIT (DISABLED for Cascading crossovers)
            # Cascading crossovers need time to establish trend (65% WR when allowed to run)
            # EMA20Breakdown was killing 74% of Cascading trades on day 3
            if (strategy == "EMA Crossover" and
                crossover_type != "Cascading" and  # 🆕 Skip for Cascading!
                current_close < current_ema20):
                exit_price = current_close
                outcome = "EMABreakdown"
                holding_days = current_holding_days
                exit_reason = "EMA20Breakdown"
                break

            # ❌ STOP LOSS HIT
            if row.Low <= stop:
                exit_price = stop
                outcome = "Loss" if stop <= entry else "PartialWin"
                holding_days = current_holding_days
                exit_reason = "StopLoss" if stop <= entry else "TrailingStop"
                break

            # ✅ TARGET HIT
            if row.High >= target:
                exit_price = target
                outcome = "Win"
                holding_days = current_holding_days
                exit_reason = "Target"
                break

        r_multiple = (exit_price - entry) / max(entry - initial_stop, 0.01)

        position_size = CAPITAL_PER_TRADE / entry
        risk = position_size * abs(entry - initial_stop)
        pnl = r_multiple * risk

        # 🆕 Calculate exit date (actual_entry_day + holding_days)
        exit_date = actual_entry_day + pd.Timedelta(days=holding_days)

        # 🆕 Add position to tracker with exit date (for future scan dates to check)
        self.position_tracker.add_position(
            ticker=ticker,
            entry_date=actual_entry_day,  # Use actual entry day (could be confirmation day)
            entry_price=entry,
            strategy=strategy,
            as_of_date=actual_entry_day,  # 🆕 Check for duplicates as of entry day
            stop_loss=initial_stop,
            target=target,
            exit_date=exit_date  # ← Key: Store when position will close
        )

        return {
            "Date": actual_entry_day,  # Use actual entry day
            "Year": actual_entry_day.year,
            "Ticker": ticker,
            "Strategy": strategy,
            "CrossoverType": crossover_type,  # 🆕 Track which crossover type
            "CrossoverBonus": round(crossover_bonus, 2),  # 🆕 Track bonus points
            "Score": round(score, 2),  # 🆕 Track quality score
            "Entry": round(entry, 2),
            "Exit": round(exit_price, 2),
            "Outcome": outcome,
            "ExitReason": exit_reason,
            "RMultiple": round(r_multiple, 2),
            "PnL_$": round(pnl, 2),
            "HoldingDays": holding_days
        }

        # -------------------------------------------------
    # EVALUATION (SAFE VERSION – NO SYNTAX ERRORS)
    # -------------------------------------------------
    def evaluate(self, df):
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

        # ---- Yearly breakdown (SAFE AGG) ----
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

        yearly.columns = [
            "Trades",
            "Wins",
            "TotalPnL_$",
            "AvgHoldingDays",
        ]

        summary["YearlySummary"] = yearly.to_dict("index")

        # 🆕 ---- Crossover Type Analysis ----
        if "CrossoverType" in df.columns:
            crossover_analysis = (
                df.groupby("CrossoverType")
                .agg({
                    "Ticker": "count",  # Number of trades
                    "Outcome": lambda x: (x == "Win").sum() / len(x) * 100,  # Win rate %
                    "RMultiple": "mean",  # Avg R-multiple
                    "PnL_$": "sum",  # Total PnL
                    "HoldingDays": "mean",  # Avg holding days
                })
                .round(2)
            )

            crossover_analysis.columns = [
                "Trades",
                "WinRate%",
                "AvgRMultiple",
                "TotalPnL_$",
                "AvgHoldingDays",
            ]

            # Sort by total PnL descending to see best performing type
            crossover_analysis = crossover_analysis.sort_values("TotalPnL_$", ascending=False)
            summary["CrossoverAnalysis"] = crossover_analysis.to_dict("index")

        # 🆕 ---- Exit Reason Analysis ----
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


# -------------------------------------------------
# RUN
# -------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Walk-forward backtester with configurable scan frequency")
    parser.add_argument(
        "--scan-frequency",
        type=str,
        default="B",
        choices=["B", "W-MON", "W-TUE", "W-WED", "W-THU", "W-FRI"],
        help="Scan frequency: B (daily), W-MON (weekly Monday), W-FRI (weekly Friday), etc."
    )
    args = parser.parse_args()

    # Example: S&P 500 tickers loaded elsewhere
    # Using local CSV to avoid SSL certificate issues on macOS
    tickers = pd.read_csv("data/sp500_constituents.csv")["Symbol"].tolist()

    # -------------------------------------------------
    # 📥 UPDATE HISTORICAL DATA (INCREMENTAL)
    # -------------------------------------------------
    print("="*60)
    print("📥 CHECKING HISTORICAL DATA")
    print("="*60)

    # 🆕 Check if we already updated today
    if was_update_session_today():
        print("⚡ Data already updated today - skipping download")
        print("   (All tickers were checked/updated earlier today)")
    else:
        print("🔄 Updating historical data for all tickers...")
        updated_count = 0
        skipped_count = 0

        for i, ticker in enumerate(tickers, 1):
            if i % 50 == 0:  # Progress update every 50 tickers
                print(f"\n[Progress: {i}/{len(tickers)} tickers processed]")
            download_ticker(ticker)

        # Also update SPY benchmark data
        print("\n📊 Updating SPY benchmark data...")
        download_ticker("SPY")

        # 🆕 Mark that we completed an update session today
        mark_update_session()
        print("\n✅ Data update complete!")

    print("\n" + "="*60)
    print("🚀 Starting backtest...")
    print("="*60 + "\n")

    bt = WalkForwardBacktester(
        tickers=tickers,
        start_date=BACKTEST_START_DATE,
        rr_ratio=RISK_REWARD_RATIO,
        max_days=MAX_HOLDING_DAYS,
        scan_frequency=args.scan_frequency
    )

    print(f"⚙️  CONFIG: R/R={RISK_REWARD_RATIO}:1, MaxTrades={MAX_TRADES_PER_SCAN}, Capital=${CAPITAL_PER_TRADE:,}/trade, ScanFreq={args.scan_frequency}\n")

    trades = bt.run()

    # Save results to CSV for detailed analysis
    if not trades.empty:
        trades.to_csv("backtest_results.csv", index=False)
        print(f"\n💾 Results saved to: backtest_results.csv")

    stats = bt.evaluate(trades)

    # ========================================
    # PRINT RESULTS
    # ========================================
    print("\n" + "="*80)
    print("📊 WALK-FORWARD BACKTEST SUMMARY")
    print("="*80)

    # Overall metrics
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

    # 🆕 Crossover type analysis
    if "CrossoverAnalysis" in stats:
        print(f"\n🎯 Performance by Crossover Type:")
        print("   " + "-"*76)
        print(f"   {'Type':<18} {'Trades':<8} {'WinRate':<10} {'AvgR':<8} {'TotalPnL':<15} {'AvgDays':<8}")
        print("   " + "-"*76)
        for crossover_type, metrics in stats["CrossoverAnalysis"].items():
            print(f"   {crossover_type:<18} {int(metrics['Trades']):<8} "
                  f"{metrics['WinRate%']:<9.1f}% {metrics['AvgRMultiple']:<8.2f} "
                  f"${metrics['TotalPnL_$']:>12,.2f} {metrics['AvgHoldingDays']:<8.1f}")
        print("   " + "-"*76)

    # 🆕 Exit reason analysis
    if "ExitReasonAnalysis" in stats:
        print(f"\n🚪 Exit Reason Breakdown:")
        print("   " + "-"*60)
        print(f"   {'Reason':<18} {'Count':<8} {'TotalPnL':<15} {'AvgR':<8}")
        print("   " + "-"*60)
        for reason, metrics in stats["ExitReasonAnalysis"].items():
            print(f"   {reason:<18} {int(metrics['Count']):<8} "
                  f"${metrics['TotalPnL_$']:>12,.2f} {metrics['AvgRMultiple']:<8.2f}")
        print("   " + "-"*60)

    print("\n" + "="*80)
