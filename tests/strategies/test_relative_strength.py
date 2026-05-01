import numpy as np
import pandas as pd

import src.config.settings as cfg
import src.data.universe as universe_module
import src.strategies.relative_strength as rs_module
import src.ta.indicators.trend as trend_module
import src.ta.indicators.volatility as volatility_module
from src.strategies.relative_strength import RelativeStrengthRanker


def test_relative_strength_signal_includes_price_action_context(monkeypatch):
    dates = pd.date_range("2023-01-02", periods=260, freq="B")
    close_vals = np.linspace(100.0, 160.0, len(dates))
    df = pd.DataFrame(
        {
            "Open": close_vals * 0.997,
            "High": close_vals * 1.002,
            "Low": close_vals * 0.99,
            "Close": close_vals,
            "Volume": np.full(len(dates), 2_000_000.0),
        },
        index=dates,
    )
    qqq_df = pd.DataFrame(
        {
            "Open": np.linspace(100.0, 120.0, len(dates)),
            "High": np.linspace(101.0, 121.0, len(dates)),
            "Low": np.linspace(99.0, 119.0, len(dates)),
            "Close": np.linspace(100.0, 120.0, len(dates)),
            "Volume": np.full(len(dates), 5_000_000.0),
        },
        index=dates,
    )

    monkeypatch.setattr(universe_module, "get_ticker_sector", lambda _ticker: cfg.RS_RANKER_SECTORS[0])
    monkeypatch.setattr(cfg, "RS_RANKER_RS_THRESHOLD", 0.10)
    monkeypatch.setattr(
        rs_module,
        "get_historical_data",
        lambda ticker: qqq_df if ticker == cfg.REGIME_INDEX else df,
    )
    monkeypatch.setattr(trend_module, "adx_latest", lambda _df: cfg.UNIVERSAL_ADX_MIN + 5)
    monkeypatch.setattr(volatility_module, "atr_latest", lambda _df, _period=20: 2.0)

    signal = RelativeStrengthRanker().scan("TEST", df, df.index[-1])

    assert signal is not None
    assert signal["Strategy"] == "RelativeStrength_Ranker_Position"
    assert signal["OrderFlowBias"] == "bullish"
    assert "LiquiditySweep" in signal
