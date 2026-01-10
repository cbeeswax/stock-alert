from utils.scanner import run_scan
from utils.pre_buy_check import pre_buy_check
from utils.email_utils import send_email_alert

if __name__ == "__main__":
    print("🚀 Running EMA crossover and 52-week high scan...")

    # --- Step 1: Run EMA and 52-week high scan ---
    ema_list, high_list = run_scan(test_mode=False)

    # --- Step 2: Apply pre-buy checks ---
    trade_ready = pre_buy_check(ema_list)

    # --- Step 3: Print console summary (optional) ---
    if ema_list:
        print("\n📈 EMA Crossovers:")
        for s in ema_list:
            print(f"{s['Ticker']} - {s['PctAboveCrossover']}% above crossover (Score: {s['Score']})")
    else:
        print("\n📈 No EMA crossovers found today.")

    if not trade_ready.empty:
        print("\n📋 Ready-to-Trade Stocks:")
        for t in trade_ready.to_dict(orient="records"):
            print(
                f"{t['Ticker']} | Entry: {t['Entry']} | Stop: {t['StopLoss']} | "
                f"Target: {t['Target']} | Score: {t['Score']}"
            )
    else:
        print("\n📋 No actionable trades found today.")

    if high_list:
        print("\n🚀 New 52-Week Highs:")
        for h in high_list:
            print(f"{h['Ticker']} ({h.get('Company','N/A')}): ${h['Close']} | Score: {h.get('Score','N/A')}")
    else:
        print("\n🚀 No new 52-week highs today.")

    # --- Step 4: Send HTML email (formatting handled inside email_utils) ---
    send_email_alert(trade_ready, high_list, ema_list=ema_list)
