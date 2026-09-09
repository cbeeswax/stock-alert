"""Live exit monitoring for the supported position strategies."""

from __future__ import annotations

import pandas as pd

from src.config.settings import (
    POSITION_PARTIAL_SIZE,
    POSITION_PYRAMID_MAX_ADDS,
    POSITION_PYRAMID_PULLBACK_ATR,
    POSITION_PYRAMID_R_TRIGGER,
    RS_RANKER_MAX_DAYS,
    RS_RANKER_PARTIAL_R,
)
from src.data.market import get_historical_data


def calculate_atr(df, period=20):
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"] - df["Close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1] if not tr.empty else 0


def _action(ticker, action_type, reason, current_r, days_held, entry_price, current_price, urgency):
    return {
        "ticker": ticker, "type": action_type, "reason": reason,
        "action": f"EXIT ALL at ${current_price:.2f}", "current_r": current_r,
        "days_held": days_held, "urgency": urgency, "entry_price": entry_price,
        "current_price": current_price,
    }


def monitor_positions(position_tracker):
    """Return exit, partial-profit, pyramid, and warning actions for open positions."""
    positions = position_tracker.get_all_positions()
    actions = {"exits": [], "partials": [], "pyramids": [], "warnings": []}
    today = pd.Timestamp.today()

    for ticker, position in positions.items():
        try:
            data = get_historical_data(ticker)
            if data is None or data.empty or len(data) < 100:
                actions["warnings"].append({"ticker": ticker, "type": "DATA_ERROR", "message": f"Unable to fetch data for {ticker}"})
                continue
            data = data.copy()
            current_close = float(data["Close"].iloc[-1])
            current_high = float(data["High"].iloc[-1])
            current_low = float(data["Low"].iloc[-1])
            entry_price = float(position["entry_price"])
            entry_date = pd.to_datetime(position["entry_date"])
            strategy = position.get("strategy", "Unknown")
            stop_loss = float(position.get("stop_loss", position.get("stop_price", 0)) or 0)
            direction = position.get("direction", "LONG")
            days_held = (today - entry_date).days

            if strategy == "Streak_Position":
                if pd.Timestamp(data.index[-1]).normalize() >= entry_date.normalize():
                    risk = max(entry_price * 0.01, 0.01)
                    streak_r = (entry_price - current_close) / risk if direction == "SHORT" else (current_close - entry_price) / risk
                    actions["exits"].append(_action(ticker, "NEXT_SESSION_CLOSE", "Streak strategy exits at the next trading session close", streak_r, days_held, entry_price, current_close, "HIGH"))
                continue

            risk = max(abs(entry_price - stop_loss) if stop_loss else entry_price * 0.02, entry_price * 0.01)
            current_r = (entry_price - current_close) / risk if direction == "SHORT" else (current_close - entry_price) / risk
            stop_hit = (direction == "LONG" and stop_loss > 0 and current_low <= stop_loss) or (direction == "SHORT" and stop_loss > 0 and current_high >= stop_loss)
            if stop_hit:
                actions["exits"].append(_action(ticker, "STOP_LOSS", f"Stop loss hit at ${stop_loss:.2f}", -1.0, days_held, entry_price, current_close, "IMMEDIATE"))
                continue

            max_days = RS_RANKER_MAX_DAYS if strategy == "RelativeStrength_Ranker_Position" else int(position.get("max_days", 120))
            if strategy == "RelativeStrength_Ranker_Position" and not position.get("partial_exited", False) and current_r >= RS_RANKER_PARTIAL_R:
                actions["partials"].append({
                    **_action(ticker, "PARTIAL_PROFIT", f"Hit +{RS_RANKER_PARTIAL_R}R profit target", current_r, days_held, entry_price, current_close, "HIGH"),
                    "action": f"EXIT {int(POSITION_PARTIAL_SIZE * 100)}% at ${current_close:.2f}, keep 70% runner",
                })
                position["partial_exited"] = True
                position_tracker._save_positions()

            exit_condition = None
            if strategy == "RallyPattern_Position":
                from src.strategies.rally_pattern import RallyPatternPosition
                exit_condition = RallyPatternPosition().get_exit_conditions(position, data, today)
            elif strategy == "RelativeStrength_Ranker_Position":
                data["EMA21"] = data["Close"].ewm(span=21).mean()
                data["MA100"] = data["Close"].rolling(100).mean()
                trail = data["EMA21"].iloc[-1] if days_held <= 60 and current_r >= 0.75 else data["MA100"].iloc[-1] if days_held > 60 else None
                needed = 5 if days_held <= 60 else 8
                closes_below = int(position.get("closes_below_trail", 0))
                if trail is not None and pd.notna(trail):
                    closes_below = closes_below + 1 if current_close < trail else 0
                    position["closes_below_trail"] = closes_below
                    position_tracker._save_positions()
                    if closes_below >= needed:
                        exit_condition = {"reason": "EMA21_TRAIL_EARLY" if days_held <= 60 else "MA100_TRAIL_LATE"}

            if exit_condition:
                actions["exits"].append(_action(ticker, str(exit_condition["reason"]).upper(), str(exit_condition["reason"]), current_r, days_held, entry_price, float(exit_condition.get("exit_price", current_close)), "HIGH"))
                continue

            pyramid_adds = position.get("pyramid_adds", position.get("pyramids_added", 0))
            pyramid_count = len(pyramid_adds) if isinstance(pyramid_adds, list) else pyramid_adds
            if not pyramid_count and days_held >= max_days:
                actions["exits"].append(_action(ticker, f"TIME_STOP_{max_days}d", f"Held for {days_held} days (max: {max_days})", current_r, days_held, entry_price, current_close, "MEDIUM"))
                continue

            if strategy != "Streak_Position" and current_r >= POSITION_PYRAMID_R_TRIGGER and pyramid_count < POSITION_PYRAMID_MAX_ADDS:
                ema21 = data["Close"].ewm(span=21).mean().iloc[-1]
                if abs(current_close - ema21) <= POSITION_PYRAMID_PULLBACK_ATR * calculate_atr(data):
                    actions["pyramids"].append({
                        "ticker": ticker, "type": "PYRAMID", "reason": f"At +{current_r:.2f}R, pulled back to EMA21",
                        "action": f"ADD 50% position at ${current_close:.2f}", "current_r": current_r,
                        "days_held": days_held, "urgency": "LOW", "entry_price": entry_price, "current_price": current_close,
                    })
        except Exception as exc:
            actions["warnings"].append({"ticker": ticker, "type": "MONITORING_ERROR", "message": f"Error monitoring {ticker}: {exc}"})
    return actions
