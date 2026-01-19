import pandas as pd
from utils.scanner_walkforward import run_scan_as_of
from utils.pre_buy_check import pre_buy_check
from utils.market_data import get_historical_data

CAPITAL_PER_TRADE = 3_000  # $3k per trade


class WalkForwardBacktester:
    """
    True walk-forward backtester:
    - Daily simulation
    - No look-ahead bias
    - Uses scanner_walkforward
    """

    def __init__(self, tickers, start_date="2022-01-01", rr_ratio=2, max_days=30):
        self.tickers = tickers
        self.start_date = pd.to_datetime(start_date)
        self.rr_ratio = rr_ratio
        self.max_days = max_days

    # -------------------------------------------------
    # MAIN RUN
    # -------------------------------------------------
    def run(self):
        print(f"🚀 Walk-forward backtest from {self.start_date.date()}")

        all_trades = []

        trading_days = pd.date_range(
            self.start_date,
            pd.Timestamp.today(),
            freq="B"
        )

        for day in trading_days:
            print(f" Simulating day from {day}")
            signals = run_scan_as_of(day, self.tickers)
            if not signals:
                continue

            trades = pre_buy_check(signals, rr_ratio=self.rr_ratio)
            if trades.empty:
                continue

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
    from config import SP500_SOURCE
    tickers = pd.read_csv(SP500_SOURCE)["Symbol"].tolist()

    bt = WalkForwardBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        rr_ratio=2,
        max_days=30
    )

    trades = bt.run()
    print(trades)

    stats = bt.evaluate(trades)
    print("\n📊 WALK-FORWARD SUMMARY")
    for k, v in stats.items():
        print(k, ":", v)
