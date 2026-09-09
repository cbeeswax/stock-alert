"""Signal normalization and validation for supported strategies."""

from __future__ import annotations

import pandas as pd

from src.config.settings import MIN_LIQUIDITY_USD, RISK_REWARD_RATIO
from src.data.market import get_historical_data
from src.scanning.rs_bought_tracker import StrategyStateTracker

RALLY_FAILURE_EXIT_REASONS = {
    "EXPANSION_FAILED_FOLLOWTHROUGH", "ZONE_SUPPORT_FAIL",
    "POWER_BREAKOUT_FAILED_FOLLOWTHROUGH", "BB_MICRO_SUPPORT_FAIL",
    "MEDIUM_CONFIRM_FAILURE",
}
RALLY_INVALIDATION_SETUP_TYPES = {
    "breakout", "power_breakout", "expansion_leader",
    "emerging_leader_breakout", "emerging_leader_ignition",
}
RALLY_FAILURE_COOLDOWN_DAYS = 3
RALLY_RETRY_TOLERANCE_PCT = 0.01
RALLY_FRESH_BREAKOUT_BUFFER_PCT = 0.02

STRATEGY_METRICS = {
    "RelativeStrength_Ranker_Position": (0.30, 2.0, -1.0),
    "RallyPattern_Position": (0.33, 2.0, -1.0),
    "Streak_Position": (0.50, 1.0, -1.0),
}
SCORE_RANGES = {
    "RelativeStrength_Ranker_Position": (0, 100),
    "RallyPattern_Position": (45, 100),
    "Streak_Position": (0, 100),
}
PRIORITY = {
    "RallyPattern_Position": 3,
    "RelativeStrength_Ranker_Position": 2,
    "Streak_Position": 4,
}


def _rally_failed_setup_invalidated(signal: dict, tracker: StrategyStateTracker, *, as_of_date=None) -> bool:
    if signal.get("Strategy") != "RallyPattern_Position":
        return False
    if str(signal.get("SetupType", "none")) not in RALLY_INVALIDATION_SETUP_TYPES:
        return False
    ticker = signal.get("Ticker")
    if not ticker:
        return False
    prior_state = tracker.get_ticker_info(str(ticker))
    if not prior_state or prior_state.get("status") != "closed":
        return False
    if prior_state.get("exit_reason") not in RALLY_FAILURE_EXIT_REASONS:
        return False
    if tracker.can_buy_again(ticker, cooldown_days=RALLY_FAILURE_COOLDOWN_DAYS, as_of_date=as_of_date):
        return False

    current_trigger = float(signal.get("TriggerLevel", 0.0) or 0.0)
    failed_trigger = float(prior_state.get("trigger_level", 0.0) or 0.0)
    current_entry = float(signal.get("Entry", signal.get("Price", 0.0)) or 0.0)
    failed_entry = float(prior_state.get("entry_price", 0.0) or 0.0)
    same_trigger = current_trigger > 0 and failed_trigger > 0 and abs(current_trigger - failed_trigger) / max(current_trigger, failed_trigger) <= RALLY_RETRY_TOLERANCE_PCT
    same_entry = current_entry > 0 and failed_entry > 0 and abs(current_entry - failed_entry) / max(current_entry, failed_entry) <= RALLY_RETRY_TOLERANCE_PCT
    fresh_breakout = (
        current_trigger > 0 and failed_trigger > 0 and current_trigger >= failed_trigger * (1 + RALLY_FRESH_BREAKOUT_BUFFER_PCT)
    ) or (
        current_entry > 0 and failed_entry > 0 and current_entry >= failed_entry * (1 + RALLY_FRESH_BREAKOUT_BUFFER_PCT)
    )
    return (same_trigger or same_entry) and not fresh_breakout


def _filter_failed_rally_retries(combined_signals, *, as_of_date=None, strategy_trackers=None):
    trackers = strategy_trackers or {}
    tracker = trackers.get("RallyPattern_Position")
    if tracker is None and any(signal.get("Strategy") == "RallyPattern_Position" for signal in combined_signals):
        tracker = StrategyStateTracker(strategy_name="RallyPattern_Position")
    if tracker is None:
        return combined_signals
    return [
        signal for signal in combined_signals
        if not _rally_failed_setup_invalidated(signal, tracker, as_of_date=as_of_date)
    ]


def calculate_atr(df, period=14):
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"] - df["Close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1] if not tr.empty else 0


def normalize_score(score, strategy):
    low, high = SCORE_RANGES.get(strategy, (0, 100))
    quality = max(0, min(1, (score - low) / max(high - low, 1)))
    win_rate, avg_win_r, avg_loss_r = STRATEGY_METRICS.get(strategy, (0.30, 1.5, -1.0))
    expectancy = (win_rate * avg_win_r) - ((1 - win_rate) * abs(avg_loss_r))
    return round(quality * expectancy * 10, 2)


def pre_buy_check(combined_signals, rr_ratio=None, benchmark="SPY", as_of_date=None, strategy_trackers=None):
    """Deduplicate supported signals and normalize them into executable trades."""
    rr_ratio = rr_ratio or RISK_REWARD_RATIO
    combined_signals = _filter_failed_rally_retries(
        combined_signals, as_of_date=as_of_date, strategy_trackers=strategy_trackers
    )
    prediction_signals = [s for s in combined_signals if s.get("Strategy") == "Streak_Position"]
    best_signal = {}
    for signal in combined_signals:
        if signal.get("Strategy") == "Streak_Position":
            continue
        ticker = signal["Ticker"]
        if ticker not in best_signal or PRIORITY.get(signal.get("Strategy"), 0) > PRIORITY.get(best_signal[ticker].get("Strategy"), 0):
            best_signal[ticker] = signal

    trades = []
    for signal in list(best_signal.values()) + prediction_signals:
        ticker = signal["Ticker"]
        strategy = signal["Strategy"]
        data = get_historical_data(ticker)
        if data is None or data.empty:
            continue
        if not isinstance(data.index, pd.DatetimeIndex):
            data = data.copy()
            data.index = pd.to_datetime(data.index, errors="coerce")
            data = data[data.index.notna()]
        if as_of_date is not None:
            data = data[data.index <= as_of_date]
        if len(data) < 60:
            continue
        data = data.tail(60)
        if (data["Close"] * data["Volume"]).rolling(20).mean().iloc[-1] < MIN_LIQUIDITY_USD:
            continue

        entry = float(signal.get("Price") or signal.get("Entry") or data["Close"].iloc[-1])
        stop = signal.get("StopLoss", signal.get("StopPrice"))
        if stop is None or pd.isna(stop) or float(stop) <= 0:
            atr = calculate_atr(data) or entry * 0.02
            stop = entry - 2 * atr
        stop = float(stop)
        direction = signal.get("Direction", "LONG")
        if (direction == "LONG" and stop >= entry) or (direction == "SHORT" and stop <= entry):
            continue
        risk = max(abs(entry - stop), entry * 0.01)
        target = signal.get("Target")
        if target is None or pd.isna(target):
            target = entry + (rr_ratio * risk if direction == "LONG" else -rr_ratio * risk)
        target = float(target)
        if target <= 0:
            continue
        win_rate, avg_win_r, avg_loss_r = STRATEGY_METRICS.get(strategy, (0.30, 1.5, -1.0))
        expectancy = (win_rate * avg_win_r) - ((1 - win_rate) * abs(avg_loss_r))
        trade = {
            "Ticker": ticker, "Strategy": strategy, "Entry": round(entry, 2),
            "StopLoss": round(stop, 2), "Target": round(target, 2),
            "Score": signal.get("Score", 0), "FinalScore": normalize_score(signal.get("Score", 0), strategy),
            "Expectancy": round(expectancy, 2), "Direction": direction,
            "Priority": signal.get("Priority"), "MaxDays": signal.get("MaxDays"),
            "RiskPerShare": round(float(signal.get("RiskPerShare", risk)), 2),
        }
        for key in (
            "ZoneSupport", "ZoneResistance", "SetupType", "SignalType", "LeadershipStage",
            "PositionSizeMultiplier", "EntryScore", "TriggerLevel", "EntryTiming", "Prediction",
            "ProbabilityNextGreen", "PredictionReason", "CandleDirection", "StreakLength", "RSI14",
            "PercentB", "VolumeRatio20", "Return5", "Return20", "EMA20", "EMA50", "QQQRegime",
        ):
            trade[key] = signal.get(key)
        trades.append(trade)
    return pd.DataFrame(trades).sort_values("FinalScore", ascending=False) if trades else pd.DataFrame()
