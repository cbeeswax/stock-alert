import pandas as pd

from src.backtesting.engine import WalkForwardBacktester


def test_entry_pipeline_summary_prints_skip_reasons(capsys):
    WalkForwardBacktester._log_entry_pipeline_summary(
        day=pd.Timestamp("2025-01-15"),
        prebuy_counts={"DivergenceReversal_Position": 3},
        post_hold_counts={"DivergenceReversal_Position": 2},
        entered_counts={"DivergenceReversal_Position": 0},
        skip_reason_counts={
            "DivergenceReversal_Position": {
                "already_holding": 1,
                "strategy_limit": 1,
                "entry_failed": 1,
            }
        },
    )

    output = capsys.readouterr().out

    assert "Entry pipeline summary for 2025-01-15" in output
    assert "DivergenceReversal_Position: pre_buy=3, after_hold=2, entered=0" in output
    assert "already_holding=1" in output
    assert "strategy_limit=1" in output
    assert "entry_failed=1" in output
