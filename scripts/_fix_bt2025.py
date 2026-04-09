"""One-time fix: replace old scoring block in backtest_2025.py."""
import re

with open("scripts/backtest_2025.py", encoding="utf-8") as f:
    content = f.read()

# Replace everything from Step 1 through the scoring loop
old_pattern = r"        # .* Step 1: Detect market regime .*\n        entry_dt.*\n        spy_slice = spy_df_ind.*\n        regime = detect_market_regime.*\n\n        # .* Step 2: Score all tickers .*\n        scored = \[\]\n        for ticker in tickers:\n            try:\n                df_raw = load_daily\(ticker\)\n                if len\(df_raw\) < 60:\n                    continue\n                df_ind = compute_daily_indicators\(df_raw\)\n\n                # Compute weekly indicators\n                sector_etf = sector_map\.get\(ticker\)\n                sector_df  = sector_dfs\.get\(sector_etf\) if sector_etf else None\n                df_weekly  = compute_weekly_indicators\(df_ind, spy_df_ind\)\n                if sector_df is not None:\n                    sector_df_ind = compute_daily_indicators\(sector_df\)\n                    df_ind = compute_sector_rs\(df_ind, sector_df_ind\)\n\n                as_of_dt = pd\.Timestamp\(as_of\)\n                snap     = get_snapshot\(df_ind, as_of_dt\)\n                wsnap    = get_weekly_snapshot\(df_weekly, as_of_dt\)\n                if snap is None:\n                    continue\n\n                result = score_ticker\(snap, df_ind, regime, spy_df_ind, wsnap=wsnap\)\n                if result:\n                    result\[\"ticker\"\] = ticker\n                    scored\.append\(result\)\n            except Exception:\n                continue"

new_block = """        # -- Step 1: Market regime ---------------------------------------------------
        spy_slice = load_daily("SPY", end=as_of)
        spy_above_ema50 = True
        regime_label    = "BULL"
        sector_dfs_week = {}

        if spy_slice is not None and len(spy_slice) >= 50:
            spy_ind  = compute_daily_indicators(spy_slice)
            spy_snap = get_snapshot(spy_ind, pd.Timestamp(as_of))
            if spy_snap is not None:
                spy_above_ema50 = float(spy_snap.get("close") or 0) > float(spy_snap.get("ema50") or 0)
                regime_label    = "BULL" if spy_above_ema50 else "BEAR"
            for etf in SECTOR_ETFS:
                sdf = load_daily(etf, end=as_of)
                if sdf is not None and not sdf.empty:
                    sector_dfs_week[etf] = sdf
        else:
            spy_slice = None

        # -- Step 2: Score all tickers ----------------------------------------------
        scored = []
        for ticker in tickers:
            try:
                df = load_daily(ticker, end=as_of)
                if df is None or len(df) < 200:
                    continue
                ind = compute_daily_indicators(df, spy=spy_slice)

                sector_etf = sector_map.get(ticker)
                if sector_etf and sector_etf in sector_dfs_week:
                    ind = compute_sector_rs(ind, sector_dfs_week[sector_etf])

                weekly_df = compute_weekly_indicators(df, spy=spy_slice)
                wsnap = get_weekly_snapshot(weekly_df, as_of) if not weekly_df.empty else pd.Series(dtype=float)

                snap = get_snapshot(ind, pd.Timestamp(as_of))
                if snap is None or snap.empty:
                    continue

                result = score_ticker_comprehensive(snap, ind, spy_above_ema50, wsnap=wsnap)
                if result is None:
                    continue
                result["ticker"] = ticker
                scored.append(result)
            except Exception:
                continue"""

new_content = re.sub(old_pattern, new_block, content, flags=re.MULTILINE)
changed = new_content != content
print("Changed:", changed)

# Also fix the print line using regime variable
new_content = new_content.replace(
    'print(f"\\n  WEEK {label:7}  {macro.level:<7}  {max_picks} picks  regime={regime:<16}  SPY={spy_ret:+5.1f}%  {status_tag}")',
    'print(f"\\n  WEEK {label:7}  {macro.level:<7}  {max_picks} picks  regime={regime_label:<6}  SPY={spy_ret:+5.1f}%  {status_tag}")',
)

# Also fix the pick's "institutional" key (correct field name)
new_content = new_content.replace(
    'p.get("institutional") in ("ACCUMULATING", "MARKUP")',
    'p.get("institutional", "") in ("ACCUMULATING", "MARKUP")',
)

# Remove unused bulk loading of spy_df and sector_dfs at top of function
new_content = new_content.replace(
    '    # Load SPY for regime + weekly return validation\n    spy_df = load_daily("SPY")\n    spy_df_ind = compute_daily_indicators(spy_df)\n\n    # Load sector ETFs\n    sector_dfs = {}\n    for etf in SECTOR_ETFS:\n        try:\n            sector_dfs[etf] = load_daily(etf)\n        except Exception:\n            pass\n\n    # Load sector map',
    '    # Load SPY for weekly return validation only (regime loaded per week with end= slicing)\n    spy_df = load_daily("SPY")\n\n    # Load sector map',
)

with open("scripts/backtest_2025.py", "w", encoding="utf-8") as f:
    f.write(new_content)
print("Written OK")
