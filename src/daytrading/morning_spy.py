from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Mapping

import pandas as pd

from src.daytrading.intraday import add_session_vwap, get_latest_regular_session
from src.daytrading.settings import DayTradingSettings, load_daytrading_settings
from src.daytrading.options import build_spy_option_plan, summarize_option_positioning

DEFAULT_HEAVYWEIGHT_SYMBOLS: list[str] = []
DEFAULT_BREADTH_SYMBOLS: list[str] = []


@dataclass(frozen=True)
class MorningSignalConfig:
    evaluation_time: str = "11:00"
    opening_range_bars: int = 2
    min_bars_before_signal: int = 3
    opening_range_break_buffer_pct: float = 0.0005
    liquidity_sweep_min_excursion_pct: float = 0.0005
    min_spy_move_from_open_pct: float = 0.001
    min_breadth_above_open_pct: float = 0.60
    min_breadth_above_vwap_pct: float = 0.60
    min_breadth_edge_pct: float = 0.20
    min_heavyweight_confirmation_pct: float = 0.67
    vwap_behavior_lookback_bars: int = 3
    near_vwap_no_trade_pct: float = 0.001
    order_flow_lookback_bars: int = 3
    order_flow_min_volume_expansion: float = 1.15
    order_flow_strong_close_threshold: float = 0.70
    order_flow_weak_close_threshold: float = 0.30
    premium_stop_loss_pct: float = 0.35
    premium_target_pct: float = 0.60
    hard_exit_time: str = "11:30"
    bullish_vwap_states: list[str] = field(default_factory=lambda: ["hold_above", "reclaim"])
    bearish_vwap_states: list[str] = field(default_factory=lambda: ["hold_below", "reject"])
    breadth_symbols: list[str] = field(default_factory=lambda: DEFAULT_BREADTH_SYMBOLS.copy())
    heavyweight_symbols: list[str] = field(default_factory=lambda: DEFAULT_HEAVYWEIGHT_SYMBOLS.copy())

    @classmethod
    def from_settings(cls, settings: DayTradingSettings) -> "MorningSignalConfig":
        return cls(
            evaluation_time=settings.evaluation_time,
            opening_range_bars=settings.opening_range_bars,
            min_bars_before_signal=settings.min_bars_before_signal,
            opening_range_break_buffer_pct=settings.opening_range_break_buffer_pct,
            liquidity_sweep_min_excursion_pct=settings.liquidity_sweep_min_excursion_pct,
            min_spy_move_from_open_pct=settings.min_underlying_move_from_open_pct,
            min_breadth_above_open_pct=settings.min_breadth_above_open_pct,
            min_breadth_above_vwap_pct=settings.min_breadth_above_vwap_pct,
            min_breadth_edge_pct=settings.min_breadth_edge_pct,
            min_heavyweight_confirmation_pct=settings.min_heavyweight_confirmation_pct,
            vwap_behavior_lookback_bars=settings.vwap_behavior_lookback_bars,
            near_vwap_no_trade_pct=settings.near_vwap_no_trade_pct,
            order_flow_lookback_bars=settings.order_flow_lookback_bars,
            order_flow_min_volume_expansion=settings.order_flow_min_volume_expansion,
            order_flow_strong_close_threshold=settings.order_flow_strong_close_threshold,
            order_flow_weak_close_threshold=settings.order_flow_weak_close_threshold,
            premium_stop_loss_pct=settings.premium_stop_loss_pct,
            premium_target_pct=settings.premium_target_pct,
            hard_exit_time=settings.hard_exit_time,
            bullish_vwap_states=settings.bullish_vwap_states.copy(),
            bearish_vwap_states=settings.bearish_vwap_states.copy(),
            breadth_symbols=settings.breadth_symbols.copy(),
            heavyweight_symbols=settings.heavyweight_symbols.copy(),
        )


def generate_morning_spy_signal(
    intraday_data: Mapping[str, pd.DataFrame],
    config: MorningSignalConfig | None = None,
    settings: DayTradingSettings | None = None,
    option_chain: pd.DataFrame | None = None,
) -> dict[str, object]:
    runtime_settings = settings or load_daytrading_settings()
    signal_config = config or MorningSignalConfig.from_settings(runtime_settings)
    if not signal_config.breadth_symbols or not signal_config.heavyweight_symbols:
        signal_config = MorningSignalConfig(
            evaluation_time=signal_config.evaluation_time,
            opening_range_bars=signal_config.opening_range_bars,
            min_bars_before_signal=signal_config.min_bars_before_signal,
            opening_range_break_buffer_pct=signal_config.opening_range_break_buffer_pct,
            liquidity_sweep_min_excursion_pct=signal_config.liquidity_sweep_min_excursion_pct,
            min_spy_move_from_open_pct=signal_config.min_spy_move_from_open_pct,
            min_breadth_above_open_pct=signal_config.min_breadth_above_open_pct,
            min_breadth_above_vwap_pct=signal_config.min_breadth_above_vwap_pct,
            min_breadth_edge_pct=signal_config.min_breadth_edge_pct,
            min_heavyweight_confirmation_pct=signal_config.min_heavyweight_confirmation_pct,
            vwap_behavior_lookback_bars=signal_config.vwap_behavior_lookback_bars,
            near_vwap_no_trade_pct=signal_config.near_vwap_no_trade_pct,
            order_flow_lookback_bars=signal_config.order_flow_lookback_bars,
            order_flow_min_volume_expansion=signal_config.order_flow_min_volume_expansion,
            order_flow_strong_close_threshold=signal_config.order_flow_strong_close_threshold,
            order_flow_weak_close_threshold=signal_config.order_flow_weak_close_threshold,
            premium_stop_loss_pct=signal_config.premium_stop_loss_pct,
            premium_target_pct=signal_config.premium_target_pct,
            hard_exit_time=signal_config.hard_exit_time,
            bullish_vwap_states=signal_config.bullish_vwap_states or runtime_settings.bullish_vwap_states.copy(),
            bearish_vwap_states=signal_config.bearish_vwap_states or runtime_settings.bearish_vwap_states.copy(),
            breadth_symbols=signal_config.breadth_symbols or runtime_settings.breadth_symbols.copy(),
            heavyweight_symbols=signal_config.heavyweight_symbols or runtime_settings.heavyweight_symbols.copy(),
        )
    required_symbols = {
        runtime_settings.underlying_symbol,
        *signal_config.breadth_symbols,
        *signal_config.heavyweight_symbols,
    }
    missing = sorted(symbol for symbol in required_symbols if symbol not in intraday_data)
    if missing:
        raise ValueError(f"Missing intraday data for symbols: {', '.join(missing)}")

    spy_snapshot = _symbol_snapshot(
        intraday_data=intraday_data[runtime_settings.underlying_symbol],
        evaluation_time=signal_config.evaluation_time,
        opening_range_bars=signal_config.opening_range_bars,
        min_bars_before_signal=signal_config.min_bars_before_signal,
        opening_range_break_buffer_pct=signal_config.opening_range_break_buffer_pct,
        liquidity_sweep_min_excursion_pct=signal_config.liquidity_sweep_min_excursion_pct,
        vwap_behavior_lookback_bars=signal_config.vwap_behavior_lookback_bars,
        near_vwap_no_trade_pct=signal_config.near_vwap_no_trade_pct,
        order_flow_lookback_bars=signal_config.order_flow_lookback_bars,
        order_flow_min_volume_expansion=signal_config.order_flow_min_volume_expansion,
        order_flow_strong_close_threshold=signal_config.order_flow_strong_close_threshold,
        order_flow_weak_close_threshold=signal_config.order_flow_weak_close_threshold,
    )
    breadth_snapshots = {
        symbol: _symbol_snapshot(
            intraday_data=intraday_data[symbol],
            evaluation_time=signal_config.evaluation_time,
            opening_range_bars=signal_config.opening_range_bars,
            min_bars_before_signal=signal_config.min_bars_before_signal,
            opening_range_break_buffer_pct=signal_config.opening_range_break_buffer_pct,
            liquidity_sweep_min_excursion_pct=signal_config.liquidity_sweep_min_excursion_pct,
            vwap_behavior_lookback_bars=signal_config.vwap_behavior_lookback_bars,
            near_vwap_no_trade_pct=signal_config.near_vwap_no_trade_pct,
            order_flow_lookback_bars=signal_config.order_flow_lookback_bars,
            order_flow_min_volume_expansion=signal_config.order_flow_min_volume_expansion,
            order_flow_strong_close_threshold=signal_config.order_flow_strong_close_threshold,
            order_flow_weak_close_threshold=signal_config.order_flow_weak_close_threshold,
        )
        for symbol in signal_config.breadth_symbols
    }
    heavyweight_snapshots = {
        symbol: breadth_snapshots[symbol]
        for symbol in signal_config.heavyweight_symbols
    }

    breadth_total = len(breadth_snapshots)
    above_open_count = sum(1 for snapshot in breadth_snapshots.values() if snapshot["AboveOpen"])
    below_open_count = sum(1 for snapshot in breadth_snapshots.values() if snapshot["BelowOpen"])
    above_vwap_count = sum(1 for snapshot in breadth_snapshots.values() if snapshot["AboveVWAP"])
    below_vwap_count = sum(1 for snapshot in breadth_snapshots.values() if snapshot["BelowVWAP"])

    heavyweight_total = len(heavyweight_snapshots)
    heavyweight_bullish_count = sum(
        1 for snapshot in heavyweight_snapshots.values()
        if snapshot["AboveOpen"] and snapshot["AboveVWAP"]
    )
    heavyweight_bearish_count = sum(
        1 for snapshot in heavyweight_snapshots.values()
        if snapshot["BelowOpen"] and snapshot["BelowVWAP"]
    )

    breadth_above_open_pct = above_open_count / breadth_total
    breadth_below_open_pct = below_open_count / breadth_total
    breadth_above_vwap_pct = above_vwap_count / breadth_total
    breadth_below_vwap_pct = below_vwap_count / breadth_total
    breadth_open_edge_pct = breadth_above_open_pct - breadth_below_open_pct
    breadth_vwap_edge_pct = breadth_above_vwap_pct - breadth_below_vwap_pct
    heavyweight_bullish_pct = heavyweight_bullish_count / heavyweight_total
    heavyweight_bearish_pct = heavyweight_bearish_count / heavyweight_total

    long_setup = (
        spy_snapshot["AboveOpen"]
        and spy_snapshot["AboveVWAP"]
        and spy_snapshot["BreakoutAboveRange"]
        and spy_snapshot["MoveFromOpenPct"] >= signal_config.min_spy_move_from_open_pct
        and breadth_above_open_pct >= signal_config.min_breadth_above_open_pct
        and breadth_above_vwap_pct >= signal_config.min_breadth_above_vwap_pct
        and breadth_open_edge_pct >= signal_config.min_breadth_edge_pct
        and breadth_vwap_edge_pct >= signal_config.min_breadth_edge_pct
        and heavyweight_bullish_pct >= signal_config.min_heavyweight_confirmation_pct
        and spy_snapshot["VWAPState"] in signal_config.bullish_vwap_states
        and not spy_snapshot["NearVWAPNoTradeZone"]
    )
    short_setup = (
        spy_snapshot["BelowOpen"]
        and spy_snapshot["BelowVWAP"]
        and spy_snapshot["BreakdownBelowRange"]
        and abs(spy_snapshot["MoveFromOpenPct"]) >= signal_config.min_spy_move_from_open_pct
        and breadth_below_open_pct >= signal_config.min_breadth_above_open_pct
        and breadth_below_vwap_pct >= signal_config.min_breadth_above_vwap_pct
        and (-breadth_open_edge_pct) >= signal_config.min_breadth_edge_pct
        and (-breadth_vwap_edge_pct) >= signal_config.min_breadth_edge_pct
        and heavyweight_bearish_pct >= signal_config.min_heavyweight_confirmation_pct
        and spy_snapshot["VWAPState"] in signal_config.bearish_vwap_states
        and not spy_snapshot["NearVWAPNoTradeZone"]
    )

    base_direction = "LONG" if long_setup else "SHORT" if short_setup else "NEUTRAL"
    no_trade_reasons: list[str] = []
    positioning_summary = None
    positioning_bias = "NEUTRAL"
    if base_direction == "NEUTRAL":
        if spy_snapshot["NearVWAPNoTradeZone"]:
            no_trade_reasons.append("Underlying is too close to VWAP")
        if spy_snapshot["VWAPState"] not in (signal_config.bullish_vwap_states + signal_config.bearish_vwap_states):
            no_trade_reasons.append("VWAP behavior is choppy")
    elif option_chain is not None:
        positioning_summary = summarize_option_positioning(
            option_chain=option_chain,
            underlying_price=float(spy_snapshot["Close"]),
            near_money_strike_window_pct=runtime_settings.near_money_strike_window_pct,
            bullish_put_call_oi_ratio_min=runtime_settings.bullish_put_call_oi_ratio_min,
            bearish_put_call_oi_ratio_max=runtime_settings.bearish_put_call_oi_ratio_max,
        )
        positioning_bias = str(positioning_summary["Bias"])
        if runtime_settings.require_positioning_confirmation and positioning_bias == "NEUTRAL":
            no_trade_reasons.append("Option-chain positioning is in the no-trade zone")
        elif base_direction != "NEUTRAL" and positioning_bias not in {base_direction, "NEUTRAL"}:
            no_trade_reasons.append("Price action diverges from option-chain positioning")
    elif runtime_settings.require_positioning_confirmation:
        no_trade_reasons.append("Option-chain confirmation is required but unavailable")

    direction = base_direction if base_direction != "NEUTRAL" and not no_trade_reasons else "NEUTRAL"
    if direction == "LONG":
        trigger = f"{spy_snapshot['VWAPState']} opening range breakout"
    elif direction == "SHORT":
        trigger = f"{spy_snapshot['VWAPState']} opening range breakdown"
    else:
        trigger = "No aligned trigger"
    underlying_stop = (
        spy_snapshot["OpeningRangeLow"]
        if direction == "LONG" else spy_snapshot["OpeningRangeHigh"]
        if direction == "SHORT" else None
    )

    return {
        "Signal": direction,
        "BaseSignal": base_direction,
        "Trigger": trigger,
        "AsOf": spy_snapshot["AsOf"],
        "Underlying": runtime_settings.underlying_symbol,
        "UnderlyingPrice": spy_snapshot["Close"],
        "UnderlyingOpen": spy_snapshot["Open"],
        "UnderlyingVWAP": spy_snapshot["VWAP"],
        "MoveFromOpenPct": spy_snapshot["MoveFromOpenPct"],
        "OpeningRangeHigh": spy_snapshot["OpeningRangeHigh"],
        "OpeningRangeLow": spy_snapshot["OpeningRangeLow"],
        "UnderlyingStop": underlying_stop,
        "VWAPState": spy_snapshot["VWAPState"],
        "NearVWAPNoTradeZone": spy_snapshot["NearVWAPNoTradeZone"],
        "LiquiditySweep": spy_snapshot["LiquiditySweep"],
        "LiquiditySweepLevel": spy_snapshot["LiquiditySweepLevel"],
        "LiquiditySweepPrice": spy_snapshot["LiquiditySweepPrice"],
        "OrderFlowProxy": spy_snapshot["OrderFlowProxy"],
        "OrderFlowScore": spy_snapshot["OrderFlowScore"],
        "OrderFlowComponents": spy_snapshot["OrderFlowComponents"],
        "BreadthAboveOpenPct": breadth_above_open_pct,
        "BreadthBelowOpenPct": breadth_below_open_pct,
        "BreadthAboveVWAPPct": breadth_above_vwap_pct,
        "BreadthBelowVWAPPct": breadth_below_vwap_pct,
        "BreadthOpenEdgePct": breadth_open_edge_pct,
        "BreadthVWAPEdgePct": breadth_vwap_edge_pct,
        "HeavyweightBullishPct": heavyweight_bullish_pct,
        "HeavyweightBearishPct": heavyweight_bearish_pct,
        "TradingMode": runtime_settings.mode,
        "MaxTradesPerDay": runtime_settings.max_trades_per_day,
        "NoTradeOnNeutral": runtime_settings.no_trade_on_neutral,
        "NoTradeReasons": no_trade_reasons,
        "OptionChainBias": positioning_bias,
        "OptionChainConfirmation": positioning_summary,
        "PositioningDivergence": (
            base_direction != "NEUTRAL"
            and positioning_bias not in {"NEUTRAL", base_direction}
        ),
        "HeavyweightConfirmations": {
            symbol: {
                "AboveOpen": snapshot["AboveOpen"],
                "AboveVWAP": snapshot["AboveVWAP"],
                "BelowOpen": snapshot["BelowOpen"],
                "BelowVWAP": snapshot["BelowVWAP"],
            }
            for symbol, snapshot in heavyweight_snapshots.items()
        },
    }


def build_morning_spy_recommendation(
    intraday_data: Mapping[str, pd.DataFrame],
    config: MorningSignalConfig | None = None,
    settings: DayTradingSettings | None = None,
    option_chain: pd.DataFrame | None = None,
    expiries: list | None = None,
    strikes: list[float] | None = None,
) -> dict[str, object]:
    runtime_settings = settings or load_daytrading_settings()
    signal = generate_morning_spy_signal(
        intraday_data=intraday_data,
        config=config,
        settings=runtime_settings,
        option_chain=option_chain,
    )
    signal_config = config or MorningSignalConfig.from_settings(runtime_settings)
    if signal["Signal"] == "NEUTRAL":
        return signal

    option_plan = build_spy_option_plan(
        symbol=str(signal["Underlying"]),
        direction=str(signal["Signal"]),
        underlying_price=float(signal["UnderlyingPrice"]),
        signal_time=pd.Timestamp(signal["AsOf"]).to_pydatetime(),
        expiries=expiries,
        strikes=strikes,
        target_moneyness=runtime_settings.target_moneyness,
        target_delta_abs=runtime_settings.target_delta_abs,
        min_days_to_expiry=runtime_settings.min_days_to_expiry,
        max_days_to_expiry=runtime_settings.max_days_to_expiry,
        premium_stop_loss_pct=signal_config.premium_stop_loss_pct,
        premium_target_pct=signal_config.premium_target_pct,
        hard_exit_time=signal_config.hard_exit_time,
    )
    return {
        **signal,
        "EntryWindow": f"{signal_config.evaluation_time} ET",
        "OptionPlan": option_plan,
    }




def _symbol_snapshot(
    intraday_data: pd.DataFrame,
    evaluation_time: str,
    opening_range_bars: int,
    min_bars_before_signal: int,
    opening_range_break_buffer_pct: float,
    liquidity_sweep_min_excursion_pct: float,
    vwap_behavior_lookback_bars: int,
    near_vwap_no_trade_pct: float,
    order_flow_lookback_bars: int,
    order_flow_min_volume_expansion: float,
    order_flow_strong_close_threshold: float,
    order_flow_weak_close_threshold: float,
) -> dict[str, object]:
    session = get_latest_regular_session(intraday_data)
    if session.empty:
        raise ValueError("No regular-session intraday bars available")

    session = add_session_vwap(session)
    cutoff = time.fromisoformat(evaluation_time)
    intraday_window = session[session.index.time <= cutoff].copy()
    min_required_bars = max(opening_range_bars, min_bars_before_signal, 1)
    if len(intraday_window) < min_required_bars:
        raise ValueError(f"Not enough bars available before {evaluation_time}")

    reference_bar = intraday_window.iloc[-1]
    session_open = float(session.iloc[0]["Open"])
    range_window = intraday_window.iloc[:opening_range_bars]
    opening_range_high = float(range_window["High"].max())
    opening_range_low = float(range_window["Low"].min())
    buffer = opening_range_high * opening_range_break_buffer_pct
    move_from_open_pct = (float(reference_bar["Close"]) - session_open) / session_open
    recent_bars = intraday_window.tail(max(vwap_behavior_lookback_bars, 1))
    vwap_state = _classify_vwap_behavior(recent_bars)
    vwap_distance_pct = (float(reference_bar["Close"]) - float(reference_bar["VWAP"])) / float(reference_bar["VWAP"])
    sweep = _detect_liquidity_sweep(
        intraday_window=intraday_window,
        opening_range_high=opening_range_high,
        opening_range_low=opening_range_low,
        min_excursion_pct=liquidity_sweep_min_excursion_pct,
    )
    order_flow = _summarize_order_flow(
        intraday_window=intraday_window,
        vwap_state=vwap_state,
        lookback_bars=order_flow_lookback_bars,
        min_volume_expansion=order_flow_min_volume_expansion,
        strong_close_threshold=order_flow_strong_close_threshold,
        weak_close_threshold=order_flow_weak_close_threshold,
    )

    return {
        "AsOf": intraday_window.index[-1].isoformat(),
        "Open": session_open,
        "Close": float(reference_bar["Close"]),
        "VWAP": float(reference_bar["VWAP"]),
        "AboveOpen": float(reference_bar["Close"]) > session_open,
        "BelowOpen": float(reference_bar["Close"]) < session_open,
        "AboveVWAP": float(reference_bar["Close"]) > float(reference_bar["VWAP"]),
        "BelowVWAP": float(reference_bar["Close"]) < float(reference_bar["VWAP"]),
        "VWAPState": vwap_state,
        "VWAPDistancePct": vwap_distance_pct,
        "NearVWAPNoTradeZone": abs(vwap_distance_pct) <= near_vwap_no_trade_pct,
        "LiquiditySweep": sweep["direction"],
        "LiquiditySweepLevel": sweep["level"],
        "LiquiditySweepPrice": sweep["price"],
        "OrderFlowProxy": order_flow["bias"],
        "OrderFlowScore": order_flow["score"],
        "OrderFlowComponents": order_flow["components"],
        "MoveFromOpenPct": move_from_open_pct,
        "OpeningRangeHigh": opening_range_high,
        "OpeningRangeLow": opening_range_low,
        "BreakoutAboveRange": float(reference_bar["Close"]) >= opening_range_high + buffer,
        "BreakdownBelowRange": float(reference_bar["Close"]) <= opening_range_low - buffer,
    }


def _classify_vwap_behavior(recent_bars: pd.DataFrame) -> str:
    closes = recent_bars["Close"].astype(float)
    vwaps = recent_bars["VWAP"].astype(float)
    above = closes > vwaps
    below = closes < vwaps
    if bool(above.all()):
        return "hold_above"
    if bool(below.all()):
        return "hold_below"
    if bool(above.iloc[-1]) and bool((~above).iloc[:-1].any()):
        return "reclaim"
    if bool(below.iloc[-1]) and bool((~below).iloc[:-1].any()):
        return "reject"
    return "chop"


def _detect_liquidity_sweep(
    intraday_window: pd.DataFrame,
    opening_range_high: float,
    opening_range_low: float,
    min_excursion_pct: float,
) -> dict[str, object]:
    if len(intraday_window) < 2:
        return {"direction": "none", "level": None, "price": None}

    reference_bar = intraday_window.iloc[-1]
    prior_bars = intraday_window.iloc[:-1]
    prior_high = float(prior_bars["High"].max())
    prior_low = float(prior_bars["Low"].min())
    close_price = float(reference_bar["Close"])
    high_price = float(reference_bar["High"])
    low_price = float(reference_bar["Low"])

    opening_range_high_swept = (
        high_price >= opening_range_high * (1.0 + min_excursion_pct)
        and close_price < opening_range_high
    )
    opening_range_low_swept = (
        low_price <= opening_range_low * (1.0 - min_excursion_pct)
        and close_price > opening_range_low
    )
    prior_high_swept = (
        high_price >= prior_high * (1.0 + min_excursion_pct)
        and close_price < prior_high
    )
    prior_low_swept = (
        low_price <= prior_low * (1.0 - min_excursion_pct)
        and close_price > prior_low
    )

    if opening_range_high_swept:
        return {"direction": "bearish_sweep", "level": "opening_range_high", "price": opening_range_high}
    if prior_high_swept:
        return {"direction": "bearish_sweep", "level": "prior_intraday_high", "price": prior_high}
    if opening_range_low_swept:
        return {"direction": "bullish_sweep", "level": "opening_range_low", "price": opening_range_low}
    if prior_low_swept:
        return {"direction": "bullish_sweep", "level": "prior_intraday_low", "price": prior_low}
    return {"direction": "none", "level": None, "price": None}


def _summarize_order_flow(
    intraday_window: pd.DataFrame,
    vwap_state: str,
    lookback_bars: int,
    min_volume_expansion: float,
    strong_close_threshold: float,
    weak_close_threshold: float,
) -> dict[str, object]:
    recent = intraday_window.tail(max(lookback_bars, 2))
    reference_bar = recent.iloc[-1]
    prior_bars = recent.iloc[:-1]
    high_price = float(reference_bar["High"])
    low_price = float(reference_bar["Low"])
    close_price = float(reference_bar["Close"])
    bar_range = max(high_price - low_price, 1e-9)
    close_position = (close_price - low_price) / bar_range
    avg_prior_volume = float(prior_bars["Volume"].mean()) if not prior_bars.empty else float(reference_bar["Volume"])
    volume_expansion = float(reference_bar["Volume"]) / max(avg_prior_volume, 1.0)
    close_change = close_price - float(prior_bars.iloc[-1]["Close"]) if not prior_bars.empty else 0.0
    recent_returns = recent["Close"].astype(float).diff().dropna()

    score = 0
    components: list[str] = []
    if vwap_state in {"hold_above", "reclaim"}:
        score += 1
        components.append("vwap bullish")
    elif vwap_state in {"hold_below", "reject"}:
        score -= 1
        components.append("vwap bearish")

    if close_position >= strong_close_threshold:
        score += 1
        components.append("strong close")
    elif close_position <= weak_close_threshold:
        score -= 1
        components.append("weak close")

    if volume_expansion >= min_volume_expansion and close_change > 0:
        score += 1
        components.append("buy volume expansion")
    elif volume_expansion >= min_volume_expansion and close_change < 0:
        score -= 1
        components.append("sell volume expansion")

    if not recent_returns.empty and bool((recent_returns > 0).all()):
        score += 1
        components.append("consecutive higher closes")
    elif not recent_returns.empty and bool((recent_returns < 0).all()):
        score -= 1
        components.append("consecutive lower closes")

    if score >= 2:
        bias = "bullish"
    elif score <= -2:
        bias = "bearish"
    else:
        bias = "neutral"

    return {"bias": bias, "score": score, "components": components}
