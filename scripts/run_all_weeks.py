"""
Run all weeks from Jan 6 through Apr 4, 2026 sequentially.
For each week: predict -> evaluate -> update weights -> predict next week.
"""
import subprocess
import sys
import os

python = sys.executable
script = os.path.join(os.path.dirname(__file__), "run_predictor.py")

# All Mondays Jan 6 through Mar 31, 2026 (13 weeks already closed)
# Week 14 (Apr 7) is still open — predict only
closed_weeks = [
    "2026-01-06",
    "2026-01-13",
    "2026-01-20",
    "2026-01-27",
    "2026-02-03",
    "2026-02-10",
    "2026-02-17",
    "2026-02-24",
    "2026-03-03",
    "2026-03-10",
    "2026-03-17",
    "2026-03-24",
    "2026-03-31",
]
next_week = "2026-04-07"


def run(cmd, label=""):
    print(f"\n{'='*65}")
    if label:
        print(f"  {label}")
    print(f"{'='*65}")
    result = subprocess.run(
        [python, script] + cmd,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    # Filter out pandas UserWarning noise
    out_lines = [
        l for l in result.stdout.splitlines()
        if not any(w in l for w in ["UserWarning", "dateutil", "infer format", "parse_dates"])
    ]
    print("\n".join(out_lines))
    if result.returncode != 0:
        err = [l for l in result.stderr.splitlines() if "Error" in l or "Traceback" in l or "line" in l]
        if err:
            print("STDERR:", "\n".join(err[-5:]))
    return result.returncode


print("WEEKLY STOCK PREDICTOR - FULL WALKTHROUGH")
print(f"Running {len(closed_weeks)} closed weeks + 1 open prediction\n")

summary = []

for week in closed_weeks:
    # Predict
    rc1 = run(["predict", "--week", week], f"PREDICT  {week}")
    # Evaluate (determine rough regime from date — post-election US market)
    regime = "bull" if week < "2026-02-15" else "chop"
    rc2 = run(["evaluate", "--week", week, "--regime", regime], f"EVALUATE {week}")
    summary.append((week, rc1 == 0, rc2 == 0))

# Predict next open week
run(["predict", "--week", next_week], f"PREDICT (LIVE)  {next_week}")

# Show log
run(["log"], "LEARNING LOG SUMMARY")

print(f"\n{'='*65}")
print("  WEEKLY SUMMARY")
print(f"{'='*65}")
for week, pred_ok, eval_ok in summary:
    status = "OK" if (pred_ok and eval_ok) else "ERR"
    print(f"  {week}  predict={'OK' if pred_ok else 'FAIL'}  evaluate={'OK' if eval_ok else 'FAIL'}  [{status}]")
