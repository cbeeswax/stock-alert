"""
deep_pattern_learner.py
=======================
Learns from ALL 179 S&P 500 tickers, 2022-2025 daily OHLCV data.

Detects 15+ pattern types across 5 categories:
  1. Candlestick  - Hammer, Engulfing, Doji, Morning Star, Shooting Star
  2. Swing        - EMA21 pullback, EMA50 pullback, Inside day breakout
  3. Momentum     - MACD cross, Volume surge breakout, RSI divergence bounce
  4. Gap Reversal - Gap down reversal, Gap up fade
  5. Squeeze      - Bollinger squeeze breakout

For each detected setup, tracks 5-day forward return to compute:
  - Win rate (% returning > +1%)
  - Avg gain on winners
  - Avg loss on losers
  - Best/worst market regimes per pattern
  - Ideal entry conditions

Outputs: data/predictor/deep_learning.json
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analysis.predictor.data_loader import load_daily, DATA_DIR

OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "predictor", "deep_learning.json"
)

TRAIN_START = "2022-01-01"
TRAIN_END   = "2025-12-31"
HOLD_DAYS   = 5       # weekly hold
WIN_THRESH  = 0.01    # +1% = win
LOSS_THRESH = -0.01   # -1% = loss


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def _rsi(close, n=14):
    d = close.diff()
    g = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))

def _atr(df, n=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def _body(df):
    return (df["close"] - df["open"]).abs()

def _range(df):
    return (df["high"] - df["low"]).replace(0, np.nan)

def _upper_wick(df):
    return df["high"] - df[["open","close"]].max(axis=1)

def _lower_wick(df):
    return df[["open","close"]].min(axis=1) - df["low"]

def _is_bull_candle(df):
    return df["close"] > df["open"]

def _spy_regime(spy_close, idx):
    """Return 'bull' or 'bear' at a given index based on SPY 50-EMA."""
    ema50 = _ema(spy_close, 50)
    if idx not in ema50.index:
        return "unknown"
    return "bull" if spy_close.loc[idx] > ema50.loc[idx] else "bear"


def _forward_return(close, i, days=5):
    """
    Return % change from close[i] to close[i+days].
    Returns None if insufficient data.
    """
    if i + days >= len(close):
        return None
    entry = close.iloc[i]
    exit_ = close.iloc[i + days]
    if entry <= 0:
        return None
    return (exit_ - entry) / entry


# ─────────────────────────────────────────────────────────────────────────────
# Pattern detectors — each returns True/False for a given row index
# ─────────────────────────────────────────────────────────────────────────────

class PatternDetector:
    def __init__(self, df: pd.DataFrame, spy_close: pd.Series = None):
        self.df = df.copy()
        self.c  = df["close"]
        self.o  = df["open"]
        self.h  = df["high"]
        self.l  = df["low"]
        self.v  = df["volume"]

        self.body   = _body(df)
        self.range_ = _range(df)
        self.uw     = _upper_wick(df)
        self.lw     = _lower_wick(df)
        self.bull   = _is_bull_candle(df)

        self.atr14  = _atr(df, 14)
        self.rsi14  = _rsi(self.c, 14)
        self.rsi7   = _rsi(self.c, 7)
        self.ema9   = _ema(self.c, 9)
        self.ema21  = _ema(self.c, 21)
        self.ema50  = _ema(self.c, 50)
        self.ema200 = _ema(self.c, 200)
        self.vol20  = self.v.rolling(20).mean()

        # MACD
        macd = _ema(self.c, 12) - _ema(self.c, 26)
        sig  = _ema(macd, 9)
        self.macd_hist = macd - sig
        self.macd_bull_cross = (macd > sig) & (macd.shift(1) <= sig.shift(1))

        # Bollinger + Keltner squeeze
        bb_mid = self.c.rolling(20).mean()
        bb_std = self.c.rolling(20).std()
        bb_up  = bb_mid + 2 * bb_std
        bb_dn  = bb_mid - 2 * bb_std
        kc_up  = _ema(self.c, 20) + 2 * self.atr14
        kc_dn  = _ema(self.c, 20) - 2 * self.atr14
        self.in_squeeze = (bb_up < kc_up) & (bb_dn > kc_dn)
        self.bb_pct = (self.c - bb_dn) / (bb_up - bb_dn).replace(0, np.nan)

        # CMF
        rng   = (self.h - self.l).replace(0, np.nan)
        mfm   = ((self.c - self.l) - (self.h - self.c)) / rng
        self.cmf = (mfm * self.v).rolling(20).sum() / self.v.rolling(20).sum().replace(0, np.nan)

        self.spy_close = spy_close

    # ── Candlestick Patterns ────────────────────────────────────────────────

    def hammer(self, i):
        """Bullish hammer: long lower wick (>2x body), small upper wick, after downtrend."""
        if i < 5:
            return False
        b = self.body.iloc[i]
        lw = self.lw.iloc[i]
        uw = self.uw.iloc[i]
        r  = self.range_.iloc[i]
        if r == 0 or b == 0:
            return False
        # lower wick >= 2x body, upper wick < 30% range, prior trend is down
        prior_down = self.c.iloc[i-1] < self.c.iloc[i-5]
        return (lw >= 2 * b) and (uw < 0.3 * r) and prior_down and (lw > 0.5 * r)

    def inverted_hammer(self, i):
        """Inverted hammer (bottom of downtrend): long upper wick, small body, small lower wick."""
        if i < 5:
            return False
        b  = self.body.iloc[i]
        uw = self.uw.iloc[i]
        lw = self.lw.iloc[i]
        r  = self.range_.iloc[i]
        if r == 0 or b == 0:
            return False
        prior_down = self.c.iloc[i-1] < self.c.iloc[i-5]
        return (uw >= 2 * b) and (lw < 0.3 * r) and prior_down

    def bullish_engulfing(self, i):
        """Today's bull candle fully engulfs prior bear candle."""
        if i < 1:
            return False
        prev_bear = not self.bull.iloc[i-1]
        cur_bull  = self.bull.iloc[i]
        engulfs   = (self.c.iloc[i] > self.o.iloc[i-1]) and (self.o.iloc[i] < self.c.iloc[i-1])
        return prev_bear and cur_bull and engulfs

    def bearish_engulfing(self, i):
        """Today's bear candle engulfs prior bull candle."""
        if i < 1:
            return False
        prev_bull = self.bull.iloc[i-1]
        cur_bear  = not self.bull.iloc[i]
        engulfs   = (self.o.iloc[i] > self.c.iloc[i-1]) and (self.c.iloc[i] < self.o.iloc[i-1])
        return prev_bull and cur_bear and engulfs

    def doji(self, i):
        """Doji: very small body relative to range (indecision)."""
        b = self.body.iloc[i]
        r = self.range_.iloc[i]
        if r == 0:
            return False
        return (b / r) < 0.1

    def morning_star(self, i):
        """3-candle reversal: big bear, doji/small body, big bull. At downtrend bottom."""
        if i < 7:
            return False
        # Day 1: big bear candle
        d1_bear = (not self.bull.iloc[i-2]) and (self.body.iloc[i-2] > 0.5 * self.range_.iloc[i-2])
        # Day 2: small body (star), gaps below
        d2_small = self.body.iloc[i-1] < 0.3 * self.body.iloc[i-2]
        # Day 3: big bull closing above midpoint of day 1
        d3_bull  = self.bull.iloc[i] and (self.c.iloc[i] > (self.o.iloc[i-2] + self.c.iloc[i-2]) / 2)
        prior_down = self.c.iloc[i-5] > self.c.iloc[i-2]
        return d1_bear and d2_small and d3_bull and prior_down

    def shooting_star(self, i):
        """Shooting star at top: long upper wick, small body, small lower wick, after uptrend."""
        if i < 5:
            return False
        b  = self.body.iloc[i]
        uw = self.uw.iloc[i]
        lw = self.lw.iloc[i]
        r  = self.range_.iloc[i]
        if r == 0 or b == 0:
            return False
        prior_up = self.c.iloc[i-1] > self.c.iloc[i-5]
        return (uw >= 2 * b) and (lw < 0.3 * r) and prior_up

    def inside_day(self, i):
        """Inside day: today's high < prior high AND today's low > prior low (consolidation)."""
        if i < 1:
            return False
        return (self.h.iloc[i] < self.h.iloc[i-1]) and (self.l.iloc[i] > self.l.iloc[i-1])

    def inside_day_breakout(self, i):
        """Inside day FOLLOWED by breakout above inside day high."""
        if i < 2:
            return False
        was_inside = self.inside_day(i-1)
        breaks_up  = self.c.iloc[i] > self.h.iloc[i-1]
        return was_inside and breaks_up

    # ── Swing Patterns ──────────────────────────────────────────────────────

    def ema21_pullback(self, i):
        """Price pulls back to EMA21 in an uptrend (EMA21 > EMA50), then closes above."""
        if i < 50:
            return False
        uptrend  = self.ema21.iloc[i] > self.ema50.iloc[i]
        touched  = self.l.iloc[i] <= self.ema21.iloc[i] * 1.005  # within 0.5%
        recov    = self.c.iloc[i] > self.ema21.iloc[i]
        rsi_ok   = 35 < self.rsi14.iloc[i] < 65
        return uptrend and touched and recov and rsi_ok

    def ema50_pullback(self, i):
        """Price pulls back to EMA50 (stronger support), closes above."""
        if i < 60:
            return False
        touched = self.l.iloc[i] <= self.ema50.iloc[i] * 1.008
        recov   = self.c.iloc[i] > self.ema50.iloc[i]
        return touched and recov

    def rsi_oversold_bounce(self, i):
        """RSI7 < 30 AND RSI7 > RSI7[i-1] (turning up from extreme oversold)."""
        if i < 20:
            return False
        oversold = self.rsi7.iloc[i] < 30
        turning  = self.rsi7.iloc[i] > self.rsi7.iloc[i-1]
        return oversold and turning

    def rsi_divergence_bounce(self, i):
        """RSI7 > RSI14 (short-term recovering faster than medium term) + RSI14 < 45."""
        if i < 20:
            return False
        return (self.rsi7.iloc[i] > self.rsi14.iloc[i]) and (self.rsi14.iloc[i] < 45)

    # ── Momentum Patterns ───────────────────────────────────────────────────

    def macd_bull_cross_setup(self, i):
        """MACD bullish cross (signal line cross) + RSI 40-60 range (not overbought)."""
        if i < 30:
            return False
        cross = bool(self.macd_bull_cross.iloc[i])
        rsi_range = 35 < self.rsi14.iloc[i] < 65
        return cross and rsi_range

    def volume_surge_breakout(self, i):
        """Volume > 2x 20-day avg AND close > prior 10-day high (volume-confirmed breakout)."""
        if i < 20:
            return False
        vol_surge  = self.v.iloc[i] > 2.0 * self.vol20.iloc[i]
        prior_high = self.c.iloc[max(0,i-10):i].max()
        breaks_out = self.c.iloc[i] > prior_high
        return vol_surge and breaks_out

    def momentum_continuation(self, i):
        """Strong trending stock: ROC5 > +3%, above EMA21, volume confirming."""
        if i < 25:
            return False
        roc5   = (self.c.iloc[i] - self.c.iloc[i-5]) / self.c.iloc[i-5]
        above  = self.c.iloc[i] > self.ema21.iloc[i]
        vol_ok = self.v.iloc[i] > 0.8 * self.vol20.iloc[i]
        return roc5 > 0.03 and above and vol_ok

    # ── Gap Patterns ────────────────────────────────────────────────────────

    def gap_down_reversal(self, i):
        """
        Gap down reversal: opens below prior low (gap down),
        then closes ABOVE prior day's close (reversal).
        High probability setup in bear markets.
        """
        if i < 1:
            return False
        gap_dn  = self.o.iloc[i] < self.l.iloc[i-1]
        reversal = self.c.iloc[i] > self.c.iloc[i-1]
        return gap_dn and reversal

    def gap_up_fade(self, i):
        """Gap up then close below prior high (fade / bearish setup)."""
        if i < 1:
            return False
        gap_up  = self.o.iloc[i] > self.h.iloc[i-1]
        fade    = self.c.iloc[i] < self.o.iloc[i]
        return gap_up and fade

    # ── Squeeze / Volatility Patterns ───────────────────────────────────────

    def squeeze_breakout(self, i):
        """
        BB squeeze releases: was in squeeze 3+ days ago, now squeeze off,
        price closes above EMA20, with volume confirmation.
        """
        if i < 5:
            return False
        was_squeeze = self.in_squeeze.iloc[max(0,i-5):i-1].any()
        now_free    = not self.in_squeeze.iloc[i]
        above_ema   = self.c.iloc[i] > _ema(self.c, 20).iloc[i]
        vol_ok      = self.v.iloc[i] >= 0.9 * self.vol20.iloc[i]
        return was_squeeze and now_free and above_ema and vol_ok

    def mean_reversion_extreme(self, i):
        """
        Extreme oversold: BB% < 0.05 (near lower band) + RSI7 < 25 + CMF starting to rise.
        Best mean reversion setup.
        """
        if i < 25:
            return False
        bb_low  = float(self.bb_pct.iloc[i] or 1) < 0.1
        rsi_ext = self.rsi7.iloc[i] < 25
        cmf_ok  = float(self.cmf.iloc[i] or 0) > float(self.cmf.iloc[i-1] or 0)
        return bb_low and rsi_ext and cmf_ok


# ─────────────────────────────────────────────────────────────────────────────
# Main learning loop
# ─────────────────────────────────────────────────────────────────────────────

PATTERNS = [
    "hammer", "inverted_hammer", "bullish_engulfing", "bearish_engulfing",
    "doji", "morning_star", "shooting_star", "inside_day_breakout",
    "ema21_pullback", "ema50_pullback",
    "rsi_oversold_bounce", "rsi_divergence_bounce",
    "macd_bull_cross_setup", "volume_surge_breakout", "momentum_continuation",
    "gap_down_reversal", "gap_up_fade",
    "squeeze_breakout", "mean_reversion_extreme",
]

# Expected direction for each pattern (buy=+, short=-)
PATTERN_DIRECTION = {
    "bearish_engulfing": -1,
    "shooting_star": -1,
    "gap_up_fade": -1,
}

def learn(verbose=True):
    tickers = sorted(
        f.replace(".csv", "") for f in os.listdir(DATA_DIR)
        if f.endswith(".csv") and not f.startswith("_")
    )

    # Load SPY for regime detection
    spy_df = load_daily("SPY", start=TRAIN_START, end=TRAIN_END)
    spy_close = spy_df["close"] if not spy_df.empty else None

    stats = {p: {"setups": 0, "wins": 0, "losses": 0, "returns": [],
                  "bull_wins": 0, "bull_setups": 0,
                  "bear_wins": 0, "bear_setups": 0,
                  "atr_high_wins": 0, "atr_high_setups": 0,
                  "combo_signal_wins": 0, "combo_signal_setups": 0}
             for p in PATTERNS}

    # Co-occurrence tracking: which patterns fire together and what's the combined WR
    combo_stats = defaultdict(lambda: {"setups": 0, "wins": 0, "returns": []})

    total_tickers = len(tickers)
    for ti, ticker in enumerate(tickers):
        if ticker == "SPY":
            continue
        try:
            df = load_daily(ticker, start=TRAIN_START, end=TRAIN_END)
            if df is None or len(df) < 250:
                continue

            det = PatternDetector(df, spy_close=spy_close)

            for i in range(10, len(df) - HOLD_DAYS - 1):
                date = df.index[i]
                fwd  = _forward_return(df["close"], i, HOLD_DAYS)
                if fwd is None:
                    continue

                # ATR regime
                atr_pct = float(det.atr14.iloc[i]) / float(df["close"].iloc[i])
                high_vol = atr_pct >= 0.04

                # SPY regime
                regime = "unknown"
                if spy_close is not None and date in spy_close.index:
                    ema50_spy = _ema(spy_close, 50)
                    regime = "bull" if spy_close.loc[date] > ema50_spy.loc[date] else "bear"

                fired_patterns = []
                for p in PATTERNS:
                    try:
                        fired = getattr(det, p)(i)
                    except Exception:
                        fired = False

                    if not fired:
                        continue

                    fired_patterns.append(p)
                    direction = PATTERN_DIRECTION.get(p, 1)
                    effective_return = fwd * direction

                    win = effective_return >= WIN_THRESH
                    loss = effective_return <= LOSS_THRESH

                    stats[p]["setups"] += 1
                    stats[p]["returns"].append(effective_return)
                    if win:
                        stats[p]["wins"] += 1
                    if loss:
                        stats[p]["losses"] += 1

                    # Regime breakdown
                    if regime == "bull":
                        stats[p]["bull_setups"] += 1
                        if win: stats[p]["bull_wins"] += 1
                    elif regime == "bear":
                        stats[p]["bear_setups"] += 1
                        if win: stats[p]["bear_wins"] += 1

                    # High-vol breakdown
                    if high_vol:
                        stats[p]["atr_high_setups"] += 1
                        if win: stats[p]["atr_high_wins"] += 1

                # Combo patterns
                if len(fired_patterns) >= 2:
                    fired_patterns.sort()
                    for pi in range(len(fired_patterns)):
                        for pj in range(pi+1, len(fired_patterns)):
                            key = f"{fired_patterns[pi]}+{fired_patterns[pj]}"
                            d1 = PATTERN_DIRECTION.get(fired_patterns[pi], 1)
                            d2 = PATTERN_DIRECTION.get(fired_patterns[pj], 1)
                            if d1 == d2:  # same direction
                                combo_stats[key]["setups"] += 1
                                er = fwd * d1
                                combo_stats[key]["returns"].append(er)
                                if er >= WIN_THRESH:
                                    combo_stats[key]["wins"] += 1

        except Exception as e:
            pass

        if verbose and (ti + 1) % 25 == 0:
            print(f"  [{ti+1}/{total_tickers}] {ticker}")

    return stats, combo_stats


def summarize(stats, combo_stats):
    """Build final learning summary."""
    results = {}
    for p, s in stats.items():
        n = s["setups"]
        if n < 30:
            continue
        wr  = s["wins"] / n
        lr  = s["losses"] / n
        rets = s["returns"]
        avg_ret = float(np.mean(rets)) if rets else 0
        avg_win = float(np.mean([r for r in rets if r >= WIN_THRESH])) if any(r >= WIN_THRESH for r in rets) else 0
        avg_loss = float(np.mean([r for r in rets if r <= LOSS_THRESH])) if any(r <= LOSS_THRESH for r in rets) else 0
        rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        bull_wr = s["bull_wins"] / s["bull_setups"] if s["bull_setups"] > 0 else None
        bear_wr = s["bear_wins"] / s["bear_setups"] if s["bear_setups"] > 0 else None
        atr_wr  = s["atr_high_wins"] / s["atr_high_setups"] if s["atr_high_setups"] > 0 else None

        results[p] = {
            "setups":       n,
            "win_rate":     round(wr * 100, 1),
            "loss_rate":    round(lr * 100, 1),
            "avg_return":   round(avg_ret * 100, 2),
            "avg_winner":   round(avg_win * 100, 2),
            "avg_loser":    round(avg_loss * 100, 2),
            "reward_risk":  round(rr, 2),
            "bull_wr":      round(bull_wr * 100, 1) if bull_wr is not None else None,
            "bear_wr":      round(bear_wr * 100, 1) if bear_wr is not None else None,
            "atr_high_wr":  round(atr_wr * 100, 1) if atr_wr is not None else None,
            "direction":    PATTERN_DIRECTION.get(p, 1),
        }

    # Top combos (min 30 setups, sorted by win rate)
    top_combos = []
    for key, s in combo_stats.items():
        n = s["setups"]
        if n < 30:
            continue
        wr = s["wins"] / n
        avg = float(np.mean(s["returns"])) if s["returns"] else 0
        top_combos.append({
            "combo":      key,
            "setups":     n,
            "win_rate":   round(wr * 100, 1),
            "avg_return": round(avg * 100, 2),
        })
    top_combos.sort(key=lambda x: x["win_rate"], reverse=True)

    return results, top_combos[:30]


if __name__ == "__main__":
    print(f"[learner] Starting deep pattern learning on S&P 500 2022-2025...")
    print(f"[learner] Patterns: {len(PATTERNS)}")
    print(f"[learner] Hold period: {HOLD_DAYS} days | Win threshold: {WIN_THRESH*100}%\n")

    stats, combo_stats = learn(verbose=True)
    pattern_results, top_combos = summarize(stats, combo_stats)

    # Sort patterns by win rate
    sorted_patterns = sorted(
        [(p, r) for p, r in pattern_results.items()],
        key=lambda x: x[1]["win_rate"], reverse=True
    )

    print("\n" + "="*70)
    print("PATTERN LEARNING RESULTS (sorted by win rate)")
    print("="*70)
    print(f"{'Pattern':<30} {'WR%':>6} {'N':>6} {'AvgRet':>8} {'R:R':>6} {'BullWR':>8} {'BearWR':>8} {'HiVolWR':>9}")
    print("-"*70)
    for p, r in sorted_patterns:
        print(f"{p:<30} {r['win_rate']:>6.1f} {r['setups']:>6} {r['avg_return']:>7.2f}% "
              f"{r['reward_risk']:>6.2f} "
              f"{str(r['bull_wr']) + '%':>8} {str(r['bear_wr']) + '%':>8} "
              f"{str(r['atr_high_wr']) + '%':>9}")

    print("\n" + "="*70)
    print("TOP PATTERN COMBINATIONS (2 signals firing together)")
    print("="*70)
    print(f"{'Combo':<50} {'WR%':>6} {'N':>6} {'AvgRet':>8}")
    print("-"*70)
    for c in top_combos[:20]:
        print(f"{c['combo'][:50]:<50} {c['win_rate']:>6.1f} {c['setups']:>6} {c['avg_return']:>7.2f}%")

    # Save
    output = {
        "generated_at":   datetime.utcnow().isoformat(),
        "train_period":   f"{TRAIN_START} to {TRAIN_END}",
        "hold_days":      HOLD_DAYS,
        "win_threshold":  WIN_THRESH,
        "patterns":       {p: r for p, r in sorted_patterns},
        "top_combos":     top_combos,
    }
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n[learner] Saved -> {OUTPUT_PATH}")
