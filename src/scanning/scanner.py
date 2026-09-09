"""Strategy scanner for the supported position strategies."""

from __future__ import annotations

import os
import traceback

import pandas as pd

from src.config.settings import POSITION_MAX_PER_STRATEGY
from src.data.market import get_historical_data
from src.scanning.rs_bought_tracker import RSBoughtTracker
from src.strategies.registry import StrategyRegistry


def _backtest_debug_enabled() -> bool:
    return os.getenv("STOCK_ALERT_BACKTEST_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _report_registry_strategy_exception(context: str, name: str, exc: Exception) -> None:
    if _backtest_debug_enabled():
        print(f"❌ [registry-strategy] {context} failed for {name}: {exc}")
        traceback.print_exc()


def _get_active_registry_strategies():
    """Return instantiated strategies enabled by ``POSITION_MAX_PER_STRATEGY``."""
    active = []
    for name in StrategyRegistry.list_available():
        if POSITION_MAX_PER_STRATEGY.get(name, 0) <= 0:
            continue
        try:
            active.append((name, StrategyRegistry.create(name)))
        except Exception as exc:
            _report_registry_strategy_exception("create", name, exc)
    return active


def _run_relative_strength(strategy, tickers, as_of_date, bought_tracker):
    """Scan RS candidates while preserving its position/recent-stop exclusion."""
    signals = []
    for ticker in tickers:
        if bought_tracker.is_bought(ticker) or bought_tracker.has_recent_stop(
            ticker, trading_days_lookback=5, as_of_date=as_of_date
        ):
            continue
        try:
            data = get_historical_data(ticker)
            if data is None or data.empty:
                continue
            if not isinstance(data.index, pd.DatetimeIndex):
                data = data.copy()
                data.index = pd.to_datetime(data.index, errors="coerce")
                data = data[data.index.notna()]
            data = data[data.index <= as_of_date]
            signal = strategy.scan(ticker, data, as_of_date)
            if signal is not None:
                signals.append(signal)
        except Exception as exc:
            _report_registry_strategy_exception("scan", strategy.name, exc)
    return signals


def run_scan_as_of(as_of_date, tickers, rs_bought_tracker=None):
    """Run every enabled supported strategy without look-ahead data."""
    scan_date = pd.Timestamp(as_of_date)
    rs_tracker = rs_bought_tracker or RSBoughtTracker()
    signals = []

    for name, strategy in _get_active_registry_strategies():
        try:
            if name == "RelativeStrength_Ranker_Position":
                strategy_signals = _run_relative_strength(strategy, tickers, scan_date, rs_tracker)
            else:
                strategy_signals = strategy.run(tickers, as_of_date=scan_date)
            if strategy_signals:
                signals.extend(strategy_signals)
        except Exception as exc:
            _report_registry_strategy_exception("run", name, exc)

    return sorted(
        signals,
        key=lambda signal: (signal.get("Priority", 0), -float(signal.get("Score", 0))),
    )
