from pathlib import Path

import pandas as pd

from src.strategies.divergence_reversal import DivergenceReversalPosition


def test_divergence_debug_logging_writes_daily_summary(tmp_path, monkeypatch):
    log_path = tmp_path / "divergence_debug.log"

    monkeypatch.setattr(DivergenceReversalPosition, "DEBUG_LOG_PATH", Path(log_path))
    monkeypatch.setattr(DivergenceReversalPosition, "_debug_logger", None)
    monkeypatch.setattr(DivergenceReversalPosition, "_debug_logger_path", None)
    DivergenceReversalPosition._debug_reset_state()

    scan_date = pd.Timestamp("2024-01-10")
    next_date = pd.Timestamp("2024-01-11")

    DivergenceReversalPosition._debug_start_scan(scan_date)
    DivergenceReversalPosition._debug_reject(
        scan_date,
        "AAPL",
        "long_failed_trigger_break",
        close=100.0,
        trigger=101.0,
    )
    DivergenceReversalPosition._debug_signal(scan_date, "MSFT", "LONG", 82.5)
    DivergenceReversalPosition._debug_start_scan(next_date)
    DivergenceReversalPosition._flush_debug_summary()

    text = log_path.read_text(encoding="utf-8")
    assert "Divergence scan summary | date=2024-01-10 | scanned=1 | raw_signals=1" in text
    assert "reject_count | long_failed_trigger_break=1" in text
    assert "outcome_count | long_signals=1" in text
    assert "samples | long_failed_trigger_break -> AAPL (close=100.0, trigger=101.0)" in text
    assert "samples | raw_signals -> MSFT (LONG, score=82.5)" in text
