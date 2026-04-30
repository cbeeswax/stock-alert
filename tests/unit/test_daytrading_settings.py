from src.daytrading.settings import load_daytrading_settings


def test_load_daytrading_settings_from_local_file():
    settings = load_daytrading_settings()

    assert settings.underlying_symbol == "SPY"
    assert settings.evaluation_time == "11:00"
    assert settings.opening_range_bars == 2
    assert settings.min_bars_before_signal == 3
    assert settings.min_days_to_expiry == 3
    assert settings.max_trades_per_day == 1
    assert settings.target_delta_abs == 0.35
    assert settings.require_positioning_confirmation is True
    assert settings.order_flow_lookback_bars == 3
    assert settings.liquidity_sweep_min_excursion_pct == 0.0005
