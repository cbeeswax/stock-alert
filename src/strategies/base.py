"""
Base Strategy Class
===================
Abstract base class for all trading strategies.
All strategies should inherit from this class and implement scan().

Lifecycle:
    scanner calls strategy.scan(ticker, df, as_of_date) per ticker
    backtester calls strategy.get_exit_conditions(position, df) per open position
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.

    Required implementation:
        scan()              — per-ticker signal generation
        get_exit_conditions() — per-position exit logic

    Optional override:
        run()               — bulk scan across all tickers (default loops scan())
    """

    name: str = "BaseStrategy"
    description: str = ""

    def __init__(self):
        pass

    @abstractmethod
    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        as_of_date: pd.Timestamp = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single ticker and return a signal dict if conditions are met.

        Args:
            ticker:      Stock symbol
            df:          Daily OHLCV DataFrame (DatetimeIndex, sorted ascending)
            as_of_date:  Date to evaluate as of (use df sliced to this date)

        Returns:
            Signal dict with keys:
                Ticker, Strategy, Close, Entry, StopLoss, Target,
                Score, Volume, Date, Priority, MaxDays
            or None if no signal.
        """
        pass

    def get_exit_conditions(
        self,
        position: Dict[str, Any],
        df: pd.DataFrame,
        current_date: pd.Timestamp,
    ) -> Optional[Dict[str, Any]]:
        """
        Check whether an open position should be exited.

        Args:
            position:     Position dict (entry_price, stop_loss, metadata, etc.)
            df:           Full daily OHLCV DataFrame for the ticker
            current_date: Date being evaluated

        Returns:
            Exit dict with keys: reason, exit_price
            or None to hold.
        """
        return None

    def run(
        self,
        tickers: List[str],
        as_of_date: pd.Timestamp = None,
    ) -> List[Dict[str, Any]]:
        """
        Bulk scan: loops scan() over all tickers.
        Override for strategies that need cross-ticker logic.
        """
        from src.data.market import get_historical_data
        signals = []
        for ticker in tickers:
            try:
                df = get_historical_data(ticker)
                if df is None or df.empty:
                    continue
                if as_of_date is not None:
                    df = df[df.index <= as_of_date]
                if len(df) < 50:
                    continue
                signal = self.scan(ticker, df, as_of_date)
                if signal:
                    signals.append(signal)
            except Exception:
                continue
        return self.format_signals(signals)

    def validate_signal(self, signal: Dict[str, Any]) -> bool:
        required_keys = {"Ticker", "Close", "Score", "Strategy", "Volume", "Date"}
        return all(key in signal for key in required_keys)

    def format_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [s for s in signals if self.validate_signal(s)]

    def build_price_action_context(self, df: pd.DataFrame):
        from src.analysis.price_action_context import analyze_price_action_context

        return analyze_price_action_context(df)

    def enrich_signal_with_price_action_context(
        self,
        signal: Optional[Dict[str, Any]],
        df: pd.DataFrame,
        *,
        context=None,
    ) -> Optional[Dict[str, Any]]:
        if signal is None:
            return None

        from src.analysis.price_action_context import context_to_signal_fields

        computed_context = context if context is not None else self.build_price_action_context(df)
        enriched_signal = dict(signal)
        enriched_signal.update(context_to_signal_fields(computed_context))
        return enriched_signal
