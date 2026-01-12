import pandas as pd
from datetime import datetime
from utils.scanner import run_scan
from utils.pre_buy_check import pre_buy_check
from utils.market_data import get_historical_data

class Backtester:
    """
    Historical backtester using your scan + pre-buy logic.
    Computes MAE, MFE, R-multiple, win-rate per strategy.
    """

    def __init__(self, start_date="2022-01-01", rr_ratio=2, max_days=30):
        self.start_date = pd.to_datetime(start_date)
        self.rr_ratio = rr_ratio
        self.max_days = max_days  # Max holding period per trade

    def run(self, test_mode=False):
        """
        Runs backtest for all tickers.
        Returns DataFrame with trades + outcomes.
        """
        print(f"🚀 Running backtest from {self.start_date.date()}...")

        # Run scan (simulate past signals)
        ema_list, high_list, watchlist_highs, consolidation_list, rs_list = run_scan(test_mode=test_mode)

        # Add Strategy field if missing (for safety)
        for lst, name in [
            (ema_list, "EMA Crossover"),
            (high_list, "52-Week High"),
            (consolidation_list, "Consolidation Breakout"),
            (rs_list, "Relative Strength"),
        ]:
            for s in lst:
                if "Strategy" not in s:
                    s["Strategy"] = name

        # Combine all signals
        combined_signals = ema_list + high_list + consolidation_list + rs_list
        trades_df = pre_buy_check(combined_signals, rr_ratio=self.rr_ratio)

        if trades_df.empty:
            print("⚠️ No trades generated for backtest.")
            return trades_df

        # Simulate trades using historical OHLC
        trades_outcomes = []
        for _, trade in trades_df.iterrows():
            ticker = trade["Ticker"]
            entry = trade["Entry"]
            stop = trade["StopLoss"]
            target = trade["Target"]
            strategy = trade.get("Strategy", "Unknown")

            hist_df = get_historical_data(ticker)
            if hist_df.empty or "Close" not in hist_df.columns:
                continue

            # Filter for backtest period
            hist_df = hist_df[hist_df.index >= self.start_date]
            if hist_df.empty:
                continue

            outcome_data = self._simulate_trade(hist_df, entry, stop, target, max_days=self.max_days)
            trade.update(outcome_data)
            trade["Strategy"] = strategy
            trades_outcomes.append(trade)

        return pd.DataFrame(trades_outcomes)

    def _simulate_trade(self, df, entry, stop, target, max_days=30):
        """
        Simulate trade using historical OHLC with realistic intraday exits.
        - Exits immediately if target or stop is hit
        - Exits at max_days if neither target nor stop hit
        Returns MAE, MFE, final R-multiple, outcome (win/loss)
        """
        df = df.copy()
        df = df.iloc[:max_days]  # limit max holding period

        # Track MAE / MFE during the trade
        adverse_moves = entry - df["Low"]
        favorable_moves = df["High"] - entry
        mae = adverse_moves.max()
        mfe = favorable_moves.max()

        # Default exit at last available close (time stop)
        exit_price = df["Close"].iloc[-1]
        outcome = "Win" if exit_price >= entry else "Loss"

        for idx, row in df.iterrows():
            if row["Low"] <= stop:
                exit_price = stop
                outcome = "Loss"
                break
            elif row["High"] >= target:
                exit_price = target
                outcome = "Win"
                break

        r_multiple = (exit_price - entry) / max(entry - stop, 0.01)  # avoid zero division

        return {
            "MAE": round(mae, 2),
            "MFE": round(mfe, 2),
            "ExitPrice": round(exit_price, 2),
            "Outcome": outcome,
            "RMultiple": round(r_multiple, 2)
        }

    def evaluate(self, trades_df):
        """
        Summarize backtest performance.
        """
        if trades_df.empty:
            return "No trades executed"

        total_trades = len(trades_df)
        wins = sum(trades_df["Outcome"] == "Win")
        losses = total_trades - wins
        win_rate = wins / total_trades * 100
        avg_r_multiple = trades_df["RMultiple"].mean()

        # Strategy-wise summary
        strategy_summary = trades_df.groupby("Strategy")["RMultiple"].agg(
            count="count", avg_r="mean"
        ).to_dict(orient="index")

        return {
            "TotalTrades": total_trades,
            "Wins": wins,
            "Losses": losses,
            "WinRate%": round(win_rate, 2),
            "AvgRMultiple": round(avg_r_multiple, 2),
            "StrategySummary": strategy_summary
        }


if __name__ == "__main__":
    bt = Backtester(start_date="2022-01-01", rr_ratio=2)
    trades = bt.run(test_mode=False)
    print(trades)
    summary = bt.evaluate(trades)
    print("\n📊 Backtest Summary:", summary)
