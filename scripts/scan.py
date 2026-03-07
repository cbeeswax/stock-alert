#!/usr/bin/env python
"""
Position Trading Scanner Entry Point

Scans S&P 500 stocks for position trading opportunities using three strategies:
- RelativeStrength_Ranker_Position
- High52_Position  
- BigBase_Breakout_Position

Monitors open positions for exit signals and manages position sizing with risk limits.

Usage:
    python scripts/scan.py                    # Run full scan
    python scripts/scan.py --no-email         # Skip email alerts
    python scripts/scan.py --regime-only      # Only check market regime
    python scripts/scan.py --monitor-only     # Only monitor existing positions
"""

import sys
import argparse
import pandas as pd
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.scanning.scanner import run_scan_as_of
from src.scanning.validator import pre_buy_check
from src.notifications.email import send_email_alert
from src.position_management.tracker import PositionTracker, filter_trades_by_position
from src.position_management.monitor import monitor_positions
from src.data.market import get_historical_data
from src.config.settings import (
    POSITION_MAX_TOTAL,
    POSITION_MAX_PER_STRATEGY,
    POSITION_RISK_PER_TRADE_PCT,
    POSITION_INITIAL_EQUITY,
    REGIME_INDEX,
    UNIVERSAL_QQQ_BULL_MA,
)


def check_market_regime():
    """
    Check if market is in bullish regime (Index > MA).
    
    Returns:
        bool: True if bullish, False otherwise
    """
    try:
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
    except Exception as e:
        print(f"⚠️  Error checking market regime: {e}")
        print("   Assuming bullish regime to continue scanning.")
        return True


def display_header():
    """Display scan header."""
    print("=" * 80)
    print("🚀 LIVE POSITION TRADING SCANNER")
    print("=" * 80)
    print(f"📅 Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"⚠️  Risk per trade: {POSITION_RISK_PER_TRADE_PCT}%")
    print(f"📊 Max positions: {POSITION_MAX_TOTAL} total")
    print(f"📊 Active strategies: RS_Ranker (10), High52 (6), BigBase (4)")
    print("=" * 80 + "\n")


def monitor_open_positions(position_tracker: PositionTracker) -> dict:
    """
    Monitor open positions for exit and action signals.
    
    Args:
        position_tracker: PositionTracker instance
        
    Returns:
        dict: Action signals (exits, partials, pyramids, warnings)
    """
    print(f"\n📊 Current Open Positions: {position_tracker.get_position_count()}/{POSITION_MAX_TOTAL}")

    action_signals = {'exits': [], 'partials': [], 'pyramids': [], 'warnings': []}

    if position_tracker.get_position_count() == 0:
        print("   ✅ No open positions")
        return action_signals

    print(position_tracker)
    
    print("\n" + "=" * 80)
    print("🔍 MONITORING POSITIONS FOR EXIT/ACTION SIGNALS...")
    print("=" * 80)

    action_signals = monitor_positions(position_tracker)

    # Display action signals
    total_actions = (
        len(action_signals['exits']) +
        len(action_signals['partials']) +
        len(action_signals['pyramids'])
    )

    if total_actions > 0:
        print(f"\n⚠️  {total_actions} ACTION(S) REQUIRED:\n")

        # Exits (highest priority)
        if action_signals['exits']:
            print(f"🚨 EXITS ({len(action_signals['exits'])}):")
            for exit_sig in action_signals['exits']:
                print(f"   {exit_sig['ticker']}: {exit_sig['type']} - {exit_sig['reason']}")
                print(f"   → {exit_sig['action']}\n")

        # Partial profits
        if action_signals['partials']:
            print(f"💰 PARTIAL PROFITS ({len(action_signals['partials'])}):")
            for partial in action_signals['partials']:
                print(f"   {partial['ticker']}: {partial['reason']}")
                print(f"   → {partial['action']}\n")

        # Pyramid opportunities
        if action_signals['pyramids']:
            print(f"📈 PYRAMID OPPORTUNITIES ({len(action_signals['pyramids'])}):")
            for pyramid in action_signals['pyramids']:
                print(f"   {pyramid['ticker']}: {pyramid['reason']}")
                print(f"   → {pyramid['action']}\n")
    else:
        print("\n✅ No exit/action signals - all positions healthy")

    # Display warnings
    if action_signals['warnings']:
        print(f"\n⚠️  Warnings ({len(action_signals['warnings'])}):")
        for warning in action_signals['warnings']:
            print(f"   {warning.get('message', warning.get('ticker', 'Unknown'))}")

    return action_signals


def get_strategy_counts(position_tracker: PositionTracker) -> dict:
    """Get position count by strategy."""
    strategy_counts = {}
    for ticker, pos in position_tracker.get_all_positions().items():
        strategy = pos.get('strategy', 'Unknown')
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
    return strategy_counts


def display_strategy_counts(strategy_counts: dict):
    """Display positions grouped by strategy."""
    if not strategy_counts:
        return
    
    print("\n📊 Positions by Strategy:")
    for strategy, count in strategy_counts.items():
        max_for_strategy = POSITION_MAX_PER_STRATEGY.get(strategy, 5)
        print(f"   {strategy}: {count}/{max_for_strategy}")


def run_scanner(
    position_tracker: PositionTracker,
    is_bullish: bool,
    strategy_counts: dict
) -> pd.DataFrame:
    """
    Run the position trading scanner.
    
    Args:
        position_tracker: PositionTracker instance
        is_bullish: Whether market is in bullish regime
        strategy_counts: Current positions by strategy
        
    Returns:
        DataFrame: Trade-ready signals
    """
    print("\n" + "=" * 80)
    print("🔍 SCANNING S&P 500 FOR POSITION TRADES...")
    print("=" * 80 + "\n")

    # Load S&P 500 tickers
    sp500_file = project_root / "data" / "sp500_constituents.csv"
    if not sp500_file.exists():
        print(f"⚠️  Could not find S&P 500 constituents file at {sp500_file}")
        return pd.DataFrame()

    tickers = pd.read_csv(sp500_file)["Symbol"].tolist()

    # Run scanner
    today = pd.Timestamp.today()
    signals = run_scan_as_of(today, tickers)

    print(f"\n✅ Scanner found {len(signals)} raw signals")

    # Pre-buy check and filtering
    trade_ready = pd.DataFrame()
    if signals:
        trade_ready = pre_buy_check(signals, benchmark=REGIME_INDEX, as_of_date=None)

        # Filter positions we already hold
        if not trade_ready.empty:
            trade_ready = filter_trades_by_position(
                trade_ready, position_tracker, as_of_date=None
            )

        # Check position limits
        if not trade_ready.empty:
            current_total = position_tracker.get_position_count()
            available_slots = max(0, POSITION_MAX_TOTAL - current_total)

            # Filter by per-strategy limits
            filtered_trades = []
            for _, trade in trade_ready.iterrows():
                strategy = trade["Strategy"]
                current_count = strategy_counts.get(strategy, 0)
                max_for_strategy = POSITION_MAX_PER_STRATEGY.get(strategy, 5)

                if current_count < max_for_strategy and len(filtered_trades) < available_slots:
                    filtered_trades.append(trade)
                    strategy_counts[strategy] = current_count + 1

            trade_ready = pd.DataFrame(filtered_trades) if filtered_trades else pd.DataFrame()

    return trade_ready


def display_trade_ready_signals(trade_ready: pd.DataFrame):
    """Display trade-ready signals with position sizing."""
    print("\n" + "=" * 80)
    print("📋 TRADE-READY SIGNALS")
    print("=" * 80)

    if not trade_ready.empty:
        print(f"\n✅ {len(trade_ready)} new position signal(s) ready:\n")

        # Calculate position sizing
        equity = POSITION_INITIAL_EQUITY
        risk_pct = POSITION_RISK_PER_TRADE_PCT / 100
        risk_amount = equity * risk_pct

        print(f"💰 Account Equity: ${equity:,} | Risk per Trade: {risk_pct*100}% = ${risk_amount:,}\n")

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


def record_new_trades(trade_ready: pd.DataFrame, position_tracker: PositionTracker):
    """Auto-record new trades to position tracker."""
    if trade_ready.empty:
        return

    print("=" * 80)
    print("💾 Auto-Recording Trades to Position Tracker...")
    print("=" * 80 + "\n")
    
    for _, trade in trade_ready.iterrows():
        ticker = trade['Ticker']
        entry_price = trade['Entry']
        strategy = trade['Strategy']
        stop_loss = trade['StopLoss']
        target = trade['Target']
        
        success = position_tracker.add_position(
            ticker=ticker,
            entry_date=datetime.now(),
            entry_price=entry_price,
            strategy=strategy,
            stop_loss=stop_loss,
            target=target
        )
        
        if success:
            print(f"✅ {ticker} @ ${entry_price:.2f} ({strategy})")
        else:
            print(f"⚠️  {ticker} - already recorded or error")
    
    print()


def send_alerts(
    trade_ready: pd.DataFrame,
    action_signals: dict,
    position_tracker: PositionTracker,
    send_email: bool = True
):
    """Send email alerts if there are actionable signals."""
    has_new_trades = not trade_ready.empty
    has_action_signals = (
        len(action_signals.get('exits', [])) > 0
        or len(action_signals.get('partials', [])) > 0
        or len(action_signals.get('pyramids', [])) > 0
    )

    if (has_new_trades or has_action_signals) and send_email:
        print("=" * 80)
        print("📧 Sending Email Alert...")
        print("=" * 80 + "\n")

        send_email_alert(
            trade_df=trade_ready,
            all_signals=[] if trade_ready.empty else trade_ready.to_dict('records'),
            subject_prefix="📊 Position Trading Scan",
            position_tracker=position_tracker,
            action_signals=action_signals
        )
    elif not send_email:
        print("📭 Email alerts disabled (--no-email)")
    else:
        print("📭 No actionable signals — email skipped")


def main():
    """Main entry point for scanner."""
    parser = argparse.ArgumentParser(
        description="Live Position Trading Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/scan.py                    # Run full scan
  python scripts/scan.py --no-email         # Skip email alerts
  python scripts/scan.py --regime-only      # Only check market regime
  python scripts/scan.py --monitor-only     # Only monitor existing positions
        """
    )
    
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip email alerts"
    )
    parser.add_argument(
        "--regime-only",
        action="store_true",
        help="Only check market regime (don't scan)"
    )
    parser.add_argument(
        "--monitor-only",
        action="store_true",
        help="Only monitor existing positions (don't scan)"
    )
    parser.add_argument(
        "--positions-file",
        default="data/open_positions.json",
        help="Path to positions file (default: data/open_positions.json)"
    )
    
    args = parser.parse_args()
    
    # Display header
    display_header()
    
    # Initialize position tracker
    position_tracker = PositionTracker(mode="live", file=args.positions_file)
    
    # Step 1: Check Market Regime
    print("\n" + "=" * 80)
    print("🏛️ STEP 1: CHECK MARKET REGIME")
    print("=" * 80 + "\n")
    
    is_bullish = check_market_regime()
    
    if not is_bullish:
        print("\n⚠️  BEARISH MARKET - Bull-only strategies will be skipped by scanner")
    
    # Early exit if only checking regime
    if args.regime_only:
        print("\n" + "=" * 80)
        print("✨ Regime Check Complete")
        print("=" * 80)
        return
    
    # Step 2: Monitor Open Positions
    print("\n" + "=" * 80)
    print("🏛️ STEP 2: MONITOR EXISTING POSITIONS")
    print("=" * 80)
    
    action_signals = monitor_open_positions(position_tracker)
    strategy_counts = get_strategy_counts(position_tracker)
    display_strategy_counts(strategy_counts)
    
    # Early exit if only monitoring
    if args.monitor_only:
        print("\n" + "=" * 80)
        print("✨ Monitoring Complete")
        print("=" * 80)
        return
    
    # Step 3: Run Scanner
    print("\n" + "=" * 80)
    print("🏛️ STEP 3: RUN POSITION SCANNER")
    print("=" * 80)
    
    trade_ready = run_scanner(position_tracker, is_bullish, strategy_counts)
    
    # Step 4: Display Results
    display_trade_ready_signals(trade_ready)
    
    # Step 5: Record Trades
    record_new_trades(trade_ready, position_tracker)
    
    # Step 6: Send Alerts
    send_alerts(trade_ready, action_signals, position_tracker, not args.no_email)
    
    # Finish
    print("\n" + "=" * 80)
    print("✨ Scan Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
