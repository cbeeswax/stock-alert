"""
stage_classifier.py
--------------------
Stock stage classification (Weinstein model) + institutional behavior detection.

A senior analyst's first question is NOT "is RSI overbought?" but
"what stage of its lifecycle is this stock in, and who is in control?"

Stage model (Weinstein):
  STAGE1_BASE     : Basing period. Flat, low volume, under 40-week MA. WATCH only.
  STAGE2_EARLY    : Fresh breakout above 40-week MA + RS line new high. BEST R/R.
  STAGE2_MATURE   : Above 40-week MA, trending, but 3+ months extended. Buy pullbacks carefully.
  STAGE3_TOP      : Rolling over from peak. RS line declining. AVOID — distribution in progress.
  STAGE4_DOWN     : Below 40-week MA, RS line downtrend, lower lows. SKIP — no bottom fishing.
  RECOVERY        : Stage 4 but volume capitulation + RSI reset underway. Watch for Stage 1.
  FAILED_BREAKOUT : Was above 40-week MA, reversed below on volume. SKIP — failed structure.

Hard rule: Stage3, Stage4, FAILED_BREAKOUT → automatic rejection, no exceptions.

Institutional behavior patterns (20-session analysis):
  ACCUMULATING  : Up-day avg vol > down-day avg vol by 40%+, price flat/rising. BEST entry signal.
  MARKUP        : Up-day vol > down-day vol by 10%, price rising steadily. Ride existing trend.
  DISTRIBUTING  : Down-day avg vol > up-day avg vol, price near highs. Professionals selling. AVOID.
  CAPITULATION  : Single spike day > 3× avg vol + large price drop. Possible reversal watch.
  NEUTRAL       : No clear institutional footprint. Requires stronger price/RS confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Stage result dataclass
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    stage: str                  # STAGE1_BASE | STAGE2_EARLY | STAGE2_MATURE | STAGE3_TOP | STAGE4_DOWN | RECOVERY | FAILED_BREAKOUT
    is_tradeable: bool          # False for Stage3, Stage4, FAILED_BREAKOUT
    stage_score: float          # 0-100, higher = better for swing trading
    evidence: list[str] = field(default_factory=list)
    weeks_in_trend: int = 0     # approximate weeks stock has been in current stage


@dataclass
class InstitutionalResult:
    pattern: str                # ACCUMULATING | MARKUP | DISTRIBUTING | CAPITULATION | NEUTRAL
    ud_vol_ratio: float         # up-day avg vol / down-day avg vol
    is_bullish: bool            # True for ACCUMULATING and MARKUP
    is_bearish: bool            # True for DISTRIBUTING
    score_adj: int              # score adjustment for the comprehensive scorer
    evidence: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage classifier
# ---------------------------------------------------------------------------

def classify_stage(snap: pd.Series, wsnap: pd.Series) -> StageResult:
    """
    Classify a stock's Weinstein stage using daily snapshot + weekly snapshot.

    Parameters
    ----------
    snap  : daily indicator snapshot (from get_snapshot())
    wsnap : weekly indicator snapshot (from get_weekly_snapshot())

    Returns
    -------
    StageResult with stage label, tradeability, and evidence list.
    """
    evidence = []

    # --- Extract key values ---
    weekly_above_ema40 = bool(wsnap.get("weekly_above_ema40", False)) if not wsnap.empty else None
    weekly_above_ema10 = bool(wsnap.get("weekly_above_ema10", False)) if not wsnap.empty else None
    weekly_ema10_slope = float(wsnap.get("weekly_ema10_slope", 0) or 0)
    weekly_ema40_slope = float(wsnap.get("weekly_ema40_slope", 0) or 0)
    weekly_rsi14 = float(wsnap.get("weekly_rsi14", 50) or 50)
    weekly_rs_line_rising = bool(wsnap.get("weekly_rs_line_rising", False)) if not wsnap.empty else None
    weekly_rs_line_new_high = bool(wsnap.get("weekly_rs_line_new_high", False)) if not wsnap.empty else None
    weekly_pct_from_52w_high = float(wsnap.get("weekly_pct_from_52w_high", -0.5) or -0.5)
    weekly_pct_vs_ema40 = float(wsnap.get("weekly_pct_vs_ema40", 0) or 0)
    weekly_consolidating = bool(wsnap.get("weekly_consolidating", False)) if not wsnap.empty else None
    weeks_in_base = int(wsnap.get("weeks_in_base", 0) or 0)

    rs_line_slope_10d = float(snap.get("rs_line_slope_10d", 0) or 0)
    rs_63d = float(snap.get("rs_63d", 0) or 0)
    hh_hl = float(snap.get("hh_hl", 0.5) or 0.5)
    pct_from_52w_high = float(snap.get("pct_from_52w_high", -0.5) or -0.5)
    ema_align = int(snap.get("ema_align", 0) or 0)

    # Handle missing weekly data gracefully (fall back to daily signals)
    if wsnap.empty or weekly_above_ema40 is None:
        weekly_above_ema40 = ema_align >= 3
        weekly_above_ema10 = ema_align >= 2
        weekly_ema10_slope = float(snap.get("ema21_slope", 0) or 0)
        evidence.append("WARN: no weekly data, using daily EMA proxies")

    # ---------------------------------------------------------------------------
    # STAGE 4 — Below 40-week MA, RS declining, lower lows
    # The most important filter. Catches falling knives.
    # ---------------------------------------------------------------------------
    if not weekly_above_ema40 and weekly_ema40_slope < -0.02 and hh_hl < 0.3:
        evidence.append(f"Below weekly EMA40 (slope={weekly_ema40_slope*100:.1f}%)")
        evidence.append(f"Downtrend structure (hh_hl={hh_hl:.2f})")
        if rs_line_slope_10d < 0:
            evidence.append("RS line declining")
        return StageResult(
            stage="STAGE4_DOWN",
            is_tradeable=False,
            stage_score=5,
            evidence=evidence,
        )

    # ---------------------------------------------------------------------------
    # FAILED BREAKOUT — Was above weekly EMA40, reversed back below on expansion vol
    # ---------------------------------------------------------------------------
    if not weekly_above_ema40 and weekly_above_ema10 is False:
        # Price moved below both weekly EMAs — likely failed breakout or deterioration
        weekly_vol_expansion = bool(wsnap.get("weekly_vol_expansion", False)) if not wsnap.empty else False
        if weekly_pct_vs_ema40 < -3:  # > 3% below 40-week MA = clearly broken
            evidence.append(f"Below weekly EMA40 by {weekly_pct_vs_ema40:.1f}%")
            evidence.append("Structure deteriorated below key weekly MA")
            return StageResult(
                stage="FAILED_BREAKOUT",
                is_tradeable=False,
                stage_score=10,
                evidence=evidence,
            )

    # ---------------------------------------------------------------------------
    # STAGE 3 — Rolling over from peak (top of a trend, distribution starting)
    # Signs: RS line declining, weekly extended but losing momentum
    # ---------------------------------------------------------------------------
    if (weekly_above_ema40 and
            not weekly_rs_line_rising and
            weekly_pct_from_52w_high > -0.05 and
            weekly_rsi14 > 70 and
            weekly_ema10_slope < 0):
        evidence.append(f"Weekly RSI extended ({weekly_rsi14:.0f}) with 10-week MA declining")
        evidence.append("RS line no longer rising — distribution possible")
        evidence.append(f"Within {abs(weekly_pct_from_52w_high)*100:.0f}% of 52w high")
        return StageResult(
            stage="STAGE3_TOP",
            is_tradeable=False,
            stage_score=15,
            evidence=evidence,
        )

    # ---------------------------------------------------------------------------
    # STAGE 1 — Basing period. Flat, low vol, under 40-week MA but stabilizing.
    # ---------------------------------------------------------------------------
    if not weekly_above_ema40 and weeks_in_base >= 8:
        evidence.append(f"Basing {weeks_in_base}+ weeks below 40-week MA")
        evidence.append("Watch for Stage 2 breakout — not yet actionable")
        return StageResult(
            stage="STAGE1_BASE",
            is_tradeable=False,
            stage_score=20,
            evidence=evidence,
            weeks_in_trend=weeks_in_base,
        )

    # ---------------------------------------------------------------------------
    # RECOVERY — Stage 4 but showing reversal signs
    # ---------------------------------------------------------------------------
    if not weekly_above_ema40:
        rsi7 = float(snap.get("rsi7", 50) or 50)
        if rsi7 < 35 and rs_line_slope_10d > 0:
            evidence.append("Below 40-week MA but RSI7 deeply oversold")
            evidence.append("RS line beginning to turn — possible reversal")
            return StageResult(
                stage="RECOVERY",
                is_tradeable=False,
                stage_score=25,
                evidence=evidence,
            )
        # Generic Stage 4
        evidence.append("Below 40-week MA, no clear base forming yet")
        return StageResult(
            stage="STAGE4_DOWN",
            is_tradeable=False,
            stage_score=8,
            evidence=evidence,
        )

    # ---------------------------------------------------------------------------
    # At this point: stock is ABOVE weekly EMA40 — candidate for Stage 2
    # Distinguish EARLY vs MATURE
    # ---------------------------------------------------------------------------

    # Approximate weeks in Stage 2 from how extended vs 40-week MA
    # and how high vs 52w high
    weeks_above_ema40 = _estimate_weeks_above_ema40(wsnap)

    # --- STAGE 2 EARLY: Best R/R setup ---
    # Fresh breakout: within 20% above EMA40, RS line new high or recently turned up,
    # price not more than 30% above 52w low
    is_stage2_early = (
        weekly_above_ema40 and
        (weekly_rs_line_new_high or weekly_rs_line_rising) and
        weekly_pct_from_52w_high < -0.02 and  # not yet at 52w high
        weekly_pct_vs_ema40 < 25 and          # within 25% of 40-week MA
        weekly_ema10_slope > 0 and            # 10-week MA rising = trend intact
        weeks_above_ema40 < 20                # fresh trend, not over-extended
    )

    if is_stage2_early:
        score = 85
        evidence.append(f"Above weekly EMA40, 10-week MA rising ({weekly_ema10_slope*100:.1f}%)")
        if weekly_rs_line_new_high:
            evidence.append("RS line at new 52-week high — institutional buying confirmed")
            score += 10
        elif weekly_rs_line_rising:
            evidence.append("RS line rising — outperforming SPY on weekly")
        evidence.append(f"Price {weekly_pct_from_52w_high*100:.0f}% from 52w high — room to run")
        evidence.append(f"~{weeks_above_ema40} weeks into Stage 2 — early trend")
        return StageResult(
            stage="STAGE2_EARLY",
            is_tradeable=True,
            stage_score=min(score, 100),
            evidence=evidence,
            weeks_in_trend=weeks_above_ema40,
        )

    # --- STAGE 2 MATURE: Still valid but prefer pullbacks ---
    score = 65
    evidence.append(f"Above weekly EMA40, ~{weeks_above_ema40} weeks in Stage 2")
    if weekly_ema10_slope > 0:
        evidence.append("10-week MA still rising — trend intact")
        score += 5
    if weekly_rs_line_rising:
        evidence.append("RS line still rising vs SPY")
        score += 5
    if weekly_pct_from_52w_high < -0.10:
        evidence.append(f"Pulled back {abs(weekly_pct_from_52w_high)*100:.0f}% from 52w high — buying opportunity")
        score += 8
    elif weekly_pct_from_52w_high > -0.03:
        evidence.append("Extended near 52w high — wait for pullback")
        score -= 10

    return StageResult(
        stage="STAGE2_MATURE",
        is_tradeable=True,
        stage_score=min(score, 100),
        evidence=evidence,
        weeks_in_trend=weeks_above_ema40,
    )


def _estimate_weeks_above_ema40(wsnap: pd.Series) -> int:
    """Estimate weeks in current Stage 2 from position vs 40-week MA."""
    pct_vs = float(wsnap.get("weekly_pct_vs_ema40", 0) or 0)
    ema10_slope = float(wsnap.get("weekly_ema10_slope", 0) or 0)

    # Rough heuristic: slope + distance suggest trend maturity
    # Fresh breakout: close to EMA40, slope just turning positive
    # Mature trend: well above EMA40, slope still positive but moderating
    if abs(pct_vs) < 5:
        return 4
    elif abs(pct_vs) < 15:
        return 12 if ema10_slope > 0.02 else 20
    elif abs(pct_vs) < 30:
        return 26 if ema10_slope > 0.01 else 40
    else:
        return 52  # extended beyond a year of trend


# ---------------------------------------------------------------------------
# Institutional behavior classifier
# ---------------------------------------------------------------------------

def classify_institutional(df: pd.DataFrame, lookback: int = 20) -> InstitutionalResult:
    """
    Classify institutional buying/selling behavior by analyzing volume on
    up-close vs down-close sessions over the last `lookback` trading days.

    A senior analyst reads the tape to understand whether professionals are
    quietly accumulating or distributing. This replaces raw CMF/OBV numbers
    with a human-readable classification.

    Parameters
    ----------
    df       : daily OHLCV DataFrame with DatetimeIndex (last row = most recent)
    lookback : number of sessions to analyze (default: 20 = 1 month)

    Returns
    -------
    InstitutionalResult with pattern label, ratio, and score adjustment.
    """
    if df is None or len(df) < lookback:
        return InstitutionalResult(
            pattern="NEUTRAL",
            ud_vol_ratio=1.0,
            is_bullish=False,
            is_bearish=False,
            score_adj=0,
            evidence=["Insufficient data for institutional analysis"],
        )

    recent = df.iloc[-lookback:].copy()
    recent["up_close"] = recent["close"] >= recent["close"].shift(1)
    recent = recent.iloc[1:]  # remove first row (no prev close)

    up_days = recent[recent["up_close"]]
    down_days = recent[~recent["up_close"]]

    up_vol_avg = up_days["volume"].mean() if len(up_days) > 2 else 0
    down_vol_avg = down_days["volume"].mean() if len(down_days) > 2 else 0

    if down_vol_avg == 0:
        ud_ratio = 2.0
    else:
        ud_ratio = up_vol_avg / down_vol_avg

    # Price trend context: is price flat/rising or near highs?
    price_change_pct = (recent["close"].iloc[-1] - recent["close"].iloc[0]) / recent["close"].iloc[0]
    pct_from_high = (recent["close"].iloc[-1] - recent["high"].max()) / recent["high"].max()

    # Spike detection: any single day with vol > 3× avg on a large down day?
    avg_vol = recent["volume"].mean()
    spike_days = recent[
        (recent["volume"] > 3 * avg_vol) &
        ((recent["close"] - recent["open"]) / recent["open"] < -0.03)
    ]

    evidence = []
    evidence.append(f"Up-day avg vol: {up_vol_avg:,.0f} | Down-day avg vol: {down_vol_avg:,.0f}")
    evidence.append(f"U/D vol ratio: {ud_ratio:.2f} | Price change 20d: {price_change_pct*100:.1f}%")

    # --- Classification logic ---

    # CAPITULATION: panic selling spike
    if len(spike_days) > 0:
        evidence.append(f"Capitulation spike detected ({len(spike_days)} day(s) > 3× avg vol + ≥3% drop)")
        return InstitutionalResult(
            pattern="CAPITULATION",
            ud_vol_ratio=ud_ratio,
            is_bullish=True,   # potential reversal signal — cautiously bullish
            is_bearish=False,
            score_adj=5,       # bonus for potential reversal, but needs confirmation
            evidence=evidence,
        )

    # ACCUMULATING: institutions buying quietly (best entry signal)
    if ud_ratio >= 1.4 and price_change_pct >= -0.05:
        evidence.append("Strong quiet accumulation: up-day vol >> down-day vol, price stable/rising")
        return InstitutionalResult(
            pattern="ACCUMULATING",
            ud_vol_ratio=ud_ratio,
            is_bullish=True,
            is_bearish=False,
            score_adj=15,
            evidence=evidence,
        )

    # MARKUP: clear uptrend with institutional participation
    if ud_ratio >= 1.1 and price_change_pct > 0.02:
        evidence.append("Markup phase: up-day vol leads, price rising steadily")
        return InstitutionalResult(
            pattern="MARKUP",
            ud_vol_ratio=ud_ratio,
            is_bullish=True,
            is_bearish=False,
            score_adj=8,
            evidence=evidence,
        )

    # DISTRIBUTING: professionals selling near highs
    if ud_ratio <= 0.75 and pct_from_high > -0.10:
        evidence.append(f"Distribution: down-day vol >> up-day vol, price near highs ({pct_from_high*100:.0f}% from high)")
        return InstitutionalResult(
            pattern="DISTRIBUTING",
            ud_vol_ratio=ud_ratio,
            is_bullish=False,
            is_bearish=True,
            score_adj=-20,   # Hard penalty — smart money leaving
            evidence=evidence,
        )

    # NEUTRAL: no clear institutional footprint
    evidence.append("No dominant institutional footprint — needs stronger confirmation")
    score_adj = 3 if ud_ratio >= 1.0 else -3
    return InstitutionalResult(
        pattern="NEUTRAL",
        ud_vol_ratio=ud_ratio,
        is_bullish=False,
        is_bearish=False,
        score_adj=score_adj,
        evidence=evidence,
    )
