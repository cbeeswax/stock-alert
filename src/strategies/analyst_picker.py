"""
Analyst Picker Strategy
=======================
Acts as an LLM-powered stock analyst to pick the top 10 weekly trades.

Philosophy (learned from 37,186 historical setups, 2022-2025):
  - SPY regime gates everything: bear market = mean reversion dominant
  - ATR regime is the #1 predictor: only trade high-vol stocks
  - RSI7 > RSI14 = short-term momentum turning (recovery signal)
  - CMF > -0.1 = institutions not aggressively selling
  - In-squeeze (BB inside KC) = energy coiling for a move
  - Prefer DEFENSIVE sectors in bear/tariff environments
  - Avoid: falling RSI7, heavy CMF outflow, OBV slope deeply negative

Sector regime awareness:
  - Bull SPY: momentum leaders, EMA stack, RS vs SPY positive
  - Bear SPY: mean reversion, oversold, defensive sectors
  - Sector rotation: detect which sector ETFs are leading and weight within them

Entry/Exit:
  - Entry: Monday open (approximated by Friday close)
  - Stop:  Entry - 1.5 * ATR14
  - Target: Entry + 2.5 * risk (2.5:1 R/R)
  - MaxDays: 5 (weekly hold)
"""

import os
import sys
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, List

# Allow import when run standalone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.strategies.base import BaseStrategy

# Sector ETF map (used for sector momentum detection)
SECTOR_ETFS = {
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLU": "Utilities",
    "XLP": "Staples",
    "XLK": "Technology",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLRE": "Real Estate",
    "XLY": "Consumer Disc",
    "XLB": "Materials",
    "XLC": "Communication",
}

# Stocks roughly mapped to sectors (subset — expands via data)
SECTOR_MAP = {
    "Energy":       ["XOM","CVX","COP","EOG","SLB","MPC","PSX","VLO","DVN","FANG","APA","HAL","BKR","HES","OXY"],
    "Healthcare":   ["UNH","JNJ","LLY","ABBV","MRK","TMO","ABT","DHR","BMY","AMGN","GILD","ISRG","SYK","ELV","CI","HUM","CNC","MOH","BAX","BSX","EW","HOLX","PODD","DXCM","ALGN","BIO","CRL","TECH","IDXX","MLAB"],
    "Utilities":    ["NEE","DUK","SO","AEP","EXC","SRE","PCG","ETR","PPL","ES","AES","CEG"],
    "Staples":      ["PG","KO","PEP","COST","WMT","MO","PM","CL","GIS","K","CPB","CLX","SJM","HSY","CAG","MKC","HRL","DLTR","DG"],
    "Technology":   ["AAPL","MSFT","NVDA","AVGO","AMD","QCOM","TXN","MU","AMAT","LRCX","KLAC","MRVL","INTC","CDNS","SNPS","ANSS","CDW","CTSH","EPAM","GDDY","PAYC"],
    "Financials":   ["JPM","BAC","WFC","GS","MS","BLK","BX","APO","KKR","SCHW","AXP","V","MA","COF","CBOE","CME","ICE","BR","CPAY"],
    "Industrials":  ["CAT","DE","EMR","HON","GE","RTX","LMT","NOC","GD","BA","UPS","FDX","CBRE","BRO","CPRT"],
    "Real Estate":  ["AMT","PLD","EQIX","CCI","WELL","ARE","BXP","CSGP","VTR","EQR"],
    "Consumer Disc":["AMZN","TSLA","HD","MCD","NKE","SBUX","TGT","TJX","BKNG","MAR","HLT","CCL","RCL","DAL","AAL","UAL","CMG","DPZ","YUM","BBY","KMX","APTV","DLTR","DASH","CZR"],
    "Materials":    ["LIN","APD","SHW","ECL","NEM","FCX","NUE","CF","DOW","LYB","ALB","MOS","BG","ADM"],
    "Communication":["GOOGL","META","NFLX","DIS","CHTR","TMUS","T","VZ","AKAM","EPAM"],
}


class AnalystPickerStrategy(BaseStrategy):
    """
    LLM-powered weekly stock analyst.

    Combines:
    1. Regime detection (SPY trend + leading sector)
    2. Per-stock multi-factor scoring using daily indicators
    3. Analyst-style reasoning: RSI7 vs RSI14 divergence, CMF, OBV, squeeze
    4. Sector-context bonus/penalty
    5. Hard filters: ATR gate, CMF outflow veto, falling RSI7 veto
    """

    name = "AnalystPicker_Weekly"
    description = "LLM-powered weekly stock analyst using daily indicators + sector regime"

    # ------------------------------------------------------------------ #
    # Core per-ticker scan
    # ------------------------------------------------------------------ #

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        as_of_date: pd.Timestamp = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single ticker. Returns signal dict or None.
        df must have lowercase columns: open, high, low, close, volume.
        """
        if df is None or len(df) < 200:
            return None

        if as_of_date is not None:
            df = df[df.index <= as_of_date]
        if len(df) < 200:
            return None

        try:
            ind = self._compute_indicators(df)
        except Exception:
            return None

        snap = ind.iloc[-1]

        # ---- Hard gates ----
        atr_pct = float(snap.get("atr_pct", 0) or 0)
        if atr_pct < 0.020:  # skip low-volatility stocks
            return None

        rsi7  = float(snap.get("rsi7", 50) or 50)
        rsi14 = float(snap.get("rsi14", 50) or 50)
        cmf   = float(snap.get("cmf", 0) or 0)
        obv_s = float(snap.get("obv_slope", 0) or 0)

        # Veto: RSI7 still falling hard AND CMF very negative = do not catch falling knife
        if rsi7 < rsi14 - 5 and cmf < -0.25:
            return None

        score, breakdown = self._analyst_score(snap)

        if score < 40:
            return None

        close = float(snap.get("close", 0) or 0)
        atr14 = float(snap.get("atr14", 0) or 0)
        if close <= 0 or atr14 <= 0:
            return None

        stop   = round(close - 1.5 * atr14, 2)
        target = round(close + 2.5 * (close - stop), 2)
        risk_pct = round((close - stop) / close * 100, 2)

        return {
            "Ticker":   ticker,
            "Strategy": self.name,
            "Date":     as_of_date or df.index[-1],
            "Close":    round(close, 2),
            "Entry":    round(close, 2),
            "StopLoss": stop,
            "Target":   target,
            "Score":    round(score, 2),
            "Volume":   int(df["volume"].iloc[-1]),
            "Priority": "HIGH" if score >= 70 else "MEDIUM",
            "MaxDays":  5,
            # Analyst metadata
            "ATR_pct":    round(atr_pct * 100, 2),
            "RSI14":      round(rsi14, 1),
            "RSI7":       round(rsi7, 1),
            "RSI_signal": "RECOVERING" if rsi7 > rsi14 else "FALLING",
            "CMF":        round(cmf, 3),
            "OBV_slope":  round(obv_s, 3),
            "In_squeeze": int(snap.get("in_squeeze", 0) or 0),
            "Pct_52wH":   round(float(snap.get("pct_from_52w_high", 0) or 0) * 100, 1),
            "Risk_pct":   risk_pct,
            "Breakdown":  breakdown,
        }

    # ------------------------------------------------------------------ #
    # Bulk scan with regime detection
    # ------------------------------------------------------------------ #

    def run(
        self,
        tickers: List[str],
        as_of_date: pd.Timestamp = None,
        spy_df: pd.DataFrame = None,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Full analyst run across all tickers.
        Detects SPY regime + leading sector, then scores all stocks.
        Returns top_n picks sorted by score.
        """
        # 1. Detect regime
        regime = self._detect_regime(spy_df, as_of_date)

        # 2. Detect leading sectors
        leading_sectors = self._detect_leading_sectors(as_of_date)

        # 3. Score all tickers
        signals = []
        for ticker in tickers:
            try:
                df = self._load(ticker, as_of_date)
                if df is None or df.empty:
                    continue
                sig = self.scan(ticker, df, as_of_date)
                if sig is None:
                    continue
                # Sector context bonus
                sig = self._apply_sector_context(sig, ticker, regime, leading_sectors)
                signals.append(sig)
            except Exception:
                continue

        # 4. Sort and return top N
        signals.sort(key=lambda s: s["Score"], reverse=True)
        return signals[:top_n]

    # ------------------------------------------------------------------ #
    # Analyst scoring — the brain
    # ------------------------------------------------------------------ #

    def _analyst_score(self, snap: pd.Series) -> tuple:
        """
        Multi-factor analyst score (0-100) with human-readable breakdown.

        Based on learnings from 37,186 historical setups (2022-2025):
          - ATR regime: high_vol = 45.6% WR, normal = 28.5%
          - RSI7 > RSI14 = momentum RECOVERING (key reversal signal)
          - CMF > 0 = institutions accumulating
          - In squeeze = energy coiling
          - Far below 52w high = mean reversion potential
          - SPY downtrend = favor defensive + mean reversion
        """
        score = 0.0
        breakdown = {}

        def _f(k, d=0): return float(snap.get(k, 0) or 0)

        rsi14    = _f("rsi14")
        rsi7     = _f("rsi7")
        adx      = _f("adx")
        di       = _f("di_spread")
        cmf      = _f("cmf")
        mfi      = _f("mfi")
        obv_s    = _f("obv_slope")
        bb_pct   = _f("bb_pct")
        atr_pct  = _f("atr_pct")
        h52      = _f("pct_from_52w_high")   # negative = below high
        ema_aln  = _f("ema_align")
        in_sqz   = _f("in_squeeze")
        volr     = _f("vol_ratio_20")
        roc5     = _f("roc5")
        roc21    = _f("roc21")
        rs21     = _f("rs_21d")
        spy_up   = _f("spy_uptrend")
        stoch_k  = _f("stoch_k")
        mhist_r  = _f("macd_hist_rising")

        # --- 1. ATR regime (28 pts) — #1 predictor ---
        atr_score = 0
        if atr_pct >= 0.06:
            atr_score = 28   # high_vol (45.6% WR)
        elif atr_pct >= 0.04:
            atr_score = 22   # elevated
        elif atr_pct >= 0.025:
            atr_score = 14   # normal-high
        else:
            atr_score = 0    # low_vol: never pick these
        score += atr_score
        breakdown["atr_regime"] = {"value": round(atr_pct * 100, 1), "score": atr_score,
                                   "note": "high_vol=best, low_vol=skip"}

        # --- 2. RSI divergence (20 pts) — key reversal signal ---
        rsi_score = 0
        rsi_div   = rsi7 - rsi14
        if rsi7 < 30 and rsi_div > 0:
            rsi_score = 20   # deeply oversold + recovering
        elif rsi7 < 40 and rsi_div > 0:
            rsi_score = 17
        elif rsi7 < 50 and rsi_div > 0:
            rsi_score = 13   # neutral range, turning up
        elif rsi_div > 5:
            rsi_score = 9    # any divergence upward
        elif rsi7 < 35:
            rsi_score = 8    # oversold even if not yet turning
        elif rsi7 > 75:
            rsi_score = -5   # overbought penalty
        elif rsi7 > 65:
            rsi_score = 0
        else:
            rsi_score = 4
        score += rsi_score
        breakdown["rsi_divergence"] = {"rsi14": round(rsi14, 1), "rsi7": round(rsi7, 1),
                                        "divergence": round(rsi_div, 1), "score": rsi_score,
                                        "note": "RSI7>RSI14 = short-term recovering"}

        # --- 3. Money flow (15 pts) ---
        mf_score = 0
        if cmf > 0.1:
            mf_score = 15    # strong inflow (institutions buying)
        elif cmf > 0:
            mf_score = 10
        elif cmf > -0.1:
            mf_score = 6     # neutral
        elif cmf > -0.2:
            mf_score = 2
        else:
            mf_score = -5    # heavy outflow penalty
        # OBV modifier
        if obv_s > 0.1:
            mf_score = min(mf_score + 3, 15)
        elif obv_s < -0.5:
            mf_score = max(mf_score - 3, -5)
        score += mf_score
        breakdown["money_flow"] = {"cmf": round(cmf, 3), "obv_slope": round(obv_s, 3),
                                    "score": mf_score, "note": "CMF>0=institutions buying"}

        # --- 4. 52-week position (12 pts) — mean reversion ---
        pos_score = 0
        h52_pct = h52 * 100  # negative number (e.g. -40 = 40% below high)
        if h52_pct < -40:
            pos_score = 12   # far_below (40.9% WR in historical data)
        elif h52_pct < -25:
            pos_score = 9
        elif h52_pct < -15:
            pos_score = 6
        elif h52_pct < -5:
            pos_score = 3
        else:
            pos_score = 0    # near 52w high (30.7% WR) — no bonus
        score += pos_score
        breakdown["52w_position"] = {"pct_from_high": round(h52_pct, 1), "score": pos_score,
                                      "note": "far below high = better mean reversion WR"}

        # --- 5. Squeeze / coiling (10 pts) ---
        sqz_score = 0
        if in_sqz:
            sqz_score = 10   # BB inside KC = energy building
        elif bb_pct < 0.25:
            sqz_score = 5    # price near lower band (oversold within bands)
        score += sqz_score
        breakdown["squeeze"] = {"in_squeeze": bool(in_sqz), "bb_pct": round(bb_pct, 2),
                                 "score": sqz_score, "note": "squeeze = coiling for move"}

        # --- 6. Trend strength / ADX (8 pts) ---
        adx_score = 0
        if adx > 30 and di > 5:
            adx_score = 2    # strong trend, bullish direction
        elif adx > 20 and di > 0:
            adx_score = 5
        elif adx > 15 and di > -5:
            adx_score = 8    # weak trend = mean reversion works BETTER
        elif adx > 30 and di < -15:
            adx_score = -3   # strong downtrend penalty
        else:
            adx_score = 4
        score += adx_score
        breakdown["trend_strength"] = {"adx": round(adx, 1), "di_spread": round(di, 1),
                                        "score": adx_score,
                                        "note": "weak ADX + neutral DI = mean reversion"}

        # --- 7. Volume confirmation (5 pts) ---
        vol_score = 0
        if volr >= 1.5:
            vol_score = 5    # volume surge (possible capitulation or breakout)
        elif volr >= 1.2:
            vol_score = 3
        elif volr >= 0.8:
            vol_score = 1
        else:
            vol_score = -2   # low volume = weak conviction
        score += vol_score
        breakdown["volume"] = {"vol_ratio_20": round(volr, 2), "score": vol_score}

        # --- 8. MACD momentum shift (4 pts) ---
        macd_score = int(mhist_r) * 4  # +4 if MACD histogram turning up
        score += macd_score
        breakdown["macd_shift"] = {"hist_rising": bool(mhist_r), "score": macd_score,
                                    "note": "MACD hist turning up = early momentum shift"}

        # --- 9. SPY regime modifier ---
        if not spy_up:
            # Bear market: mean reversion setups get a bonus, momentum penalized
            if rsi7 < 40:
                score += 4
            if ema_aln >= 3:
                score -= 3   # momentum setups fail more in bear market
        breakdown["spy_regime"] = {"spy_above_50ema": bool(spy_up)}

        # --- 10. Short-term momentum (ROC5) ---
        if 0 < roc5 < 0.10:
            score += 3   # already bouncing a little (but not too much)
        elif roc5 > 0.10:
            score += 1   # bouncing too much already
        elif roc5 < -0.10:
            score -= 3   # still in free-fall
        breakdown["roc5"] = {"value": round(roc5 * 100, 1)}

        return max(0.0, min(100.0, score)), breakdown

    # ------------------------------------------------------------------ #
    # Regime + sector detection
    # ------------------------------------------------------------------ #

    def _detect_regime(self, spy_df: pd.DataFrame, as_of_date) -> dict:
        """Detect SPY regime: bull/bear, volatility level."""
        regime = {"spy_uptrend": True, "label": "bull", "atr_pct": 0.01}
        if spy_df is None or spy_df.empty:
            return regime
        df = spy_df if as_of_date is None else spy_df[spy_df.index <= as_of_date]
        if len(df) < 50:
            return regime
        close = df["close"] if "close" in df.columns else df["Close"]
        ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
        last  = close.iloc[-1]
        spy_up = bool(last > ema50)
        roc21  = float(close.pct_change(21).iloc[-1])
        label  = "bull" if spy_up else ("bear" if roc21 < -0.05 else "chop")
        atr    = float(self._atr(df, 14).iloc[-1])
        regime = {"spy_uptrend": spy_up, "label": label,
                  "atr_pct": atr / last if last > 0 else 0.01,
                  "spy_roc21": round(roc21 * 100, 1)}
        return regime

    def _detect_leading_sectors(self, as_of_date) -> List[str]:
        """
        Find which sectors are outperforming SPY over 21 days.
        Returns list of leading sector names.
        """
        leading = []
        try:
            spy = self._load("SPY", as_of_date)
            if spy is None or spy.empty:
                return leading
            spy_roc = float(spy["close"].pct_change(21).iloc[-1])
            for etf, sector in SECTOR_ETFS.items():
                df = self._load(etf, as_of_date)
                if df is None or df.empty or len(df) < 30:
                    continue
                etf_roc = float(df["close"].pct_change(21).iloc[-1])
                if etf_roc > spy_roc + 0.02:   # outperforming SPY by >2%
                    leading.append(sector)
        except Exception:
            pass
        return leading

    def _apply_sector_context(
        self, sig: dict, ticker: str, regime: dict, leading_sectors: List[str]
    ) -> dict:
        """Boost score for stocks in leading sectors; penalize lagging in bear."""
        ticker_sector = None
        for sector, members in SECTOR_MAP.items():
            if ticker in members:
                ticker_sector = sector
                break

        sig["Sector"] = ticker_sector or "Unknown"
        sig["Leading_sectors"] = leading_sectors

        if ticker_sector and ticker_sector in leading_sectors:
            sig["Score"] = min(sig["Score"] + 8, 100)
            sig["Sector_boost"] = f"+8 (leading sector: {ticker_sector})"
        elif not regime["spy_uptrend"] and ticker_sector in ("Energy", "Utilities", "Healthcare", "Staples"):
            sig["Score"] = min(sig["Score"] + 5, 100)
            sig["Sector_boost"] = f"+5 (defensive sector in bear market)"
        else:
            sig["Sector_boost"] = "0"

        return sig

    # ------------------------------------------------------------------ #
    # Indicator computation
    # ------------------------------------------------------------------ #

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all daily indicators needed for analyst scoring."""
        # normalise column names
        col_map = {c: c.lower() for c in df.columns}
        df = df.rename(columns=col_map)
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            # try capitalised
            col_map2 = {c: c.lower() for c in df.columns}
            df = df.rename(columns=col_map2)
        if not required.issubset(set(df.columns)):
            raise ValueError(f"Missing columns. Have: {list(df.columns)}")

        c = df["close"]
        h = df["high"]
        l = df["low"]
        v = df["volume"]

        out = df.copy()

        # EMAs
        for n in (9, 21, 50, 200):
            out[f"ema{n}"] = c.ewm(span=n, adjust=False).mean()
        out["ema_align"] = (
            (c > out["ema9"]).astype(int)
            + (out["ema9"] > out["ema21"]).astype(int)
            + (out["ema21"] > out["ema50"]).astype(int)
            + (out["ema50"] > out["ema200"]).astype(int)
        )
        out["spy_uptrend"] = (c > out["ema50"]).astype(int)

        # RSI 14 and 7
        for n in (14, 7):
            delta = c.diff()
            g = delta.clip(lower=0)
            ls = -delta.clip(upper=0)
            ag = g.ewm(alpha=1/n, adjust=False).mean()
            al = ls.ewm(alpha=1/n, adjust=False).mean()
            rs = ag / al.replace(0, np.nan)
            out[f"rsi{n}"] = 100 - 100 / (1 + rs)

        # ATR14
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        out["atr14"] = tr.ewm(alpha=1/14, adjust=False).mean()
        out["atr_pct"] = out["atr14"] / c.replace(0, np.nan)

        # ADX / DI
        up   = h.diff();  dn = -l.diff()
        pdm  = up.where((up > dn) & (up > 0), 0.0)
        mdm  = dn.where((dn > up) & (dn > 0), 0.0)
        atr_ = tr.ewm(alpha=1/14, adjust=False).mean()
        pdi  = 100 * pdm.ewm(alpha=1/14, adjust=False).mean() / atr_.replace(0, np.nan)
        mdi  = 100 * mdm.ewm(alpha=1/14, adjust=False).mean() / atr_.replace(0, np.nan)
        dx   = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
        out["adx"]      = dx.ewm(alpha=1/14, adjust=False).mean()
        out["di_spread"] = pdi - mdi

        # MACD histogram rising
        macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
        sig_ = macd.ewm(span=9, adjust=False).mean()
        hist = macd - sig_
        out["macd_hist_rising"] = (hist > hist.shift(1)).astype(int)

        # Bollinger Bands
        bb_mid = c.rolling(20).mean()
        bb_std = c.rolling(20).std()
        bb_up  = bb_mid + 2 * bb_std
        bb_dn  = bb_mid - 2 * bb_std
        out["bb_pct"] = (c - bb_dn) / (bb_up - bb_dn).replace(0, np.nan)

        # Keltner / Squeeze
        kc_mid = c.ewm(span=20, adjust=False).mean()
        kc_up  = kc_mid + 2 * out["atr14"]
        kc_dn  = kc_mid - 2 * out["atr14"]
        out["in_squeeze"] = ((bb_up < kc_up) & (bb_dn > kc_dn)).astype(int)

        # CMF (20)
        rng  = (h - l).replace(0, np.nan)
        mfm  = ((c - l) - (h - c)) / rng
        mfv  = mfm * v
        out["cmf"] = mfv.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)

        # OBV slope
        obv  = (np.sign(c.diff()).fillna(0) * v).cumsum()
        out["obv_slope"] = obv.diff(10) / (obv.abs().rolling(10).mean().replace(0, np.nan))

        # Volume ratio
        out["vol_ratio_20"] = v / v.rolling(20).mean().replace(0, np.nan)

        # ROC
        out["roc5"]  = c.pct_change(5)
        out["roc21"] = c.pct_change(21)
        out["rs_21d"] = 0.0  # filled by caller if SPY available

        # 52w
        out["pct_from_52w_high"] = (c - c.rolling(252).max()) / c.rolling(252).max().replace(0, np.nan)

        return out

    def _atr(self, df: pd.DataFrame, n: int = 14) -> pd.Series:
        col = lambda x: x if x in df.columns else x.capitalize()
        h = df[col("high")];  l = df[col("low")];  c = df[col("close")]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        return tr.ewm(alpha=1/n, adjust=False).mean()

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #

    def _load(self, ticker: str, as_of_date=None) -> Optional[pd.DataFrame]:
        """Load daily data. Uses predictor data_loader if available, else market module."""
        try:
            from src.analysis.predictor.data_loader import load_daily
            df = load_daily(ticker, end=str(as_of_date.date()) if as_of_date else None)
            if not df.empty:
                return df
        except Exception:
            pass
        try:
            from src.data.market import get_historical_data
            df = get_historical_data(ticker)
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]
                if as_of_date is not None:
                    df = df[df.index <= as_of_date]
                return df
        except Exception:
            pass
        return None

    def get_exit_conditions(self, position, df, current_date):
        """Weekly hold: exit on Friday close, stop-loss, or target hit."""
        entry = position.get("entry_price", 0)
        stop  = position.get("stop_loss", 0)
        target = position.get("target", entry * 1.05)

        if df is None or df.empty:
            return None
        row = df[df.index <= current_date]
        if row.empty:
            return None
        last = row.iloc[-1]
        col = lambda x: x if x in last.index else x.capitalize()
        low_   = float(last[col("low")])
        high_  = float(last[col("high")])
        close_ = float(last[col("close")])

        if low_ <= stop:
            return {"reason": "STOP_HIT", "exit_price": stop}
        if high_ >= target:
            return {"reason": "TARGET_HIT", "exit_price": target}
        # Max hold = 5 trading days
        entry_date = position.get("entry_date")
        if entry_date and (current_date - entry_date).days >= 7:
            return {"reason": "MAX_HOLD", "exit_price": close_}
        return None
