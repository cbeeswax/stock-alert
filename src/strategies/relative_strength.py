import pandas as pd
from typing import Optional, Dict, Any
from src.data.market import get_historical_data
from src.data.indicators import compute_ema_incremental
from src.strategies.base import BaseStrategy


def check_relative_strength(ticker, benchmark_df, lookback=50):
    """
    Checks if a stock is outperforming a benchmark (e.g., SPY/Nasdaq)
    over a lookback period.

    Returns a dict with performance metrics and a score if outperforming,
    else returns None.
    """
    try:
        stock_df = get_historical_data(ticker)
        if stock_df.empty or "Close" not in stock_df.columns:
            return None

        stock_df = stock_df.copy()
        stock_df["Close"] = pd.to_numeric(stock_df["Close"], errors="coerce")
        stock_df.dropna(subset=["Close"], inplace=True)

        benchmark_df = benchmark_df.copy()
        benchmark_df["Close"] = pd.to_numeric(benchmark_df["Close"], errors="coerce")
        benchmark_df.dropna(subset=["Close"], inplace=True)

        if len(stock_df) < lookback or len(benchmark_df) < lookback:
            return None

        stock_start = float(stock_df["Close"].iloc[-lookback])
        stock_end = float(stock_df["Close"].iloc[-1])
        benchmark_start = float(benchmark_df["Close"].iloc[-lookback])
        benchmark_end = float(benchmark_df["Close"].iloc[-1])

        stock_ret = (stock_end - stock_start) / stock_start
        benchmark_ret = (benchmark_end - benchmark_start) / benchmark_start
        rs_ratio = stock_ret - benchmark_ret

        if rs_ratio <= 0:
            return None

        score = round(min(rs_ratio * 100, 10), 2)

        ema_df = compute_ema_incremental(ticker)
        ema20 = ema50 = ema200 = 0
        if not ema_df.empty and len(ema_df) > 0:
            ema20 = ema_df["EMA20"].iloc[-1] if "EMA20" in ema_df.columns else 0
            ema50 = ema_df["EMA50"].iloc[-1] if "EMA50" in ema_df.columns else 0
            ema200 = ema_df["EMA200"].iloc[-1] if "EMA200" in ema_df.columns else 0

        return {
            "Ticker": ticker,
            "StockReturn%": round(stock_ret * 100, 2),
            "BenchmarkReturn%": round(benchmark_ret * 100, 2),
            "RS%": round(rs_ratio * 100, 2),
            "Score": score,
            "EMA20": ema20,
            "EMA50": ema50,
            "EMA200": ema200
        }

    except Exception as e:
        print(f"⚠️ [relative_strength] Error for {ticker}: {e}")
        return None


class RelativeStrengthRanker(BaseStrategy):
    """
    RelativeStrength_Ranker_Position as a proper BaseStrategy subclass.

    Entry criteria:
        - Tech/Comm Services sector only
        - 6-month RS vs QQQ >= +30%
        - Price > MA50 > MA100 > MA200 (stacked)
        - ADX(14) >= 30
        - New 3-month high OR pullback to EMA21 + breakout above prior high
    Stop: 4.5 × ATR(20) below entry
    Exit: price closes below MA100 for 10 consecutive days
    """

    name = "RelativeStrength_Ranker_Position"
    description = "Tech/Comm RS leaders with strong trend and momentum"

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        as_of_date=None,
    ) -> Optional[Dict[str, Any]]:
        from src.ta.indicators.trend import adx_latest
        from src.ta.indicators.volatility import atr_latest
        from src.data.universe import get_ticker_sector
        from src.config.settings import (
            RS_RANKER_SECTORS, RS_RANKER_RS_THRESHOLD,
            RS_RANKER_STOP_ATR_MULT, RS_RANKER_MAX_DAYS,
            UNIVERSAL_ADX_MIN, REGIME_INDEX,
            STRATEGY_PRIORITY,
        )

        try:
            if len(df) < 252:
                return None

            sector = get_ticker_sector(ticker)
            if sector not in RS_RANKER_SECTORS:
                return None

            close = df["Close"]
            high = df["High"]
            volume = df["Volume"]
            last_close = float(close.iloc[-1])

            # Volatility filter (skip whipsawing stocks)
            vol_20d = close.pct_change().rolling(20).std().iloc[-1]
            if vol_20d > 0.04:
                return None

            # MA stack
            ma50 = close.rolling(50).mean()
            ma100 = close.rolling(100).mean()
            ma200 = close.rolling(200).mean()
            stacked = (
                last_close > ma50.iloc[-1]
                and ma50.iloc[-1] > ma100.iloc[-1]
                and ma100.iloc[-1] > ma200.iloc[-1]
            )
            if not stacked:
                return None

            # RS vs QQQ (6-month)
            qqq_df = get_historical_data(REGIME_INDEX)
            if qqq_df.empty or len(qqq_df) < 126:
                return None
            if as_of_date is not None:
                qqq_df = qqq_df[qqq_df.index <= pd.Timestamp(as_of_date)]
            stock_ret = (last_close / float(close.iloc[-126])) - 1
            qqq_ret = (float(qqq_df["Close"].iloc[-1]) / float(qqq_df["Close"].iloc[-126])) - 1
            rs_6mo = stock_ret - qqq_ret
            if rs_6mo < RS_RANKER_RS_THRESHOLD:
                return None

            # ADX
            if adx_latest(df) < UNIVERSAL_ADX_MIN:
                return None

            # Trigger: new 3-month high OR pullback to EMA21 + close above prior high
            ema21 = close.ewm(span=21).mean()
            high_3mo = high.rolling(63).max().iloc[-1]
            is_3mo_high = last_close >= high_3mo * 0.995
            near_ema21 = abs(last_close - ema21.iloc[-1]) / ema21.iloc[-1] < 0.02
            above_prior_high = len(high) >= 2 and last_close > float(high.iloc[-2])
            pullback_breakout = near_ema21 and above_prior_high

            if not (is_3mo_high or pullback_breakout):
                return None

            # Liquidity
            avg_vol = float(volume.rolling(20).mean().iloc[-1])
            dollar_vol = avg_vol * last_close
            if dollar_vol < 30_000_000:
                return None

            atr20 = atr_latest(df, 20)
            stop = last_close - (RS_RANKER_STOP_ATR_MULT * atr20)
            score = min((rs_6mo / RS_RANKER_RS_THRESHOLD) * 100, 100)

            signal = {
                "Ticker": ticker,
                "Strategy": self.name,
                "Priority": STRATEGY_PRIORITY.get(self.name, 2),
                "Price": round(last_close, 2),
                "Close": round(last_close, 2),
                "Entry": round(last_close, 2),
                "StopLoss": round(stop, 2),
                "StopPrice": round(stop, 2),
                "Target": None,  # No fixed target — exit managed by MA100 trail
                "ATR20": round(atr20, 2),
                "RS_6mo": round(rs_6mo * 100, 2),
                "Score": round(score, 2),
                "Volume": int(volume.iloc[-1]),
                "Date": as_of_date or df.index[-1],
                "AsOfDate": as_of_date or df.index[-1],
                "MaxDays": RS_RANKER_MAX_DAYS,
            }
            return self.enrich_signal_with_price_action_context(signal, df)

        except Exception:
            return None

    def get_exit_conditions(self, position, df, current_date):
        """Exit when price closes below MA100 for 10 days, or stop is hit."""
        from src.config.settings import RS_RANKER_TRAIL_MA, RS_RANKER_TRAIL_DAYS
        try:
            close = df["Close"]
            last_close = float(close.iloc[-1])
            stop = position.get("stop_loss", 0)

            if stop and last_close <= stop:
                return {"reason": "stop_loss", "exit_price": stop}

            ma = close.rolling(RS_RANKER_TRAIL_MA).mean()
            if len(ma.dropna()) >= RS_RANKER_TRAIL_DAYS:
                below = (close.iloc[-RS_RANKER_TRAIL_DAYS:] < ma.iloc[-RS_RANKER_TRAIL_DAYS:]).all()
                if below:
                    return {"reason": f"trailing_ma{RS_RANKER_TRAIL_MA}", "exit_price": last_close}
        except Exception:
            pass
        return None
