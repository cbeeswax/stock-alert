from utils.scanner import run_scan
from utils.pre_buy_check import pre_buy_check
from utils.email_utils import send_email_alert
from utils.high_52w_strategy import score_52week_high_stock, is_52w_watchlist_candidate
from utils.consolidation_strategy import get_consolidation_breakouts
from utils.rs_strategy import get_relative_strength_stocks
import pandas as pd

if __name__ == "__main__":
    print("🚀 Running EMA crossover and 52-week high scan...")

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
    # Step 4: Run Consolidation Breakouts & Relative Strength
    # --------------------------------------------------
    consolidation_list = get_consolidation_breakouts()
    rs_list = get_relative_strength_stocks()

    # --------------------------------------------------
    # Step 5: Console summary (optional)
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
        print("\n📊 Consolidation Breakouts:")
        for c in consolidation_list:
            print(f"{c['Ticker']} | Score: {c.get('Score','N/A')}")
    else:
        print("\n📊 No consolidation breakout setups today.")

    if rs_list:
        print("\n⭐ Relative Strength / Sector Leaders:")
        for r in rs_list:
            print(f"{r['Ticker']} | Score: {r.get('Score','N/A')}")
    else:
        print("\n⭐ No relative strength setups today.")

    # --------------------------------------------------
    # Step 6: Send email (ALL formatting inside email_utils)
    # --------------------------------------------------
    send_email_alert(
        trade_df=trade_ready,
        high_buy_list=high_buy_list,
        high_watch_list=high_watch_list,
        ema_list=ema_list,
        consolidation_list=consolidation_list,
        rs_list=rs_list
    )
