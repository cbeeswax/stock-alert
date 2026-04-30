from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from src.daytrading.morning_spy import MorningSignalConfig, build_morning_spy_recommendation, generate_morning_spy_signal
from src.daytrading.options import (
    build_spy_option_plan,
    choose_preferred_expiry,
    select_option_contract,
    summarize_option_positioning,
)
from src.daytrading.settings import DayTradingSettings


TEST_SETTINGS = DayTradingSettings(
    underlying_symbol="SPY",
    intraday_period="5d",
    intraday_interval="5m",
    include_prepost=False,
    evaluation_time="11:00",
    opening_range_bars=2,
    min_bars_before_signal=3,
    opening_range_break_buffer_pct=0.0005,
    liquidity_sweep_min_excursion_pct=0.0005,
    min_underlying_move_from_open_pct=0.001,
    min_breadth_above_open_pct=0.6,
    min_breadth_above_vwap_pct=0.6,
    min_breadth_edge_pct=0.2,
    min_heavyweight_confirmation_pct=0.67,
    vwap_behavior_lookback_bars=3,
    near_vwap_no_trade_pct=0.001,
    order_flow_lookback_bars=3,
    order_flow_min_volume_expansion=1.15,
    order_flow_strong_close_threshold=0.70,
    order_flow_weak_close_threshold=0.30,
    bullish_vwap_states=["hold_above", "reclaim"],
    bearish_vwap_states=["hold_below", "reject"],
    breadth_symbols=["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL"],
    heavyweight_symbols=["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL"],
    target_moneyness="atm",
    target_delta_abs=0.35,
    delta_tolerance=0.20,
    min_days_to_expiry=3,
    max_days_to_expiry=10,
    min_volume=100,
    min_open_interest=500,
    max_spread_pct=0.12,
    require_positioning_confirmation=True,
    near_money_strike_window_pct=0.02,
    bullish_put_call_oi_ratio_min=1.1,
    bearish_put_call_oi_ratio_max=0.9,
    premium_stop_loss_pct=0.35,
    premium_target_pct=0.60,
    hard_exit_time="11:30",
    mode="single-decision",
    max_trades_per_day=1,
    no_trade_on_neutral=True,
)


def _intraday_frame(open_values, high_values, low_values, close_values):
    base_times = [
        "2026-04-28 09:30:00-04:00",
        "2026-04-28 09:35:00-04:00",
        "2026-04-28 09:40:00-04:00",
    ]
    index = pd.DatetimeIndex(base_times[:len(open_values)])
    return pd.DataFrame(
        {
            "Open": open_values,
            "High": high_values,
            "Low": low_values,
            "Close": close_values,
            "Volume": [1000, 1200, 1400][:len(open_values)],
        },
        index=index,
    )


def _option_chain(
    call_oi: int,
    put_oi: int,
    call_volume: int,
    put_volume: int,
    underlying_price: float = 602.0,
):
    return pd.DataFrame(
        [
            {
                "contractSymbol": "SPY260501C00602000",
                "optionType": "CALL",
                "strike": underlying_price,
                "bid": 4.80,
                "ask": 5.10,
                "volume": call_volume,
                "openInterest": call_oi,
                "expiry": "2026-05-01",
            },
            {
                "contractSymbol": "SPY260501P00602000",
                "optionType": "PUT",
                "strike": underlying_price,
                "bid": 4.70,
                "ask": 5.00,
                "volume": put_volume,
                "openInterest": put_oi,
                "expiry": "2026-05-01",
            },
        ]
    )


def test_generate_morning_spy_long_signal():
    intraday_data = {
        "SPY": _intraday_frame(
            [600.0, 600.8, 601.1],
            [601.0, 602.0, 603.0],
            [599.5, 600.5, 600.9],
            [600.8, 601.4, 602.8],
        ),
        "AAPL": _intraday_frame(
            [200.0, 200.4, 200.7],
            [200.5, 201.0, 201.4],
            [199.9, 200.2, 200.5],
            [200.3, 200.8, 201.2],
        ),
        "MSFT": _intraday_frame(
            [430.0, 430.6, 431.0],
            [431.0, 432.0, 433.0],
            [429.8, 430.4, 430.8],
            [430.7, 431.5, 432.7],
        ),
        "NVDA": _intraday_frame(
            [110.0, 110.5, 111.0],
            [111.0, 112.0, 113.0],
            [109.8, 110.3, 110.8],
            [110.6, 111.3, 112.6],
        ),
        "AMZN": _intraday_frame(
            [185.0, 185.2, 185.7],
            [186.0, 186.6, 187.3],
            [184.8, 185.1, 185.5],
            [185.4, 186.0, 186.9],
        ),
        "META": _intraday_frame(
            [510.0, 510.7, 511.2],
            [511.0, 512.5, 513.4],
            [509.8, 510.6, 511.0],
            [510.9, 511.8, 513.0],
        ),
        "GOOGL": _intraday_frame(
            [170.0, 170.4, 170.7],
            [170.8, 171.5, 172.0],
            [169.8, 170.2, 170.5],
            [170.5, 171.0, 171.7],
        ),
    }

    recommendation = build_morning_spy_recommendation(
        intraday_data,
        settings=TEST_SETTINGS,
        option_chain=_option_chain(call_oi=1000, put_oi=1400, call_volume=900, put_volume=700),
    )

    assert recommendation["Signal"] == "LONG"
    assert recommendation["EntryWindow"] == "11:00 ET"
    assert recommendation["OptionPlan"]["OptionSide"] == "CALL"
    assert recommendation["OptionPlan"]["HardExitTime"] == "11:30"
    assert recommendation["TradingMode"] == "single-decision"
    assert recommendation["MaxTradesPerDay"] == 1
    assert recommendation["VWAPState"] == "hold_above"
    assert recommendation["OptionChainBias"] == "LONG"
    assert recommendation["LiquiditySweep"] == "none"
    assert recommendation["OrderFlowProxy"] == "bullish"


def test_generate_morning_spy_short_signal():
    intraday_data = {
        "SPY": _intraday_frame(
            [600.0, 599.2, 598.8],
            [600.3, 599.4, 599.0],
            [598.9, 597.8, 596.9],
            [599.0, 598.3, 597.1],
        ),
        "AAPL": _intraday_frame(
            [200.0, 199.7, 199.3],
            [200.1, 199.8, 199.4],
            [199.4, 198.8, 198.1],
            [199.6, 199.0, 198.3],
        ),
        "MSFT": _intraday_frame(
            [430.0, 429.6, 429.1],
            [430.2, 429.7, 429.3],
            [429.1, 428.6, 427.8],
            [429.3, 428.8, 428.0],
        ),
        "NVDA": _intraday_frame(
            [110.0, 109.7, 109.1],
            [110.1, 109.8, 109.3],
            [109.2, 108.6, 107.8],
            [109.3, 108.8, 108.0],
        ),
        "AMZN": _intraday_frame(
            [185.0, 184.7, 184.2],
            [185.1, 184.9, 184.4],
            [184.2, 183.7, 183.0],
            [184.4, 183.8, 183.2],
        ),
        "META": _intraday_frame(
            [510.0, 509.6, 508.9],
            [510.2, 509.8, 509.1],
            [509.0, 507.9, 506.8],
            [509.1, 508.0, 507.0],
        ),
        "GOOGL": _intraday_frame(
            [170.0, 169.8, 169.2],
            [170.1, 169.9, 169.3],
            [169.1, 168.4, 167.8],
            [169.2, 168.6, 168.0],
        ),
    }

    recommendation = build_morning_spy_recommendation(
        intraday_data,
        settings=TEST_SETTINGS,
        option_chain=_option_chain(call_oi=1400, put_oi=900, call_volume=700, put_volume=900),
    )

    assert recommendation["Signal"] == "SHORT"
    assert recommendation["OptionPlan"]["OptionSide"] == "PUT"
    assert recommendation["OrderFlowProxy"] == "bearish"


def test_generate_morning_spy_neutral_when_breadth_is_weak():
    intraday_data = {
        "SPY": _intraday_frame(
            [600.0, 600.8, 601.1],
            [601.0, 602.0, 603.0],
            [599.5, 600.5, 600.9],
            [600.8, 601.4, 602.8],
        ),
        "AAPL": _intraday_frame(
            [200.0, 200.4, 200.7],
            [200.5, 201.0, 201.4],
            [199.9, 200.2, 200.5],
            [200.3, 200.8, 201.2],
        ),
        "MSFT": _intraday_frame(
            [430.0, 430.6, 431.0],
            [431.0, 432.0, 433.0],
            [429.8, 430.4, 430.8],
            [430.7, 431.5, 432.7],
        ),
        "NVDA": _intraday_frame(
            [110.0, 109.8, 109.3],
            [110.2, 110.0, 109.6],
            [109.4, 109.0, 108.5],
            [109.6, 109.2, 108.8],
        ),
        "AMZN": _intraday_frame(
            [185.0, 184.8, 184.1],
            [185.1, 184.9, 184.3],
            [184.0, 183.6, 183.0],
            [184.2, 183.7, 183.1],
        ),
        "META": _intraday_frame(
            [510.0, 510.7, 511.2],
            [511.0, 512.5, 513.4],
            [509.8, 510.6, 511.0],
            [510.9, 511.8, 513.0],
        ),
        "GOOGL": _intraday_frame(
            [170.0, 169.7, 169.1],
            [170.2, 169.8, 169.3],
            [169.1, 168.8, 168.2],
            [169.2, 168.9, 168.4],
        ),
    }

    signal = generate_morning_spy_signal(
        intraday_data,
        MorningSignalConfig(min_breadth_above_open_pct=0.80, min_breadth_above_vwap_pct=0.80),
        settings=TEST_SETTINGS,
        option_chain=_option_chain(call_oi=1000, put_oi=1400, call_volume=900, put_volume=700),
    )

    assert signal["Signal"] == "NEUTRAL"


def test_generate_morning_spy_requires_three_bars_by_default():
    intraday_data = {
        "SPY": _intraday_frame([600.0, 600.8], [601.0, 602.0], [599.5, 600.5], [600.8, 601.8]),
        "AAPL": _intraday_frame([200.0, 200.4], [200.5, 201.0], [199.9, 200.2], [200.3, 200.9]),
        "MSFT": _intraday_frame([430.0, 430.6], [431.0, 432.0], [429.8, 430.4], [430.7, 431.8]),
        "NVDA": _intraday_frame([110.0, 110.5], [111.0, 112.0], [109.8, 110.3], [110.6, 111.7]),
        "AMZN": _intraday_frame([185.0, 185.2], [186.0, 186.6], [184.8, 185.1], [185.4, 186.2]),
        "META": _intraday_frame([510.0, 510.7], [511.0, 512.5], [509.8, 510.6], [510.9, 512.0]),
        "GOOGL": _intraday_frame([170.0, 170.4], [170.8, 171.5], [169.8, 170.2], [170.5, 171.2]),
    }

    for symbol, frame in intraday_data.items():
        intraday_data[symbol] = frame.iloc[:2]

    try:
        generate_morning_spy_signal(intraday_data, settings=TEST_SETTINGS)
    except ValueError as exc:
        assert "Not enough bars available before 11:00" in str(exc)
    else:
        raise AssertionError("Expected default configuration to require three bars through 11:00 ET")


def test_generate_morning_spy_neutral_when_option_chain_diverges():
    intraday_data = {
        "SPY": _intraday_frame([600.0, 600.8, 601.1], [601.0, 602.0, 603.0], [599.5, 600.5, 600.9], [600.8, 601.4, 602.8]),
        "AAPL": _intraday_frame([200.0, 200.4, 200.7], [200.5, 201.0, 201.4], [199.9, 200.2, 200.5], [200.3, 200.8, 201.2]),
        "MSFT": _intraday_frame([430.0, 430.6, 431.0], [431.0, 432.0, 433.0], [429.8, 430.4, 430.8], [430.7, 431.5, 432.7]),
        "NVDA": _intraday_frame([110.0, 110.5, 111.0], [111.0, 112.0, 113.0], [109.8, 110.3, 110.8], [110.6, 111.3, 112.6]),
        "AMZN": _intraday_frame([185.0, 185.2, 185.7], [186.0, 186.6, 187.3], [184.8, 185.1, 185.5], [185.4, 186.0, 186.9]),
        "META": _intraday_frame([510.0, 510.7, 511.2], [511.0, 512.5, 513.4], [509.8, 510.6, 511.0], [510.9, 511.8, 513.0]),
        "GOOGL": _intraday_frame([170.0, 170.4, 170.7], [170.8, 171.5, 172.0], [169.8, 170.2, 170.5], [170.5, 171.0, 171.7]),
    }

    recommendation = build_morning_spy_recommendation(
        intraday_data,
        settings=TEST_SETTINGS,
        option_chain=_option_chain(call_oi=1400, put_oi=800, call_volume=900, put_volume=600),
    )

    assert recommendation["Signal"] == "NEUTRAL"
    assert recommendation["BaseSignal"] == "LONG"
    assert recommendation["PositioningDivergence"] is True
    assert "diverges" in recommendation["NoTradeReasons"][0]


def test_generate_morning_spy_neutral_when_near_vwap_chop():
    intraday_data = {
        "SPY": _intraday_frame([600.0, 600.1, 600.1], [600.6, 600.8, 600.7], [599.7, 599.8, 599.9], [600.1, 600.0, 600.05]),
        "AAPL": _intraday_frame([200.0, 200.2, 200.3], [200.5, 200.7, 200.8], [199.8, 199.9, 200.0], [200.2, 200.1, 200.15]),
        "MSFT": _intraday_frame([430.0, 430.1, 430.2], [430.6, 430.7, 430.8], [429.7, 429.8, 429.9], [430.2, 430.1, 430.15]),
        "NVDA": _intraday_frame([110.0, 110.1, 110.2], [110.4, 110.5, 110.6], [109.8, 109.9, 110.0], [110.1, 110.0, 110.05]),
        "AMZN": _intraday_frame([185.0, 185.1, 185.2], [185.5, 185.6, 185.7], [184.8, 184.9, 185.0], [185.1, 185.0, 185.05]),
        "META": _intraday_frame([510.0, 510.2, 510.3], [510.6, 510.7, 510.8], [509.8, 509.9, 510.0], [510.2, 510.1, 510.15]),
        "GOOGL": _intraday_frame([170.0, 170.1, 170.2], [170.4, 170.5, 170.6], [169.8, 169.9, 170.0], [170.1, 170.0, 170.05]),
    }

    signal = generate_morning_spy_signal(
        intraday_data,
        settings=TEST_SETTINGS,
        option_chain=_option_chain(call_oi=1000, put_oi=1400, call_volume=900, put_volume=700, underlying_price=600.0),
    )

    assert signal["Signal"] == "NEUTRAL"
    assert signal["NearVWAPNoTradeZone"] is True
    assert signal["OrderFlowProxy"] == "neutral"


def test_summarize_option_positioning_uses_put_call_ratio_bias():
    summary = summarize_option_positioning(
        option_chain=_option_chain(call_oi=1000, put_oi=1500, call_volume=800, put_volume=700),
        underlying_price=602.0,
        near_money_strike_window_pct=0.02,
        bullish_put_call_oi_ratio_min=1.1,
        bearish_put_call_oi_ratio_max=0.9,
    )

    assert summary["Bias"] == "LONG"


def test_generate_morning_spy_surfaces_bearish_liquidity_sweep():
    intraday_data = {
        "SPY": _intraday_frame([600.0, 600.4, 600.7], [601.0, 601.1, 602.2], [599.6, 600.2, 600.3], [600.6, 600.9, 600.8]),
        "AAPL": _intraday_frame([200.0, 200.3, 200.5], [200.6, 200.8, 201.0], [199.8, 200.1, 200.3], [200.3, 200.6, 200.5]),
        "MSFT": _intraday_frame([430.0, 430.3, 430.6], [430.8, 431.0, 431.2], [429.7, 430.0, 430.2], [430.3, 430.7, 430.5]),
        "NVDA": _intraday_frame([110.0, 110.2, 110.4], [110.6, 110.8, 111.0], [109.8, 110.0, 110.2], [110.2, 110.5, 110.4]),
        "AMZN": _intraday_frame([185.0, 185.2, 185.5], [185.7, 185.9, 186.1], [184.8, 185.0, 185.2], [185.2, 185.6, 185.4]),
        "META": _intraday_frame([510.0, 510.4, 510.7], [510.9, 511.2, 511.5], [509.8, 510.1, 510.4], [510.4, 510.8, 510.6]),
        "GOOGL": _intraday_frame([170.0, 170.2, 170.5], [170.6, 170.8, 171.0], [169.8, 170.0, 170.3], [170.2, 170.6, 170.5]),
    }

    signal = generate_morning_spy_signal(
        intraday_data,
        settings=TEST_SETTINGS,
        option_chain=_option_chain(call_oi=1000, put_oi=1400, call_volume=900, put_volume=700, underlying_price=600.8),
    )

    assert signal["LiquiditySweep"] == "bearish_sweep"
    assert signal["LiquiditySweepLevel"] == "opening_range_high"


def test_build_spy_option_plan_prefers_same_week_if_dte_is_available():
    plan = build_spy_option_plan(
        symbol="SPY",
        direction="LONG",
        underlying_price=602.34,
        signal_time=datetime(2026, 4, 28, 9, 35, tzinfo=ZoneInfo("America/New_York")),
        expiries=[date(2026, 5, 1), date(2026, 5, 8)],
        target_moneyness="atm",
        target_delta_abs=0.35,
    )

    assert plan["Expiry"] == "2026-05-01"
    assert plan["Strike"] == 602.0
    assert plan["TargetDeltaAbs"] == 0.35


def test_choose_preferred_expiry_skips_too_close_expiry():
    expiry = choose_preferred_expiry(
        trade_date=date(2026, 4, 29),
        expiries=[date(2026, 5, 1), date(2026, 5, 8)],
    )

    assert expiry == date(2026, 5, 8)


def test_select_option_contract_uses_liquidity_filters():
    chain = pd.DataFrame(
        [
            {
                "contractSymbol": "SPY260501C00602000",
                "optionType": "CALL",
                "strike": 602.0,
                "bid": 4.80,
                "ask": 5.10,
                "volume": 800,
                "openInterest": 5000,
                "expiry": "2026-05-01",
            },
            {
                "contractSymbol": "SPY260501C00603000",
                "optionType": "CALL",
                "strike": 603.0,
                "bid": 4.70,
                "ask": 5.50,
                "volume": 20,
                "openInterest": 80,
                "expiry": "2026-05-01",
            },
        ]
    )

    selected = select_option_contract(
        chain,
        option_side="CALL",
        target_strike=602.2,
        underlying_price=602.2,
        target_delta_abs=0.35,
        delta_tolerance=0.25,
    )

    assert selected["ContractSymbol"] == "SPY260501C00602000"
