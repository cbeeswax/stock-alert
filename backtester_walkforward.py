import pandas as pd
from scanners.scanner_walkforward import run_scan_as_of
from core.pre_buy_check import pre_buy_check
from utils.market_data import get_historical_data
from scripts.download_history import download_ticker
from config.trading_config import (
    CAPITAL_PER_TRADE,
    RISK_REWARD_RATIO,
    MAX_HOLDING_DAYS,
    BACKTEST_START_DATE,
    SCAN_FREQUENCY,
    MAX_TRADES_PER_SCAN
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
            print(f"📅 [{idx}/{len(scan_dates)}] Simulating {day.date()}")

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

            # 🎯 Take top N trades per day based on config
            if not trades.empty:
                trades = trades.head(MAX_TRADES_PER_SCAN)
                tickers_selected = ", ".join([f"{row['Ticker']}({row['NormalizedScore']:.1f})" for _, row in trades.iterrows()])
                print(f"   🎯 Selected top {len(trades)} trade(s): {tickers_selected}")

            for trade in trades.to_dict("records"):
                result = self._simulate_trade(day, trade)
                if result:
                    all_trades.append(result)

        return pd.DataFrame(all_trades)

    # -------------------------------------------------
    # TRADE SIMULATION
    # -------------------------------------------------
    def _simulate_trade(self, entry_day, trade):
        ticker = trade["Ticker"]
        entry = trade["Entry"]
        stop = trade["StopLoss"]
        target = trade["Target"]
        strategy = trade.get("Strategy", "Unknown")

        df = get_historical_data(ticker)
        if df.empty:
            return None

        # 🔒 Only future candles AFTER entry day
        df = df[df.index > entry_day].iloc[: self.max_days]
        if df.empty:
            return None

        exit_price = df["Close"].iloc[-1]
        outcome = "Loss"
        holding_days = len(df)

        for i, row in enumerate(df.itertuples()):
            if row.Low <= stop:
                exit_price = stop
                outcome = "Loss"
                holding_days = i + 1
                break
            if row.High >= target:
                exit_price = target
                outcome = "Win"
                holding_days = i + 1
                break

        r_multiple = (exit_price - entry) / max(entry - stop, 0.01)

        position_size = CAPITAL_PER_TRADE / entry
        risk = position_size * abs(entry - stop)
        pnl = r_multiple * risk

        return {
            "Date": entry_day,
            "Year": entry_day.year,
            "Ticker": ticker,
            "Strategy": strategy,
            "Entry": round(entry, 2),
            "Exit": round(exit_price, 2),
            "Outcome": outcome,
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

        return summary


# -------------------------------------------------
# RUN
# -------------------------------------------------
if __name__ == "__main__":
    # Example: S&P 500 tickers loaded elsewhere
    # Using local CSV to avoid SSL certificate issues on macOS
    tickers = pd.read_csv("data/sp500_constituents.csv")["Symbol"].tolist()

    # -------------------------------------------------
    # 📥 UPDATE HISTORICAL DATA (INCREMENTAL)
    # -------------------------------------------------
    print("="*60)
    print("📥 UPDATING HISTORICAL DATA FOR ALL TICKERS")
    print("="*60)
    updated_count = 0
    skipped_count = 0

    for i, ticker in enumerate(tickers, 1):
        if i % 50 == 0:  # Progress update every 50 tickers
            print(f"\n[Progress: {i}/{len(tickers)} tickers processed]")
        download_ticker(ticker)

    # Also update SPY benchmark data
    print("\n📊 Updating SPY benchmark data...")
    download_ticker("SPY")

    print("\n" + "="*60)
    print("✅ DATA UPDATE COMPLETE! Starting backtest...")
    print("="*60 + "\n")

    bt = WalkForwardBacktester(
        tickers=tickers,
        start_date=BACKTEST_START_DATE,
        rr_ratio=RISK_REWARD_RATIO,
        max_days=MAX_HOLDING_DAYS,
        scan_frequency=SCAN_FREQUENCY
    )

    print(f"⚙️  CONFIG: R/R={RISK_REWARD_RATIO}:1, MaxTrades={MAX_TRADES_PER_SCAN}, Capital=${CAPITAL_PER_TRADE:,}/trade\n")

    trades = bt.run()
    print(trades)

    stats = bt.evaluate(trades)
    print("\n📊 WALK-FORWARD SUMMARY")
    for k, v in stats.items():
        print(k, ":", v)
