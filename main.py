from utils.scanner import run_scan
from utils.pre_buy_check import pre_buy_check
from utils.email_utils import send_email_alert
from utils.high_52w_strategy import score_52week_high_stock, is_52w_watchlist_candidate
from utils.consolidation_breakout import check_consolidation_breakout
from utils.relative_strength import check_relative_strength
import pandas as pd

# Benchmark for relative strength (SPY or Nasdaq)
from utils.market_data import get_historical_data
benchmark_df = get_historical_data("SPY")  # You can change to QQQ for Nasdaq

if __name__ == "__main__":
    print("🚀 Running EMA crossover, 52-week high, consolidation breakout, and relative strength scans...")

    # --------------------------------------------------
    # Step 1: Run scan for EMA and 52-week highs
    # --------------------------------------------------
    ema_list, high_list = run_scan(test_mode=False)

    # --------------------------------------------------
    # Step 2: Apply pre-buy checks on EMA setups
    # --------------------------------------------------
    trade_ready = pre_buy_check(ema_list)

    # --------------------------------------------------
    # Step 3: Split 52-week highs into BUY-ready and WATCHLIST
    # --------------------------------------------------
    high_buy_list = []
    high_watch_list = []

    for h in high_list or []:
        score = score_52week_high_stock(h)

        if score is not None:
            h["Score"] = score
            high_buy_list.append(h)
        elif is_52w_watchlist_candidate(h):
            high_watch_list.append(h)

    # --------------------------------------------------
    # Step 4: Check consolidation breakouts
    # --------------------------------------------------
    consolidation_list = []
    for s in ema_list or []:
        consolidation = check_consolidation_breakout(s["Ticker"])
        if consolidation:
            consolidation_list.append(consolidation)

    # --------------------------------------------------
    # Step 5: Check relative strength (RS) / sector leaders
    # --------------------------------------------------
    rs_list = []
    for s in ema_list or []:
        rs = check_relative_strength(s["Ticker"], benchmark_df)
        if rs:
            rs_list.append(rs)

    # --------------------------------------------------
    # Step 6: Console summary (optional)
    # --------------------------------------------------
    if ema_list:
        print("\n📈 EMA Crossovers:")
        for s in ema_list:
            print(f"{s['Ticker']} - {s['PctAboveCrossover']}% | Score: {s['Score']}")
    else:
        print("\n📈 No EMA crossovers found today.")

    if not trade_ready.empty:
        print("\n🔥 Pre-Buy Actionable Trades:")
        for t in trade_ready.to_dict(orient="records"):
            print(
                f"{t['Ticker']} | Entry: {t['Entry']} | Stop: {t['StopLoss']} | "
                f"Target: {t['Target']} | Score: {t['Score']}"
            )
    else:
        print("\n🔥 No actionable trades found today.")

    if high_buy_list:
        print("\n🚀 52-Week High BUY-READY:")
        for h in high_buy_list:
            print(f"{h['Ticker']} | Score: {h['Score']}")
    else:
        print("\n🚀 No BUY-ready 52-week highs today.")

    if high_watch_list:
        print("\n👀 52-Week High WATCHLIST:")
        for h in high_watch_list:
            print(f"{h['Ticker']} | {h['PctFrom52High']}% from high")
    else:
        print("\n👀 No watchlist candidates today.")

    if consolidation_list:
        print("\n🔹 Consolidation Breakouts:")
        for c in consolidation_list:
            print(f"{c['Ticker']} | Score: {c['Score']} | Range: {c['RangeLow']} - {c['RangeHigh']}")
    else:
        print("\n🔹 No consolidation breakouts today.")

    if rs_list:
        print("\n⚡ Relative Strength / Sector Leaders:")
        for r in rs_list:
            print(f"{r['Ticker']} | RS%: {r['RS%']} | Score: {r['Score']}")
    else:
        print("\n⚡ No relative strength leaders today.")

    # --------------------------------------------------
    # Step 7: Send HTML email (ALL formatting inside email_utils)
    # --------------------------------------------------
    send_email_alert(
        trade_df=trade_ready,
        high_buy_list=high_buy_list,
        high_watch_list=high_watch_list,
        ema_list=ema_list,
        consolidation_list=consolidation_list,
        rs_list=rs_list  # <-- Added Relative Strength
    )
