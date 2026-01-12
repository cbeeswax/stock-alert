from utils.scanner import run_scan
from utils.pre_buy_check import pre_buy_check
from utils.email_utils import send_email_alert
from utils.ema_utils import compute_ema_incremental

MAX_TRADES_EMAIL = 5
MIN_NORM_SCORE = 7

def get_market_regime(benchmark_ticker="SPY"):
    """
    Determines current market regime using EMA200 of benchmark.
    Returns True if bullish (SPY > EMA200), False if bearish.
    """
    df = compute_ema_incremental(benchmark_ticker)
    if df.empty or "EMA200" not in df.columns:
        print("⚠️ Unable to determine market regime, assuming bullish.")
        return True

    close_today = df["Close"].iloc[-1]
    ema200_today = df["EMA200"].iloc[-1]

    bullish = close_today > ema200_today
    print(f"📊 Market Regime: {'Bullish' if bullish else 'Bearish'} | {benchmark_ticker} Close: {close_today}, EMA200: {ema200_today}")
    return bullish


if __name__ == "__main__":
    print("🚀 Running full stock scan...")

    # --------------------------------------------------
    # Step 0: Determine market regime
    # --------------------------------------------------
    is_bullish = get_market_regime()

    # --------------------------------------------------
    # Step 1: Run complete scan
    # --------------------------------------------------
    ema_list, high_list, high_watch_list, consolidation_list, rs_list = run_scan(test_mode=False)

    # --------------------------------------------------
    # Step 1.1: Apply Market Regime Filter
    # Disable breakout signals if market is bearish
    # --------------------------------------------------
    if not is_bullish:
        print("⚠️ Bearish market detected → disabling breakout trades.")
        high_list = []
        consolidation_list = []

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
    # Step 3.1: Apply normalized score filter and max email trades
    # --------------------------------------------------
    if not trade_ready.empty:
        trade_ready = trade_ready[
            trade_ready["NormalizedScore"] >= MIN_NORM_SCORE
        ].head(MAX_TRADES_EMAIL)

    # --------------------------------------------------
    # Step 4: Send email
    # --------------------------------------------------
    send_email_alert(
        trade_df=trade_ready,
        high_buy_list=high_list,
        high_watch_list=high_watch_list,
        ema_list=ema_list,
        consolidation_list=consolidation_list,
        rs_list=rs_list
    )
