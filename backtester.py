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
        ema_list, high_list, watchlist_highs, consolidation_list, rs_list = run_scan(
            test_mode=test_mode
        )

        # Ensure Strategy field exists (safety for backtest)
        for lst, name in [
            (ema_list, "EMA Crossover"),
            (high_list, "52-Week High"),
            (consolidation_list, "Consolidation Breakout"),
            (rs_list, "Relative Strength"),
        ]:
            for s in lst:
                s.setdefault("Strategy", name)

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

            outcome_data = self._simulate_trade(
                hist_df,
                entry,
                stop,
                target,
                max_days=self.max_days
            )

            # ✅ CRITICAL FIX: build dict, do NOT update Series
            trade_dict = trade.to_dict()
            trade_dict.update(outcome_data)
            trade_dict["Strategy"] = strategy

            trades_outcomes.append(trade_dict)

        return pd.DataFrame(trades_outcomes)

    def _simulate_trade(self, df, entry, stop, target, max_days=30):
        """
        Simulate trade using historical OHLC with realistic exits.
        """
        df = df.copy().iloc[:max_days]

        # MAE / MFE
        mae = (entry - df["Low"]).max()
        mfe = (df["High"] - entry).max()

        exit_price = df["Close"].iloc[-1]
        outcome = "Win" if exit_price >= entry else "Loss"

        for _, row in df.iterrows():
            if row["Low"] <= stop:
                exit_price = stop
                outcome = "Loss"
                break
            if row["High"] >= target:
                exit_price = target
                outcome = "Win"
                break

        r_multiple = (exit_price - entry) / max(entry - stop, 0.01)

        return {
            "MAE": round(mae, 2),
            "MFE": round(mfe, 2),
            "ExitPrice": round(exit_price, 2),
            "Outcome": outcome,
            "RMultiple": round(r_multiple, 2),
        }

    def evaluate(self, trades_df):
        """
        Summarize backtest performance.
        """
        if trades_df.empty or "Outcome" not in trades_df.columns:
            return "No completed trades with outcomes"

        total_trades = len(trades_df)
        wins = int((trades_df["Outcome"] == "Win").sum())
        losses = total_trades - wins
        win_rate = wins / total_trades * 100
        avg_r_multiple = trades_df["RMultiple"].mean()

        strategy_summary = (
            trades_df
            .groupby("Strategy")["RMultiple"]
            .agg(count="count", avg_r="mean")
            .to_dict(orient="index")
        )

        return {
            "TotalTrades": total_trades,
            "Wins": wins,
            "Losses": losses,
            "WinRate%": round(win_rate, 2),
            "AvgRMultiple": round(avg_r_multiple, 2),
            "StrategySummary": strategy_summary,
        }


if __name__ == "__main__":
    bt = Backtester(start_date="2022-01-01", rr_ratio=2)
    trades = bt.run(test_mode=False)
    print(trades)
    summary = bt.evaluate(trades)
    print("\n📊 Backtest Summary:", summary)
