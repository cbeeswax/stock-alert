"""
Live Position Trading Scanner
==============================
Uses the same position trading strategies as the backtester.
Scans for 3 active strategies:
- RelativeStrength_Ranker_Position
- High52_Position
- BigBase_Breakout_Position
"""

import pandas as pd
from datetime import datetime
from scanners.scanner_walkforward import run_scan_as_of
from core.pre_buy_check import pre_buy_check
from utils.email_utils import send_email_alert
from utils.position_tracker import PositionTracker, filter_trades_by_position
from utils.position_monitor import monitor_positions
from utils.market_data import get_historical_data
from config.trading_config import (
    POSITION_MAX_TOTAL,
    POSITION_MAX_PER_STRATEGY,
    POSITION_RISK_PER_TRADE_PCT,
    POSITION_INITIAL_EQUITY,
    REGIME_INDEX,
    UNIVERSAL_QQQ_BULL_MA,
)

# Position tracker for live trading (persistent file)
position_tracker = PositionTracker(mode="live", file="data/open_positions.json")


def check_market_regime():
    """
    Check if market is in bullish regime (QQQ > 100-MA).
    Returns True if bullish, False otherwise.
    """
    df = get_historical_data(REGIME_INDEX)
    if df.empty or len(df) < UNIVERSAL_QQQ_BULL_MA:
        print("⚠️ Unable to determine market regime, assuming bullish.")
        return True

    close = df["Close"].iloc[-1]
    ma = df["Close"].rolling(UNIVERSAL_QQQ_BULL_MA).mean().iloc[-1]

    # Check if MA is rising
    ma_20d_ago = df["Close"].rolling(UNIVERSAL_QQQ_BULL_MA).mean().iloc[-21] if len(df) >= 21 else ma
    ma_rising = ma > ma_20d_ago

    bullish = close > ma and ma_rising

    print(f"📊 Market Regime: {'✅ BULLISH' if bullish else '⚠️ BEARISH'}")
    print(f"   {REGIME_INDEX}: ${close:.2f} | MA{UNIVERSAL_QQQ_BULL_MA}: ${ma:.2f} | MA Rising: {ma_rising}")

    return bullish


if __name__ == "__main__":
    print("="*80)
    print("🚀 LIVE POSITION TRADING SCANNER")
    print("="*80)
    print(f"📅 Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"⚠️  Risk per trade: {POSITION_RISK_PER_TRADE_PCT}%")
    print(f"📊 Max positions: {POSITION_MAX_TOTAL} total")
    print(f"📊 Active strategies: RS_Ranker (10), High52 (6), BigBase (4)")
    print("="*80 + "\n")

    # --------------------------------------------------
    # Step 1: Check Market Regime
    # --------------------------------------------------
    is_bullish = check_market_regime()

    if not is_bullish:
        print("\n⚠️  BEARISH MARKET - No new positions will be entered")
        print("📧 Sending status email...\n")

        # Monitor existing positions even in bearish market
        action_signals = {'exits': [], 'partials': [], 'pyramids': [], 'warnings': []}
        if position_tracker.get_position_count() > 0:
            action_signals = monitor_positions(position_tracker)

        # Send email with current positions only
        send_email_alert(
            trade_df=pd.DataFrame(),
            all_signals=[],
            subject_prefix="⚠️ BEARISH MARKET - No New Trades",
            position_tracker=position_tracker,
            action_signals=action_signals
        )
        exit(0)

    # --------------------------------------------------
    # Step 2: Monitor Open Positions for Exits/Actions
    # --------------------------------------------------
    print(f"\n📊 Current Open Positions: {position_tracker.get_position_count()}/{POSITION_MAX_TOTAL}")

    action_signals = {'exits': [], 'partials': [], 'pyramids': [], 'warnings': []}

    if position_tracker.get_position_count() > 0:
        print(position_tracker)

        print("\n" + "="*80)
        print("🔍 MONITORING POSITIONS FOR EXIT/ACTION SIGNALS...")
        print("="*80)

        action_signals = monitor_positions(position_tracker)

        # Display action signals
        total_actions = len(action_signals['exits']) + len(action_signals['partials']) + len(action_signals['pyramids'])

        if total_actions > 0:
            print(f"\n⚠️  {total_actions} ACTION(S) REQUIRED:\n")

            # Exits (highest priority)
            if action_signals['exits']:
                print(f"🚨 EXITS ({len(action_signals['exits'])}):")
                for exit_sig in action_signals['exits']:
                    print(f"   {exit_sig['ticker']}: {exit_sig['type']} - {exit_sig['reason']}")
                    print(f"   → {exit_sig['action']}")
                    print()

            # Partial profits
            if action_signals['partials']:
                print(f"💰 PARTIAL PROFITS ({len(action_signals['partials'])}):")
                for partial in action_signals['partials']:
                    print(f"   {partial['ticker']}: {partial['reason']}")
                    print(f"   → {partial['action']}")
                    print()

            # Pyramid opportunities
            if action_signals['pyramids']:
                print(f"📈 PYRAMID OPPORTUNITIES ({len(action_signals['pyramids'])}):")
                for pyramid in action_signals['pyramids']:
                    print(f"   {pyramid['ticker']}: {pyramid['reason']}")
                    print(f"   → {pyramid['action']}")
                    print()
        else:
            print("\n✅ No exit/action signals - all positions healthy")

        # Display warnings (FYI only)
        if action_signals['warnings']:
            print(f"\n⚠️  Warnings ({len(action_signals['warnings'])}):")
            for warning in action_signals['warnings']:
                print(f"   {warning.get('message', warning.get('ticker', 'Unknown'))}")

    # Count positions per strategy
    strategy_counts = {}
    for ticker, pos in position_tracker.get_all_positions().items():
        strategy = pos.get('strategy', 'Unknown')
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

    if strategy_counts:
        print("\n📊 Positions by Strategy:")
        for strategy, count in strategy_counts.items():
            max_for_strategy = POSITION_MAX_PER_STRATEGY.get(strategy, 5)
            print(f"   {strategy}: {count}/{max_for_strategy}")

    # --------------------------------------------------
    # Step 3: Run Position Trading Scanner
    # --------------------------------------------------
    print("\n" + "="*80)
    print("🔍 SCANNING S&P 500 FOR POSITION TRADES...")
    print("="*80 + "\n")

    # Load S&P 500 tickers
    tickers = pd.read_csv("data/sp500_constituents.csv")["Symbol"].tolist()

    # Run scanner as of today
    today = pd.Timestamp.today()
    signals = run_scan_as_of(today, tickers)

    print(f"\n✅ Scanner found {len(signals)} raw signals")

    # --------------------------------------------------
    # Step 4: Pre-buy Check (Format & Deduplicate)
    # --------------------------------------------------
    if signals:
        trade_ready = pre_buy_check(signals, benchmark=REGIME_INDEX, as_of_date=None)

        # Filter out positions we already hold
        if not trade_ready.empty:
            trade_ready = filter_trades_by_position(trade_ready, position_tracker, as_of_date=None)

        # Check position limits
        if not trade_ready.empty:
            current_total = position_tracker.get_position_count()
            available_slots = max(0, POSITION_MAX_TOTAL - current_total)

            # Further filter by per-strategy limits
            filtered_trades = []
            for _, trade in trade_ready.iterrows():
                strategy = trade["Strategy"]
                current_count = strategy_counts.get(strategy, 0)
                max_for_strategy = POSITION_MAX_PER_STRATEGY.get(strategy, 5)

                if current_count < max_for_strategy and len(filtered_trades) < available_slots:
                    filtered_trades.append(trade)
                    strategy_counts[strategy] = current_count + 1

            trade_ready = pd.DataFrame(filtered_trades) if filtered_trades else pd.DataFrame()
    else:
        trade_ready = pd.DataFrame()

    # --------------------------------------------------
    # Step 5: Display Results
    # --------------------------------------------------
    print("\n" + "="*80)
    print("📋 TRADE-READY SIGNALS")
    print("="*80)

    if not trade_ready.empty:
        print(f"\n✅ {len(trade_ready)} new position signal(s) ready:\n")

        # Calculate position sizing
        equity = POSITION_INITIAL_EQUITY  # From config (default $100k)
        risk_pct = POSITION_RISK_PER_TRADE_PCT / 100  # 2%
        risk_amount = equity * risk_pct

        print(f"💰 Account Equity: ${equity:,} | Risk per Trade: {risk_pct*100}% = ${risk_amount:,}\n")

        # Display format with position sizing
        for idx, trade in trade_ready.iterrows():
            ticker = trade['Ticker']
            entry = trade['Entry']
            stop = trade['StopLoss']
            target = trade['Target']

            # Calculate shares
            risk_per_share = entry - stop
            shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
            position_size = shares * entry

            print(f"   {idx+1}. {ticker:<6} | {trade['Strategy']:<35}")
            print(f"      🎯 BUY {shares} shares at ${entry:.2f} = ${position_size:,.0f} position")
            print(f"      📉 Stop: ${stop:.2f} (risk: ${risk_per_share:.2f}/share)")
            print(f"      📈 Target: ${target:.2f} | Max Days: {trade.get('MaxDays', 150)}")
            print(f"      Score: {trade.get('Score', 0):.1f} | Priority: {trade.get('Priority', 999)}")
            print()
    else:
        print("\n⚠️  No trade-ready signals today")
        print("   - All active strategies checked")
        print("   - Either no setups found or all slots filled\n")

    # --------------------------------------------------
    # Step 6: Send Email Alert (only if there is something actionable)
    # --------------------------------------------------
    has_new_trades = not trade_ready.empty
    has_action_signals = (
        len(action_signals.get('exits', [])) > 0
        or len(action_signals.get('partials', [])) > 0
        or len(action_signals.get('pyramids', [])) > 0
    )

    if has_new_trades or has_action_signals:
        print("="*80)
        print("📧 Sending Email Alert...")
        print("="*80 + "\n")

        send_email_alert(
            trade_df=trade_ready,
            all_signals=signals if signals else [],
            subject_prefix="📊 Position Trading Scan",
            position_tracker=position_tracker,
            action_signals=action_signals
        )

        print("✅ Email sent successfully!")
    else:
        print("📭 No actionable signals — email skipped")

    print("\n" + "="*80)
    print("✨ Scan Complete")
    print("="*80)
