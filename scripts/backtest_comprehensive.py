"""
backtest_comprehensive.py
=========================
Full multi-layer stock scorer using ALL technical indicators.
Thinks like a senior analyst, not just a momentum chaser.

SCORING LAYERS:
  0. Context Filter    — Stage classification, weekly trend, REJECT Stage3/4/FAILED
  A. Stock Health      (0-25 pts)  — uptrend structure, RS, trend strength, sector leadership
  B. Pullback Quality  (0-30 pts)  — is this a BUY POINT, not a chase?
  C. Signal Strength   (0-25 pts)  — candle pattern + momentum turning
  D. Volume Story      (0-20 pts)  — institutional pattern (ACCUMULATING/MARKUP/DISTRIBUTING)
  Bonus:              (0-25 pts)  — weekly context, RS line new high, squeeze, etc.

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
from src.analysis.predictor.daily_indicators import (
    compute_daily_indicators, compute_weekly_indicators,
    compute_sector_rs, get_snapshot, get_weekly_snapshot
)
from src.analysis.predictor.stage_classifier import classify_stage, classify_institutional

WEEKS = [
    # January 2026
    {"week_label": "Jan 5",  "as_of": "2026-01-02", "entry_date": "2026-01-05", "exit_date": "2026-01-09"},
    {"week_label": "Jan 12", "as_of": "2026-01-09", "entry_date": "2026-01-12", "exit_date": "2026-01-16"},
    {"week_label": "Jan 19", "as_of": "2026-01-16", "entry_date": "2026-01-20", "exit_date": "2026-01-24"},
    {"week_label": "Jan 26", "as_of": "2026-01-23", "entry_date": "2026-01-26", "exit_date": "2026-01-30"},
    # February 2026
    {"week_label": "Feb 2",  "as_of": "2026-01-30", "entry_date": "2026-02-02", "exit_date": "2026-02-06"},
    {"week_label": "Feb 9",  "as_of": "2026-02-06", "entry_date": "2026-02-09", "exit_date": "2026-02-13"},
    {"week_label": "Feb 17", "as_of": "2026-02-13", "entry_date": "2026-02-17", "exit_date": "2026-02-20"},  # Presidents Day Feb 16
    {"week_label": "Feb 23", "as_of": "2026-02-20", "entry_date": "2026-02-23", "exit_date": "2026-02-27"},
    # March 2026
    {"week_label": "Mar 2",  "as_of": "2026-02-27", "entry_date": "2026-03-02", "exit_date": "2026-03-06"},
    {"week_label": "Mar 9",  "as_of": "2026-03-06", "entry_date": "2026-03-09", "exit_date": "2026-03-13"},
    {"week_label": "Mar 16", "as_of": "2026-03-13", "entry_date": "2026-03-16", "exit_date": "2026-03-20"},
    {"week_label": "Mar 23", "as_of": "2026-03-20", "entry_date": "2026-03-23", "exit_date": "2026-03-27"},
    {"week_label": "Mar 30", "as_of": "2026-03-27", "entry_date": "2026-03-30", "exit_date": "2026-04-03"},
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


def _detect_support(df_ind: pd.DataFrame, wsnap: pd.Series = None) -> dict:
    """
    Collect ALL meaningful support levels below the current price,
    then select the CLOSEST one as the stop anchor.

    Support levels checked (in descending priority of reliability):
      - EMA9, EMA21, EMA50, EMA200         (dynamic trend support)
      - Swing low 5d, 10d, 15d, 20d        (recent structural lows)
      - Bollinger lower band (20-day)       (mean-reversion floor)
      - Keltner lower band (20-day)         (volatility-adjusted floor)
      - Prior week's candle low             (weekly structure support)
      - Volume shelf / POC (60-day)         (institutional accumulation zone)
      - Nearest round numbers               ($5/$10/$25/$50 levels)

    Stop = closest support level below price - ATR-proportional buffer.

    Rationale: if the nearest support breaks, price falls to the next level.
    We exit before that cascade begins — thesis is invalidated at first break.
    """
    if len(df_ind) < 20:
        close = float(df_ind["close"].iloc[-1]) if len(df_ind) > 0 else 0
        return {"structural_stop": close * 0.95, "note": "insufficient data",
                "ema_confluence": False, "structural_target": close * 1.10,
                "all_levels": []}

    close = float(df_ind["close"].iloc[-1])
    atr   = float(df_ind["atr14"].iloc[-1]) if "atr14" in df_ind.columns else close * 0.02

    def _get(col):
        if col in df_ind.columns:
            v = df_ind[col].iloc[-1]
            if pd.notna(v):
                return float(v)
        return None

    # ── Collect every support level below close ───────────────────────────────
    candidates: list[tuple[str, float]] = []

    def _add(label, value):
        if value is not None and value > 0 and value < close:
            candidates.append((label, round(value, 2)))

    # EMAs — dynamic trend support (most reliable for swing trades)
    _add("EMA9",   _get("ema9"))
    _add("EMA21",  _get("ema21"))
    _add("EMA50",  _get("ema50"))
    _add("EMA200", _get("ema200"))

    # Swing lows — recent structural lows
    _add("swing_5d",  _get("swing_low_5d"))
    _add("swing_10d", _get("swing_low_10d"))
    _add("swing_15d", _get("swing_low_15d"))
    _add("swing_20d", _get("swing_low_20d"))

    # Bollinger lower — mean-reversion floor
    _add("BB_lower", _get("bb_lower"))

    # Keltner lower — volatility-adjusted floor
    _add("KC_lower", _get("kc_lower"))

    # Volume shelf / POC — institutional accumulation zone
    _add("vol_shelf", _get("vol_shelf"))

    # Prior week low from weekly snapshot
    if wsnap is not None and not wsnap.empty:
        pw_low = wsnap.get("prior_week_low")
        if pw_low and pd.notna(pw_low):
            _add("prior_week_low", float(pw_low))

    # Round number levels — psychological support ($5/$10/$25/$50)
    for step in [50, 25, 10, 5]:
        rnd = (close // step) * step
        if 0 < rnd < close:
            _add(f"round_{step}", rnd)
            break  # only add the nearest round number per tier

    # ── Select best support: closest that is still ≥1.0×ATR away ────────────
    # Stops inside 1×ATR are pure noise — they get hit by normal daily volatility.
    # We want structure-based stops that are meaningful, not just the nearest EMA.
    min_dist = 1.0 * atr  # minimum distance from price to be outside noise zone

    if not candidates:
        structural_stop = round(close - 2.0 * atr, 2)
        note = "2×ATR fallback (no support levels found)"
        best_level = structural_stop
    else:
        candidates.sort(key=lambda x: x[1], reverse=True)  # closest first

        # Find the closest support that is ≥ min_dist below close
        best_label, best_level = None, None
        for lbl, lvl in candidates:
            if (close - lvl) >= min_dist:
                best_label, best_level = lbl, lvl
                break

        if best_level is None:
            # All supports are inside noise zone — use 2×ATR
            best_label = "2×ATR_fallback"
            best_level = close - 2.0 * atr

        # Buffer below support: 0.2×ATR clears the support level cleanly
        buffer = min(max(atr * 0.20, best_level * 0.003), best_level * 0.01)
        structural_stop = round(best_level - buffer, 2)
        note = f"stop below {best_label} @ {best_level:.2f} (buf={buffer:.2f}, dist={close-best_level:.2f}={((close-best_level)/atr):.1f}×ATR)"

    # Hard floor: never closer than 1.5×ATR (stops inside this range get hit by noise)
    noise_floor = round(close - 1.5 * atr, 2)
    if structural_stop > noise_floor:
        structural_stop = noise_floor
        note += " [clamped to 1.5×ATR noise floor]"

    # ── R/R target at 2.5:1 ──────────────────────────────────────────────────
    risk = max(close - structural_stop, atr * 0.5)
    structural_target = round(close + 2.5 * risk, 2)

    # EMA confluence: EMA21 and EMA50 within 2% = double support
    ema21 = _get("ema21") or 0
    ema50 = _get("ema50") or 0
    ema_confluence = (ema21 > 0 and ema50 > 0
                      and abs(ema21 - ema50) / ema50 < 0.02)

    return {
        "structural_stop":   structural_stop,
        "structural_target": structural_target,
        "structural_rr":     round((structural_target - close) / max(risk, 0.01), 1),
        "ema_confluence":    ema_confluence,
        "note":              note,
        "all_levels":        candidates,   # full stack for debugging
    }


# ─────────────────────────────────────────────────────────────────────────────
# THE COMPREHENSIVE SCORER
# ─────────────────────────────────────────────────────────────────────────────

def score_ticker_comprehensive(snap, df_ind, spy_above_ema50, wsnap=None) -> dict | None:
    """
    4-layer scoring using ALL technical indicators.
    Returns None if stock fails hard filters or scores < QUALIFY_SCORE.

    Parameters
    ----------
    snap            : daily indicator snapshot (pd.Series from get_snapshot)
    df_ind          : full daily indicator DataFrame (needed for candle patterns, support)
    spy_above_ema50 : bool — broad market regime
    wsnap           : weekly indicator snapshot (pd.Series from get_weekly_snapshot) — optional
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
    # Stage 1 additions: RS line trend + sector RS
    rs_line_new_high    = int(_f(snap, "rs_line_new_high", 0))
    rs_line_63d_high    = int(_f(snap, "rs_line_63d_high", 0))
    rs_line_above_ema21 = int(_f(snap, "rs_line_above_ema21", 0))
    rs_vs_sector_63d    = _f(snap, "rs_vs_sector_63d", 0)
    sector_leader       = int(_f(snap, "sector_leader", 0))

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
    qualify_threshold = QUALIFY_SCORE  # local copy — never mutate global

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 0: WEEKLY CONTEXT + STAGE CONTEXT (additive only — no hard rejects)
    # Stage/institutional info adds BONUS points or DEDUCTIONS.
    # The original A/B/C/D scoring (which gave 75% WR) is the primary signal.
    # These are senior analyst context signals layered ON TOP.
    # ═══════════════════════════════════════════════════════════════════════
    stage_result = None
    inst_result  = None
    weekly_context_bonus = 0.0
    weekly_above_ema40 = False
    weekly_ema10_slope = 0.0
    weekly_macd_bull   = False
    weekly_rsi14       = 50.0
    weekly_rs_rising   = False

    if wsnap is not None and not (isinstance(wsnap, pd.Series) and wsnap.empty):
        stage_result = classify_stage(snap, wsnap)
        breakdown["stage"] = stage_result.stage

        weekly_above_ema40 = bool(wsnap.get("weekly_above_ema40", False))
        weekly_ema10_slope = float(wsnap.get("weekly_ema10_slope", 0) or 0)
        weekly_macd_bull   = bool(wsnap.get("weekly_macd_bullish", False))
        weekly_rsi14       = float(wsnap.get("weekly_rsi14", 50) or 50)
        weekly_rs_rising   = bool(wsnap.get("weekly_rs_line_rising", False))

        # Weekly context bonus (positive signals)
        if weekly_above_ema40 and weekly_ema10_slope > 0:
            weekly_context_bonus += 5
        elif weekly_above_ema40:
            weekly_context_bonus += 2
        if weekly_macd_bull:
            weekly_context_bonus += 3
        if 35 < weekly_rsi14 < 65:
            weekly_context_bonus += 2   # room to run on weekly timeframe
        if weekly_rs_rising:
            weekly_context_bonus += 3

        # Counter-trend: raise qualify bar (don't hard reject)
        if not weekly_above_ema40 and spy_above_ema50:
            qualify_threshold = 58
            breakdown["counter_trend"] = True

    if len(df_ind) >= 20:
        inst_result = classify_institutional(df_ind, lookback=20)
        breakdown["institutional"] = inst_result.pattern

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
    # Primary: raw CMF/OBV (same as original 75% WR system)
    # Secondary: institutional pattern from classifier adds context
    # ═══════════════════════════════════════════════════════════════════════
    pts_d = 0.0

    # OBV: overall volume trend (5 pts) — original scoring
    if obv_ema and obv_s > 0.05:  pts_d += 5
    elif obv_ema:                  pts_d += 3
    elif obv_s > 0:                pts_d += 1

    # CMF: Chaikin Money Flow (6 pts) — original scoring
    if cmf > 0.15:    pts_d += 6
    elif cmf > 0.08:  pts_d += 5
    elif cmf > 0.0:   pts_d += 3
    elif cmf > -0.08: pts_d += 1

    # MFI: Money Flow Index (4 pts) — original scoring
    if mfi > 55:  pts_d += 2
    if mfi < 40:  pts_d += 2

    # Volume on signal candle (5 pts) — original scoring
    if vol_r > 1.8:   pts_d += 5
    elif vol_r > 1.3: pts_d += 3
    elif vol_r > 0.9: pts_d += 1

    # Institutional pattern: small adjustment on top of above (not replacing it)
    if inst_result is not None:
        if inst_result.pattern == "ACCUMULATING":  pts_d += 3   # strong confirmation
        elif inst_result.pattern == "DISTRIBUTING": pts_d -= 8  # deduction, not hard reject

    pts_d = max(pts_d, 0)
    breakdown["D_volume"] = round(pts_d, 1)
    score += pts_d

    # ═══════════════════════════════════════════════════════════════════════
    # BONUS POINTS (up to +25)
    # Weekly context, RS line leadership, squeeze, consolidation, sector
    # ═══════════════════════════════════════════════════════════════════════
    bonus = 0.0

    # Weekly structural context (pre-computed above)
    bonus += weekly_context_bonus

    # RS line leadership (earliest institutional signal)
    if rs_line_new_high:           bonus += 8   # RS at 52-week high = institutions accumulating BEFORE price
    elif rs_line_63d_high:         bonus += 5   # RS line at 63-day high = recent momentum
    if rs_line_above_ema21:        bonus += 3   # RS line in uptrend

    # Sector leadership: stock beats sector, sector beats SPY
    if sector_leader:              bonus += 5   # true leader: beats sector + SPY
    elif rs_vs_sector_63d > 0.05: bonus += 3   # beats sector moderately
    elif rs_vs_sector_63d > 0.0:  bonus += 1

    # ── Stage bonus: senior analyst logic ──────────────────────────────────
    # Stage 2 Early is the BEST setup ONLY when ALL three are true:
    #   1. RS line is at new high (institutions accumulating BEFORE price breakout)
    #   2. Weekly volume expanded on the breakout week (real buying, not drift)
    #   3. Stock formed a proper base first (≥6 weeks of tight consolidation)
    # Without all three, an early breakout is a FALSE BREAKOUT RISK and is
    # actually WORSE than a confirmed mature trend.
    #
    # Stage 2 Mature: confirmed trend — institutions have established positions.
    # It has lower upside ceiling but much higher reliability. Reward the RS quality.
    # ───────────────────────────────────────────────────────────────────────────
    weekly_vol_expansion = bool(wsnap.get("weekly_vol_expansion", False)) if wsnap is not None and not (isinstance(wsnap, pd.Series) and wsnap.empty) else False
    weeks_in_base = int(wsnap.get("weeks_in_base", 0) or 0) if wsnap is not None and not (isinstance(wsnap, pd.Series) and wsnap.empty) else 0

    if stage_result is not None:
        if stage_result.stage == "STAGE2_EARLY":
            # Count confirmation signals — need all three for full bonus
            early_confirms = sum([
                bool(rs_line_new_high),       # RS line leading price = institutional pre-accumulation
                bool(weekly_vol_expansion),   # volume surge on breakout week = real institutional buying
                weeks_in_base >= 6,           # proper base = coiled energy, not random drift up
            ])
            if early_confirms == 3:
                bonus += 12   # textbook VCP breakout — highest conviction setup
            elif early_confirms == 2:
                bonus += 5    # good but one signal missing — still actionable
            elif early_confirms == 1:
                bonus += 0    # weak confirmation — don't reward; treat same as mature
            else:
                bonus -= 6    # unconfirmed breakout = false start risk, penalise

        elif stage_result.stage == "STAGE2_MATURE":
            # Mature trend reward: the RS line quality determines how much runway remains
            if rs_line_new_high:
                bonus += 8    # mature trend but RS still making new highs = still leading, buy the dip
            elif rs_line_above_ema21:
                bonus += 5    # RS line healthy in mature trend — reliable
            else:
                bonus += 2    # RS fading in mature trend = later stage, less upside, still ok

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

    bonus = min(bonus, 25)
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

    if final_score < qualify_threshold:
        return None

    # Full support-stack stop — pass weekly snapshot so weekly low is included
    support    = _detect_support(df_ind, wsnap=wsnap)
    stop_price = support["structural_stop"]
    target     = support["structural_target"]

    return {
        "score":         final_score,
        "setup":         setup_type,
        "stage":         stage_result.stage if stage_result else "UNKNOWN",
        "institutional": inst_result.pattern if inst_result else "UNKNOWN",
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
        "rs_vs_sector":  round(rs_vs_sector_63d * 100, 1),
        "rs_line_new_high": bool(rs_line_new_high),
        "sector_leader": bool(sector_leader),
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
        "rr":            round((target - close) / max(close - stop_price, 0.01), 1),
        "support_note":  support["note"],
        "support_levels": support.get("all_levels", []),
        "ema_confluence": support["ema_confluence"],
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
    import json
    tickers = sorted(
        f.replace(".csv","") for f in os.listdir(DATA_DIR)
        if f.endswith(".csv") and not f.startswith("_")
    )
    # Exclude sector ETFs from stock universe
    sector_etfs = {"XLK","XLF","XLV","XLE","XLI","XLU","XLP","XLY","XLB","XLRE","XLC"}
    tickers = [t for t in tickers if t not in sector_etfs]

    # Load sector map once
    sector_map_path = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "sector_map.json")
    sector_map = {}
    if os.path.exists(sector_map_path):
        with open(sector_map_path) as f:
            sector_map = json.load(f)

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

        # Pre-load sector ETF data for this week
        sector_dfs = {}
        for etf in sector_etfs:
            sdf = load_daily(etf, end=as_of)
            if not sdf.empty:
                sector_dfs[etf] = sdf

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

                # Add sector RS if available
                sector_etf = sector_map.get(ticker)
                if sector_etf and sector_etf in sector_dfs:
                    ind = compute_sector_rs(ind, sector_dfs[sector_etf])

                # Compute weekly indicators
                weekly_df = compute_weekly_indicators(df, spy=spy_df)
                wsnap = get_weekly_snapshot(weekly_df, as_of) if not weekly_df.empty else pd.Series(dtype=float)

                snap = get_snapshot(ind, pd.Timestamp(as_of))
                if snap is None or snap.empty: continue

                result = score_ticker_comprehensive(snap, ind, spy_above_ema50, wsnap=wsnap)
                if result is None: continue
                result["ticker"] = ticker
                candidates.append(result)
            except Exception as e:
                errors += 1
                continue

        candidates.sort(key=lambda x: x["score"], reverse=True)
        top5 = candidates[:TOP_N]

        print(f"\n{len(candidates)} qualified (out of {len(tickers)-1} tickers, {errors} errors) | Top {TOP_N}:\n")

        hdr = f"{'TICK':<6} {'Scr':>4} {'A':>4} {'B':>4} {'C':>4} {'D':>4} {'Bon':>4} {'Stage':<14} {'Inst':<12} {'Setup':<22} {'RSI7':>5} {'RS63%':>6} {'RS_sec%':>8}"
        print(hdr)
        print("-"*120)

        week_pnl  = 0.0
        week_wins = 0

        for rank, pick in enumerate(top5, 1):
            ticker = pick["ticker"]
            actual = get_weekly_return(ticker, entry_date, exit_date)

            candle_str = ",".join(pick["candles"][:2]) if pick["candles"] else "none"
            rs_line_str = "RS_NEW_HIGH" if pick.get("rs_line_new_high") else ""
            sector_str = "SECTOR_LEAD" if pick.get("sector_leader") else ""
            print(f"{ticker:<6} {pick['score']:>4.0f} {pick['layer_A']:>4.0f} {pick['layer_B']:>4.0f} "
                  f"{pick['layer_C']:>4.0f} {pick['layer_D']:>4.0f} {pick['bonus']:>4.0f} "
                  f"{pick['stage']:<14} {pick['institutional']:<12} {pick['setup']:<22} "
                  f"{pick['rsi7']:>5.0f} {pick['rs63_pct']:>6.1f} {pick['rs_vs_sector']:>8.1f}")
            print(f"       candles={candle_str:<20} {rs_line_str:<12} {sector_str:<12} "
                  f"stop=${pick['stop']:.2f}  target=${pick['target']:.2f}  R/R={pick['rr']}")
            print(f"       {pick['support_note']}")

            if actual:
                pnl    = actual["pnl_pct"]
                sym    = "WIN" if actual["win"] else ("LOSS" if actual["loss"] else "flat")
                print(f"       RESULT: entry=${actual['entry_price']} -> exit=${actual['exit_price']}  "
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
                    "stage": pick["stage"], "institutional": pick["institutional"],
                    "pnl_pct": pnl, "win": actual["win"], "loss": actual["loss"],
                    "week_high": actual["week_high"],
                    "entry": actual["entry_price"],
                    "exit": actual["exit_price"],
                    "stop": pick["stop"],
                })
            print()

        avg = week_pnl / len(top5) if top5 else 0
        print(f"  --- Week {label}: {week_wins}/{len(top5)} wins | Avg PnL = {avg:+.2f}% ---")

    # ── SUMMARY ──
    print(f"\n{'='*75}")
    print("COMPREHENSIVE BACKTEST SUMMARY — JAN-MAR 2026")
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

        print(f"\nStage breakdown:")
        for stage, cnt in Counter(t["stage"] for t in all_trades).most_common():
            st = [t for t in all_trades if t["stage"]==stage]
            sw = sum(1 for t in st if t["win"])
            print(f"  {stage:<20} {sw}/{cnt} wins")

        print(f"\nBest trades:")
        for t in sorted(all_trades, key=lambda x: x["pnl_pct"], reverse=True)[:5]:
            print(f"  {t['week']:6} {t['ticker']:6} {t['pnl_pct']:+.1f}%  [{t['setup']}] [{t['stage']}]")
        print(f"\nWorst trades:")
        for t in sorted(all_trades, key=lambda x: x["pnl_pct"])[:5]:
            print(f"  {t['week']:6} {t['ticker']:6} {t['pnl_pct']:+.1f}%  [{t['setup']}] [{t['stage']}]")

        # Save structured trades for dollar P&L analysis
        import json as _json
        trades_path = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "backtest_trades.json")
        with open(trades_path, "w") as f:
            _json.dump(all_trades, f, indent=2)
        print(f"\nTrades saved to {trades_path}")


if __name__ == "__main__":
    run_backtest()
