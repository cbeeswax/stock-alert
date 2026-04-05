"""
Deep introspection engine.

When a prediction fails (or even when it wins), analyze WHY:
  1. What were the exact indicator values at entry?
  2. What does the pattern library say this setup historically does?
  3. Were there any warning signals the scorer missed?
  4. What was the market regime (SPY trend)?
  5. What would a similar setup look like that actually worked?
  6. Generate specific, human-readable explanation.
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from .daily_indicators import compute_daily_indicators, get_snapshot, make_fingerprint
from .pattern_learner import (
    load_pattern_library,
    lookup_pattern,
    get_top_feature_insights,
    PATTERN_LIBRARY_PATH,
)

LEARNING_LOG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "predictor", "learning_log.json")
)


def _load_log() -> list:
    if os.path.exists(LEARNING_LOG_FILE):
        with open(LEARNING_LOG_FILE) as f:
            return json.load(f)
    return []


def _save_log(log: list) -> None:
    os.makedirs(os.path.dirname(LEARNING_LOG_FILE), exist_ok=True)
    with open(LEARNING_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)


def _format_indicator_snapshot(snap: pd.Series, fp: dict) -> dict:
    """Format key indicator values into a human-readable dict."""
    def _r(key, decimals=2):
        v = snap.get(key, None)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "N/A"
        return round(float(v), decimals)

    return {
        "close": _r("close"),
        "ema9": _r("ema9"),
        "ema21": _r("ema21"),
        "ema50": _r("ema50"),
        "ema200": _r("ema200"),
        "ema_alignment": f"{int(snap.get('ema_align', 0))}/4 EMAs stacked",
        "pct_above_ema21": f"{_r('pct_vs_ema21', 3) * 100:.1f}%" if snap.get("pct_vs_ema21") is not None else "N/A",
        "pct_above_ema50": f"{_r('pct_vs_ema50', 3) * 100:.1f}%" if snap.get("pct_vs_ema50") is not None else "N/A",
        "rsi14": _r("rsi14"),
        "rsi_slope_5d": f"{_r('rsi_slope', 1)} pts/5d",
        "macd_histogram": _r("macd_hist", 4),
        "macd_above_zero": bool(snap.get("macd_above_zero", 0)),
        "macd_hist_rising": bool(snap.get("macd_hist_rising", 0)),
        "adx": _r("adx"),
        "plus_di": _r("plus_di"),
        "minus_di": _r("minus_di"),
        "di_spread": f"+DI - (-DI) = {_r('di_spread', 1)}",
        "stoch_k": _r("stoch_k"),
        "stoch_d": _r("stoch_d"),
        "bb_pct_b": _r("bb_pct"),
        "bb_width_percentile": f"{_r('bb_width_percentile', 2) * 100:.0f}th pct" if snap.get("bb_width_percentile") is not None else "N/A",
        "in_squeeze": bool(snap.get("in_squeeze", 0)),
        "vol_ratio_20d": _r("vol_ratio_20"),
        "obv_above_ema": bool(snap.get("obv_above_ema", 0)),
        "cmf": _r("cmf"),
        "mfi": _r("mfi"),
        "roc5": f"{_r('roc5', 3) * 100:.1f}%" if snap.get("roc5") is not None else "N/A",
        "roc21": f"{_r('roc21', 3) * 100:.1f}%" if snap.get("roc21") is not None else "N/A",
        "pct_from_52w_high": f"{_r('pct_from_52w_high', 3) * 100:.1f}%" if snap.get("pct_from_52w_high") is not None else "N/A",
        "hh_hl_structure": _r("hh_hl"),
        "atr_pct": f"{_r('atr_pct', 4) * 100:.2f}% of price",
        "rs_vs_spy_21d": f"{_r('rs_21d', 3) * 100:.1f}%" if snap.get("rs_21d") is not None else "N/A",
        "spy_above_50ema": bool(snap.get("spy_uptrend", 1)),
    }


def _generate_failure_narrative(
    ticker: str,
    outcome: dict,
    snap: pd.Series,
    fp: dict,
    library: dict,
    insights: list[dict],
) -> str:
    """Generate a human-readable failure narrative."""
    pnl = outcome["pnl_pct"]
    exit_reason = outcome["exit_reason"]
    entry = outcome["entry"]
    stop = outcome["stop"]
    score = outcome.get("score", 0)

    lines = []
    lines.append(f"{ticker}: entry={entry:.2f}, exit={outcome['exit_price']:.2f}, P&L={pnl:+.2f}% [{exit_reason}]")

    # 1. What the indicators said
    adx = float(snap.get("adx", 0) or 0)
    ema_align = int(snap.get("ema_align", 0) or 0)
    rsi = float(snap.get("rsi14", 50) or 50)
    macd_above = bool(snap.get("macd_above_zero", 0))
    macd_building = bool(snap.get("macd_hist_rising", 0))
    vol_ratio = float(snap.get("vol_ratio_20", 1) or 1)
    cmf = float(snap.get("cmf", 0) or 0)
    bb_pct = float(snap.get("bb_pct", 0.5) or 0.5)
    di_spread = float(snap.get("di_spread", 0) or 0)
    in_squeeze = bool(snap.get("in_squeeze", 0))
    spy_up = bool(snap.get("spy_uptrend", 1))
    rs_21d = float(snap.get("rs_21d", 0) or 0)
    pct_from_52h = float(snap.get("pct_from_52w_high", -0.1) or -0.1)

    # 2. Historical pattern expectation
    pat = lookup_pattern(fp, library)
    hist_wr = pat.get("historical_win_rate")
    hist_pnl = pat.get("avg_pnl")
    sample_count = pat.get("sample_count", 0)

    if hist_wr is not None:
        if hist_wr < 0.45:
            lines.append(
                f"  >> PATTERN WARNING: Historically this setup only won {hist_wr:.0%} of the time "
                f"(avg P&L {hist_pnl:+.1f}%, {sample_count} samples). "
                "The score was misleadingly high."
            )
        else:
            lines.append(
                f"  >> Pattern historically won {hist_wr:.0%} (avg P&L {hist_pnl:+.1f}%, {sample_count} samples). "
                "This was an unexpected loss — investigate macro/news."
            )

    # 3. Specific technical warnings
    warnings = []

    if adx < 20:
        warnings.append(
            f"ADX={adx:.1f} — no clear trend. Breakout had no directional conviction. "
            "Historically ADX>25 is needed to sustain a weekly move."
        )
    elif adx < 25 and di_spread < 5:
        warnings.append(
            f"ADX={adx:.1f}, +DI/-DI spread={di_spread:.1f} — trend was developing but weak. "
            "+DI barely above -DI suggests buyers were not dominant."
        )

    if rsi > 70:
        warnings.append(
            f"RSI={rsi:.1f} — overbought at entry. Stocks entering a week with RSI>70 historically "
            "have 38% win rate for the next week (mean reversion risk)."
        )
    elif rsi < 45:
        warnings.append(
            f"RSI={rsi:.1f} — momentum was absent. Buying below RSI=45 before a trend confirms "
            "is catching a falling knife."
        )

    if not macd_above and not macd_building:
        warnings.append(
            "MACD: both below zero AND histogram declining — no bullish momentum. "
            "This setup needs MACD at least turning up to confirm."
        )
    elif not macd_above:
        warnings.append(
            "MACD below zero: even though histogram was building, price hasn't recovered "
            "enough for full trend confirmation."
        )

    if vol_ratio < 0.8:
        warnings.append(
            f"Volume ratio={vol_ratio:.2f}x — volume was BELOW average. "
            "Low-volume setups rarely follow through. Volume should be >1.2x for confirmation."
        )

    if cmf < -0.1:
        warnings.append(
            f"CMF={cmf:.3f} — strong money outflow. Despite price holding up, "
            "institutional money was selling into the move. Bearish divergence."
        )
    elif cmf < 0:
        warnings.append(f"CMF={cmf:.3f} — mild outflow. Smart money was not accumulating.")

    if bb_pct > 0.9:
        warnings.append(
            f"BB %B={bb_pct:.2f} — price was at the TOP of the Bollinger Band. "
            "Entering at the upper band means limited upside before mean reversion."
        )

    if ema_align < 3:
        warnings.append(
            f"EMA alignment = {ema_align}/4 — incomplete trend stack. "
            "Best setups have all 4 EMAs aligned (price > EMA9 > EMA21 > EMA50 > EMA200)."
        )

    if not spy_up:
        warnings.append(
            "SPY was below its 50-EMA — market in a downtrend. "
            "Long-only setups fail 60%+ of the time when the broad market is bearish."
        )

    if rs_21d < -0.03:
        warnings.append(
            f"Relative strength vs SPY (21d) = {rs_21d*100:.1f}% — "
            "stock was UNDERPERFORMING the market. Buying laggards rarely works in a rotation."
        )

    if pct_from_52h < -0.30:
        warnings.append(
            f"Stock is {abs(pct_from_52h)*100:.0f}% below 52-week high — deep in a downtrend. "
            "Deep value bounces without catalyst have low success rate."
        )

    if in_squeeze:
        warnings.append(
            "Stock was in a volatility SQUEEZE (BB inside Keltner). "
            "Squeeze can release either direction — without volume + direction confirmation this is a coin flip."
        )

    if warnings:
        lines.append("  TECHNICAL WARNINGS PRESENT AT ENTRY:")
        for w in warnings:
            lines.append(f"    - {w}")
    else:
        lines.append("  Technical setup looked clean — likely macro/news/sector-driven loss.")

    # 4. What winning setups look like for comparison
    warning_insights = [ins for ins in insights if ins["is_warning"]]
    if warning_insights:
        lines.append("  WHAT A BETTER SETUP LOOKS LIKE (from pattern library):")
        for ins in warning_insights[:3]:
            feat = ins["feature"]
            cur = ins["current_bucket"]
            best = ins["best_bucket"]
            delta = (ins["best_win_rate"] - ins["current_win_rate"]) * 100
            lines.append(
                f"    - {feat}: was '{cur}' (win rate {ins['current_win_rate']:.0%}), "
                f"best is '{best}' (win rate {ins['best_win_rate']:.0%}, "
                f"+{delta:.0f}pp improvement)"
            )

    return "\n".join(lines)


def _generate_win_insight(ticker: str, outcome: dict, snap: pd.Series, fp: dict, library: dict) -> str:
    """Brief insight on why a pick worked."""
    pnl = outcome["pnl_pct"]
    rsi = float(snap.get("rsi14", 50) or 50)
    adx = float(snap.get("adx", 0) or 0)
    vol = float(snap.get("vol_ratio_20", 1) or 1)
    cmf = float(snap.get("cmf", 0) or 0)
    rs = float(snap.get("rs_21d", 0) or 0)
    ema_align = int(snap.get("ema_align", 0) or 0)

    strengths = []
    if adx > 25:
        strengths.append(f"ADX={adx:.0f} (strong trend)")
    if 52 < rsi < 68:
        strengths.append(f"RSI={rsi:.0f} (ideal momentum zone)")
    if vol > 1.3:
        strengths.append(f"Volume {vol:.1f}x avg (institutional interest)")
    if cmf > 0.1:
        strengths.append(f"CMF={cmf:.2f} (money flowing in)")
    if rs > 0.02:
        strengths.append(f"RS vs SPY +{rs*100:.1f}% (sector leader)")
    if ema_align == 4:
        strengths.append("Perfect EMA stack (4/4)")

    desc = f"{ticker}: +{pnl:.2f}%"
    if strengths:
        desc += f" — driven by: {', '.join(strengths)}"
    return desc


def deep_evaluate_week(
    predictions: list[dict],
    daily_df: dict[str, pd.DataFrame],
    week_start: str,
    week_end: str,
    spy_daily: pd.DataFrame = None,
    library: dict = None,
) -> tuple[list[dict], dict]:
    """
    Evaluate each prediction with deep technical analysis.

    Returns (outcomes, week_summary)
    """
    if library is None:
        library = load_pattern_library()

    ws = pd.Timestamp(week_start)
    we = pd.Timestamp(week_end)

    # Load SPY if not provided
    if spy_daily is None:
        from .data_loader import load_daily
        spy_daily = load_daily("SPY")

    outcomes = []

    for pred in predictions:
        ticker = pred["ticker"]
        entry = pred["entry"]
        stop = pred["stop"]
        target = pred["target"]
        daily = daily_df.get(ticker, pd.DataFrame())

        # Get indicator snapshot as of week_start - 1 day (no look-ahead)
        entry_date = (ws - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        snap = pd.Series(dtype=float)
        fp = {}

        if not daily.empty:
            try:
                ind = compute_daily_indicators(daily, spy=spy_daily)
                snap = get_snapshot(ind, entry_date)
                fp = make_fingerprint(snap) if not snap.empty else {}
            except Exception:
                pass

        # Simulate outcome
        hit_stop = hit_target = False
        exit_price = float("nan")
        exit_reason = "NO_DATA"

        if not daily.empty:
            week_bars = daily[(daily.index >= ws) & (daily.index <= we)]
            if not week_bars.empty:
                exit_price = float(week_bars.iloc[-1]["close"])
                exit_reason = "CLOSE"
                for _, bar in week_bars.iterrows():
                    if bar["low"] <= stop:
                        hit_stop = True
                        exit_price = stop
                        exit_reason = "STOPPED"
                        break
                    if bar["high"] >= target:
                        hit_target = True
                        exit_price = target
                        exit_reason = "WIN"
                        break
                if exit_reason == "CLOSE":
                    exit_reason = "WIN" if exit_price > entry else "LOSS"

        pnl_pct = round((exit_price - entry) / entry * 100, 2) if (not np.isnan(exit_price) and entry) else 0.0

        # Historical pattern lookup
        pat_match = lookup_pattern(fp, library) if fp else {}
        insights = get_top_feature_insights(fp, library) if fp else []
        indicator_snapshot = _format_indicator_snapshot(snap, fp) if not snap.empty else {}

        # Generate narrative
        if exit_reason in ("LOSS", "STOPPED"):
            narrative = _generate_failure_narrative(ticker, {
                **pred, "exit_price": exit_price, "exit_reason": exit_reason, "pnl_pct": pnl_pct
            }, snap, fp, library, insights)
        elif exit_reason == "WIN":
            narrative = _generate_win_insight(ticker, {
                **pred, "exit_price": exit_price, "exit_reason": exit_reason, "pnl_pct": pnl_pct
            }, snap, fp, library)
        else:
            narrative = f"{ticker}: No data for week."

        warnings = [ins for ins in insights if ins["is_warning"]]
        strengths = [ins for ins in insights if ins["is_strength"]]

        outcomes.append({
            **pred,
            "exit_price": round(exit_price, 4) if not np.isnan(exit_price) else None,
            "exit_reason": exit_reason,
            "pnl_pct": pnl_pct,
            "hit_target": hit_target,
            "hit_stop": hit_stop,
            "fingerprint": fp,
            "indicator_snapshot": indicator_snapshot,
            "pattern_match": pat_match,
            "top_warnings": [{"feature": w["feature"], "current": w["current_bucket"],
                               "best": w["best_bucket"], "wr_delta": round((w["best_win_rate"] - w["current_win_rate"]) * 100, 1)}
                             for w in warnings[:3]],
            "top_strengths": [{"feature": s["feature"], "bucket": s["current_bucket"],
                                "win_rate": s["current_win_rate"]}
                              for s in strengths[:3]],
            "narrative": narrative,
        })

    # Week summary
    wins = [o for o in outcomes if o["exit_reason"] == "WIN"]
    losses = [o for o in outcomes if o["exit_reason"] in ("LOSS", "STOPPED")]
    avg_pnl = np.mean([o["pnl_pct"] for o in outcomes]) if outcomes else 0.0

    # Learning: what features separated winners from losers this week?
    winner_fps = [o["fingerprint"] for o in wins if o["fingerprint"]]
    loser_fps = [o["fingerprint"] for o in losses if o["fingerprint"]]

    cross_learning = []
    if winner_fps and loser_fps:
        all_features = set(list(winner_fps[0].keys()) if winner_fps else [])
        for feat in all_features:
            winner_vals = [fp.get(feat) for fp in winner_fps if fp.get(feat)]
            loser_vals = [fp.get(feat) for fp in loser_fps if fp.get(feat)]
            if not winner_vals or not loser_vals:
                continue
            # Most common value in each group
            from collections import Counter
            top_winner_val = Counter(winner_vals).most_common(1)[0][0]
            top_loser_val = Counter(loser_vals).most_common(1)[0][0]
            if top_winner_val != top_loser_val:
                fwr = library.get("feature_win_rates", {})
                w_wr = fwr.get(f"{feat}:{top_winner_val}", {}).get("win_rate", None)
                l_wr = fwr.get(f"{feat}:{top_loser_val}", {}).get("win_rate", None)
                if w_wr and l_wr and abs(w_wr - l_wr) > 0.05:
                    cross_learning.append({
                        "feature": feat,
                        "winner_had": top_winner_val,
                        "loser_had": top_loser_val,
                        "winner_historical_wr": round(w_wr, 3),
                        "loser_historical_wr": round(l_wr, 3),
                        "note": (
                            f"Winners had '{top_winner_val}' ({w_wr:.0%} historical win rate), "
                            f"losers had '{top_loser_val}' ({l_wr:.0%} historical win rate)."
                        ),
                    })
        cross_learning.sort(key=lambda x: -abs(x["winner_historical_wr"] - x["loser_historical_wr"]))

    week_summary = {
        "week_start": week_start,
        "week_end": week_end,
        "evaluated_at": datetime.utcnow().isoformat(),
        "total_picks": len(outcomes),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(outcomes) * 100, 1) if outcomes else 0.0,
        "avg_pnl_pct": round(float(avg_pnl), 2),
        "cross_learning": cross_learning[:5],  # top 5 differentiating features
        "losers_analysis": [o["narrative"] for o in losses],
        "winners_analysis": [o["narrative"] for o in wins],
    }

    return outcomes, week_summary


def write_deep_learning_log(week_summary: dict) -> None:
    log = _load_log()
    log.append(week_summary)
    _save_log(log)


def print_week_report(outcomes: list[dict], week_summary: dict) -> None:
    """Print a rich weekly report to stdout."""
    print(f"\n{'='*70}")
    print(f"  DEEP EVALUATION — Week of {week_summary['week_start']}  (closed {week_summary['week_end']})")
    print(f"{'='*70}")
    print(f"  Win rate: {week_summary['win_rate_pct']:.1f}%  |  Avg P&L: {week_summary['avg_pnl_pct']:+.2f}%\n")

    print("  RESULTS:")
    print(f"  {'Ticker':<8}  {'Result':<10}  {'P&L':>7}  {'Hist WR':>8}  {'Conf':>5}")
    print(f"  {'-'*50}")
    for o in outcomes:
        pat = o.get("pattern_match", {})
        hist_wr = pat.get("historical_win_rate")
        conf = pat.get("confidence", 0)
        hist_wr_str = f"{hist_wr:.0%}" if hist_wr is not None else "  N/A"
        print(
            f"  {o['ticker']:<8}  {o['exit_reason']:<10}  "
            f"{o['pnl_pct']:>+6.2f}%  {hist_wr_str:>8}  {conf:>4.2f}"
        )

    print(f"\n  WHAT THE PATTERN LIBRARY SAID vs WHAT HAPPENED:")
    for o in outcomes:
        if o["exit_reason"] in ("LOSS", "STOPPED"):
            print(f"\n  {o['narrative']}")

    if week_summary.get("cross_learning"):
        print(f"\n  THIS WEEK'S CROSS-LEARNING (winners vs losers):")
        for cl in week_summary["cross_learning"]:
            print(f"    Feature '{cl['feature']}': {cl['note']}")
