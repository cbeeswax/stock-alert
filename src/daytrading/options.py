from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd
import yfinance as yf


def fetch_option_expiries(symbol: str) -> list[date]:
    ticker = yf.Ticker(symbol)
    expiries = []
    for value in ticker.options:
        expiries.append(date.fromisoformat(value))
    return expiries


def choose_preferred_expiry(
    trade_date: date,
    expiries: Iterable[date],
    min_days_to_expiry: int = 3,
    max_days_to_expiry: int = 10,
) -> date:
    valid_expiries = sorted(expiry for expiry in expiries if expiry >= trade_date)
    if not valid_expiries:
        raise ValueError("No valid option expiries available")

    preferred = [
        expiry for expiry in valid_expiries
        if min_days_to_expiry <= (expiry - trade_date).days <= max_days_to_expiry
    ]
    if preferred:
        return preferred[0]

    for expiry in valid_expiries:
        if (expiry - trade_date).days >= min_days_to_expiry:
            return expiry
    return valid_expiries[-1]


def choose_target_strike(
    underlying_price: float,
    strikes: Iterable[float] | None = None,
) -> float:
    if strikes is None:
        return float(round(underlying_price))

    valid_strikes = sorted(float(strike) for strike in strikes)
    if not valid_strikes:
        raise ValueError("No strikes available for option selection")
    return min(valid_strikes, key=lambda strike: abs(strike - underlying_price))


def build_spy_option_plan(
    symbol: str,
    direction: str,
    underlying_price: float,
    signal_time: datetime,
    expiries: Iterable[date] | None = None,
    strikes: Iterable[float] | None = None,
    target_moneyness: str = "atm",
    target_delta_abs: float = 0.35,
    min_days_to_expiry: int = 3,
    max_days_to_expiry: int = 10,
    premium_stop_loss_pct: float = 0.35,
    premium_target_pct: float = 0.60,
    hard_exit_time: str = "11:30",
) -> dict[str, object]:
    normalized_direction = direction.upper()
    if normalized_direction not in {"LONG", "SHORT"}:
        raise ValueError(f"Unsupported option direction: {direction}")

    option_side = "CALL" if normalized_direction == "LONG" else "PUT"
    available_expiries = list(expiries) if expiries is not None else []
    expiry = choose_preferred_expiry(
        trade_date=signal_time.date(),
        expiries=available_expiries or [_next_friday(signal_time.date())],
        min_days_to_expiry=min_days_to_expiry,
        max_days_to_expiry=max_days_to_expiry,
    )
    strike = choose_target_strike(underlying_price=underlying_price, strikes=strikes)

    return {
        "Underlying": symbol.upper(),
        "Direction": normalized_direction,
        "OptionSide": option_side,
        "Expiry": expiry.isoformat(),
        "Strike": strike,
        "TargetDeltaAbs": target_delta_abs,
        "PremiumStopLossPct": premium_stop_loss_pct,
        "PremiumTargetPct": premium_target_pct,
        "HardExitTime": hard_exit_time,
        "SelectionRule": (
            f"{target_moneyness.upper()} weekly contract targeting {target_delta_abs:.2f} delta "
            f"with at least {min_days_to_expiry} DTE"
        ),
    }


def download_option_chain(symbol: str, expiry: date) -> pd.DataFrame:
    chain = yf.Ticker(symbol).option_chain(expiry.isoformat())
    calls = chain.calls.copy()
    calls["optionType"] = "CALL"
    puts = chain.puts.copy()
    puts["optionType"] = "PUT"
    combined = pd.concat([calls, puts], ignore_index=True)
    combined["expiry"] = expiry.isoformat()
    return combined


def select_option_contract(
    option_chain: pd.DataFrame,
    option_side: str,
    target_strike: float,
    underlying_price: float | None = None,
    target_delta_abs: float = 0.35,
    delta_tolerance: float = 0.20,
    min_volume: int = 100,
    min_open_interest: int = 500,
    max_spread_pct: float = 0.12,
) -> dict[str, object]:
    filtered = option_chain.copy()
    filtered = filtered[filtered["optionType"].str.upper() == option_side.upper()]
    if filtered.empty:
        raise ValueError(f"No {option_side} contracts found in option chain")

    filtered = filtered.assign(
        midpoint=(filtered["bid"] + filtered["ask"]) / 2.0,
        spread_pct=(filtered["ask"] - filtered["bid"]).div(((filtered["bid"] + filtered["ask"]) / 2.0).replace(0, pd.NA)),
        strike_distance=(filtered["strike"] - target_strike).abs(),
    )
    if "delta" in filtered.columns:
        filtered = filtered.assign(
            abs_delta=filtered["delta"].abs(),
            delta_distance=(filtered["delta"].abs() - target_delta_abs).abs(),
        )
    else:
        if underlying_price is None:
            raise ValueError("underlying_price is required when option chain delta data is unavailable")
        filtered = filtered.assign(
            abs_delta=filtered.apply(
                lambda row: _estimate_abs_delta(
                    option_type=str(row["optionType"]),
                    strike=float(row["strike"]),
                    underlying_price=underlying_price,
                ),
                axis=1,
            )
        )
        filtered = filtered.assign(delta_distance=(filtered["abs_delta"] - target_delta_abs).abs())
    liquid = filtered[
        (filtered["volume"].fillna(0) >= min_volume)
        & (filtered["openInterest"].fillna(0) >= min_open_interest)
        & (filtered["spread_pct"].fillna(float("inf")) <= max_spread_pct)
        & (filtered["delta_distance"].fillna(float("inf")) <= delta_tolerance)
    ].copy()
    if liquid.empty:
        raise ValueError("No liquid option contract matched the configured filters")

    liquid = liquid.sort_values(
        by=["delta_distance", "spread_pct", "strike_distance", "openInterest", "volume"],
        ascending=[True, True, True, False, False],
    )
    selected = liquid.iloc[0]
    return {
        "ContractSymbol": selected["contractSymbol"],
        "OptionType": selected["optionType"],
        "Strike": float(selected["strike"]),
        "Bid": float(selected["bid"]),
        "Ask": float(selected["ask"]),
        "Midpoint": float(selected["midpoint"]),
        "SpreadPct": float(selected["spread_pct"]),
        "AbsDelta": float(selected["abs_delta"]),
        "Volume": int(selected["volume"]),
        "OpenInterest": int(selected["openInterest"]),
        "Expiry": selected["expiry"],
    }


def summarize_option_positioning(
    option_chain: pd.DataFrame,
    underlying_price: float,
    near_money_strike_window_pct: float = 0.01,
    bullish_put_call_oi_ratio_min: float = 1.1,
    bearish_put_call_oi_ratio_max: float = 0.9,
) -> dict[str, object]:
    if option_chain.empty:
        raise ValueError("Option chain is empty")

    filtered = option_chain.copy()
    strike_window = underlying_price * near_money_strike_window_pct
    filtered = filtered[(filtered["strike"] - underlying_price).abs() <= strike_window].copy()
    if filtered.empty:
        filtered = option_chain.copy()

    calls = filtered[filtered["optionType"].str.upper() == "CALL"]
    puts = filtered[filtered["optionType"].str.upper() == "PUT"]

    call_oi = float(calls["openInterest"].fillna(0).sum())
    put_oi = float(puts["openInterest"].fillna(0).sum())
    call_volume = float(calls["volume"].fillna(0).sum())
    put_volume = float(puts["volume"].fillna(0).sum())
    put_call_oi_ratio = put_oi / call_oi if call_oi > 0 else float("inf")
    total_volume = call_volume + put_volume
    call_volume_share = (call_volume / total_volume) if total_volume > 0 else 0.0
    if put_call_oi_ratio >= bullish_put_call_oi_ratio_min:
        bias = "LONG"
    elif put_call_oi_ratio <= bearish_put_call_oi_ratio_max:
        bias = "SHORT"
    else:
        bias = "NEUTRAL"

    return {
        "Bias": bias,
        "PutCallOIRatio": put_call_oi_ratio,
        "CallOpenInterest": call_oi,
        "PutOpenInterest": put_oi,
        "CallVolume": call_volume,
        "PutVolume": put_volume,
        "CallVolumeShare": call_volume_share,
        "NearMoneyStrikeWindowPct": near_money_strike_window_pct,
    }


def _next_friday(trade_date: date) -> date:
    days_ahead = (4 - trade_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return trade_date + timedelta(days=days_ahead)


def _estimate_abs_delta(option_type: str, strike: float, underlying_price: float) -> float:
    moneyness = (strike - underlying_price) / underlying_price
    option_type_upper = option_type.upper()
    if option_type_upper == "CALL":
        if strike <= underlying_price:
            return min(0.90, 0.55 + abs(moneyness) * 12.0)
        return max(0.05, 0.50 - moneyness * 15.0)
    if option_type_upper == "PUT":
        if strike >= underlying_price:
            return min(0.90, 0.55 + abs(moneyness) * 12.0)
        return max(0.05, 0.50 - abs(moneyness) * 15.0)
    raise ValueError(f"Unsupported option type for delta estimate: {option_type}")
