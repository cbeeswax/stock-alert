from utils.scanner import run_scan
from utils.email_utils import send_email_alert

if __name__ == "__main__":
    print("🚀 Running EMA crossover and 52-week high scan...")

    ema_list, high_list = run_scan(test_mode=False)

    if ema_list:
        print("\n📈 EMA Crossovers:")
        for s in ema_list:
            print(
                f"  {s['Ticker']} - "
                f"{s['PctAboveCrossover']}% above crossover "
                f"(Crossed on {s['CrossoverDate']}) | "
                f"RSI: {s['RSI14']} | "
                f"VolRatio: {s['VolumeRatio']} | "
                f"Score: {s['Score']}"
            )
    else:
        print("\n📈 EMA Crossovers: None")

    print("\n🏆 New 52-Week Highs:", high_list or "None")

    send_email_alert(ema_list, high_list)
