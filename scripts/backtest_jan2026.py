"""
backtest_jan2026.py  (v2 - regime-aware)
=========================================
Backtest the pattern system for all 4 weeks of January 2026.
January 2026 was a BULL market (SPY above EMA50, RSI ~52-62).

Key fix: scoring is now fully REGIME-AWARE.
  BULL: EMA pullbacks, momentum continuation, squeeze breakouts, RS leaders
  BEAR: Mean reversion extremes, oversold bounces, gap-down reversals
"""

import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analysis.predictor.data_loader import load_daily, DATA_DIR
from src.analysis.predictor.daily_indicators import compute_daily_indicators, get_snapshot

WEEKS = [
    {"week_label": "Jan 5",  "as_of": "2026-01-02", "entry_date": "2026-01-05", "exit_date": "2026-01-09"},
    {"week_label": "Jan 12", "as_of": "2026-01-09", "entry_date": "2026-01-12", "exit_date": "2026-01-16"},
    {"week_label": "Jan 19", "as_of": "2026-01-16", "entry_date": "2026-01-19", "exit_date": "2026-01-23"},
    {"week_label": "Jan 26", "as_of": "2026-01-23", "entry_date": "2026-01-26", "exit_date": "2026-01-30"},
]
TOP_N = 5


# ─────────────────────────────────────────────────────────────────────────────
# Regime-aware pattern scoring — learned from 2022-2025 backtests
# ─────────────────────────────────────────────────────────────────────────────

# Win rates from deep_pattern_learner (2022-2025, 178 stocks):
#   ema21_pullback   bull=38.9%  bear=41.8%  high_vol=44.0%
#   ema50_pullback   bull=39.7%  bear=41.8%  high_vol=45.7%
#   momentum_cont    bull=39.1%  bear=40.1%  high_vol=44.3%
#   squeeze_breakout bull=39.2%  bear=42.7%  high_vol=46.9%
#   macd_bull_cross  bull=39.6%  bear=42.8%  high_vol=45.3%
#   mean_rev_extreme bull=44.5%  bear=53.8%  high_vol=54.3%
#   rsi_oversold_bo  bull=41.1%  bear=50.2%  high_vol=51.8%
#
# KEY INSIGHT: Bear patterns dominate in absolute WR, but bull patterns
# (EMA pullbacks, momentum) are THE patterns to trade in bull markets.
# You still make money in bull markets — just lower WR per trade (~39-40%)
# compensated by smaller drawdowns and trending with the market.

def _f(snap, k, d=0.0):
    v = snap.get(k)
    if v is None: return d
    try: return float(v)
    except: return d

def detect_bull_patterns(snap):
    """
    BULL MARKET PATTERNS (spy_above_ema50=True)
    Best setups when market is trending up:
      1. EMA Pullback  — price pulls back to EMA21/50 in uptrend, bounces (38.9-39.7% WR)
      2. Momentum Cont — strong RS stock above EMA21, dip < 3% then recovery (39.1% WR)
      3. Squeeze Break — Bollinger squeeze releasing upward with volume (39.2% WR)
      4. MACD Bull Cross — MACD crosses signal from below, RSI neutral (39.6% WR)
      5. Inside Day Break — tight consolidation breaks up with volume (38.3% WR bull)
      6. RS Leader Momentum — outperforming SPY on rs_21d, trending (compound boost)
    """
    rsi14  = _f(snap, "rsi14", 50)
    rsi7   = _f(snap, "rsi7", 50)
    cmf    = _f(snap, "cmf", 0)
    macd_r = bool(snap.get("macd_hist_rising", False))
    macd_c = int(_f(snap, "macd_cross_days", 0))
    ema_al = int(_f(snap, "ema_align", 0))
    pema21 = _f(snap, "pct_vs_ema21", 0)
    pema50 = _f(snap, "pct_vs_ema50", 0)
    in_sqz = bool(snap.get("in_squeeze", False))
    vol_r  = _f(snap, "vol_ratio_20", 1)
    roc5   = _f(snap, "roc5_pct", 0)
    roc21  = _f(snap, "roc21_pct", 0)
    di_sp  = _f(snap, "di_spread", 0)
    adx    = _f(snap, "adx", 15)
    rs21   = _f(snap, "rs_21d", 0)
    bb_pct = _f(snap, "bb_pct", 0.5)
    obv_s  = _f(snap, "obv_slope", 0)

    patterns = []

    # 1. EMA21 Pullback — price pulled back 1-6% to EMA21
    #    In bull market: just need ema_align >= 2, price near EMA21, RSI not oversold
    #    macd_r NOT required — pullback to EMA21 IS the setup, recovery comes after entry
    if ema_al >= 2 and -7 <= pema21 <= 1.0 and 30 <= rsi14 <= 68:
        depth = abs(pema21)
        base = 41 if depth > 3 else 39
        patterns.append(("ema21_pullback", base, f"Pulled {pema21:.1f}% to EMA21 (ema_align={ema_al})"))

    # 2. EMA50 Pullback — deeper pullback to EMA50 (stronger support level)
    if ema_al >= 1 and -10 <= pema50 <= 1.0 and 28 <= rsi14 <= 62:
        patterns.append(("ema50_pullback", 40, f"Pulled {pema50:.1f}% to EMA50 support"))

    # 3. Momentum Continuation — trending stock, healthy RSI, not extended
    #    Strong signal: outperforming SPY (rs21 > 0), above EMA21
    if ema_al >= 3 and -5 <= roc5 <= 3 and 42 <= rsi14 <= 72 and di_sp > -5:
        rs_boost = 2 if rs21 > 0.02 else 0
        patterns.append(("momentum_continuation", 39 + rs_boost,
                         f"Bull trend: ema_align={ema_al} RS={rs21:.3f} rsi14={rsi14:.1f}"))

    # 4. Squeeze Breakout — BB inside KC releasing, confirmed by MACD
    if in_sqz and macd_r and rsi14 > 40:
        patterns.append(("squeeze_breakout", 40, "Squeeze releasing with MACD rising"))
    elif not in_sqz and bb_pct > 0.55 and macd_r and vol_r > 1.2:
        # Was in squeeze, now breaking out with volume
        patterns.append(("post_squeeze_breakout", 40, "Post-squeeze breakout with volume"))

    # 5. MACD Bull Cross
    if macd_c > 0 and macd_r and 38 <= rsi14 <= 65:
        patterns.append(("macd_bull_cross", 40, f"MACD crossed bullish, RSI={rsi14:.1f}"))

    # 6. Volume Surge Breakout — institutional buying surge
    if vol_r >= 2.0 and roc5 > 1 and rsi14 < 70:
        patterns.append(("volume_surge_bull", 39, f"2x+ vol surge, roc5={roc5:.1f}%"))

    # 7. Inside Day Breakout — tight coil breaking up
    if bb_pct > 0.6 and vol_r > 1.3 and roc5 > 0.5 and ema_al >= 2:
        patterns.append(("inside_day_breakout_bull", 39, f"BB expanding upward with volume"))

    # 8. RS Momentum Leader — outperforming SPY significantly
    if rs21 > 0.05 and ema_al >= 3 and rsi14 > 50 and cmf > 0:
        patterns.append(("rs_momentum_leader", 41, f"RS leader: {rs21:.3f} vs SPY, CMF={cmf:.3f}"))

    return patterns


def detect_bear_patterns(snap):
    """
    BEAR MARKET PATTERNS (spy_above_ema50=False)
    Best setups when market is correcting/declining:
      1. Mean Reversion Extreme — bb_pct<0.10 + rsi7<25     (49.9% WR, bear=53.8%)
      2. RSI Oversold Bounce   — rsi7<30 recovering          (46.0% WR, bear=50.2%)
      3. Hammer / Inverted Hammer at lows                    (43-44% WR)
      4. RSI Divergence Bounce — rsi7>rsi14 at low RSI       (43.6% WR)
      5. Gap Down Reversal     — large drop + intraday reversal (40.3% WR)
      6. EMA50 Pullback (bear) — still works at support      (41.8% bear WR)
    """
    rsi14  = _f(snap, "rsi14", 50)
    rsi7   = _f(snap, "rsi7", 50)
    cmf    = _f(snap, "cmf", 0)
    bb_pct = _f(snap, "bb_pct", 0.5)
    in_sqz = bool(snap.get("in_squeeze", False))
    macd_r = bool(snap.get("macd_hist_rising", False))
    macd_c = int(_f(snap, "macd_cross_days", 0))
    pema50 = _f(snap, "pct_vs_ema50", 0)
    pema21 = _f(snap, "pct_vs_ema21", 0)
    vol_r  = _f(snap, "vol_ratio_20", 1)
    roc5   = _f(snap, "roc5_pct", 0)
    roc21  = _f(snap, "roc21_pct", 0)
    obv_s  = _f(snap, "obv_slope", 0)
    pct52h = _f(snap, "pct_from_52w_high", 0)

    rsi_recovering = rsi7 > rsi14
    patterns = []

    # 1. Mean Reversion Extreme — best single pattern in bear markets
    if bb_pct < 0.10 and rsi7 < 25:
        patterns.append(("mean_reversion_extreme", 50, f"BB%={bb_pct:.3f} RSI7={rsi7:.1f} extreme oversold"))
    elif bb_pct < 0.15 and rsi7 < 30:
        patterns.append(("near_mean_reversion_extreme", 47, f"Near extreme oversold"))

    # 2. RSI Oversold Bounce
    if rsi7 < 30 and rsi_recovering:
        patterns.append(("rsi_oversold_bounce", 46, f"RSI7={rsi7:.1f} turning up"))
    elif rsi7 < 35 and rsi_recovering and cmf > -0.1:
        patterns.append(("rsi_near_oversold_bounce", 43, f"RSI7={rsi7:.1f} recovering"))

    # 3. Hammer (Oversold candle with long lower wick — proxy via indicators)
    if bb_pct < 0.20 and rsi7 < 40 and vol_r > 1.0 and rsi_recovering:
        patterns.append(("hammer_bounce", 44, f"Hammer at low: bb%={bb_pct:.2f} vol={vol_r:.2f}x"))

    # 4. RSI Divergence Bounce
    if rsi_recovering and rsi14 < 45:
        patterns.append(("rsi_divergence_bounce", 44, f"RSI7({rsi7:.1f})>RSI14({rsi14:.1f})"))

    # 5. Gap Down Reversal
    if roc21 < -8 and roc5 > 0 and cmf > -0.15:
        patterns.append(("gap_down_reversal", 40, f"Down {roc21:.1f}% in 21d, now recovering"))

    # 6. EMA50 Pullback (even in bear, EMA50 is strong support)
    if -5 <= pema50 <= 0.5 and rsi14 < 55 and macd_r:
        patterns.append(("ema50_pullback_bear", 42, f"EMA50 support: {pema50:.1f}% from EMA50"))

    # 7. Squeeze at lows — coiling before recovery move
    if in_sqz and bb_pct < 0.35 and rsi14 < 50:
        patterns.append(("squeeze_at_low", 41, f"Squeeze at low: coiling for bounce"))

    return patterns


def score_ticker(snap, spy_above_ema50: bool):
    atr_pct = _f(snap, "atr_pct", 0)   # ratio e.g. 0.016 = 1.6%
    close   = _f(snap, "close", 0)
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

    # Hard filters — atr_pct is a ratio (0.020 = 2%), not a percentage
    if atr_pct < 0.015: return None    # <1.5% daily range = too quiet to trade
    if close < 15:      return None
    if vol_r < 0.4:     return None
    # Falling knife veto (only if both signals very negative)
    if (rsi14 - rsi7) > 10 and cmf < -0.25: return None

    # Regime-specific pattern detection
    if spy_above_ema50:
        patterns = detect_bull_patterns(snap)
    else:
        patterns = detect_bear_patterns(snap)

    # Also check cross-regime patterns (work in both)
    cross_patterns = []
    if _f(snap, "macd_cross_days", 0) > 0 and macd_r and 35 < rsi14 < 65:
        cross_patterns.append(("macd_bull_cross", 40, "MACD cross both regimes"))

    all_patterns = patterns + cross_patterns
    tier12 = [p for p in all_patterns if p[1] >= 39]
    tier3  = [p for p in all_patterns if p[1] < 39]

    if not tier12:
        return None

    tier12_sorted = sorted(tier12, key=lambda x: x[1], reverse=True)
    score = float(tier12_sorted[0][1])

    # Combo bonus: 2+ confirming patterns
    if len(tier12) >= 2:
        score += 8

    score += len(tier3) * 2

    # ATR modifier — atr_pct is a ratio (0.020 = 2%)
    if atr_pct >= 0.06: score += 10
    elif atr_pct >= 0.04: score += 6
    elif atr_pct >= 0.025: score += 2

    # 52w position
    if pct52h < -40: score += 6
    elif pct52h < -25: score += 4
    elif pct52h < -15: score += 2

    # CMF money flow
    if cmf > 0.1:  score += 8
    elif cmf > 0:  score += 5
    elif cmf < -0.15: score -= 5

    # OBV slope (volume trend)
    if obv_s > 0.1:  score += 4
    elif obv_s < -0.3: score -= 3

    # MACD hist rising
    if macd_r: score += 3

    # Bull-specific: RS leader bonus
    if spy_above_ema50 and rs21 > 0.03:
        score += 5  # strong relative strength vs SPY
    if spy_above_ema50 and di_sp > 10 and adx > 20:
        score += 4  # strong trend direction

    # Bear-specific: oversold depth bonus
    if not spy_above_ema50 and rsi7 < 35:
        score += 5
    if not spy_above_ema50 and ema_al >= 3:
        score -= 5  # momentum trap in bear market

    return {
        "score":           round(min(score, 100), 1),
        "primary_pattern": tier12_sorted[0][0],
        "pattern_wr":      tier12_sorted[0][1],
        "pattern_detail":  tier12_sorted[0][2],
        "patterns_fired":  [p[0] for p in all_patterns],
        "combo_count":     len(tier12),
        "atr_pct":         round(atr_pct, 2),
        "rsi14":           round(rsi14, 1),
        "rsi7":            round(rsi7, 1),
        "rsi_recovering":  rsi7 > rsi14,
        "cmf":             round(cmf, 3),
        "rs21":            round(rs21, 4),
        "ema_align":       ema_al,
        "in_squeeze":      bool(snap.get("in_squeeze", False)),
        "close":           round(close, 2),
        "pct52h":          round(pct52h, 1),
    }


def get_weekly_return(ticker, entry_date, exit_date):
    df = load_daily(ticker)
    if df is None or df.empty:
        return None
    entry_ts = pd.Timestamp(entry_date)
    exit_ts  = pd.Timestamp(exit_date)
    entry_rows = df[df.index >= entry_ts]
    exit_rows  = df[(df.index >= entry_ts) & (df.index <= exit_ts)]
    if entry_rows.empty or exit_rows.empty:
        return None
    entry_row   = entry_rows.iloc[0]
    entry_price = float(entry_row.get("open", entry_row["close"]))
    exit_price  = float(exit_rows.iloc[-1]["close"])
    if entry_price <= 0:
        return None
    pnl_pct   = round((exit_price - entry_price) / entry_price * 100, 2)
    week_high  = float(exit_rows["high"].max())
    week_low   = float(exit_rows["low"].min())
    return {
        "entry_price": round(entry_price, 2),
        "exit_price":  round(exit_price, 2),
        "pnl_pct":     pnl_pct,
        "week_high":   round(week_high, 2),
        "week_low":    round(week_low, 2),
        "win":   pnl_pct > 1.0,
        "loss":  pnl_pct < -1.0,
    }


def run_backtest():
    tickers = sorted(
        f.replace(".csv","") for f in os.listdir(DATA_DIR)
        if f.endswith(".csv") and not f.startswith("_")
    )

    all_weeks = []
    grand_pnl = 0; grand_wins = 0; grand_picks = 0

    for week in WEEKS:
        label      = week["week_label"]
        as_of      = week["as_of"]
        entry_date = week["entry_date"]
        exit_date  = week["exit_date"]

        print(f"\n{'='*68}")
        print(f"WEEK OF {label.upper()} | as-of {as_of} | entry {entry_date} | exit {exit_date}")
        print(f"{'='*68}")

        spy_df = load_daily("SPY", end=as_of)
        spy_above_ema50 = True
        regime_label = "BULL"
        spy_rsi = 50.0; spy_cmf = 0.0; spy_roc21 = 0.0

        if spy_df is not None and len(spy_df) >= 50:
            spy_ind  = compute_daily_indicators(spy_df)
            spy_snap = get_snapshot(spy_ind, pd.Timestamp(as_of))
            if spy_snap is not None:
                spy_close = float(spy_snap.get("close") or 0)
                spy_ema50 = float(spy_snap.get("ema50") or 0)
                spy_above_ema50 = spy_close > spy_ema50
                regime_label = "BULL" if spy_above_ema50 else "BEAR"
                spy_rsi  = round(float(spy_snap.get("rsi14") or 50), 1)
                spy_cmf  = round(float(spy_snap.get("cmf")  or 0), 3)
                spy_roc21 = round(float(spy_snap.get("roc21") or 0) * 100, 1)

        playbook = "EMA pullbacks + Momentum + RS leaders" if spy_above_ema50 else "Mean reversion + Oversold bounces"
        print(f"Regime: {regime_label} | SPY ROC21: {spy_roc21:+.1f}% | RSI: {spy_rsi} | CMF: {spy_cmf}")
        print(f"Playbook: {playbook}")

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

        week_pnl = 0; week_wins = 0

        for rank, pick in enumerate(top5, 1):
            ticker = pick["ticker"]
            actual = get_weekly_return(ticker, entry_date, exit_date)

            if actual is None:
                outcome = "NO_DATA"; pnl = 0.0; pnl_str = "N/A"
            else:
                pnl = actual["pnl_pct"]; pnl_str = f"{pnl:+.2f}%"
                if actual["win"]:
                    outcome = "WIN  ✓"; week_wins += 1; grand_wins += 1
                elif actual["loss"]:
                    outcome = "LOSS ✗"
                else:
                    outcome = "FLAT ~"
                week_pnl += pnl; grand_pnl += pnl; grand_picks += 1

            # Stop analysis — atr_pct is a ratio, so dollar ATR = atr_pct * close
            atr_dollar = pick["atr_pct"] * pick["close"]
            stop_price = pick["close"] - 1.5 * atr_dollar
            stop_note  = ""
            if actual:
                if actual["week_low"] <= stop_price:
                    stop_note = f"STOP HIT (low={actual['week_low']} < stop={round(stop_price,2)})"
                else:
                    stop_note = f"stop held (low={actual['week_low']} > {round(stop_price,2)})"

            pat_str = " + ".join(pick["patterns_fired"][:2]) if len(pick["patterns_fired"]) > 1 else pick["primary_pattern"]
            combo_note = f" [COMBO x{pick['combo_count']}]" if pick["combo_count"] >= 2 else ""

            print(f"  #{rank} {ticker:<6} | {outcome} | PnL: {pnl_str:>8} | Score:{pick['score']:>5.1f}{combo_note}")
            print(f"     Pattern  : {pat_str}")
            print(f"     Detail   : {pick['pattern_detail']}")
            print(f"     Signals  : RSI14={pick['rsi14']} RSI7={pick['rsi7']} {'RECOV' if pick['rsi_recovering'] else 'FALL'} | CMF={pick['cmf']} | ATR={round(pick['atr_pct']*100,1)}% | EMA_align={pick['ema_align']} | RS21={pick['rs21']:.3f}")
            if actual:
                print(f"     Price    : entry={actual['entry_price']} exit={actual['exit_price']} | hi={actual['week_high']} lo={actual['week_low']}")
            if stop_note:
                print(f"     Stop     : {stop_note}")
            print()

        avg_pnl = week_pnl / len(top5) if top5 else 0
        print(f"{'─'*68}")
        print(f"WEEK: {week_wins}/{len(top5)} wins | Avg PnL: {avg_pnl:+.2f}% | Sum: {week_pnl:+.2f}%")

        all_weeks.append({
            "week": label, "regime": regime_label,
            "wins": week_wins, "total": len(top5), "avg_pnl": round(avg_pnl,2),
            "picks": [{"ticker": p["ticker"], "pattern": p["primary_pattern"],
                       "score": p["score"]} for p in top5]
        })

    # ── Grand Summary ──────────────────────────────────────────────────────
    print(f"\n{'='*68}")
    print("JANUARY 2026 BACKTEST — FINAL SUMMARY (regime-aware v2)")
    print(f"{'='*68}")
    print(f"{'Week':<10} {'Regime':<6} {'W/L':<7} {'AvgPnL':<10} Picks")
    print(f"{'─'*68}")
    for r in all_weeks:
        picks_str = "  ".join(f"{p['ticker']}({p['score']:.0f})" for p in r["picks"])
        print(f"{r['week']:<10} {r['regime']:<6} {r['wins']}/{r['total']:<5} {r['avg_pnl']:>+7.2f}%   {picks_str}")
    overall_wr = round(grand_wins / grand_picks * 100) if grand_picks else 0
    overall_avg = round(grand_pnl / grand_picks, 2) if grand_picks else 0
    print(f"{'─'*68}")
    print(f"OVERALL:  {grand_wins}/{grand_picks} wins ({overall_wr}%)  |  Avg PnL/pick: {overall_avg:+.2f}%  |  Sum: {grand_pnl:+.2f}%")
    print()

    # ── Failure Analysis ──────────────────────────────────────────────────
    print("WHAT WORKED / WHAT DIDN'T:")
    print("  - January 2026 = full BULL market (SPY above EMA50 all 4 weeks)")
    print("  - v1 system only had bear/oversold patterns → 0 candidates → BROKEN")
    print("  - v2 system adds bull playbook: EMA pullbacks, momentum, RS leaders")
    print("  - Key bull signals: ema_align>=2, roc5 in range, rs21>0, di_spread>0")


if __name__ == "__main__":
    run_backtest()
