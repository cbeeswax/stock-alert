from utils.scanner import run_scan
from utils.pre_buy_check import pre_buy_check
from utils.email_utils import send_email_alert
from utils.high_52w_strategy import score_52week_high_stock, is_52w_watchlist_candidate
import pandas as pd

if __name__ == "__main__":
    print("🚀 Running full stock scan...")

    # --------------------------------------------------
    # Step 1: Run complete scan
    # Returns: ema_list, high_list (BUY-ready), watchlist_highs, consolidation_list, rs_list
    # --------------------------------------------------
    ema_list, high_list, high_watch_list, consolidation_list, rs_list = run_scan(test_mode=False)

    # --------------------------------------------------
    # Step 2: Label strategy for each signal
    # --------------------------------------------------
    for s in ema_list:
        s["Strategy"] = "EMA Crossover"
    for s in high_list:
        s["Strategy"] = "52-Week High"
    for s in consolidation_list:
        s["Strategy"] = "Consolidation Breakout"
    for s in rs_list:
        s["Strategy"] = "Relative Strength"

    # --------------------------------------------------
    # Step 3: Combine all signals for pre-buy checks
    # --------------------------------------------------
    combined_signals = ema_list + high_list + consolidation_list + rs_list
    trade_ready = pre_buy_check(combined_signals)

    # --------------------------------------------------
    # Step 4: Console summary
    # --------------------------------------------------
    # EMA Crossovers
    if ema_list:
        print("\n📈 EMA Crossovers:")
        for s in ema_list:
            print(f"{s['Ticker']} - {s.get('PctAboveCrossover','N/A')}% | Score: {s.get('Score','N/A')}")
    else:
        print("\n📈 No EMA crossovers today.")

    # Pre-Buy Actionable Trades
    if not trade_ready.empty:
        print("\n🔥 Pre-Buy Actionable Trades:")
        for t in trade_ready.to_dict(orient="records"):
            print(
                f"{t['Ticker']} | Strategy: {t['Strategy']} | "
                f"Entry: {t['Entry']} | Stop: {t['StopLoss']} | Target: {t['Target']} | "
                f"Score: {t['Score']}"
            )
    else:
        print("\n🔥 No actionable trades today.")

    # 52-Week High BUY-READY
    if high_list:
        print("\n🚀 52-Week High BUY-READY:")
        for h in high_list:
            print(f"{h['Ticker']} | Score: {h.get('Score', 'N/A')}")
    else:
        print("\n🚀 No BUY-ready 52-week highs today.")

    # 52-Week High WATCHLIST
    if high_watch_list:
        print("\n👀 52-Week High WATCHLIST:")
        for h in high_watch_list:
            print(f"{h['Ticker']} | {h['PctFrom52High']:.2f}% from high")
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
    # --------------------------------------------------
    send_email_alert(
        trade_df=trade_ready,
        high_buy_list=high_list,
        high_watch_list=high_watch_list,
        ema_list=ema_list,
        consolidation_list=consolidation_list,
        rs_list=rs_list
    )
