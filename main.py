from utils.scanner import run_scan
from utils.pre_buy_check import pre_buy_check
from utils.email_utils import send_email_alert
from utils.high_52w_strategy import score_52week_high_stock, is_52w_watchlist_candidate
import pandas as pd

if __name__ == "__main__":
    print("🚀 Running full stock scan...")

    # --------------------------------------------------
    # Step 1: Run complete scan
    # Returns: ema_list, high_list, consolidation_list, rs_list
    # --------------------------------------------------
    ema_list, high_list, consolidation_list, rs_list = run_scan(test_mode=False)

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
    # Step 4: Console summary
    # --------------------------------------------------
    # EMA Crossovers
    if ema_list:
        print("\n📈 EMA Crossovers:")
        for s in ema_list:
            print(f"{s['Ticker']} - {s['PctAboveCrossover']}% | Score: {s['Score']}")
    else:
        print("\n📈 No EMA crossovers today.")

    # Pre-Buy Actionable Trades
    if not trade_ready.empty:
        print("\n🔥 Pre-Buy Actionable Trades:")
        for t in trade_ready.to_dict(orient="records"):
            print(
                f"{t['Ticker']} | Entry: {t['Entry']} | Stop: {t['StopLoss']} | "
                f"Target: {t['Target']} | Score: {t['Score']}"
            )
    else:
        print("\n🔥 No actionable trades today.")

    # 52-Week High BUY-READY
    if high_buy_list:
        print("\n🚀 52-Week High BUY-READY:")
        for h in high_buy_list:
            print(f"{h['Ticker']} | Score: {h['Score']}")
    else:
        print("\n🚀 No BUY-ready 52-week highs today.")

    # 52-Week High WATCHLIST
    if high_watch_list:
        print("\n👀 52-Week High WATCHLIST:")
        for h in high_watch_list:
            print(f"{h['Ticker']} | {h['PctFrom52High']}% from high")
    else:
        print("\n👀 No watchlist candidates today.")

    # Consolidation Breakouts
    if consolidation_list:
        print("\n📦 Consolidation Breakouts:")
        for c in consolidation_list:
            print(f"{c['Ticker']} | Score: {c['Score']}")
    else:
        print("\n📦 No consolidation breakouts today.")

    # Relative Strength Leaders
    if rs_list:
        print("\n💪 Relative Strength Leaders:")
        for r in rs_list:
            print(f"{r['Ticker']} | RS%: {r['RS%']} | Score: {r['Score']}")
    else:
        print("\n💪 No relative strength leaders today.")

    # --------------------------------------------------
    # Step 5: Send HTML email
    # Formatting fully handled in email_utils.py
    # --------------------------------------------------
    send_email_alert(
        trade_df=trade_ready,
        high_buy_list=high_buy_list,
        high_watch_list=high_watch_list,
        ema_list=ema_list,
        consolidation_list=consolidation_list,
        rs_list=rs_list
    )
