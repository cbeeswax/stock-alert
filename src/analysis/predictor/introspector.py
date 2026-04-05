"""
Evaluate closed-week outcomes and adapt indicator weights.

After each week closes (Friday), we:
  1. Compute actual P&L for each pick (entry → Friday close, or stop if hit)
  2. Classify each as WIN / LOSS / STOPPED
  3. Identify which signal categories were most/least predictive
  4. Update weights in data/predictor/weights.json
  5. Write a qualitative learning note to data/predictor/learning_log.json
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from .scorer import load_weights, save_weights, _normalize

LEARNING_LOG_FILE = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data", "predictor", "learning_log.json"
    )
)


def _load_log() -> list:
    if os.path.exists(LEARNING_LOG_FILE):
        with open(LEARNING_LOG_FILE) as f:
            return json.load(f)
    return []


def _save_log(log: list) -> None:
    os.makedirs(os.path.dirname(LEARNING_LOG_FILE), exist_ok=True)
    with open(LEARNING_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def evaluate_week(
    predictions: list[dict],
    daily_df: dict[str, pd.DataFrame],
    week_start: str,
    week_end: str,
) -> list[dict]:
    """
    Evaluate each prediction against actual price action.

    Parameters
    ----------
    predictions : list of dicts from engine.generate_predictions()
    daily_df    : dict ticker -> daily OHLCV DataFrame
    week_start  : ISO date string for Monday (entry day)
    week_end    : ISO date string for Friday (close day)

    Returns
    -------
    list of outcome dicts with added keys:
        exit_price, exit_reason (WIN/LOSS/STOPPED/NO_DATA), pnl_pct, hit_target, hit_stop
    """
    ws = pd.Timestamp(week_start)
    we = pd.Timestamp(week_end)
    outcomes = []

    for pred in predictions:
        ticker = pred["ticker"]
        entry = pred["entry"]
        stop = pred["stop"]
        target = pred["target"]
        daily = daily_df.get(ticker, pd.DataFrame())

        if daily.empty:
            outcomes.append({**pred, "exit_price": None, "exit_reason": "NO_DATA", "pnl_pct": 0.0, "hit_target": False, "hit_stop": False})
            continue

        week_bars = daily[(daily.index >= ws) & (daily.index <= we)]
        if week_bars.empty:
            outcomes.append({**pred, "exit_price": None, "exit_reason": "NO_DATA", "pnl_pct": 0.0, "hit_target": False, "hit_stop": False})
            continue

        # Simulate intrabar: did price hit stop or target intraday?
        hit_stop = False
        hit_target = False
        exit_price = float(week_bars.iloc[-1]["close"])
        exit_reason = "CLOSE"

        for _, bar in week_bars.iterrows():
            if not hit_stop and bar["low"] <= stop:
                hit_stop = True
                exit_price = stop
                exit_reason = "STOPPED"
                break
            if not hit_target and bar["high"] >= target:
                hit_target = True
                exit_price = target
                exit_reason = "WIN"
                break

        if exit_reason == "CLOSE":
            exit_reason = "WIN" if exit_price > entry else "LOSS"

        pnl_pct = round((exit_price - entry) / entry * 100, 2) if entry else 0.0

        outcomes.append(
            {
                **pred,
                "exit_price": round(exit_price, 4),
                "exit_reason": exit_reason,
                "pnl_pct": pnl_pct,
                "hit_target": hit_target,
                "hit_stop": hit_stop,
            }
        )

    return outcomes


def adapt_weights(
    outcomes: list[dict],
    week_start: str,
    market_regime: str = "unknown",
    win_boost: float = 0.03,
    loss_penalty: float = 0.05,
) -> dict:
    """
    Adjust indicator weights based on outcome analysis.

    Winning picks: boost their strongest category by win_boost.
    Losing picks: penalize their strongest "misleading" category by loss_penalty.
    Re-normalize weights to sum to 1.0.

    Returns updated weights dict.
    """
    weights = load_weights()
    categories = list(weights.keys())

    winners = [o for o in outcomes if o["exit_reason"] in ("WIN",)]
    losers = [o for o in outcomes if o["exit_reason"] in ("LOSS", "STOPPED")]

    # For winners: find strongest category and gently boost it
    for o in winners:
        cats = o.get("category_scores", {})
        if not cats:
            continue
        best_cat = max(cats, key=cats.get)
        if best_cat in weights:
            weights[best_cat] = weights[best_cat] * (1 + win_boost)

    # For losers: find strongest misleading category and penalize
    for o in losers:
        cats = o.get("category_scores", {})
        if not cats:
            continue
        # Category that was high but still led to a loss = misleading signal
        misleading = max(cats, key=cats.get)
        if misleading in weights:
            weights[misleading] = max(weights[misleading] * (1 - loss_penalty), 0.02)

    weights = _normalize(weights)
    save_weights(weights)
    return weights


def write_learning_note(
    week_start: str,
    outcomes: list[dict],
    new_weights: dict,
    market_regime: str = "unknown",
) -> None:
    """Append a qualitative learning entry to the learning log."""
    wins = [o for o in outcomes if o["exit_reason"] == "WIN"]
    losses = [o for o in outcomes if o["exit_reason"] in ("LOSS", "STOPPED")]
    no_data = [o for o in outcomes if o["exit_reason"] == "NO_DATA"]

    avg_pnl = np.mean([o["pnl_pct"] for o in outcomes if o["pnl_pct"] is not None])
    win_rate = len(wins) / len(outcomes) * 100 if outcomes else 0

    failure_analysis = []
    for o in losses:
        cats = o.get("category_scores", {})
        top_cats = sorted(cats.items(), key=lambda x: -x[1])[:2]
        failure_analysis.append(
            {
                "ticker": o["ticker"],
                "pnl_pct": o["pnl_pct"],
                "exit_reason": o["exit_reason"],
                "misleading_signals": [c[0] for c in top_cats],
                "note": (
                    f"Score={o['score']:.1f} but lost {abs(o['pnl_pct']):.1f}%. "
                    f"Strongest signals were {', '.join(c[0] for c in top_cats)} — "
                    "may indicate false breakout or regime misalignment."
                ),
            }
        )

    entry = {
        "week_start": week_start,
        "evaluated_at": datetime.utcnow().isoformat(),
        "market_regime": market_regime,
        "total_picks": len(outcomes),
        "wins": len(wins),
        "losses": len(losses),
        "no_data": len(no_data),
        "win_rate_pct": round(win_rate, 1),
        "avg_pnl_pct": round(float(avg_pnl), 2) if not np.isnan(avg_pnl) else 0.0,
        "updated_weights": {k: round(v, 4) for k, v in new_weights.items()},
        "failure_analysis": failure_analysis,
        "winners": [{"ticker": o["ticker"], "pnl_pct": o["pnl_pct"]} for o in wins],
    }

    log = _load_log()
    log.append(entry)
    _save_log(log)
    return entry
