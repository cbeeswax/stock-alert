from scanners.scanner import run_scan
from core.pre_buy_check import pre_buy_check
from utils.email_utils import send_email_alert
from utils.ema_utils import compute_ema_incremental
from utils.position_tracker import PositionTracker, filter_trades_by_position
from config.trading_config import MAX_TRADES_PER_SCAN

# Email-specific filtering (separate from trade selection)
MIN_FINAL_SCORE = 3.0  # Minimum FinalScore to include in email
                       # FinalScore = NormalizedScore × ExpectedValue
                       # Range: 0 to ~13 (varies by strategy)
                       # 3.0 = filters out low-quality signals across all strategies

# 🆕 Position tracker for live trading (persistent file)
position_tracker = PositionTracker(mode="live", file="data/open_positions.json")

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
    # Step 3.1: Filter out tickers already in position (🆕 LIVE TRADING)
    # --------------------------------------------------
    print(f"\n📊 Current Open Positions: {position_tracker.get_position_count()}")
    if position_tracker.get_position_count() > 0:
        print(position_tracker)

    if not trade_ready.empty:
        trade_ready = filter_trades_by_position(trade_ready, position_tracker)

    # --------------------------------------------------
    # Step 3.2: Apply final score filter and max trades
    # --------------------------------------------------
    if not trade_ready.empty:
        trade_ready = trade_ready[
            trade_ready["FinalScore"] >= MIN_FINAL_SCORE
        ].head(MAX_TRADES_PER_SCAN)

    print(f"\n📧 Sending email with top {len(trade_ready)} trade(s) (max: {MAX_TRADES_PER_SCAN})")

    # --------------------------------------------------
    # Step 4: Send email (with open positions)
    # --------------------------------------------------
    send_email_alert(
        trade_df=trade_ready,
        all_signals=combined_signals,  # Pass all signals for watchlist
        high_buy_list=high_list,
        high_watch_list=high_watch_list,
        ema_list=ema_list,
        consolidation_list=consolidation_list,
        rs_list=rs_list,
        position_tracker=position_tracker  # 🆕 Pass position tracker
    )
