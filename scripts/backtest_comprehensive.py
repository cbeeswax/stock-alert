"""
backtest_comprehensive.py
=========================
Full multi-layer stock scorer using ALL technical indicators.
Thinks like a senior analyst, not just a momentum chaser.

SCORING LAYERS:
  A. Stock Health      (0-25 pts)  — uptrend structure, RS, trend strength
  B. Pullback Quality  (0-30 pts)  — is this a BUY POINT, not a chase?
  C. Signal Strength   (0-25 pts)  — candle pattern + momentum turning
  D. Volume Story      (0-20 pts)  — institutional footprint
  Bonus:              (0-20 pts)  — squeeze, consolidation, stochastic, etc.

Minimum score to qualify: 48/100

Two valid bull setups:
  1. CLASSIC PULLBACK:  Orderly 5-12 day pullback to EMA21/50, volume dry-up, reversal candle
  2. MOMENTUM RESET:    High RS63 stock, RSI7 dropped 25+ pts from extreme, still above EMA50
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
    {"week_label": "Jan 19", "as_of": "2026-01-16", "entry_date": "2026-01-20", "exit_date": "2026-01-24"},
    {"week_label": "Jan 26", "as_of": "2026-01-23", "entry_date": "2026-01-26", "exit_date": "2026-01-30"},
]
TOP_N        = 5
QUALIFY_SCORE = 48


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _f(snap, k, d=0.0):
    v = snap.get(k)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return d
    try: return float(v)
    except: return d


def _detect_candle_patterns(df_ind: pd.DataFrame) -> list[str]:
    """
    Detect reversal candle patterns on the last bar.
    Needs the full indicator DataFrame (which includes open/high/low/close).
    Returns list of pattern names found.
    """
    if len(df_ind) < 3:
        return []

    patterns = []
    row0 = df_ind.iloc[-1]   # signal candle (today)
    row1 = df_ind.iloc[-2]   # prior day
    row2 = df_ind.iloc[-3]   # two days back

    o, h, l, c = float(row0["open"]), float(row0["high"]), float(row0["low"]), float(row0["close"])
    o1, h1, l1, c1 = float(row1["open"]), float(row1["high"]), float(row1["low"]), float(row1["close"])
    o2, h2, l2, c2 = float(row2["open"]), float(row2["high"]), float(row2["low"]), float(row2["close"])

    body   = abs(c - o)
    rng    = h - l if h > l else 0.001
    ls     = min(o, c) - l      # lower shadow
    us     = h - max(o, c)      # upper shadow

    body1  = abs(c1 - o1)
    rng1   = h1 - l1 if h1 > l1 else 0.001
    body2  = abs(c2 - o2)

    # --- Hammer: small body, long lower shadow (≥ 2×body), tiny upper shadow ---
    if rng > 0 and body / rng < 0.4 and ls >= 2 * body and us <= body * 0.5:
        patterns.append("hammer")

    # --- Bullish engulfing: green candle body wraps prior red body ---
    if c > o and c1 < o1 and c >= o1 and o <= c1 and body > body1 * 0.7:
        patterns.append("bullish_engulfing")

    # --- Doji: body < 10% of range ---
    if rng > 0 and body / rng < 0.10:
        patterns.append("doji")

    # --- Inside day: today's high/low inside prior bar ---
    if h < h1 and l > l1:
        patterns.append("inside_day")

    # --- Morning star (3-candle): big red → small body → big green ---
    if c2 < o2 and body2 > rng1 * 0.7 and body < body2 * 0.4 and c > o and c > (o2 + c2) / 2:
        patterns.append("morning_star")

    # --- Inverted hammer: small body, long upper shadow at a low ---
    if rng > 0 and body / rng < 0.35 and us >= 2 * body and ls <= body * 0.5:
        patterns.append("inverted_hammer")

    # --- Piercing line: red day then green opens lower but closes > midpoint of red ---
    if c1 < o1 and c > o and o < c1 and c > (o1 + c1) / 2:
        patterns.append("piercing_line")

    return patterns


def _volume_dryup(df_ind: pd.DataFrame, n=4) -> tuple[bool, float]:
    """
    Check if volume dried up over last n pullback days.
    True if average vol_ratio_20 < 0.87 — weak sellers, orderly pullback.
    Excludes today's bar (signal candle may have surge).
    """
    recent = df_ind["vol_ratio_20"].iloc[-(n+1):-1].dropna()
    if len(recent) < 2:
        return False, 1.0
    avg = float(recent.mean())
    return avg < 0.87, round(avg, 2)


def _rsi7_reset(df_ind: pd.DataFrame, lookback=8) -> tuple[float, bool]:
    """
    How much did RSI7 drop from its recent peak over the last 'lookback' days?
    Returns (drop_amount, was_reset_significant).
    """
    rsi7_series = df_ind["rsi7"].iloc[-lookback:].dropna()
    if len(rsi7_series) < 2:
        return 0.0, False
    peak = float(rsi7_series.iloc[:-1].max())   # peak BEFORE today
    current = float(rsi7_series.iloc[-1])
    drop = peak - current
    return drop, drop >= 20


def _pullback_days(df_ind: pd.DataFrame, n=12) -> int:
    """Count consecutive down-closes leading into today."""
    closes = df_ind["close"].iloc[-n:].dropna()
    count = 0
    for i in range(len(closes)-1, 0, -1):
        if closes.iloc[i] < closes.iloc[i-1]:
            count += 1
        else:
            break
    return count


# ─────────────────────────────────────────────────────────────────────────────
# THE COMPREHENSIVE SCORER
# ─────────────────────────────────────────────────────────────────────────────

def score_ticker_comprehensive(snap, df_ind, spy_above_ema50) -> dict | None:
    """
    4-layer scoring using ALL technical indicators.
    Returns None if stock fails hard filters or scores < QUALIFY_SCORE.
    """
    # ─── Extract all indicators ───
    close       = _f(snap, "close", 0)
    atr_pct     = _f(snap, "atr_pct", 0)          # ratio e.g. 0.025 = 2.5%
    rsi14       = _f(snap, "rsi14", 50)
    rsi7        = _f(snap, "rsi7", 50)
    rsi_slope   = _f(snap, "rsi_slope", 0)         # 5-day RSI14 change
    pct21       = _f(snap, "pct_vs_ema21", 0)      # ratio vs EMA21
    pct50       = _f(snap, "pct_vs_ema50", 0)
    pct200      = _f(snap, "pct_vs_ema200", 0)
    ema_align   = int(_f(snap, "ema_align", 0))
    ema21_slope = _f(snap, "ema21_slope", 0)
    ema50_slope = _f(snap, "ema50_slope", 0)
    vol_r       = _f(snap, "vol_ratio_20", 1)
    cmf         = _f(snap, "cmf", 0)
    mfi         = _f(snap, "mfi", 50)
    obv_s       = _f(snap, "obv_slope", 0)
    obv_ema     = int(_f(snap, "obv_above_ema", 0))
    macd_r      = int(_f(snap, "macd_hist_rising", 0))
    macd_hist   = _f(snap, "macd_hist", 0)
    macd_zero   = int(_f(snap, "macd_above_zero", 0))
    macd_cross  = _f(snap, "macd_cross_days", 0)
    stoch_k     = _f(snap, "stoch_k", 50)
    stoch_d     = _f(snap, "stoch_d", 50)
    stoch_bull  = int(_f(snap, "stoch_bullish", 0))
    adx         = _f(snap, "adx", 15)
    adx_rising  = int(_f(snap, "adx_rising", 0))
    di_spread   = _f(snap, "di_spread", 0)
    bb_pct      = _f(snap, "bb_pct", 0.5)
    bb_width_p  = _f(snap, "bb_width_percentile", 0.5)
    in_sq       = int(_f(snap, "in_squeeze", 0))
    bars_sq     = _f(snap, "bars_since_squeeze", 99)
    rs21        = _f(snap, "rs_21d", 0)
    rs63        = _f(snap, "rs_63d", 0)
    hh_hl       = _f(snap, "hh_hl", 0.5)
    pct52h      = _f(snap, "pct_from_52w_high", -0.5)
    pct52l      = _f(snap, "pct_from_52w_low", 0.5)
    consol      = _f(snap, "consolidation_score", 0.5)
    roc5        = _f(snap, "roc5", 0)
    roc21       = _f(snap, "roc21", 0)

    # ── HARD FILTERS — automatic disqualification ──────────────────────────
    if close < 15:             return None   # micro-caps: too risky
    if atr_pct < 0.012:        return None   # too quiet to trade
    if atr_pct > 0.12:         return None   # too volatile (>12%/day = speculation)
    if vol_r < 0.3:            return None   # dead volume
    if pct200 < -0.05:         return None   # below SMA200 = long-term downtrend
    if pct52h < -0.55:         return None   # fallen knife: 55%+ below 52w high
    if cmf < -0.22:            return None   # heavy institutional selling
    # Falling knife: sharp drop + money flowing out
    if (rsi14 - rsi7) > 14 and cmf < -0.12: return None
    # Extended: way above EMA21 in a bull market (chasing)
    if spy_above_ema50 and pct21 > 0.17:   return None
    # RSI7 extreme overbought: extended, not a buy point
    if spy_above_ema50 and rsi7 > 78 and pct21 > 0.03: return None
    # In bear, skip stocks still in strong uptrend (catch falling knives in reverse)
    if not spy_above_ema50 and ema_align == 4 and rsi14 > 65: return None

    score     = 0.0
    breakdown = {}

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER A: STOCK HEALTH (0-25 pts)
    # Is this stock in a healthy uptrend worth trading?
    # ═══════════════════════════════════════════════════════════════════════
    pts_a = 0.0

    # Long-term trend health (10 pts max)
    if ema_align >= 4: pts_a += 10     # fully stacked: price>EMA9>21>50>200
    elif ema_align == 3: pts_a += 7    # 3/4 aligned
    elif ema_align == 2: pts_a += 4    # 2/4 — mixed
    elif ema_align == 1: pts_a += 1    # weak

    # 63-day relative strength vs SPY (institutional timeframe) (6 pts max)
    if rs63 > 0.20:  pts_a += 6       # massive outperformer
    elif rs63 > 0.10: pts_a += 5
    elif rs63 > 0.05: pts_a += 4
    elif rs63 > 0.0:  pts_a += 3
    elif rs63 > -0.05: pts_a += 1
    # negative rs63 = underperformer, 0 pts

    # Trend direction quality (5 pts max)
    if adx > 30 and di_spread > 10:   pts_a += 5  # strong trend, buyers in control
    elif adx > 22 and di_spread > 5:  pts_a += 3
    elif adx > 15 and di_spread > 0:  pts_a += 1

    # Price structure: higher highs / higher lows (4 pts)
    if hh_hl >= 0.7:    pts_a += 4
    elif hh_hl >= 0.5:  pts_a += 2

    breakdown["A_health"] = round(pts_a, 1)
    score += pts_a

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER B: PULLBACK QUALITY (0-30 pts)
    # Is this a BUY POINT, not a chase?
    # Two valid setups: Classic Pullback OR Momentum RSI Reset
    # ═══════════════════════════════════════════════════════════════════════
    pts_b = 0.0
    setup_type = "NONE"

    rsi7_drop, had_reset = _rsi7_reset(df_ind, lookback=10)
    vol_dryup, avg_pull_vol = _volume_dryup(df_ind, n=4)
    pb_days = _pullback_days(df_ind, n=12)

    if spy_above_ema50:
        # ── Setup Type 1: CLASSIC EMA PULLBACK ──
        # Orderly pullback to EMA21/50 on declining volume with RSI cooling
        classic_pb = (
            -0.15 <= pct21 <= -0.015       # price between -1.5% and -15% vs EMA21
            and 30 <= rsi14 <= 62           # RSI14 cooled off but not oversold crash
            and rsi7 <= 62                  # RSI7 not extended
            and ema21_slope >= -0.003       # EMA21 still rising or flat (trend intact)
        )

        # ── Setup Type 2: MOMENTUM RSI RESET ──
        # High RS63 stock, RSI7 dropped hard (≥ 20pts from peak), still above EMA50
        momentum_reset = (
            rs63 >= 0.08                    # stock is a solid outperformer
            and had_reset                   # RSI7 reset ≥ 20 pts from peak
            and rsi7 <= 62                  # current RSI7 is now moderate
            and pct50 > -0.03              # still above/near EMA50 (trend intact)
            and adx > 22                    # trend is still real
        )

        if classic_pb:
            setup_type = "CLASSIC_PULLBACK"
            # Score the pullback quality
            # Price location (how perfectly aligned to EMA21)
            if -0.08 <= pct21 <= -0.02:   pts_b += 12   # sweet spot
            elif -0.12 <= pct21 <= -0.008: pts_b += 8
            else:                           pts_b += 4

            # RSI cooldown depth
            if 35 <= rsi14 <= 52:          pts_b += 8   # nicely cooled
            elif 52 < rsi14 <= 60:         pts_b += 5   # moderately cooled
            elif 30 <= rsi14 < 35:         pts_b += 4   # deep but valid

            # RSI7 < RSI14: short-term weaker than medium = cooling momentum
            if rsi7 < rsi14:               pts_b += 4

            # Volume drying up during pullback
            if vol_dryup:                  pts_b += 6   # sellers losing steam
            elif avg_pull_vol < 1.0:       pts_b += 2

        if momentum_reset:
            if setup_type == "CLASSIC_PULLBACK":
                setup_type = "CLASSIC_PULLBACK+RESET"
                pts_b += 5   # bonus for combo
            else:
                setup_type = "MOMENTUM_RESET"
                # RSI reset magnitude
                if rsi7_drop >= 35:        pts_b += 15
                elif rsi7_drop >= 25:      pts_b += 12
                else:                       pts_b += 8

                # Still healthy: above EMA50
                if pct50 >= -0.02:         pts_b += 8
                elif pct50 >= -0.08:       pts_b += 4

                # RS63 quality
                if rs63 > 0.30:            pts_b += 7
                elif rs63 > 0.15:          pts_b += 5
                else:                       pts_b += 3

        # Bonus: RSI slope turning (was falling, now flat/rising)
        if rsi_slope > 0 and setup_type != "NONE":    pts_b += 3
        # Bonus: price held EMA50 (deep but safe)
        if -0.03 <= pct50 <= 0.02 and setup_type != "NONE": pts_b += 3

    else:
        # ── BEAR MARKET: Oversold Mean Reversion ──
        setup_type = "BEAR_MEAN_REVERSION"

        if bb_pct < 0.10 and rsi7 < 25:
            pts_b += 20   # extreme oversold — highest prob bear setup
        elif rsi7 < 30 and rsi14 < 42:
            pts_b += 14
        elif rsi7 < 38 and bb_pct < 0.25:
            pts_b += 8

        # Volume capitulation + exhaustion
        if vol_r > 2.5 and rsi7 < 30:    pts_b += 6   # capitulation volume
        if rsi_slope > 0:                  pts_b += 4   # RSI starting to recover

    if setup_type == "NONE":
        return None   # No valid setup found

    breakdown["B_pullback"] = round(pts_b, 1)
    breakdown["B_setup"] = setup_type
    score += pts_b

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER C: SIGNAL STRENGTH (0-25 pts)
    # Is momentum actually TURNING? Reversal candle + indicators confirming
    # ═══════════════════════════════════════════════════════════════════════
    pts_c = 0.0
    candle_patterns = _detect_candle_patterns(df_ind)

    # Reversal candle (the actual signal)
    # Weighted by quality of pattern (from backtested win rates)
    if "morning_star" in candle_patterns:          pts_c += 10  # 3-candle, 39% WR
    if "bullish_engulfing" in candle_patterns:     pts_c += 9   # 39.3% WR
    if "hammer" in candle_patterns:                pts_c += 8   # 43.8% WR
    if "piercing_line" in candle_patterns:         pts_c += 7
    if "inverted_hammer" in candle_patterns:       pts_c += 6   # 44.1% WR
    if "doji" in candle_patterns:                  pts_c += 5   # 41.9% WR
    if "inside_day" in candle_patterns:            pts_c += 4   # 38.6% WR
    pts_c = min(pts_c, 10)  # cap candle contribution at 10

    # MACD momentum turn
    if macd_r and macd_hist > macd_hist:           pts_c += 3   # histogram rising
    if macd_r:                                     pts_c += 3
    if macd_cross > 0:                             pts_c += 4   # bull cross in last 3 days

    # Stochastic: oversold in short term = near inflection
    if stoch_k < 25:                               pts_c += 5
    elif stoch_k < 35:                             pts_c += 3
    elif stoch_k < 45 and stoch_bull:             pts_c += 2

    # RSI14 slope turning up (momentum inflection)
    if rsi_slope > 2:                              pts_c += 3   # RSI actively rising
    elif rsi_slope > 0:                            pts_c += 1

    breakdown["C_signal"]  = round(pts_c, 1)
    breakdown["C_candles"] = candle_patterns
    score += pts_c

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER D: VOLUME STORY (0-20 pts)
    # Are institutions accumulating? Is smart money flowing in?
    # ═══════════════════════════════════════════════════════════════════════
    pts_d = 0.0

    # OBV: overall volume trend (5 pts)
    if obv_ema and obv_s > 0.05:  pts_d += 5   # OBV above EMA AND rising slope
    elif obv_ema:                  pts_d += 3   # OBV above EMA
    elif obv_s > 0:                pts_d += 1   # slope positive but below EMA

    # CMF: Chaikin Money Flow (6 pts)
    if cmf > 0.15:   pts_d += 6   # strong institutional inflow
    elif cmf > 0.08: pts_d += 5
    elif cmf > 0.0:  pts_d += 3
    elif cmf > -0.08: pts_d += 1  # slight outflow — neutral

    # MFI: Money Flow Index (4 pts)
    if mfi > 55:     pts_d += 2
    if mfi < 40:     pts_d += 2   # oversold in MFI = good entry for bull

    # Volume on signal candle (5 pts)
    if vol_r > 1.8:  pts_d += 5   # strong surge = buyers stepping in
    elif vol_r > 1.3: pts_d += 3
    elif vol_r > 0.9: pts_d += 1

    breakdown["D_volume"] = round(pts_d, 1)
    score += pts_d

    # ═══════════════════════════════════════════════════════════════════════
    # BONUS POINTS (up to +20)
    # Extra conviction from squeeze, consolidation, sector, stochastic
    # ═══════════════════════════════════════════════════════════════════════
    bonus = 0.0

    # Bollinger squeeze releasing = coiled energy
    if in_sq:                       bonus += 5   # squeeze still on = energy building
    if 0 < bars_sq <= 3:           bonus += 8   # just released from squeeze → breakout
    elif 0 < bars_sq <= 7:         bonus += 4

    # Tight consolidation before move
    if consol > 0.70:              bonus += 5   # very tight range = ready to break
    elif consol > 0.55:            bonus += 3
    elif consol > 0.40:            bonus += 1

    # 21-day RS: positive (outperforming SPY recently)
    if rs21 > 0.05:                bonus += 3
    elif rs21 > 0.0:               bonus += 1

    # ATR volatility: more volatile = more potential reward per setup
    if atr_pct > 0.05:             bonus += 4   # >5%/day ATR
    elif atr_pct > 0.03:           bonus += 2

    # MACD above zero line = overall bullish momentum
    if macd_zero:                  bonus += 2

    # ADX rising = trend gaining strength
    if adx_rising:                 bonus += 2

    # Multiple candle patterns firing = higher conviction
    if len(candle_patterns) >= 2:  bonus += 4

    bonus = min(bonus, 20)
    breakdown["bonus"] = round(bonus, 1)
    score += bonus

    # ═══════════════════════════════════════════════════════════════════════
    # APPLY DEDUCTIONS (red flags)
    # ═══════════════════════════════════════════════════════════════════════
    deductions = 0.0

    # RSI7 still high: not cooled enough (only matters for classic pullback)
    if setup_type == "CLASSIC_PULLBACK" and rsi7 > 65:
        deductions += 8
    elif setup_type == "CLASSIC_PULLBACK" and rsi7 > 58:
        deductions += 4

    # Overbought MFI: potential top
    if mfi > 75:                   deductions += 4

    # 21-day RS negative: underperforming SPY recently (momentum divergence)
    if spy_above_ema50 and rs21 < -0.05:  deductions += 5

    # Price far below 52w high without being in a bounce setup
    if pct52h < -0.40 and setup_type not in ("BEAR_MEAN_REVERSION", "CLASSIC_PULLBACK"):
        deductions += 6

    # CMF mildly negative (already penalized in Layer D, mild extra)
    if -0.22 < cmf < -0.12:       deductions += 3

    breakdown["deductions"] = round(deductions, 1)
    score -= deductions

    final_score = round(min(max(score, 0), 100), 1)

    if final_score < QUALIFY_SCORE:
        return None

    # Calculate risk/reward for display
    atr_dollar = atr_pct * close
    stop_dist  = max(2.0 * atr_dollar, abs(pct21) * close * 0.5)  # 2×ATR or half the pullback depth
    stop_price = round(close - stop_dist, 2)
    target     = round(close + 2.5 * stop_dist, 2)   # 2.5:1 reward/risk

    return {
        "score":         final_score,
        "setup":         setup_type,
        "layer_A":       breakdown["A_health"],
        "layer_B":       breakdown["B_pullback"],
        "layer_C":       breakdown["C_signal"],
        "layer_D":       breakdown["D_volume"],
        "bonus":         breakdown["bonus"],
        "deductions":    breakdown["deductions"],
        "candles":       candle_patterns,
        "rsi14":         round(rsi14, 1),
        "rsi7":          round(rsi7, 1),
        "rsi7_drop":     round(rsi7_drop, 1),
        "rs63_pct":      round(rs63 * 100, 1),
        "rs21_pct":      round(rs21 * 100, 1),
        "pct21":         round(pct21 * 100, 1),
        "pct50":         round(pct50 * 100, 1),
        "atr_pct":       round(atr_pct * 100, 2),
        "close":         round(close, 2),
        "adx":           round(adx, 1),
        "cmf":           round(cmf, 3),
        "stoch_k":       round(stoch_k, 1),
        "vol_dry":       vol_dryup,
        "stop":          stop_price,
        "target":        target,
        "rr":            2.5,
        "pct52h":        round(pct52h * 100, 1),
        "in_squeeze":    bool(in_sq),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ACTUAL P&L (exit at Friday close, honest weekly return)
# ─────────────────────────────────────────────────────────────────────────────

def get_weekly_return(ticker, entry_date, exit_date):
    df = load_daily(ticker)
    if df is None or df.empty: return None
    entry_ts = pd.Timestamp(entry_date)
    exit_ts  = pd.Timestamp(exit_date)
    entry_rows = df[df.index >= entry_ts]
    exit_rows  = df[(df.index >= entry_ts) & (df.index <= exit_ts)]
    if entry_rows.empty or exit_rows.empty: return None
    entry_price = float(entry_rows.iloc[0].get("open", entry_rows.iloc[0]["close"]))
    exit_price  = float(exit_rows.iloc[-1]["close"])
    if entry_price <= 0: return None
    pnl_pct   = round((exit_price - entry_price) / entry_price * 100, 2)
    return {
        "entry_price": round(entry_price, 2),
        "exit_price":  round(exit_price, 2),
        "pnl_pct":     pnl_pct,
        "week_high":   round(float(exit_rows["high"].max()), 2),
        "week_low":    round(float(exit_rows["low"].min()), 2),
        "win":         pnl_pct > 1.0,
        "loss":        pnl_pct < -1.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest():
    tickers = sorted(
        f.replace(".csv","") for f in os.listdir(DATA_DIR)
        if f.endswith(".csv") and not f.startswith("_")
    )

    all_trades  = []
    grand_pnl   = 0.0
    grand_wins  = 0
    grand_picks = 0

    for week in WEEKS:
        label      = week["week_label"]
        as_of      = week["as_of"]
        entry_date = week["entry_date"]
        exit_date  = week["exit_date"]

        print(f"\n{'='*75}")
        print(f"WEEK OF {label.upper()} | as-of {as_of} | entry {entry_date} | exit {exit_date}")
        print(f"{'='*75}")

        spy_df = load_daily("SPY", end=as_of)
        spy_above_ema50 = True
        regime_label = "BULL"

        if spy_df is not None and len(spy_df) >= 50:
            spy_ind  = compute_daily_indicators(spy_df)
            spy_snap = get_snapshot(spy_ind, pd.Timestamp(as_of))
            if spy_snap is not None:
                spy_close       = float(spy_snap.get("close") or 0)
                spy_ema50       = float(spy_snap.get("ema50") or 0)
                spy_above_ema50 = spy_close > spy_ema50
                regime_label    = "BULL" if spy_above_ema50 else "BEAR"
                spy_rsi         = round(float(spy_snap.get("rsi14") or 50), 1)
                spy_cmf         = round(float(spy_snap.get("cmf") or 0), 3)
                spy_roc21       = round(float(spy_snap.get("roc21") or 0) * 100, 1)
                spy_adx         = round(float(spy_snap.get("adx") or 0), 1)
                print(f"Regime: {regime_label} | SPY ROC21={spy_roc21:+.1f}% RSI={spy_rsi} CMF={spy_cmf} ADX={spy_adx}")

        candidates = []
        errors = 0
        for ticker in tickers:
            if ticker == "SPY": continue
            try:
                df  = load_daily(ticker, end=as_of)
                if df is None or len(df) < 200: continue
                ind  = compute_daily_indicators(df, spy=spy_df)
                snap = get_snapshot(ind, pd.Timestamp(as_of))
                if snap is None or snap.empty: continue
                result = score_ticker_comprehensive(snap, ind, spy_above_ema50)
                if result is None: continue
                result["ticker"] = ticker
                candidates.append(result)
            except Exception as e:
                errors += 1
                continue

        candidates.sort(key=lambda x: x["score"], reverse=True)
        top5 = candidates[:TOP_N]

        print(f"\n{len(candidates)} qualified (out of {len(tickers)-1} tickers, {errors} errors) | Top {TOP_N}:\n")

        hdr = f"{'TICK':<6} {'Scr':>4} {'A':>4} {'B':>4} {'C':>4} {'D':>4} {'Bon':>4} {'Setup':<22} {'RSI14':>5} {'RSI7':>5} {'RS63%':>6} {'ATR%':>5} {'%EMA21':>7} {'StchK':>5} {'CMF':>6} {'ADX':>4}"
        print(hdr)
        print("-"*115)

        week_pnl  = 0.0
        week_wins = 0

        for rank, pick in enumerate(top5, 1):
            ticker = pick["ticker"]
            actual = get_weekly_return(ticker, entry_date, exit_date)

            candle_str = ",".join(pick["candles"][:2]) if pick["candles"] else "none"
            print(f"{ticker:<6} {pick['score']:>4.0f} {pick['layer_A']:>4.0f} {pick['layer_B']:>4.0f} "
                  f"{pick['layer_C']:>4.0f} {pick['layer_D']:>4.0f} {pick['bonus']:>4.0f} "
                  f"{pick['setup']:<22} {pick['rsi14']:>5.0f} {pick['rsi7']:>5.0f} "
                  f"{pick['rs63_pct']:>6.1f} {pick['atr_pct']:>5.1f} "
                  f"{pick['pct21']:>7.1f} {pick['stoch_k']:>5.0f} {pick['cmf']:>6.3f} "
                  f"{pick['adx']:>4.0f}")
            print(f"       candles={candle_str:<30} vol_dry={pick['vol_dry']} squeeze={pick['in_squeeze']}"
                  f"  stop=${pick['stop']:.2f}  target=${pick['target']:.2f}")

            if actual:
                pnl    = actual["pnl_pct"]
                sym    = "✓" if actual["win"] else ("✗" if actual["loss"] else "—")
                print(f"       RESULT: entry=${actual['entry_price']} → exit=${actual['exit_price']}  "
                      f"PnL={pnl:+.2f}%{sym}  (week high=${actual['week_high']}  low=${actual['week_low']})")
                week_pnl  += pnl
                grand_pnl += pnl
                grand_picks += 1
                if actual["win"]:
                    week_wins  += 1
                    grand_wins += 1
                all_trades.append({
                    "week": label, "ticker": ticker,
                    "score": pick["score"], "setup": pick["setup"],
                    "pnl_pct": pnl, "win": actual["win"], "loss": actual["loss"],
                    "week_high": actual["week_high"], "entry": actual["entry_price"],
                })
            print()

        avg = week_pnl / len(top5) if top5 else 0
        print(f"  ─── Week {label}: {week_wins}/{len(top5)} wins | Avg PnL = {avg:+.2f}% ───")

    # ── SUMMARY ──
    print(f"\n{'='*75}")
    print("COMPREHENSIVE BACKTEST SUMMARY — JANUARY 2026")
    print(f"{'='*75}")
    if grand_picks:
        print(f"Total picks: {grand_picks} | Wins: {grand_wins} ({grand_wins/grand_picks*100:.0f}%)")
        print(f"Total PnL (sum all picks): {grand_pnl:+.2f}%")
        print(f"Avg PnL per pick:          {grand_pnl/grand_picks:+.2f}%")

        wins   = [t for t in all_trades if t["win"]]
        losses = [t for t in all_trades if t["loss"]]
        if wins:   print(f"Avg WIN:  {sum(t['pnl_pct'] for t in wins)/len(wins):+.2f}%")
        if losses: print(f"Avg LOSS: {sum(t['pnl_pct'] for t in losses)/len(losses):+.2f}%")

        print(f"\nSetup breakdown:")
        from collections import Counter
        for setup, cnt in Counter(t["setup"] for t in all_trades).most_common():
            st = [t for t in all_trades if t["setup"]==setup]
            sw = sum(1 for t in st if t["win"])
            print(f"  {setup:<30} {sw}/{cnt} wins")

        print(f"\nBest trades:")
        for t in sorted(all_trades, key=lambda x: x["pnl_pct"], reverse=True)[:5]:
            print(f"  {t['week']:6} {t['ticker']:6} {t['pnl_pct']:+.1f}%  [{t['setup']}]")
        print(f"\nWorst trades:")
        for t in sorted(all_trades, key=lambda x: x["pnl_pct"])[:5]:
            print(f"  {t['week']:6} {t['ticker']:6} {t['pnl_pct']:+.1f}%  [{t['setup']}]")


if __name__ == "__main__":
    run_backtest()
