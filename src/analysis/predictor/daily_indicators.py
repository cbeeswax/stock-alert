"""
Rich daily indicator engine.

Computes 25+ technical indicators from daily OHLCV data.
All indicators are computed on the FULL daily series and returned as a DataFrame.
The caller slices to the desired date for scoring/pattern-building.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def _rma(series: pd.Series, n: int) -> pd.Series:
    """Wilder's smoothed moving average (used in RSI, ADX)."""
    return series.ewm(alpha=1 / n, adjust=False).mean()


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_g = _rma(gain, n)
    avg_l = _rma(loss, n)
    rs = avg_g / avg_l.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _true_range(df: pd.DataFrame) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"] - df["close"].shift(1)).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return _rma(_true_range(df), n)


def _adx(df: pd.DataFrame, n: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (ADX, +DI, -DI)."""
    tr = _true_range(df)
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr = _rma(tr, n)
    plus_di = 100 * _rma(plus_dm, n) / atr.replace(0, np.nan)
    minus_di = 100 * _rma(minus_dm, n) / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = _rma(dx, n)
    return adx, plus_di, minus_di


def _macd(close: pd.Series, fast=12, slow=26, signal=9):
    """Return (macd_line, signal_line, histogram)."""
    line = _ema(close, fast) - _ema(close, slow)
    sig = _ema(line, signal)
    hist = line - sig
    return line, sig, hist


def _stoch(df: pd.DataFrame, k=14, d=3) -> tuple[pd.Series, pd.Series]:
    low_min = df["low"].rolling(k).min()
    high_max = df["high"].rolling(k).max()
    rng = (high_max - low_min).replace(0, np.nan)
    stoch_k = 100 * (df["close"] - low_min) / rng
    stoch_d = stoch_k.rolling(d).mean()
    return stoch_k, stoch_d


def _bollinger(close: pd.Series, n=20, mult=2.0):
    mid = close.rolling(n).mean()
    std = close.rolling(n).std()
    upper = mid + mult * std
    lower = mid - mult * std
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    width = (upper - lower) / mid.replace(0, np.nan)
    return pct_b, width, upper, lower


def _keltner(df: pd.DataFrame, n=20, mult=2.0):
    mid = _ema(df["close"], n)
    atr = _atr(df, n)
    upper = mid + mult * atr
    lower = mid - mult * atr
    return upper, lower


def _obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def _obv_slope(obv: pd.Series, n=10) -> pd.Series:
    """Slope of OBV over n days, normalized."""
    return obv.diff(n) / (obv.abs().rolling(n).mean().replace(0, np.nan))


def _cmf(df: pd.DataFrame, n=20) -> pd.Series:
    """Chaikin Money Flow."""
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng
    mfv = mfm * df["volume"]
    return mfv.rolling(n).sum() / df["volume"].rolling(n).sum().replace(0, np.nan)


def _mfi(df: pd.DataFrame, n=14) -> pd.Series:
    """Money Flow Index."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    up_mf = mf.where(tp > tp.shift(1), 0.0)
    down_mf = mf.where(tp < tp.shift(1), 0.0)
    mfr = up_mf.rolling(n).sum() / down_mf.rolling(n).sum().replace(0, np.nan)
    return 100 - 100 / (1 + mfr)


def _hh_hl_structure(df: pd.DataFrame, n=20) -> pd.Series:
    """
    Score 0-1 for higher-high / higher-low structure over last n bars.
    1.0 = perfect uptrend structure, 0.0 = downtrend structure.
    """
    highs = df["high"].rolling(n).apply(
        lambda x: int(x[-1] > x[:-1].max()) if len(x) > 1 else 0, raw=True
    )
    lows = df["low"].rolling(n).apply(
        lambda x: int(x[-1] > x[:-1].min()) if len(x) > 1 else 0, raw=True
    )
    return (highs + lows) / 2.0


def _squeeze(bb_upper, bb_lower, kc_upper, kc_lower) -> pd.Series:
    """True = BB inside KC = market coiling (squeeze on)."""
    return (bb_upper < kc_upper) & (bb_lower > kc_lower)


# ---------------------------------------------------------------------------
# Main computation function
# ---------------------------------------------------------------------------

def compute_daily_indicators(df: pd.DataFrame, spy: pd.DataFrame = None) -> pd.DataFrame:
    """
    Compute all indicators on daily OHLCV DataFrame.

    Parameters
    ----------
    df  : daily OHLCV DataFrame (columns: open, high, low, close, volume)
    spy : daily OHLCV for SPY (for relative strength calculation)

    Returns
    -------
    DataFrame with original columns plus all indicator columns.
    Only rows with ≥ 200 days of history will have valid EMA200 values.
    """
    if len(df) < 60:
        return df

    close = df["close"]
    volume = df["volume"]

    out = df.copy()

    # --- Trend: EMAs and distances ---
    out["ema9"] = _ema(close, 9)
    out["ema21"] = _ema(close, 21)
    out["ema50"] = _ema(close, 50)
    out["ema200"] = _ema(close, 200)

    out["pct_vs_ema9"] = (close - out["ema9"]) / out["ema9"]
    out["pct_vs_ema21"] = (close - out["ema21"]) / out["ema21"]
    out["pct_vs_ema50"] = (close - out["ema50"]) / out["ema50"]
    out["pct_vs_ema200"] = (close - out["ema200"]) / out["ema200"]

    # EMA alignment count (0-4): how many EMAs are stacked correctly
    out["ema_align"] = (
        (close > out["ema9"]).astype(int)
        + (out["ema9"] > out["ema21"]).astype(int)
        + (out["ema21"] > out["ema50"]).astype(int)
        + (out["ema50"] > out["ema200"]).astype(int)
    )

    # EMA slope: 5-day rate of change of EMA21 (trend direction)
    out["ema21_slope"] = out["ema21"].pct_change(5)
    out["ema50_slope"] = out["ema50"].pct_change(10)

    # --- Momentum: RSI ---
    out["rsi14"] = _rsi(close, 14)
    out["rsi7"] = _rsi(close, 7)  # short-term
    # RSI trend: rising or falling over 5 days
    out["rsi_slope"] = out["rsi14"].diff(5)

    # --- Momentum: MACD ---
    macd_line, macd_sig, macd_hist = _macd(close)
    out["macd_line"] = macd_line
    out["macd_signal"] = macd_sig
    out["macd_hist"] = macd_hist
    # MACD above/below zero line
    out["macd_above_zero"] = (macd_line > 0).astype(int)
    # MACD histogram rising (bullish momentum building)
    out["macd_hist_rising"] = (macd_hist > macd_hist.shift(1)).astype(int)
    # Recent MACD cross: 1=bullish, -1=bearish, 0=none (within last 3 days)
    cross = ((macd_line > macd_sig) & (macd_line.shift(1) <= macd_sig.shift(1))).astype(int)
    cross -= ((macd_line < macd_sig) & (macd_line.shift(1) >= macd_sig.shift(1))).astype(int)
    out["macd_cross_days"] = cross.rolling(3).sum()  # +1/-1 in last 3 days

    # --- Momentum: Stochastic ---
    stoch_k, stoch_d = _stoch(df)
    out["stoch_k"] = stoch_k
    out["stoch_d"] = stoch_d
    out["stoch_bullish"] = (
        (stoch_k > stoch_d)
        & (stoch_k < 80)
        & (stoch_k > 20)
    ).astype(int)

    # --- Momentum: Rate of Change ---
    out["roc5"] = close.pct_change(5)
    out["roc10"] = close.pct_change(10)
    out["roc21"] = close.pct_change(21)
    out["roc63"] = close.pct_change(63)  # ~1 quarter

    # --- Strength: ADX ---
    adx, plus_di, minus_di = _adx(df, 14)
    out["adx"] = adx
    out["plus_di"] = plus_di
    out["minus_di"] = minus_di
    out["di_spread"] = plus_di - minus_di  # positive = bullish
    out["adx_rising"] = (adx > adx.shift(3)).astype(int)

    # --- Volatility: Bollinger Bands ---
    bb_pct, bb_width, bb_upper, bb_lower = _bollinger(close, 20)
    out["bb_pct"] = bb_pct
    out["bb_width"] = bb_width
    out["bb_width_percentile"] = bb_width.rolling(252).rank(pct=True)
    out["bb_lower"] = bb_lower   # support level — lower band = mean-reversion floor

    # --- Volatility: Keltner Channels ---
    kc_upper, kc_lower = _keltner(df, 20)
    out["kc_lower"] = kc_lower   # support level — volatility-adjusted dynamic floor

    # --- Squeeze: BB inside KC ---
    out["in_squeeze"] = _squeeze(bb_upper, bb_lower, kc_upper, kc_lower).astype(int)
    # Bars since squeeze released
    squeeze_off = (~out["in_squeeze"].astype(bool)).astype(int)
    out["bars_since_squeeze"] = squeeze_off.groupby((out["in_squeeze"] == 1).cumsum()).cumcount()

    # --- Swing lows at multiple lookbacks (structural support) ---
    out["swing_low_5d"]  = df["low"].rolling(5).min()
    out["swing_low_10d"] = df["low"].rolling(10).min()
    out["swing_low_15d"] = df["low"].rolling(15).min()
    out["swing_low_20d"] = df["low"].rolling(20).min()

    # --- Volume shelf (POC): price with highest cumulative volume over last 60 days ---
    def _vol_shelf_series(df_w: pd.DataFrame, n_bins: int = 20) -> pd.Series:
        result = pd.Series(np.nan, index=df_w.index)
        for i in range(20, len(df_w)):
            window = df_w.iloc[max(0, i - 59): i + 1]
            lo, hi = window["low"].min(), window["high"].max()
            if hi <= lo:
                continue
            bins    = np.linspace(lo, hi, n_bins + 1)
            mid     = (bins[:-1] + bins[1:]) / 2
            tp      = (window["high"] + window["low"] + window["close"]) / 3
            vols    = window["volume"].values
            vol_bin = np.zeros(n_bins)
            for tp_val, v in zip(tp.values, vols):
                idx = min(int(np.searchsorted(bins, tp_val, side="right")) - 1, n_bins - 1)
                vol_bin[max(0, idx)] += v
            result.iloc[i] = mid[int(np.argmax(vol_bin))]
        return result

    out["vol_shelf"] = _vol_shelf_series(df)

    # --- ATR ---
    out["atr14"] = _atr(df, 14)
    out["atr_pct"] = out["atr14"] / close  # ATR as % of price = volatility level

    # --- Volume indicators ---
    vol_ma20 = volume.rolling(20).mean()
    vol_ma50 = volume.rolling(50).mean()
    out["vol_ratio_20"] = volume / vol_ma20.replace(0, np.nan)
    out["vol_ratio_50"] = volume / vol_ma50.replace(0, np.nan)

    obv = _obv(df)
    out["obv"] = obv
    out["obv_slope"] = _obv_slope(obv, 10)
    out["obv_above_ema"] = (obv > _ema(obv, 21)).astype(int)

    out["cmf"] = _cmf(df, 20)
    out["mfi"] = _mfi(df, 14)

    # --- Price structure ---
    out["hh_hl"] = _hh_hl_structure(df, 20)  # 0-1 score for uptrend structure

    # 52-week high/low proximity
    rolling_high_252 = close.rolling(252).max()
    rolling_low_252 = close.rolling(252).min()
    out["pct_from_52w_high"] = (close - rolling_high_252) / rolling_high_252
    out["pct_from_52w_low"] = (close - rolling_low_252) / rolling_low_252

    # Consolidation: % range of last 10 days relative to ATR
    day10_high = df["high"].rolling(10).max()
    day10_low = df["low"].rolling(10).min()
    out["consolidation_score"] = 1 - (
        (day10_high - day10_low) / (out["atr14"] * 10).replace(0, np.nan)
    ).clip(0, 1)

    # Average true range expansion: is ATR expanding or contracting vs 50-day ATR avg?
    atr_ma50 = out["atr14"].rolling(50).mean()
    out["atr_expanding"] = (out["atr14"] > atr_ma50).astype(int)

    # --- Relative strength vs SPY ---
    if spy is not None and not spy.empty:
        spy_close = spy["close"].reindex(close.index, method="ffill")
        out["rs_21d"] = close.pct_change(21) - spy_close.pct_change(21)
        out["rs_63d"] = close.pct_change(63) - spy_close.pct_change(63)
        out["rs_positive"] = (out["rs_21d"] > 0).astype(int)
        # SPY trend
        spy_ema50 = _ema(spy_close, 50)
        out["spy_uptrend"] = (spy_close > spy_ema50).astype(int)
        # SPY weekly structure (above 200-day EMA = broad market healthy)
        spy_ema200 = _ema(spy_close, 200)
        out["spy_above_ema200"] = (spy_close > spy_ema200).astype(int)
    else:
        out["rs_21d"] = np.nan
        out["rs_63d"] = np.nan
        out["rs_positive"] = 0
        out["spy_uptrend"] = 1  # assume neutral
        out["spy_above_ema200"] = 1

    # --- RS line trend: direction and acceleration of the RS line itself ---
    # The RS line's own trend often leads price — a new RS high before price = early signal
    if "rs_63d" in out.columns and not out["rs_63d"].isna().all():
        rs_line = out["rs_63d"]
        # Smooth RS line with EMA21 to reduce noise
        out["rs_line_ema21"] = _ema(rs_line, 21)
        # Is RS line above its own EMA? = RS line in uptrend
        out["rs_line_above_ema21"] = (rs_line > out["rs_line_ema21"]).astype(int)
        # Rate of change of RS line over 10 days: positive = RS accelerating vs SPY
        out["rs_line_slope_10d"] = rs_line.diff(10)
        # RS line at new 52-week high: earliest institutional leadership signal
        rs_52w_max = rs_line.rolling(252, min_periods=126).max()
        out["rs_line_new_high"] = (rs_line >= rs_52w_max).astype(int)
        # RS line vs its own 63-day max (shorter-term new high = momentum)
        rs_63d_max = rs_line.rolling(63, min_periods=21).max()
        out["rs_line_63d_high"] = (rs_line >= rs_63d_max).astype(int)
    else:
        out["rs_line_ema21"] = np.nan
        out["rs_line_above_ema21"] = 0
        out["rs_line_slope_10d"] = np.nan
        out["rs_line_new_high"] = 0
        out["rs_line_63d_high"] = 0

    return out


def get_snapshot(df_indicators: pd.DataFrame, as_of_date: str) -> pd.Series:
    """
    Get the indicator snapshot for a single date (last row on or before as_of_date).
    Returns a Series with all indicator values.
    """
    ts = pd.Timestamp(as_of_date)
    past = df_indicators[df_indicators.index <= ts]
    if past.empty:
        return pd.Series(dtype=float)
    return past.iloc[-1]


# ---------------------------------------------------------------------------
# Weekly indicator engine
# ---------------------------------------------------------------------------

def compute_weekly_indicators(df: pd.DataFrame, spy: pd.DataFrame = None) -> pd.DataFrame:
    """
    Resample daily OHLCV to weekly bars and compute weekly-timeframe indicators.

    Weekly chart is the CONTEXT chart — used to determine trend stage and structural
    quality. Daily chart is the DECISION/TIMING chart. Never reverse this hierarchy.

    Parameters
    ----------
    df  : daily OHLCV DataFrame (must have DatetimeIndex, columns: open/high/low/close/volume)
    spy : daily OHLCV for SPY (for weekly relative strength)

    Returns
    -------
    DataFrame indexed by week-ending Friday with weekly indicator columns.
    """
    if len(df) < 60:
        return pd.DataFrame()

    # Resample daily → weekly (anchor on Friday close)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    w = df.resample("W-FRI").agg(agg).dropna(subset=["close"])

    if len(w) < 10:
        return pd.DataFrame()

    close = w["close"]
    volume = w["volume"]
    out = w.copy()

    # --- Trend: Weekly EMAs ---
    # 10-week EMA ≈ 50-day; 40-week EMA ≈ 200-day (Weinstein's stage system uses 40-week)
    out["weekly_ema10"] = _ema(close, 10)
    out["weekly_ema40"] = _ema(close, 40)
    out["weekly_above_ema10"] = (close > out["weekly_ema10"]).astype(int)
    out["weekly_above_ema40"] = (close > out["weekly_ema40"]).astype(int)
    # Slope of 10-week EMA: positive = uptrend context confirmed
    out["weekly_ema10_slope"] = out["weekly_ema10"].pct_change(4)  # 4-week rate of change
    out["weekly_ema40_slope"] = out["weekly_ema40"].pct_change(13)  # quarter rate of change

    # Distance from weekly EMAs
    out["weekly_pct_vs_ema10"] = (close - out["weekly_ema10"]) / out["weekly_ema10"]
    out["weekly_pct_vs_ema40"] = (close - out["weekly_ema40"]) / out["weekly_ema40"]

    # --- Momentum: Weekly RSI ---
    out["weekly_rsi14"] = _rsi(close, 14)

    # --- Momentum: Weekly MACD ---
    _, _, weekly_macd_hist = _macd(close, fast=12, slow=26, signal=9)
    out["weekly_macd_hist"] = weekly_macd_hist
    out["weekly_macd_bullish"] = (weekly_macd_hist > 0).astype(int)
    out["weekly_macd_hist_rising"] = (weekly_macd_hist > weekly_macd_hist.shift(1)).astype(int)

    # --- Volatility: Weekly Bollinger Bands (20-week) ---
    bb_pct, bb_width, _, _ = _bollinger(close, n=20)
    out["weekly_bb_pct"] = bb_pct
    out["weekly_bb_width"] = bb_width

    # --- Volume: Weekly volume ratio ---
    vol_ma10 = volume.rolling(10).mean()
    out["weekly_vol_ratio"] = volume / vol_ma10.replace(0, np.nan)
    out["weekly_vol_expansion"] = (out["weekly_vol_ratio"] > 1.5).astype(int)
    out["weekly_vol_dryup"] = (out["weekly_vol_ratio"] < 0.7).astype(int)

    # --- Price structure: 52-week high proximity ---
    rolling_high_52w = close.rolling(52, min_periods=26).max()
    out["weekly_pct_from_52w_high"] = (close - rolling_high_52w) / rolling_high_52w
    out["weekly_near_52w_high"] = (out["weekly_pct_from_52w_high"] > -0.05).astype(int)

    # Prior week's candle low — key structural support level for stop placement
    out["prior_week_low"] = w["low"].shift(1)
    out["prior_week_high"] = w["high"].shift(1)

    # Consolidation: range over last 8 weeks relative to ATR
    high8 = w["high"].rolling(8).max()
    low8 = w["low"].rolling(8).min()
    weekly_atr = _atr(w, 10)
    out["weekly_atr"] = weekly_atr
    out["weekly_consolidating"] = (
        ((high8 - low8) / (weekly_atr * 8).replace(0, np.nan)) < 0.8
    ).astype(int)

    # Weeks in base: consecutive weeks where price is within 15% range (Stage 1 detection)
    base_range = (high8 - low8) / low8.replace(0, np.nan)
    in_base = (base_range < 0.15) & (out["weekly_above_ema40"] == 0)
    out["weeks_in_base"] = in_base.astype(int).groupby(
        (~in_base).cumsum()
    ).cumcount()

    # --- Relative strength vs SPY on weekly bars ---
    if spy is not None and not spy.empty:
        spy_w = spy["close"].resample("W-FRI").last().reindex(w.index, method="ffill")
        out["weekly_rs_4w"] = close.pct_change(4) - spy_w.pct_change(4)
        out["weekly_rs_13w"] = close.pct_change(13) - spy_w.pct_change(13)
        out["weekly_rs_26w"] = close.pct_change(26) - spy_w.pct_change(26)
        # Weekly RS line trend: is the RS line making new highs on the weekly chart?
        rs_line_w = out["weekly_rs_13w"]
        rs_52w_max = rs_line_w.rolling(52, min_periods=26).max()
        out["weekly_rs_line_new_high"] = (rs_line_w >= rs_52w_max).astype(int)
        out["weekly_rs_line_rising"] = (rs_line_w > rs_line_w.shift(4)).astype(int)
    else:
        out["weekly_rs_4w"] = np.nan
        out["weekly_rs_13w"] = np.nan
        out["weekly_rs_26w"] = np.nan
        out["weekly_rs_line_new_high"] = 0
        out["weekly_rs_line_rising"] = 0

    return out


def get_weekly_snapshot(df_weekly: pd.DataFrame, as_of_date: str) -> pd.Series:
    """
    Get the weekly indicator snapshot for the last completed week on or before as_of_date.
    The weekly chart provides STRUCTURAL CONTEXT for daily entry decisions.
    """
    ts = pd.Timestamp(as_of_date)
    past = df_weekly[df_weekly.index <= ts]
    if past.empty:
        return pd.Series(dtype=float)
    return past.iloc[-1]


# ---------------------------------------------------------------------------
# Sector relative strength
# ---------------------------------------------------------------------------

def compute_sector_rs(df: pd.DataFrame, sector_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add sector-relative strength columns to the daily OHLCV DataFrame.

    A true market leader beats its sector AND its sector beats SPY.
    This function computes stock vs sector RS (not stock vs SPY).

    Parameters
    ----------
    df          : daily OHLCV (must already have DatetimeIndex)
    sector_df   : daily OHLCV for the sector ETF

    Returns
    -------
    DataFrame with added columns: rs_vs_sector_21d, rs_vs_sector_63d,
    rs_vs_sector_positive, sector_leader
    """
    if df.empty or sector_df.empty:
        df["rs_vs_sector_21d"] = np.nan
        df["rs_vs_sector_63d"] = np.nan
        df["rs_vs_sector_positive"] = 0
        df["sector_leader"] = 0
        return df

    close = df["close"]
    sector_close = sector_df["close"].reindex(close.index, method="ffill")

    out = df.copy()
    out["rs_vs_sector_21d"] = close.pct_change(21) - sector_close.pct_change(21)
    out["rs_vs_sector_63d"] = close.pct_change(63) - sector_close.pct_change(63)
    out["rs_vs_sector_positive"] = (out["rs_vs_sector_21d"] > 0).astype(int)
    # True sector leader = beats sector on both 21d and 63d timeframes
    out["sector_leader"] = (
        (out["rs_vs_sector_21d"] > 0) & (out["rs_vs_sector_63d"] > 0)
    ).astype(int)
    return out


def compute_sector_regime(sector_df: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    """
    Compute sector ETF regime: is the sector itself leading or lagging SPY?

    Returns a DataFrame with sector RS vs SPY columns, used to assess whether
    we are buying from a strong or weak sector group.
    """
    if sector_df.empty or spy.empty:
        return pd.DataFrame()

    close = sector_df["close"]
    spy_close = spy["close"].reindex(close.index, method="ffill")

    out = sector_df[["close"]].copy()
    out["sector_rs_21d"] = close.pct_change(21) - spy_close.pct_change(21)
    out["sector_rs_63d"] = close.pct_change(63) - spy_close.pct_change(63)
    out["sector_above_spy_21d"] = (out["sector_rs_21d"] > 0).astype(int)
    out["sector_above_spy_63d"] = (out["sector_rs_63d"] > 0).astype(int)
    # Sector leadership score: 2 = leading on both tf, 1 = mixed, 0 = lagging
    out["sector_leadership"] = out["sector_above_spy_21d"] + out["sector_above_spy_63d"]
    return out


def make_fingerprint(snap: pd.Series) -> dict:
    """
    Discretize key indicators into qualitative buckets for pattern matching.
    Returns a dict of {indicator_name: bucket_label}.
    """
    def _bucket(val, thresholds: list, labels: list) -> str:
        if pd.isna(val):
            return "unknown"
        for i, t in enumerate(thresholds):
            if val <= t:
                return labels[i]
        return labels[-1]

    return {
        "ema_align":    _bucket(snap.get("ema_align", np.nan),   [1, 2, 3],   ["weak", "mixed", "good", "strong"]),
        "rsi14":        _bucket(snap.get("rsi14", np.nan),        [40, 50, 60, 70, 80], ["oversold", "low", "neutral", "momentum", "high", "overbought"]),
        "rsi_slope":    _bucket(snap.get("rsi_slope", np.nan),    [-3, 0, 3],  ["falling_fast", "falling", "rising", "rising_fast"]),
        "macd_zone":    _bucket(snap.get("macd_above_zero", np.nan), [0],      ["below_zero", "above_zero"]),
        "macd_hist":    _bucket(snap.get("macd_hist_rising", np.nan), [0],     ["declining", "building"]),
        "adx":          _bucket(snap.get("adx", np.nan),          [15, 20, 30, 40], ["no_trend", "weak", "developing", "trending", "strong_trend"]),
        "di_spread":    _bucket(snap.get("di_spread", np.nan),    [-10, 0, 10, 20], ["strong_bear", "bear", "neutral", "bull", "strong_bull"]),
        "bb_pct":       _bucket(snap.get("bb_pct", np.nan),       [0.2, 0.4, 0.6, 0.8], ["near_lower", "lower_half", "neutral", "upper_half", "near_upper"]),
        "bb_width":     _bucket(snap.get("bb_width_percentile", np.nan), [0.2, 0.4, 0.6, 0.8], ["very_tight", "tight", "normal", "wide", "very_wide"]),
        "squeeze":      _bucket(snap.get("in_squeeze", np.nan),   [0],        ["no_squeeze", "in_squeeze"]),
        "vol_surge":    _bucket(snap.get("vol_ratio_20", np.nan), [0.7, 1.0, 1.5, 2.5], ["very_low", "below_avg", "avg", "above_avg", "surge"]),
        "obv_trend":    _bucket(snap.get("obv_above_ema", np.nan), [0],       ["obv_falling", "obv_rising"]),
        "cmf":          _bucket(snap.get("cmf", np.nan),          [-0.1, 0.0, 0.1, 0.2], ["strong_outflow", "outflow", "neutral", "inflow", "strong_inflow"]),
        "rs_21d":       _bucket(snap.get("rs_positive", np.nan),  [0],        ["underperforming", "outperforming"]),
        "structure":    _bucket(snap.get("hh_hl", np.nan),        [0.3, 0.5, 0.7], ["downtrend", "weak", "neutral", "uptrend"]),
        "52w_position": _bucket(snap.get("pct_from_52w_high", np.nan), [-0.30, -0.15, -0.05, 0.0], ["far_below", "below", "near_high", "at_high", "breakout"]),
        "atr_regime":   _bucket(snap.get("atr_pct", np.nan),      [0.01, 0.02, 0.04], ["low_vol", "normal", "elevated", "high_vol"]),
        "spy_trend":    _bucket(snap.get("spy_uptrend", np.nan),  [0],        ["spy_below_50ema", "spy_above_50ema"]),
        "stoch":        _bucket(snap.get("stoch_bullish", np.nan), [0],       ["stoch_bearish", "stoch_bullish"]),
        "consolidation": _bucket(snap.get("consolidation_score", np.nan), [0.3, 0.5, 0.7], ["extended", "normal", "tight", "coiling"]),
    }
