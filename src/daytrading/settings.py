from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.storage.gcs import download_file

CONFIG_PATH = Path("config\\daytrading_settings.json")
GCS_CONFIG_PATH = "config/daytrading_settings.json"
REQUIRED_SECTIONS = {"market_data", "signal", "options", "risk", "workflow"}
REQUIRED_SECTION_KEYS = {
    "market_data": {"underlying_symbol", "intraday_period", "intraday_interval", "include_prepost"},
    "signal": {
        "evaluation_time",
        "opening_range_bars",
        "min_bars_before_signal",
        "opening_range_break_buffer_pct",
        "liquidity_sweep_min_excursion_pct",
        "min_underlying_move_from_open_pct",
        "min_breadth_above_open_pct",
        "min_breadth_above_vwap_pct",
        "min_breadth_edge_pct",
        "min_heavyweight_confirmation_pct",
        "vwap_behavior_lookback_bars",
        "near_vwap_no_trade_pct",
        "order_flow_lookback_bars",
        "order_flow_min_volume_expansion",
        "order_flow_strong_close_threshold",
        "order_flow_weak_close_threshold",
        "bullish_vwap_states",
        "bearish_vwap_states",
        "breadth_symbols",
        "heavyweight_symbols",
    },
    "options": {
        "target_moneyness",
        "target_delta_abs",
        "delta_tolerance",
        "min_days_to_expiry",
        "max_days_to_expiry",
        "min_volume",
        "min_open_interest",
        "max_spread_pct",
        "require_positioning_confirmation",
        "near_money_strike_window_pct",
        "bullish_put_call_oi_ratio_min",
        "bearish_put_call_oi_ratio_max",
    },
    "risk": {
        "premium_stop_loss_pct",
        "premium_target_pct",
        "hard_exit_time",
    },
    "workflow": {
        "mode",
        "max_trades_per_day",
        "no_trade_on_neutral",
    },
}


@dataclass(frozen=True)
class DayTradingSettings:
    underlying_symbol: str
    intraday_period: str
    intraday_interval: str
    include_prepost: bool
    evaluation_time: str
    opening_range_bars: int
    min_bars_before_signal: int
    opening_range_break_buffer_pct: float
    liquidity_sweep_min_excursion_pct: float
    min_underlying_move_from_open_pct: float
    min_breadth_above_open_pct: float
    min_breadth_above_vwap_pct: float
    min_breadth_edge_pct: float
    min_heavyweight_confirmation_pct: float
    vwap_behavior_lookback_bars: int
    near_vwap_no_trade_pct: float
    order_flow_lookback_bars: int
    order_flow_min_volume_expansion: float
    order_flow_strong_close_threshold: float
    order_flow_weak_close_threshold: float
    bullish_vwap_states: list[str]
    bearish_vwap_states: list[str]
    breadth_symbols: list[str]
    heavyweight_symbols: list[str]
    target_moneyness: str
    target_delta_abs: float
    delta_tolerance: float
    min_days_to_expiry: int
    max_days_to_expiry: int
    min_volume: int
    min_open_interest: int
    max_spread_pct: float
    require_positioning_confirmation: bool
    near_money_strike_window_pct: float
    bullish_put_call_oi_ratio_min: float
    bearish_put_call_oi_ratio_max: float
    premium_stop_loss_pct: float
    premium_target_pct: float
    hard_exit_time: str
    mode: str
    max_trades_per_day: int
    no_trade_on_neutral: bool


def load_daytrading_settings() -> DayTradingSettings:
    raw_config = _load_required_config()
    return _to_settings(raw_config)


def _load_required_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    else:
        with tempfile.TemporaryDirectory(prefix="daytrading-settings-") as tmp_dir:
            local_path = Path(tmp_dir) / "daytrading_settings.json"
            if not download_file(GCS_CONFIG_PATH, local_path):
                raise FileNotFoundError(
                    "Missing required daytrading settings file: config\\daytrading_settings.json "
                    "(expected locally or in GCS)."
                )
            with local_path.open("r", encoding="utf-8") as handle:
                config = json.load(handle)

    _validate_config(config)
    return config


def _validate_config(config: dict[str, Any]) -> None:
    missing_sections = sorted(REQUIRED_SECTIONS - set(config))
    if missing_sections:
        raise ValueError(f"Daytrading settings missing required sections: {missing_sections}")

    for section_name in REQUIRED_SECTIONS:
        section = config[section_name]
        if not isinstance(section, dict):
            raise ValueError(f"Daytrading settings section '{section_name}' must be an object.")
        missing_keys = sorted(REQUIRED_SECTION_KEYS[section_name] - set(section))
        if missing_keys:
            raise ValueError(
                f"Daytrading settings section '{section_name}' missing required keys: {missing_keys}"
            )


def _to_settings(config: dict[str, Any]) -> DayTradingSettings:
    market_data = config["market_data"]
    signal = config["signal"]
    options = config["options"]
    risk = config["risk"]
    workflow = config["workflow"]
    return DayTradingSettings(
        underlying_symbol=str(market_data["underlying_symbol"]).upper(),
        intraday_period=str(market_data["intraday_period"]),
        intraday_interval=str(market_data["intraday_interval"]),
        include_prepost=bool(market_data["include_prepost"]),
        evaluation_time=str(signal["evaluation_time"]),
        opening_range_bars=int(signal["opening_range_bars"]),
        min_bars_before_signal=int(signal["min_bars_before_signal"]),
        opening_range_break_buffer_pct=float(signal["opening_range_break_buffer_pct"]),
        liquidity_sweep_min_excursion_pct=float(signal["liquidity_sweep_min_excursion_pct"]),
        min_underlying_move_from_open_pct=float(signal["min_underlying_move_from_open_pct"]),
        min_breadth_above_open_pct=float(signal["min_breadth_above_open_pct"]),
        min_breadth_above_vwap_pct=float(signal["min_breadth_above_vwap_pct"]),
        min_breadth_edge_pct=float(signal["min_breadth_edge_pct"]),
        min_heavyweight_confirmation_pct=float(signal["min_heavyweight_confirmation_pct"]),
        vwap_behavior_lookback_bars=int(signal["vwap_behavior_lookback_bars"]),
        near_vwap_no_trade_pct=float(signal["near_vwap_no_trade_pct"]),
        order_flow_lookback_bars=int(signal["order_flow_lookback_bars"]),
        order_flow_min_volume_expansion=float(signal["order_flow_min_volume_expansion"]),
        order_flow_strong_close_threshold=float(signal["order_flow_strong_close_threshold"]),
        order_flow_weak_close_threshold=float(signal["order_flow_weak_close_threshold"]),
        bullish_vwap_states=[str(value) for value in signal["bullish_vwap_states"]],
        bearish_vwap_states=[str(value) for value in signal["bearish_vwap_states"]],
        breadth_symbols=[str(symbol).upper() for symbol in signal["breadth_symbols"]],
        heavyweight_symbols=[str(symbol).upper() for symbol in signal["heavyweight_symbols"]],
        target_moneyness=str(options["target_moneyness"]).lower(),
        target_delta_abs=float(options["target_delta_abs"]),
        delta_tolerance=float(options["delta_tolerance"]),
        min_days_to_expiry=int(options["min_days_to_expiry"]),
        max_days_to_expiry=int(options["max_days_to_expiry"]),
        min_volume=int(options["min_volume"]),
        min_open_interest=int(options["min_open_interest"]),
        max_spread_pct=float(options["max_spread_pct"]),
        require_positioning_confirmation=bool(options["require_positioning_confirmation"]),
        near_money_strike_window_pct=float(options["near_money_strike_window_pct"]),
        bullish_put_call_oi_ratio_min=float(options["bullish_put_call_oi_ratio_min"]),
        bearish_put_call_oi_ratio_max=float(options["bearish_put_call_oi_ratio_max"]),
        premium_stop_loss_pct=float(risk["premium_stop_loss_pct"]),
        premium_target_pct=float(risk["premium_target_pct"]),
        hard_exit_time=str(risk["hard_exit_time"]),
        mode=str(workflow["mode"]),
        max_trades_per_day=int(workflow["max_trades_per_day"]),
        no_trade_on_neutral=bool(workflow["no_trade_on_neutral"]),
    )
