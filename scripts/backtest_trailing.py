"""
backtest_trailing.py
====================
Realistic backtest: HOLD WINNERS, don't force exit at week end.

Exit rules:
  1. Daily trailing stop — trail 2×ATR below the highest close seen
  2. Price target hit  — exit next open if close >= entry + 15%
  3. Hard stop         — exit at open if stock opens below initial stop
  4. Max hold          — 4 weeks (20 trading days), then exit at close

This is the REAL P&L — not chopped at Friday.
"""

import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analysis.predictor.data_loader import load_daily, DATA_DIR
from src.analysis.predictor.daily_indicators import compute_daily_indicators, get_snapshot

WEEKS = [
    {"week_label": "Jan 5",  "as_of": "2026-01-02", "entry_date": "2026-01-05"},
    {"week_label": "Jan 12", "as_of": "2026-01-09", "entry_date": "2026-01-12"},
    {"week_label": "Jan 19", "as_of": "2026-01-16", "entry_date": "2026-01-20"},  # Jan 19 = MLK, market opens Jan 20
    {"week_label": "Jan 26", "as_of": "2026-01-23", "entry_date": "2026-01-26"},
]
TOP_N     = 5
MAX_DAYS  = 20        # max 4 weeks hold
TARGET_R  = 0.15      # 15% gain → take profit
TRAIL_ATR = 2.0       # trail stop at 2×ATR below highest close
INIT_ATR  = 2.0       # initial stop at 2×ATR below entry


# ─────────────────────────────────────────────────────────────────────────────
# Scoring (same as backtest_jan2026.py v2 — regime-aware)
# ─────────────────────────────────────────────────────────────────────────────

def _f(snap, k, d=0.0):
    v = snap.get(k)
    if v is None: return d
    try: return float(v)
    except: return d


def detect_bull_patterns(snap):
    close    = _f(snap, "close", 1)
    rsi14    = _f(snap, "rsi14", 50)
    rsi7     = _f(snap, "rsi7", 50)
    pct21    = _f(snap, "pct_vs_ema21", 0)
    pct50    = _f(snap, "pct_vs_ema50", 0)
    ema_al   = int(_f(snap, "ema_align", 0))
    cmf      = _f(snap, "cmf", 0)
    rs21     = _f(snap, "rs_21d", 0)
    vol_r    = _f(snap, "vol_ratio_20", 1)
    in_sq    = bool(snap.get("in_squeeze", False))
    macd_r   = bool(snap.get("macd_hist_rising", False))
    bb_pct   = _f(snap, "bb_pct", 0.5)

    patterns = []

    # EMA21 pullback: aligned trend, pulled back to EMA21, not overbought
    if ema_al >= 2 and -0.07 <= pct21 <= 0.01 and 35 < rsi14 < 70 and rsi7 < 80:
        patterns.append(("ema21_pullback", 39, f"EMA21 pull {pct21*100:.1f}% RSI14={rsi14:.0f}"))

    # EMA50 pullback: deeper pullback to EMA50, stronger entry
    if ema_al >= 2 and -0.12 <= pct50 <= 0.02 and 30 < rsi14 < 65 and rsi7 < 78:
        patterns.append(("ema50_pullback", 40, f"EMA50 pull {pct50*100:.1f}% RSI14={rsi14:.0f}"))

    # Momentum continuation: RS leader resting (not oversold, not overbought)
    if ema_al >= 3 and rs21 > 0 and 40 < rsi14 < 70 and -0.05 <= pct21 <= 0.02 and rsi7 < 80:
        patterns.append(("momentum_cont", 39, f"RS leader rest RS21={rs21*100:.1f}%"))

    # Squeeze breakout: Bollinger band squeeze releasing with volume
    if in_sq and vol_r > 1.5 and macd_r and rsi14 > 45:
        patterns.append(("squeeze_break", 39, f"Squeeze release vol×{vol_r:.1f}"))

    # RS momentum leader with flow: strong outperformer + CMF positive
    if rs21 > 0.05 and cmf > 0 and ema_al >= 2 and rsi7 < 78:
        patterns.append(("rs_momentum_leader", 40, f"RS+CMF leader RS21={rs21*100:.1f}%"))

    return patterns


def detect_bear_patterns(snap):
    rsi14  = _f(snap, "rsi14", 50)
    rsi7   = _f(snap, "rsi7", 50)
    bb_pct = _f(snap, "bb_pct", 0.5)
    cmf    = _f(snap, "cmf", 0)
    vol_r  = _f(snap, "vol_ratio_20", 1)
    pct21  = _f(snap, "pct_vs_ema21", 0)

    patterns = []

    if bb_pct < 0.10 and rsi7 < 25:
        patterns.append(("mean_rev_extreme", 50, f"BB={bb_pct:.2f} RSI7={rsi7:.0f}"))

    if rsi7 < 30 and rsi7 < rsi14:
        patterns.append(("rsi_oversold_bounce", 46, f"RSI7={rsi7:.0f} recovering"))

    if rsi7 < 25 and bb_pct < 0.05 and vol_r > 2.0:
        patterns.append(("hammer_reversal", 44, f"Extreme vol+BB+RSI"))

    if rsi7 < 30 and pct21 < -0.10:
        patterns.append(("gap_down_reversal", 42, f"Gap down RSI7={rsi7:.0f}"))

    return patterns


def score_ticker(snap, spy_above_ema50):
    close   = _f(snap, "close", 0)
    atr_pct = _f(snap, "atr_pct", 0)
    vol_r   = _f(snap, "vol_ratio_20", 1)
    rsi14   = _f(snap, "rsi14", 50)
    rsi7    = _f(snap, "rsi7", 50)
    cmf     = _f(snap, "cmf", 0)
    obv_s   = _f(snap, "obv_slope", 0)
    pct52h  = _f(snap, "pct_from_52w_high", 0)
    ema_al  = int(_f(snap, "ema_align", 0))
    macd_r  = bool(snap.get("macd_hist_rising", False))
    rs21    = _f(snap, "rs_21d", 0)
    adx     = _f(snap, "adx", 15)
    di_sp   = _f(snap, "di_spread", 0)

    if atr_pct < 0.015: return None
    if close < 15:      return None
    if vol_r < 0.4:     return None
    if (rsi14 - rsi7) > 10 and cmf < -0.25: return None

    if spy_above_ema50:
        patterns = detect_bull_patterns(snap)
    else:
        patterns = detect_bear_patterns(snap)

    cross_patterns = []
    if _f(snap, "macd_cross_days", 0) > 0 and macd_r and 35 < rsi14 < 65:
        cross_patterns.append(("macd_bull_cross", 40, "MACD cross"))

    all_patterns = patterns + cross_patterns
    tier12 = [p for p in all_patterns if p[1] >= 39]
    tier3  = [p for p in all_patterns if p[1] < 39]

    if not tier12: return None

    tier12_sorted = sorted(tier12, key=lambda x: x[1], reverse=True)
    score = float(tier12_sorted[0][1])
    if len(tier12) >= 2: score += 8
    score += len(tier3) * 2

    if atr_pct >= 0.06: score += 10
    elif atr_pct >= 0.04: score += 6
    elif atr_pct >= 0.025: score += 2

    if pct52h < -40: score += 6
    elif pct52h < -25: score += 4
    elif pct52h < -15: score += 2

    if cmf > 0.1:  score += 8
    elif cmf > 0:  score += 5
    elif cmf < -0.15: score -= 5

    if obv_s > 0.1:  score += 4
    elif obv_s < -0.3: score -= 3
    if macd_r: score += 3

    if spy_above_ema50 and rs21 > 0.03: score += 5
    if spy_above_ema50 and di_sp > 10 and adx > 20: score += 4
    if not spy_above_ema50 and rsi7 < 35: score += 5
    if not spy_above_ema50 and ema_al >= 3: score -= 5

    return {
        "score":           round(min(score, 100), 1),
        "primary_pattern": tier12_sorted[0][0],
        "pattern_wr":      tier12_sorted[0][1],
        "patterns_fired":  [p[0] for p in all_patterns],
        "combo_count":     len(tier12),
        "atr_pct":         round(atr_pct, 4),
        "rsi14":           round(rsi14, 1),
        "rsi7":            round(rsi7, 1),
        "cmf":             round(cmf, 3),
        "rs21":            round(rs21, 4),
        "ema_align":       ema_al,
        "close":           round(close, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# TRAILING STOP EXIT ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def simulate_trade(ticker: str, entry_date: str, atr_pct_ratio: float) -> dict | None:
    """
    Simulate a trade with trailing stop logic.
    - Entry at Monday open
    - Stop: 2×ATR below entry (initial hard stop)
    - Trail: as price rises, stop trails 2×ATR below highest close
    - Target: 15% gain → exit next open
    - Max: 20 trading days
    """
    df = load_daily(ticker)
    if df is None or df.empty:
        return None

    entry_ts = pd.Timestamp(entry_date)
    future   = df[df.index >= entry_ts].copy()
    if len(future) < 2:
        return None

    entry_price = float(future.iloc[0]["open"])
    if entry_price <= 0:
        return None

    atr_dollar = atr_pct_ratio * entry_price   # atr_pct is a ratio
    init_stop  = entry_price - INIT_ATR * atr_dollar
    target     = entry_price * (1 + TARGET_R)

    trailing_stop = init_stop
    highest_close = entry_price
    exit_price    = None
    exit_date     = None
    exit_reason   = None
    daily_log     = []

    # Start from day 1 (not entry day itself for stop check — let it breathe)
    for i, (ts, row) in enumerate(future.iterrows()):
        if i >= MAX_DAYS:
            exit_price  = float(row["close"])
            exit_date   = str(ts.date())
            exit_reason = "MAX_HOLD"
            break

        day_open  = float(row["open"])
        day_high  = float(row["high"])
        day_low   = float(row["low"])
        day_close = float(row["close"])

        # Day 0 = entry day — skip stop checks, set initial reference
        if i == 0:
            highest_close = day_close
            trailing_stop = max(trailing_stop, highest_close - TRAIL_ATR * atr_dollar)
            daily_log.append((str(ts.date()), day_close, trailing_stop, "ENTRY"))
            continue

        # Gap down open through stop → exit at open
        if day_open < trailing_stop:
            exit_price  = day_open
            exit_date   = str(ts.date())
            exit_reason = "STOP_GAP"
            daily_log.append((str(ts.date()), day_open, trailing_stop, "STOP_GAP"))
            break

        # Intraday stop hit
        if day_low < trailing_stop:
            exit_price  = trailing_stop
            exit_date   = str(ts.date())
            exit_reason = "STOP_TRAIL"
            daily_log.append((str(ts.date()), trailing_stop, trailing_stop, "STOP_TRAIL"))
            break

        # Update trailing stop from highest close
        if day_close > highest_close:
            highest_close = day_close
            new_stop = highest_close - TRAIL_ATR * atr_dollar
            trailing_stop = max(trailing_stop, new_stop)

        # Target hit — exit at next open (let's use next bar's open)
        if day_close >= target:
            if i + 1 < len(future):
                next_row = future.iloc[i + 1]
                exit_price  = float(next_row["open"])
                exit_date   = str(future.index[i + 1].date())
                exit_reason = "TARGET"
                daily_log.append((str(ts.date()), day_close, trailing_stop, "TARGET_HIT"))
            else:
                exit_price  = day_close
                exit_date   = str(ts.date())
                exit_reason = "TARGET"
            break

        daily_log.append((str(ts.date()), day_close, trailing_stop, "HOLD"))

    if exit_price is None:
        # End of data
        exit_price  = float(future.iloc[-1]["close"])
        exit_date   = str(future.index[-1].date())
        exit_reason = "EOD"

    pnl_pct   = round((exit_price - entry_price) / entry_price * 100, 2)
    hold_days = len([d for d in daily_log if d[3] not in ("STOP_GAP","STOP_TRAIL","TARGET_HIT")])
    max_gain  = round((max(r[1] for r in daily_log) - entry_price) / entry_price * 100, 2) if daily_log else 0

    return {
        "entry_price":  round(entry_price, 2),
        "exit_price":   round(exit_price, 2),
        "pnl_pct":      pnl_pct,
        "exit_reason":  exit_reason,
        "exit_date":    exit_date,
        "hold_days":    hold_days,
        "max_gain_pct": max_gain,
        "init_stop":    round(init_stop, 2),
        "win":          pnl_pct > 1.0,
        "loss":         pnl_pct < -1.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BACKTEST
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest():
    tickers = sorted(
        f.replace(".csv","") for f in os.listdir(DATA_DIR)
        if f.endswith(".csv") and not f.startswith("_")
    )

    all_trades   = []
    grand_pnl    = 0.0
    grand_wins   = 0
    grand_picks  = 0

    for week in WEEKS:
        label      = week["week_label"]
        as_of      = week["as_of"]
        entry_date = week["entry_date"]

        print(f"\n{'='*72}")
        print(f"WEEK OF {label.upper()} | as-of {as_of} | entry {entry_date}")
        print(f"(trailing stop — hold winners up to {MAX_DAYS} days)")
        print(f"{'='*72}")

        spy_df = load_daily("SPY", end=as_of)
        spy_above_ema50 = True
        regime_label    = "BULL"

        if spy_df is not None and len(spy_df) >= 50:
            spy_ind  = compute_daily_indicators(spy_df)
            spy_snap = get_snapshot(spy_ind, pd.Timestamp(as_of))
            if spy_snap is not None:
                spy_close       = float(spy_snap.get("close") or 0)
                spy_ema50       = float(spy_snap.get("ema50") or 0)
                spy_above_ema50 = spy_close > spy_ema50
                regime_label    = "BULL" if spy_above_ema50 else "BEAR"
                spy_rsi  = round(float(spy_snap.get("rsi14") or 50), 1)
                spy_roc21 = round(float(spy_snap.get("roc21") or 0) * 100, 1)
                print(f"Regime: {regime_label} | SPY ROC21: {spy_roc21:+.1f}% | RSI: {spy_rsi}")

        candidates = []
        for ticker in tickers:
            if ticker == "SPY": continue
            try:
                df  = load_daily(ticker, end=as_of)
                if df is None or len(df) < 200: continue
                ind  = compute_daily_indicators(df, spy=spy_df)
                snap = get_snapshot(ind, pd.Timestamp(as_of))
                if snap is None: continue
                result = score_ticker(snap, spy_above_ema50)
                if result is None: continue
                result["ticker"] = ticker
                candidates.append(result)
            except Exception:
                continue

        candidates.sort(key=lambda x: x["score"], reverse=True)
        top5 = candidates[:TOP_N]

        print(f"\n{len(candidates)} qualified | Top {TOP_N} picks:\n")
        fmt = "{:<6} {:>6} {:>7} {:>7} {:>7} {:<12} {:>8} {:>6} {:>10} {:>10}"
        print(fmt.format("TICK","Score","RSI14","RSI7","RS21%","Pattern","Entry","PnL%","Exit$","Reason"))
        print("-"*90)

        week_pnl  = 0.0
        week_wins = 0

        for pick in top5:
            ticker  = pick["ticker"]
            atr_r   = pick["atr_pct"]
            result  = simulate_trade(ticker, entry_date, atr_r)

            if result is None:
                print(f"{ticker:<6} {'?':>6} — no data")
                continue

            pnl     = result["pnl_pct"]
            reason  = result["exit_reason"]
            days    = result["hold_days"]
            entry_p = result["entry_price"]
            exit_p  = result["exit_price"]
            max_g   = result["max_gain_pct"]
            outcome_sym = "✓" if result["win"] else ("✗" if result["loss"] else "—")

            week_pnl  += pnl
            grand_pnl += pnl
            grand_picks += 1
            if result["win"]:
                week_wins  += 1
                grand_wins += 1

            print(fmt.format(
                ticker,
                f"{pick['score']:.0f}",
                f"{pick['rsi14']:.0f}",
                f"{pick['rsi7']:.0f}",
                f"{pick['rs21']*100:.1f}",
                pick["primary_pattern"][:12],
                f"${entry_p:.2f}",
                f"{pnl:+.1f}%{outcome_sym}",
                f"${exit_p:.2f}",
                reason
            ))
            print(f"       held={days}d  max_gain={max_g:+.1f}%  exit={result['exit_date']}")

            all_trades.append({
                "week": label, "ticker": ticker,
                **result,
                "score": pick["score"],
                "pattern": pick["primary_pattern"],
            })

        avg = week_pnl / len(top5) if top5 else 0
        print(f"\n  → Week {label}: {week_wins}/{len(top5)} wins | Avg PnL = {avg:+.2f}%")

    # Summary
    print(f"\n{'='*72}")
    print("OVERALL TRAILING-STOP BACKTEST — JANUARY 2026")
    print(f"{'='*72}")
    print(f"Total picks: {grand_picks} | Wins: {grand_wins} ({grand_wins/grand_picks*100:.0f}%)")
    print(f"Total PnL (sum all picks): {grand_pnl:+.2f}%")
    print(f"Avg PnL per pick:          {grand_pnl/grand_picks:+.2f}%")

    wins   = [t for t in all_trades if t["win"]]
    losses = [t for t in all_trades if t["loss"]]
    if wins:
        avg_win  = sum(t["pnl_pct"] for t in wins)  / len(wins)
        avg_days_win = sum(t["hold_days"] for t in wins) / len(wins)
        print(f"\nAvg WIN:  {avg_win:+.2f}%  (held {avg_days_win:.1f} days avg)")
    if losses:
        avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses)
        avg_days_loss = sum(t["hold_days"] for t in losses) / len(losses)
        print(f"Avg LOSS: {avg_loss:+.2f}%  (held {avg_days_loss:.1f} days avg)")

    exit_counts = {}
    for t in all_trades:
        exit_counts[t["exit_reason"]] = exit_counts.get(t["exit_reason"], 0) + 1
    print(f"\nExit breakdown: {exit_counts}")

    print("\nBest trades:")
    for t in sorted(all_trades, key=lambda x: x["pnl_pct"], reverse=True)[:5]:
        print(f"  {t['week']:6} {t['ticker']:6} {t['pnl_pct']:+.1f}% ({t['hold_days']}d) [{t['exit_reason']}]")

    print("\nWorst trades:")
    for t in sorted(all_trades, key=lambda x: x["pnl_pct"])[:5]:
        print(f"  {t['week']:6} {t['ticker']:6} {t['pnl_pct']:+.1f}% ({t['hold_days']}d) [{t['exit_reason']}]")


if __name__ == "__main__":
    run_backtest()
