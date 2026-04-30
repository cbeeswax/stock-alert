import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.daytrading.intraday import get_latest_regular_session
from src.daytrading.intraday import download_intraday_batch
from src.daytrading.morning_spy import MorningSignalConfig, build_morning_spy_recommendation
from src.daytrading.settings import load_daytrading_settings
from src.daytrading.options import (
    choose_preferred_expiry,
    download_option_chain,
    fetch_option_expiries,
    select_option_contract,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a morning SPY options recommendation from 5-minute underlying data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/morning_spy_signal.py
  python scripts/morning_spy_signal.py --evaluation-time 11:00 --json
  python scripts/morning_spy_signal.py --period 5d --interval 5m --include-prepost
        """,
    )
    parser.add_argument("--period", help="Override intraday period from daytrading settings")
    parser.add_argument("--interval", help="Override intraday interval from daytrading settings")
    parser.add_argument("--evaluation-time", help="Override decision cutoff from daytrading settings")
    parser.add_argument("--include-prepost", action="store_true", help="Include pre/post-market bars in the Yahoo download")
    parser.add_argument("--json", action="store_true", help="Print output as JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_daytrading_settings()
    config = MorningSignalConfig.from_settings(settings)
    if args.evaluation_time:
        config = MorningSignalConfig(
            evaluation_time=args.evaluation_time,
            opening_range_bars=config.opening_range_bars,
            min_bars_before_signal=config.min_bars_before_signal,
            opening_range_break_buffer_pct=config.opening_range_break_buffer_pct,
            min_spy_move_from_open_pct=config.min_spy_move_from_open_pct,
            min_breadth_above_open_pct=config.min_breadth_above_open_pct,
            min_breadth_above_vwap_pct=config.min_breadth_above_vwap_pct,
            min_heavyweight_confirmation_pct=config.min_heavyweight_confirmation_pct,
            premium_stop_loss_pct=config.premium_stop_loss_pct,
            premium_target_pct=config.premium_target_pct,
            hard_exit_time=config.hard_exit_time,
            breadth_symbols=config.breadth_symbols.copy(),
            heavyweight_symbols=config.heavyweight_symbols.copy(),
        )
    symbols = [settings.underlying_symbol, *config.breadth_symbols]

    intraday_data = download_intraday_batch(
        tickers=symbols,
        period=args.period or settings.intraday_period,
        interval=args.interval or settings.intraday_interval,
        include_prepost=args.include_prepost or settings.include_prepost,
    )
    expiries = fetch_option_expiries(settings.underlying_symbol)
    trade_date = get_latest_regular_session(intraday_data[settings.underlying_symbol]).index[-1].date()
    preferred_expiry = choose_preferred_expiry(
        trade_date=trade_date,
        expiries=expiries,
        min_days_to_expiry=settings.min_days_to_expiry,
        max_days_to_expiry=settings.max_days_to_expiry,
    )
    option_chain = download_option_chain(settings.underlying_symbol, preferred_expiry)
    recommendation = build_morning_spy_recommendation(
        intraday_data=intraday_data,
        config=config,
        settings=settings,
        option_chain=option_chain,
        expiries=expiries,
    )

    if recommendation["Signal"] != "NEUTRAL":
        option_plan = recommendation["OptionPlan"]
        chain = download_option_chain(
            settings.underlying_symbol,
            expiry=date.fromisoformat(str(option_plan["Expiry"])),
        )
        selected_contract = select_option_contract(
            option_chain=chain,
            option_side=option_plan["OptionSide"],
            target_strike=float(option_plan["Strike"]),
            underlying_price=float(recommendation["UnderlyingPrice"]),
            target_delta_abs=settings.target_delta_abs,
            delta_tolerance=settings.delta_tolerance,
            min_volume=settings.min_volume,
            min_open_interest=settings.min_open_interest,
            max_spread_pct=settings.max_spread_pct,
        )
        recommendation["SelectedContract"] = selected_contract

    if args.json:
        print(json.dumps(recommendation, indent=2))
    else:
        print(f"Signal: {recommendation['Signal']}")
        print(f"As Of: {recommendation['AsOf']}")
        print(f"Mode: {recommendation['TradingMode']}")
        print(f"Max Trades Per Day: {recommendation['MaxTradesPerDay']}")
        print(f"Trigger: {recommendation['Trigger']}")
        print(f"VWAP State: {recommendation['VWAPState']}")
        print(f"Liquidity Sweep: {recommendation['LiquiditySweep']}")
        print(f"Order Flow Proxy: {recommendation['OrderFlowProxy']} ({recommendation['OrderFlowScore']})")
        print(f"Underlying Price: {recommendation['UnderlyingPrice']:.2f}")
        print(
            "Breadth Above Open / Above VWAP: "
            f"{recommendation['BreadthAboveOpenPct']:.0%} / {recommendation['BreadthAboveVWAPPct']:.0%}"
        )
        print(f"Option Chain Bias: {recommendation['OptionChainBias']}")
        if recommendation["Signal"] == "NEUTRAL" and recommendation["NoTradeReasons"]:
            print("No Trade Reasons: " + "; ".join(recommendation["NoTradeReasons"]))
        if recommendation["Signal"] != "NEUTRAL":
            option_plan = recommendation["OptionPlan"]
            print(
                f"Option Plan: {option_plan['OptionSide']} {option_plan['Strike']} "
                f"{option_plan['Expiry']} | stop {option_plan['PremiumStopLossPct']:.0%} "
                f"| target {option_plan['PremiumTargetPct']:.0%} | hard exit {option_plan['HardExitTime']} ET"
            )
            selected_contract = recommendation["SelectedContract"]
            print(
                f"Selected Contract: {selected_contract['ContractSymbol']} "
                f"(bid {selected_contract['Bid']:.2f} / ask {selected_contract['Ask']:.2f})"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
