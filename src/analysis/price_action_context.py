from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PriceActionContext:
    liquidity_sweep: str = "none"
    liquidity_sweep_level: float | None = None
    liquidity_sweep_strength_pct: float | None = None
    order_flow_bias: str = "neutral"
    order_flow_score: float = 0.0
    close_strength: float = 0.5
    body_fraction: float = 0.0
    volume_ratio_20: float = 1.0


def analyze_price_action_context(
    df: pd.DataFrame,
    *,
    lookback: int = 20,
    volume_window: int = 20,
    sweep_buffer_pct: float = 0.001,
) -> PriceActionContext:
    frame = _normalize_ohlcv(df)
    if frame.empty:
        return PriceActionContext()

    current = frame.iloc[-1]
    current_open = float(current["Open"])
    current_high = float(current["High"])
    current_low = float(current["Low"])
    current_close = float(current["Close"])
    current_volume = float(current["Volume"])

    bar_range = max(current_high - current_low, 1e-9)
    close_strength = min(max((current_close - current_low) / bar_range, 0.0), 1.0)
    body_fraction = min(max(abs(current_close - current_open) / bar_range, 0.0), 1.0)
    upper_wick_fraction = max(0.0, current_high - max(current_open, current_close)) / bar_range
    lower_wick_fraction = max(0.0, min(current_open, current_close) - current_low) / bar_range

    prior = frame.iloc[:-1]
    if prior.empty:
        return PriceActionContext(
            close_strength=round(close_strength, 4),
            body_fraction=round(body_fraction, 4),
        )

    volume_sample = prior["Volume"].tail(volume_window)
    avg_volume = float(volume_sample.mean()) if not volume_sample.empty else 0.0
    volume_ratio_20 = current_volume / avg_volume if avg_volume > 0 else 1.0

    previous_close = float(prior["Close"].iloc[-1])
    follow_through = 0.0
    if previous_close > 0:
        follow_through = ((current_close / previous_close) - 1.0) / 0.03
        follow_through = min(max(follow_through, -1.0), 1.0)

    direction = 1.0 if current_close > current_open else -1.0 if current_close < current_open else 0.0
    signed_close = ((close_strength - 0.5) * 2.0) * 30.0
    body_component = direction * body_fraction * 25.0
    volume_component = direction * (min(max(volume_ratio_20 - 1.0, 0.0), 1.5) / 1.5) * 15.0
    wick_component = min(max(lower_wick_fraction - upper_wick_fraction, -1.0), 1.0) * 10.0
    order_flow_score = signed_close + body_component + (follow_through * 20.0) + volume_component + wick_component
    order_flow_score = round(min(max(order_flow_score, -100.0), 100.0), 2)

    if order_flow_score >= 15.0:
        order_flow_bias = "bullish"
    elif order_flow_score <= -15.0:
        order_flow_bias = "bearish"
    else:
        order_flow_bias = "neutral"

    liquidity_sweep = "none"
    liquidity_sweep_level = None
    liquidity_sweep_strength_pct = None

    recent = prior.tail(lookback)
    if not recent.empty:
        recent_high = float(recent["High"].max())
        recent_low = float(recent["Low"].min())

        bullish_sweep_strength = None
        if (
            recent_low > 0
            and current_low <= recent_low * (1.0 - sweep_buffer_pct)
            and current_close > recent_low
            and close_strength >= 0.55
        ):
            bullish_sweep_strength = max(0.0, (recent_low - current_low) / recent_low)

        bearish_sweep_strength = None
        if (
            recent_high > 0
            and current_high >= recent_high * (1.0 + sweep_buffer_pct)
            and current_close < recent_high
            and close_strength <= 0.45
        ):
            bearish_sweep_strength = max(0.0, (current_high - recent_high) / recent_high)

        if bullish_sweep_strength is not None and (
            bearish_sweep_strength is None or bullish_sweep_strength >= bearish_sweep_strength
        ):
            liquidity_sweep = "bullish_sweep"
            liquidity_sweep_level = recent_low
            liquidity_sweep_strength_pct = bullish_sweep_strength * 100.0
        elif bearish_sweep_strength is not None:
            liquidity_sweep = "bearish_sweep"
            liquidity_sweep_level = recent_high
            liquidity_sweep_strength_pct = bearish_sweep_strength * 100.0

    return PriceActionContext(
        liquidity_sweep=liquidity_sweep,
        liquidity_sweep_level=None if liquidity_sweep_level is None else round(liquidity_sweep_level, 2),
        liquidity_sweep_strength_pct=(
            None if liquidity_sweep_strength_pct is None else round(liquidity_sweep_strength_pct, 2)
        ),
        order_flow_bias=order_flow_bias,
        order_flow_score=order_flow_score,
        close_strength=round(close_strength, 4),
        body_fraction=round(body_fraction, 4),
        volume_ratio_20=round(volume_ratio_20, 4),
    )


def context_to_signal_fields(context: PriceActionContext) -> dict[str, Any]:
    return {
        "LiquiditySweep": context.liquidity_sweep,
        "LiquiditySweepLevel": context.liquidity_sweep_level,
        "LiquiditySweepStrengthPct": context.liquidity_sweep_strength_pct,
        "OrderFlowBias": context.order_flow_bias,
        "OrderFlowScore": round(context.order_flow_score, 2),
        "CloseStrength": round(context.close_strength, 2),
        "BodyFraction": round(context.body_fraction, 2),
        "VolumeRatio20": round(context.volume_ratio_20, 2),
    }


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    column_map = {str(column).strip().lower(): column for column in df.columns}
    required = ("open", "high", "low", "close", "volume")
    if any(name not in column_map for name in required):
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    frame = pd.DataFrame(
        {
            "Open": pd.to_numeric(df[column_map["open"]], errors="coerce"),
            "High": pd.to_numeric(df[column_map["high"]], errors="coerce"),
            "Low": pd.to_numeric(df[column_map["low"]], errors="coerce"),
            "Close": pd.to_numeric(df[column_map["close"]], errors="coerce"),
            "Volume": pd.to_numeric(df[column_map["volume"]], errors="coerce"),
        },
        index=df.index,
    )
    return frame.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
